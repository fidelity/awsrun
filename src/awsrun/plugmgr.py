#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Loads and instantiates awsrun plug-ins for the CLI.

## Overview

The awsrun CLI supports two pluggable behaviors: **account loading** and
**credential loading**. To provide choices and extensibility for CLI users,
these behaviors can be changed via a user's awsrun YAML configuration file.
There are several plug-ins included for each. Users may, alternatively, provide
their own implementations, so long as they are installed and available in the
standard Python path. Non-CLI users of awsrun will not use this module.

This module provides a `PluginManager` which is responsible for loading and
instantiating a `Plugin` as well as managing the state associated with CLI
argument processing as plug-ins can register their own CLI flags. Users specify
plug-ins and the options to those plugins in their awsrun configuration file.
Most options can also be overridden via CLI flags if desired. The documentation
for each plug-in provides details on options available in the configuration file
as well as CLI flags. Please refer to `awsrun.plugins` for details on the
pluggable behaviors and included plug-ins.

For example, one pluggable behavior is the `awsrun.acctload.AccountLoader`. By
default, awsrun will use the `awsrun.plugins.accts.Identity` plug-in unless a
user specifies an alternate plug-in in their awsrun configuration. To replace
the standard account loader, the user would define a plug-in specification block
in their config called `Accounts`. This specification block contains a `plugin`
key that is a dotted Python path to a `Plugin` implementation and an `options`
block containing the appropriate options for the factory method:

    Accounts:
      plugin: awsrun.plugins.accts.JSON
      options:
        url: "http://www.example.com/accounts"
        max_age: 86400

To load the above plug-in, create an instance of a `PluginManager`, invoke
`PluginManager.parse_args` to register CLI flags and defaults, and then call
`PluginManager.instantiate` to build the instance of the plug-in. The following
illustrates how the manager interoperates with argument processing of the CLI:

    # Main CLI arg parser (definition of args omitted)
    parser = argparse.ArgumentParser()
    args, unparsed_argv = parser.parse_known_args()

    # Load and parse args for any plug-ins
    pm = PluginManager(config, parser, parsed_args, unparsed_argv)
    pm.parse_args('Accounts', default='awsrun.plugins.accts.Identity')

    # After parsing args for all the plug-ins, parse any remaining that
    # were not consumed by the plug-ins.
    args = parser.parse_args(pm.remaining_argv, pm.args)

    # Sometime later, instantiate your plug-in
    acct_loader = pm.instantiate('Accounts', must_be=AccountLoader)

