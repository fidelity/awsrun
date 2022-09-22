#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Loads and instantiates user-defined awsrun commands.

## Overview

This module provides a `CommandManager`, which is responsible for loading and
instantiating user-defined commands for use with `awsrun.runner`. The command
manager was built to allow `awsrun.cli` users to dynamically point awsrun to
commands installed in user-defined paths. Non-CLI users of awsrun without the
need to dynamically load commands will not use this module.

To facilitate the discovery of commands, each user-defined command intended for
use from the CLI must be defined in a separate Python module that contains a
class called `CLICommand`, which must be a subclass of `awsrun.runner.Command`.
The name of the Python module containing this class is the name used on the
awsrun command line when specifying the command to execute. For example, assume
`~/commands/test_command.py` contains the following user-defined command:

    from awsrun.runner import Command

    class CLICommand(Command):
        \"\"\"Example command that prints a simple message for accounts.\"\"\"

        def execute(self, session, acct, region):
            return f'test_command executed in {acct} and {region}'

To invoke this command from the CLI:

    # Notice the name of the command is the same name as the Python module
    # containing the CLICommand, but without the ".py" extension.
    $ awsrun -d ~/commands -r us-east-1 -a 100200300400 test_command

The `CommandManager` relies on a `CommandLoader` to discover, find, and load
user-defined commands. There are three command loaders provided in this package:
`DirectoryLoader`, `ModuleLoader`, and `ChainLoader`. For example:

    dl = DirectoryLoader("/tmp")
    cm = CommandManager(dl)

    ml = ModuleLoader("awsrun.commands")
    cm = CommandManager(ml)

    cl = ChainLoader(dl, ml)
    cm = CommandManager(cl)

As a convenience, a class factory method exists, `CommandManager.from_paths`, to
simplify the creation of a `CommandManager` and one or more loaders. For
example, to create a `CommandManager` that searches the directories `/tmp` and
`/Users/me/mycmds` as well as a Python module called `mycompany.commands`:

    cm = CommandManager.from_paths("/tmp/", "/Users/me/mycmds", "mycompany.commands")