The parsing of arguments and the instantiation of a `Plugin` are two separate
steps by design. This is particularly useful when one wants to complete all of
the CLI argument processing before doing the heavy lifting of instantiating the
plug-in. Why bother instantiating one plug-in if a user has not specified the
correct args to another? This is the reason why the steps are distinct. One can,
on the other hand, combine both into a single step by omitting the call to
`PluginManager.parse_args` as it will be called by `PluginManager.instantiate`
if it was not already.
"""
import importlib
import logging
from contextlib import suppress
from functools import partial, reduce
from inspect import isclass

LOG = logging.getLogger(__name__)


class Plugin:
    """Abstract base class for a plug-in that can register flags on the main CLI.

    A plug-in is a wrapper around a Python object that is configured via options
    in a user configuration file or CLI flags. This is abstract base class must
    be subclassed by plug-ins authors as the `PluginManager` will type check
    loaded plug-ins.

    Plug-ins can hook into the command line argument processing of the main CLI,
    which is done via the constructor. This allows plug-in author's to define
    options in user configuration files via `awsrun.config.Config` as well as
    flags on the command line using `argparse` library. The loading and
    instantiation of plug-ins is handled by the `PluginManager`, which is
    responsible for managing the state of CLI argument processing.

    The `parser` argument is an `argparse.ArgumentParser` that can be used to
    define additional flags on the main awsrun CLI. It is suggested that plug-in
    CLI flags are added to their own argument group, which is used by `argparse`
    when displaying help to the user:

        group = parser.add_argument_group('account loader options')
        group.add_argument('--loader-url', metavar='URL', help='URL to account data')

    If new CLI arguments are defined on the `parser`, it is highly recommended
    that they are prefixed with a name that will not conflict with the main
    awsrun CLI args. For example, a plug-in should not define a `--url` option
    as that may conflict with a future awsrun argument or another plug-in trying
    to define the same. Instead, use a prefix on all of the plug-in options
    defined to avoid conflicts. E.g., `--loader-url`.

    The `cfg` argument is a callable that implements the
    `awsrun.config.Config.get` interface allowing one to query for type-checked
    key/value pairs defined in a user configuration file. The keys passed to
    `cfg` are relative to the `options` key in the plug-in definition. For
    example, assume the following plug-in specification in a user configuration:

        Accounts:
          plugin: awsrun.plugins.accts.JSON
          options:
            url: "http://www.example.com/accounts"
            max_age: 86400

    To obtain the value of the `url` option, the `cfg` callable can be used:

        url = cfg('url', type=URL, must_exist=True)

    By combining the use of `parser` and `cfg`, a plug-in author can define
    options in both the user configuration file as well as command line flags to
    override those values. For example, the following defines a CLI argument
    called `--loader-max-age` that will default to the value of the `max_age`
    key in the user configuration file if it exists, otherwise it defaults to 0:

        parser.add_argument(
            '--loader-max-age',
            metavar='SECS',
            type=int,
            default=cfg('max_age', type=Int, default=0),
            help='maximum age of the cache')

    **Note:** A plug-in author must not invoke the `parse_args` or
    `parse_known_args` on the `parser` object provided in the constructor. The
    `PluginManager` is responsible for managing this and maintaining the state
    associated with argument processing. The constructor should be used to only
    register new CLI arguments and invoke the superclass's constructor.
    """

    def __init__(self, parser, cfg):
        self.parser = parser
        self.cfg = cfg

    def instantiate(self, args):
        """Returns an object created with options and arguments defined by the plug-in.

        The `PluginManager` will invoke this method after it has completed
        parsing the command line arguments that the plug-in defined in the
        constructor. The `args` argument is a populated `argparse.Namespace`
        object that contains the values of any command line arguments provided
        by the user on the CLI.

        This method also has access to the `self.parser` and `self.cfg` objects
        that were provided in the constructor. The `self.cfg` object is useful
        for cases where one does not want to provide a CLI flag for an option
        defined in the configuration file. In this case, when instantiating the
        object, you can pull values for the configuration file.

        The `self.parser` object is useful if one wishes to abort the
        instantiation of the plug-in. `argparse.ArgumentParser.error()` can be
        used to provide an error message to the CLI user and terminate the
        program.  It is perfectly acceptable to terminate the main program from
        within this method. Alternatively, one can raise an exception which will
        also terminate the program.
        """
        raise NotImplementedError


class PluginManager:
    """Manages the loading and instantiation of awsrun plug-ins.

    The `PluginManager` is responsible for loading and instantiating a `Plugin`
    as well as managing the state associated with CLI argument processing as
    plug-ins can register their own CLI flags. Users specify plug-ins and the
    options to those plugins in their awsrun configuration file. Most options
    can also be overridden via CLI flags if desired. See the `awsrun.plugmgr`
    for example usage.

    The `config` argument is a `awsrun.config.Config` that contains one or more
    plug-in specifications (discussed below). `parser` is a the main CLI
    `argparse.ArgumentParser` that will be provided to plug-ins so they can
    define new CLI arguments. `parsed_args` is a `argparse.Namespace` containing
    the results of CLI argument processing up to this point. And,
    `unparsed_argv` is a list of unprocessed arguments passed on the command
    line, which might contain arguments destined for a plug-in.

    A plug-in specification identifies the name of the plug-in, the `Plugin`
    implementation, and its options. The format of the specification is as
    follows:

        PLUGIN_NAME:
          plugin: PYTHON_MODULE.CLASSNAME
          options:
            ARG1: VAL1
            ARG2: VAL2

    For example, the following is a sample plug-in specification for the
    "Accounts" plug-in:

        Accounts:
          plugin: awsrun.plugins.accts.JSON
          options:
            url: "http://www.example.com/accounts"
            max_age: 86400

    The specification must include the `plugin` key that identifies, via a
    dotted string, the Python module concatenated with the name of a `Plugin`
    subclass. Plug-ins must be installed in the standard Python path. In the
    above example, `awsrun.plugins.accts.JSON` points to a subclass called
    `JSON` in the `awsrun.plugins.accts` module. The specification can also
    optionally include the `options` key that defines options made available
    to the plug-in via an `awsrun.config.Config` object, which is passed to the
    constructor of a `Plugin`. This allows the plug-in to type check values and
    use other features of the config module.

    Plug-in authors should refer to the documentation for `Plugin` to understand
    how the `config` and `parser` interact with each other during the
    instantiation of a plug-in.
    """

    def __init__(self, config, parser, parsed_args, unparsed_argv):
        self._config = config
        self._parser = parser
        self._plugins = {}

        self.args = parsed_args
        """A `argparse.Namespace` that parsed plug-in arguments are added.

        After each call to `PluginManager.parse_args`, this namespace is updated
        with any unparsed arguments consumed by a `Plugin`. In addition, when
        the `PluginManager` instantiates a plug-in, this namespace is provided
        to the plug-in, so it has access to its parsed arguments.
        """

        self.remaining_argv = unparsed_argv
        """A list of unparsed command line arguments remaining to be parsed.

        At the start of the `PluginManager`, this contains any command line
        arguments that might be intended for one or more plug-ins. It is updated
        after each successive call to `PluginManager.parse_args`. If a plug-in
        consumes arguments, they are transferred from this unparsed list to the
        parsed `PluginManager.args` namespace.
        """

    def parse_args(self, *keys, default=None):
        """Load the plug-in and parse command line arguments passed via the CLI.

        This method does not return anything, nor does it instantiate the
        plug-in. It only loads the plug-in class and performs command line
        argument processing for the `Plugin`. It is provided to allow one to
        separate the parsing of all line arguments from the instantiation of
        plug-ins. If this method is not explicitly called by the user, then it
        will be implicitly called when `PluginManager.instantiate` is called.
        See the `awsrun.plugmgr` documentation for the rationale.

        The `keys` varargs specifies the path to the plug-in specification
        contained with the configuration. See the `PluginManager` documentation
        for details on the plug-in specification. If the path does not exist,
        then the value of `default` is used instead. This default value must be
        a dotted string pointing to a subclass of `Plugin`. For example:

            pm = PluginManager(config, parser, parsed_args, unparsed_argv)
            pm.parse_args('Accounts', default='awsrun.plugins.accts.Identity')

        If the `Accounts` key does not exist in the configuration, then the
        `awsrun.plugins.accts.Identity` plug-in will be used instead.
        """
        path = self._config.get(*keys, "plugin") or default
        LOG.info("loading plug-in: %s", path)

        try:
            plugin_class = load_dotted_object(path)

        except ImportError as e:
            raise ValueError(f"Error in config: {'->'.join(keys)}->plugin: {e}") from e

        if not (isclass(plugin_class) and issubclass(plugin_class, Plugin)):
            raise TypeError(
                f"Error in config: {'->'.join(keys)}->plugin: '{path}' is not a {Plugin}"
            )

        # Create a new config callable that points directly to the options
        # stored in the configuration. This will make it easy for plugin authors
        # to query the config without having to specify the key path leading up
        # to the options section of the config.
        cfg = partial(self._config.get, *keys, "options")

        plugin = plugin_class(self._parser, cfg)
        self.args, self.remaining_argv = self._parser.parse_known_args(
            self.remaining_argv, self.args
        )
        LOG.info("parsed args=%s remaining args=%s", self.args, self.remaining_argv)

        self._plugins[keys] = plugin

    def instantiate(self, *keys, default=None, must_be=None):
        """Returns the instantiated plug-in.

        This method ultimately returns the value from `Plugin.instantiate`,
        which is passed a reference to the `PluginManager.args` object, so the
        plug-in can use any parsed command line arguments it had requested. It
        is usual, but not necessary, to invoke `PluginManager.parse_args` for
        each plug-in before calling this method. This allows all command line
        processing, and more important errors, to be complete before the actual
        instantiation of any plug-ins.

        The `keys` varargs specifies the path to the plug-in specification
        contained with the configuration. See the `PluginManager` documentation
        for details on the plug-in specification. If the path does not exist,
        then the value of `default` is used instead. This default value must be
        a dotted string pointing to a subclass of `Plugin`. For example:

            pm = PluginManager(config, parser, parsed_args, unparsed_argv)
            acct_loader = pm.instantiate(
                'Accounts',
                must_be=AccountLoader,
                default='awsrun.plugins.accts.Identity')

        If the `Accounts` key does not exist in the configuration, then the
        `awsrun.plugins.accts.Identity` plug-in will be used instead. If
        `must_be` is provided, the returned value from `Plugin.instantiate` must
        be an instance of the type specified, otherwise a `TypeError` is raised.
        If `must_be` is not provided, the returned object can be of any type.
        """
        if keys not in self._plugins:
            self.parse_args(*keys, default)

        instance = self._plugins[keys].instantiate(self.args)

        if must_be and not isinstance(instance, must_be):
            raise TypeError(
                f"Error in config: {'->'.join(keys)}->plugin: plugin did not build a {must_be}"
            )

        return instance


def load_dotted_object(dotted_name):
    """Returns the Python object found at the `dotted_name`.

    `dotted_name` should include both the Python module as well as the object in
    the module to return. For example, `some.module.MyClass` will return the
    class object `MyClass` from the Python module `some.module`. If the object
    cannot be loaded, `ImportError` is raised.
    """

    def doit(mod_name, attributes=None):
        attributes = [] if attributes is None else attributes

        if not mod_name:
            raise ImportError(f"cannot import '{dotted_name}'")

        mod = None
        with suppress(ModuleNotFoundError):
            mod = importlib.import_module(mod_name)

        if not mod:
            mod_name, _, attr = mod_name.rpartition(".")
            attributes.append(attr)
            return doit(mod_name, attributes)

        attributes.reverse()
        obj = reduce(lambda a, p: getattr(a, p, {}), attributes, mod)
        if not obj:
            raise ImportError(
                f"module '{mod_name}' does not contain '{'.'.join(attributes)}'"
            )

        return obj

    return doit(dotted_name)