Once a command manager has been created, a specific awsrun command can be loaded
via `CommandManager.instantiate_command`.  If the command cannot be found,
`CommandNotFoundError` is raised. `CommandManager.commands` returns a dict of
all the discovered commands found in the configured paths.
"""

import argparse
import ast
import contextlib
import importlib
import logging
import os
import pkgutil
import sys

from awsrun.argparse import RawAndDefaultsFormatter
from awsrun.runner import Command

LOG = logging.getLogger(__name__)


class CommandManager:
    """Manages the loading and instantiation of user-defined awsrun commands.

    The `loader` parameter of the constructor must be an instance of a
    `CommandLoader`.  As a convenience, there is a factory method called
    `CommandManager.from_paths` that will construct a `CommandManager` instance
    which will load user-defined commands from the specified directories and
    Python modules.
    """

    def __init__(self, loader):
        self._loader = loader

    @classmethod
    def from_paths(cls, *paths):
        """Creates a `CommandManager` that searches `paths` for awsrun commands.

        The `paths` varags parameter should be a list of strings of directory
        paths or Python module names that contain one or more Python modules
        containing an `CLICommand` class. If a path contains any slashes
        (forward or backward), it will be treated as a directory, otherwise it
        is assumed to be a valid Python module name unless it is the bare '.',
        which specifies the current directory:

            CommandManager.from_paths('awsrun.commands', '/some/dir', '.')
        """
        loaders = []
        for p in paths:
            if ("/" in p) or ("\\" in p) or (p == "."):
                loaders.append(DirectoryLoader(p))
            else:
                loaders.append(ModuleLoader(p))

        return cls(ChainLoader(*loaders))

    def commands(self):
        """Returns a dict of names and classes of all valid commands."""
        return self._loader.load_all()

    def instantiate_command(self, command_name, argv, cfg):
        """Returns an instantiated command identified by `command_name`.

        The `argv` parameter should be a a string of command line arguments
        captured by `argparse.REMAINDER` in the main program that will be passed
        directly to the command for processing via its static `from_cli` method.
        If the arguments are not valid, the program will terminate by the arg
        parser in the command. This is expected as the command's `argparse` will
        present a user-friendly help message.

        The `cfg` parameter is a function that can lookup key value pairs from a
        user's configuration file. This is provided to the command author via
        `Command.from_cli`, so default values can be provided for the any of the
        CLI options defined by the command. See the documentation on
        `awsrun.config.Config.get` for the parameters of the function.

        If `command_name` is not found, raises `CommandNotFoundError`.
        """
        # Dynamically load the command specified by the user. All commands are
        # really defined as modules in the 'commands' directory of this package
        # by default, but this can be overridden by the --cmd-dir flag.
        cmd_class = self._loader.load(command_name)

        if not issubclass(cmd_class, Command):
            raise TypeError(
                f"'{command_name}' must be a subclass of awsrun.runner.Command"
            )

        # Create an argument parser for the command author, which is populated
        # with the name and a help string from the command's module docstring.
        parser = argparse.ArgumentParser(
            command_name,
            formatter_class=RawAndDefaultsFormatter,
            epilog=sys.modules[cmd_class.__module__].__doc__,
        )

        # We then call the static method on the class to obtain an instance of
        # the command. The command author is expected to parse whatever command
        # line args the user passed on the command line. It is expected that the
        # author terminate the program if incorrect arguments were passed.
        return cmd_class.from_cli(parser, argv, cfg)


class CommandLoader:
    """Abstract base class that loads user-defined awsrun commands from a source.

    Subclasses must provide implementations for `load` and `load_all`.
    """

    def load(self, command_name):
        """Returns the class object for the command called `command_name`.

        If a valid class cannot be found, raises `CommandNotFoundError`.
        """
        raise NotImplementedError

    def load_all(self):
        """Returns a dict of all valid commands found.

        The keys of the dict are the command names and the values are the class
        objects that have been loaded.
        """
        raise NotImplementedError


class ChainLoader(CommandLoader):
    """Chains multiple command loaders together in a priority order.

    The `loaders` varargs parameter must be a list of `CommandLoader` objects
    that will be used to search for awsrun commands. This class allows one to
    chain one or more loaders together to search for commands in one or more
    locations.
    """

    def __init__(self, *loaders):
        self.loaders = loaders

    def load(self, command_name):
        """Returns the class object for the command called `command_name`.

        All loaders are searched for the command. If a command is found in
        multiple loaders, the first loader containing the command is preferred.
        If a valid class cannot be found, raises `CommandNotFoundError`.
        """
        path_errors = {}
        for loader in self.loaders:
            try:
                return loader.load(command_name)
            except CommandNotFoundError as e:
                path_errors.update(e.path_errors)

        raise CommandNotFoundError(command_name, path_errors)

    def load_all(self):
        """Returns a dict of all valid commands found from all loaders.

        The keys of the dict are the command names and the values are the class
        objects that have been loaded.  If a command is found in multiple
        loaders, the first loader containing the command is preferred.
        """
        classes = {}
        for loader in reversed(self.loaders):
            # dict.update() replaces existing keys with new values, so reversing
            # the list ensures that loaders at the beginning of the list take
            # priority over those that come afterwards.
            classes.update(loader.load_all())

        return classes


class DirectoryLoader(CommandLoader):
    """Loads user-defined awsrun commands from a filesystem directory.

    The `directory_path` parameter specifies a directory that should contain one
    or more Python modules that implement a class called `CLICommand`, which
    allows the loader to find compatible commands.
    """

    def __init__(self, directory_path):
        self.path = directory_path
        if directory_path not in sys.path:
            sys.path.append(directory_path)

    def load(self, command_name):
        fullpath = os.path.join(self.path, command_name) + ".py"
        LOG.info("loading command at '%s'", fullpath)
        try:
            # We inspect the AST of the python file without importing it because
            # we don't want to accidentally execute a python script someone has
            # sitting in their command path, so we inspect the AST to see if it
            # contains a class definition of CLICommand.
            if not self._contains_awsrun_command(fullpath):
                raise Exception("CLICommand class not found")

            # Now we will import the module as we know the file is likely an
            # awsrun command given it contains a CLICommand class.
            module = importlib.import_module(command_name)

            # All Commands must define an 'CLICommand' class as this is the
            # contract that we have defined as part of the command system.
            return module.CLICommand

        except Exception as e:
            LOG.info("Invalid command at '%s': %s", fullpath, e)
            raise CommandNotFoundError(command_name, {fullpath: e}) from e

    def load_all(self):
        classes = {}
        LOG.info("scanning directory '%s' for commands", self.path)
        for fn in os.listdir(self.path):
            if fn.startswith("__") or not fn.endswith(".py"):
                continue

            name = fn.split(".py")[0]
            with contextlib.suppress(Exception):
                classes[name] = self.load(name)

        return classes

    @staticmethod
    def _contains_awsrun_command(filename):
        with open(filename, encoding="utf-8") as f:
            node = ast.parse(f.read(), filename)
        return any(
            n.name == "CLICommand" for n in node.body if isinstance(n, ast.ClassDef)
        )


class ModuleLoader(CommandLoader):
    """Loads user-defined awsrun commands from a Python module/package.

    The `module_name` parameter specifies a base Python module that should
    contain one or more modules that implement a class called `CLICommand`,
    which allows the loader to find compatible commands.
    """

    def __init__(self, module_name):
        self.module_name = module_name

    def load(self, command_name):
        try:
            path = f"{self.module_name}.{command_name}"
            LOG.info("loading command at '%s'", path)
            module = importlib.import_module(path)

            # All Commands must define an 'CLICommand' class as this is the
            # contract that we have defined as part of the command system.
            return module.CLICommand

        except Exception as e:
            raise CommandNotFoundError(command_name, {self.module_name: e}) from e

    def load_all(self):
        classes = {}
        base = importlib.import_module(self.module_name)

        for m in pkgutil.iter_modules(base.__path__):
            with contextlib.suppress(Exception):
                classes[m.name] = self.load(m.name)

        return classes


class CommandNotFoundError(Exception):
    """Raised if command cannot be found.

    The `command_name` attribute of the instance is the command that could not be
    found.  The `path_errors` attribute is a dict of path -> loader exceptions for
    each path searched.
    """

    def __init__(self, command_name, path_errors):
        self.path_errors = path_errors
        self.command_name = command_name

        msg = f"'{command_name}' command not found:\n"
        for path, error in path_errors.items():
            msg += f"  {path} => {error}\n"
        super().__init__(msg)
