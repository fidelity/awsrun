#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""The awsrun CLI concurrently executes commands across AWS accounts.

## Overview

The CLI is a tool that can execute user-defined commands across one or more
accounts concurrently. This page is a reference containing the available command
line arguments and configuration options. Please refer to the `awsrun` page for
the user guide and gentle introduction to its capabilities.

## Synopsis

    $ awsrun [core options] [plug-in options] command [command options]

The CLI accepts three types of command line options:

core options
:  Defined by the awsrun CLI itself. These control the behavior of the main
program. These options are documented on this page.

plug-in options
:  Defined by the various plug-ins. Plug-in authors can register their own
command line arguments and configuration options. These are documented on the
respective plug-in pages at `awsrun.plugins`.

command options
:  Defined by the command being executed. Command authors can register their
own command line arguments and configuration options. The built-in commands and
their options are documented in `awsrun.commands`.

Executing the CLI without specifying a command to run will simply print the list
of selected accounts to the console as well as a list of the available commands
that have been found in the command path.

## Configuration

The behavior of the CLI can be controlled by passing command line arguments as
noted above, but those options can also be specified in a YAML configuration
file that is loaded from "$HOME/.awsrun.yaml" by default. Set the AWSRUN_CONFIG
environment variable to use an alternate configuration file. Options defined in
the configuration file can generally be overridden via command line arguments.

The configuration file contains four optional top-level sections: CLI, Commands,
Accounts, and Credentials. Each section is described below in more detail.

### CLI

This section of the configuration contains the core options of the CLI. Below is
the syntax and expected types for each option. Options are described in detail
in the [CLI Options](#cli-options) section of this document.

    CLI:
      account:
        - STRING
      account_file: FILENAME
      include:
        ATTR_NAME:
          - ATTR_VALUE
      exclude:
        ATTR_NAME:
          - ATTR_VALUE
      threads: INTEGER
      log_level: ("DEBUG" | "INFO" | "WARN" | "ERROR")
      cmd_path:
        - STRING

### Commands

This section of the configuration contains the default options for various
awsrun commands. A command is defined in its own block, where COMMAND_NAME is
the Python module that contains the command. I.e., the same name specified on
the command line. Within the specific command block, users can define default
values for the command's options. For the built-in commands, refer to the
`awsrun.commands` pages for the available options on each command.

    Commands:
      COMMAND_NAME:
        ARG: VALUE
        ...
      COMMAND_NAME:
        ARG: VALUE
        ...

### Accounts

This section of the configuration file specifies the account loader plug-in to
be used and its default options. It must contain a `plugin` key with the path to
the account loader plug-in in the form of PYTHON_MODULE.CLASSNAME, so the CLI
can find and load it. If the plug-in accepts options, they can be provided in an
optional `options` block. Refer to the account loader's documentation for a list
of available configuration options. The included account loader plug-ins are
documented at the `awsrun.plugins.accts` page.

If this section is not defined, the CLI will use the default account loader
`awsrun.plugins.accts.Identity`.

    Accounts:
      plugin: PYTHON_MODULE.CLASSNAME
      options:
        ARG: VALUE
        ...

### Credentials

This section of the configuration file specifies the credential loader plug-in
to be used and its default options. It must contain a `plugin` key with the path
to the account loader plug-in in the form of PYTHON_MODULE.CLASSNAME, so the CLI
can find and load it. If the plug-in accepts options, they can be provided in an
optional `options` block. Refer to the credential loader's documentation for a
list of available configuration options. The included credential loader plug-ins
are documented at the `awsrun.plugins.creds` page.

If this section is not defined, the CLI will use the default credential loader
`awsrun.plugins.creds.Profile.`.

    Credentials:
      plugin: PYTHON_MODULE.CLASSNAME
      options:
        ARG: VALUE
        ...

## CLI Options

The following is a list of configuration options for the CLI. Some options can
be overridden on the awsrun CLI via command line flags. In those cases, the CLI
flags are specified next to the option name below:

`account`, `--account ACCT`
:  The list of accounts to process. If specifying more than one account on the
command line, use multiple `--account` flags.

`account_file`, `--account-file`
:  Load the list of accounts to process from the specified file. The file should
contain one account per line. Blank lines are ignored as are lines that start
with a # mark.

`cmd_path`, `--cmd-path`
:  A list of locations to search for commands. This should be a list of Python
modules that contain commands or a directories containing Python files with
commands defined within. The default path is "awsrun.commands.aws".

`--metadata`
:  List the available metadata attributes from the account loader. If an
attribute name is passed as an argument to the flag, list the available values
for that metadata attribute.

`include`, `--include`
:  Include only the accounts that match the specified filter. A filter consists
of an attribute name and a list of possible values for that attribute. If more
than one attribute is specified, then all attributes must match. If more than
one value is specified for an attribute, then only one value must match.

`exclude`, `--exclude`
:  Exclude the accounts that match the specified filter. A filter consists of an
attribute name and a list of possible values for that attribute. If more than
one attribute is specified, then all attributes must match. If more than one
value is specified for an attribute, then only one value must match.

`--help`
:  Print detailed help to the console. The help also includes any defaults read
from the user's configuration file.

`--force`
:  Do not prompt the user for confirmation when processing accounts. By default,
if more than one account has been selected, the CLI prompts the user to confirm
they really want to execute the command over all of those accounts.

`log_level`, `--log-level`
:  Set the logging level. By default, the value is set to ERROR.

`--version`
:  Print the version of awsrun to the console.

## Metadata Filters

When specifying the `--include` and `--exclude` filters on the CLI, the
following syntax is used:

    $ awsrun --include ATTR_NAME=TYPE:ATTR_VALUE,ATTR_VALUE,...

Where `TYPE` is optional and only needed if the values must be cast to a
different type. The type conversion applies to all of the values specified.

For more information on the use of metadata filters, see the Account Plug-ins
section of the user guide at `awsrun`.

## Other CSPs

Other CSPs aside from AWS can be supported. The name of the installed CLI script
is used to determine which CSP is being used. For example, if the CLI has been
installed as "awsrun", the CSP is "aws". If the CLI has been installed as
"azurerun", the CSP is "azure". The name of the CSP impacts the following:

- The user configuration file is loaded from "$HOME/.csprun.yaml", where "csp"
  is the name of the CSP.

- The environment variable used to select an alternate path for the configuration
  file is "CSPRUN_CONFIG", where "CSP" is the name of the CSP.

- The default command path is set to "awsrun.commands.csp", where "csp" is the name
  of the CSP.

- The default credential loader plug-in is "awsrun.plugins.creds.csp", where
  "csp" is the name of the CSP.

## Debugging

By default, tracebacks from the core CLI are not printed to the console. Set the
environment variable AWSRUN_TRACE to 1 to print tracebacks to the console. Note:
that variable name does not change with different CSPs.

Tracebacks from exceptions that arise from within a user-defined command,
however, are included if the default logging level is set to `WARN`.
"""

import argparse
import logging
import os
import sys
import traceback
from datetime import timedelta
from functools import partial
from pathlib import Path

import awsrun.commands
from awsrun.acctload import AccountLoader
from awsrun.argparse import (AppendAttributeValuePair, AppendWithoutDefault,
                             RawAndDefaultsFormatter, prevent_option_reuse)
from awsrun.cmdmgr import CommandManager
from awsrun.config import Any, Choice, Config, Dict, File, Int, List, Str
from awsrun.plugmgr import PluginManager
from awsrun.runner import AccountRunner
from awsrun.session import SessionProvider

LOG = logging.getLogger(__name__)

SHORT_DESCRIPTION = """
Executes a command concurrently across one or more AWS accounts.

Accounts can be specified by using one or more --account flags.
Alternatively, one or more filter flags (--include or --exclude) can be
used to select accounts based on metadata attributes. To list the
attributes available, use the --metadata flag. To list the possible
values for an attribute, pass the attribute name to the --metadata
flag.

The list of available commands, and brief descriptions of each, can be
displayed by omitting the command.  Each command can have its own set
of command line arguments, which can be viewed by passing --help after
the command.
    """.strip()


# setup.py establishes this as the entry point for the awsrun CLI.
def main():
    """The main entry point for the `*run` CLI tool installed with this package.

    Runs the CLI tool. Exits with a `0` status code upon success. Upon error,
    prints the error message to standard error. By default, a stack trace is not
    included to minimize output. If the trace is desired, set the `AWSRUN_TRACE`
    environment variable to `1`.

    The CLI tool is installed on the system via the setup.py entry_points key.
    There can be many instances of this command installed on the system with
    different names. The CLI uses the name of the shell script installed to
    determine default path locations for commands as well as the default
    session manager.
    """
    try:
        csp = _CSP.from_prog_name(sys.argv[0])
        _cli(csp)

    except Exception as e:  # pylint: disable=broad-except
        # Don't print stack traces by default as it can be overwhelming (scary)
        # for those not familiar with Python development.
        if os.getenv('AWSRUN_TRACE'):
            traceback.print_exc(file=sys.stderr)

        print(e, file=sys.stderr)
        sys.exit(1)


def _cli(csp):
    """Parses command line arguments and invokes the awsrun CLI.

    This function may exit and terminate the Python program. It is the driver of
    the main interactive command line tool and may print output to the console.
    """

    # Load the main user configuration file, which is used extensively to
    # provide default values for argparse arguments. This allows users to
    # specify default values for commonly used flags.
    config = Config.from_file(csp.config_filename())

    # Build a callable to simplify access to the 'CLI' section of the config.
    cfg = partial(config.get, 'CLI', type=Str)

    # Argument parsing for awsrun is performed in four distinct stages because
    # arguments are defined by the main CLI program, plug-ins can define their
    # own arguments, and commands can also define their own arguments.
    #
    #   1. Parse *known* args for the main CLI
    #   2. Parse *known* args for the plug-ins
    #   3. Parse *remaining* args to grab the command and its args
    #   4. Parse the command's args later in cmdmgr.py
    #
    # Visually, here is a representation of the above;
    #
    #             awsrun and plug-in args          command             cmd args
    #        vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv vvvvvvvvvvvvv vvvvvvvvvvvvvvvvvvvvvvvvvvvv
    # awsrun --account 123 --saml-username pete access_report --region us-east-1 --verbose
    #        ^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    #           stage 1           stage 2          stage 3    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    #                                                                    stage 4
    #
    # In stage 1, this function calls `parse_known_args` in argparse, which does
    # not error out if an unknown argument is encountered. Why do we do this?
    # Because there may be arguments intermixed with the main awsrun args that
    # are intended for a plug-in, so we don't want argparse to terminate the
    # main program, which the more commonly used `parse_args` would do. Note:
    # the main awsrun arguments on the CLI can be specified anywhere before the
    # command. Note: flags defined in a command with the same name as a flag in
    # the main CLI will be eaten by stage 1 processing. I.e. if the main CLI
    # defines a flag called --count and a command author builds a command that
    # also takes a flag called --count, then in an invocation such:
    #
    #   awsrun --account 123 access_report --count
    #
    # The --count arg would never make it to stage 4 processing as it would
    # be shadowed and consumed by stage 1.
    #
    # In stage 2, this function uses the PluginManager to load plug-ins, which
    # may have registered additional command line arguments on the main parser.
    # The PluginManager uses `parse_known_args` when loading each plug-in, again
    # for the same reason as above. There may be arguments destined for a
    # different plug-in that has yet to be loaded, so we don't want to error
    # out. Note: plug-in flags can also shadow command flags as described above.
    # This is why plug-in author's should use a prefix on their flags to
    # minimize chance of collision.
    #
    # In stage 3, this function registers arguments for a help flag, the awsrun
    # command name, and gathers the remaining arguments after the command name.
    # It then calls `parse_args` as all command line arguments should have been
    # consumed at this point. If there are any extra arguments, argparse will
    # error and exit out with an appropriate message.
    #
    # Finally, in stage 4, this function uses the CommandManager to load the
    # command via the name and collected arguments from stage 3. The command
    # manager creates a new argument parser internally to parse the arguments
    # that were sent to the command as each command has the option to register
    # command line arguments.

    # To minimize the likelihood of shadowing flags defined by command authors,
    # this little hack wraps an internal method of argparse to track use of
    # flag names across all instances of ArgumentParser. We use two of these
    # during the 4 stages of CLI parsing. Stage 1-3 use one and stage 4 uses
    # a second ArgumentParser, so this prevents a command author from defining
    # the same flag name that we already use in the main CLI or one that a
    # plug-in author uses. We exclude -h from the check as we want both the
    # main CLI to have a -h as well as a command. The command's -h will not be
    # shadowed as the stage 1 and 2 do not include a -h option. We only add
    # the -h option in stage 3, and by then, the command name is parsed as
    # well as the remainder of the argv line, so -h is not processed if it
    # comes after the command name. This provides the behavior we want. If
    # you have a -h anywhere before the command name, you get the main help
    # for all of the awsrun CLI options as well as the options for any flags
    # defined by plugins. If you specify a command and then a -h afterwards,
    # you get the help that the command author includes for their command.
    prevent_option_reuse(exclude=('-h', '--help'))

    # STAGE 1 Argument Processing (see description above)

    # Do not add_help here or --help will not include descriptions of arguments
    # that were registered by the plug-ins. We will add the help flag in stage 3
    # processing.
    parser = argparse.ArgumentParser(
        add_help=False,
        allow_abbrev=False,
        formatter_class=RawAndDefaultsFormatter,
        description=SHORT_DESCRIPTION)

    acct_group = parser.add_argument_group('account selection options')
    acct_group.add_argument(
        '--account',
        metavar='ACCT',
        action=AppendWithoutDefault,
        default=cfg('account', type=List(Str), default=[]),
        dest='accounts',
        help='run command on specified list of accounts')

    acct_group.add_argument(
        '--account-file',
        metavar='FILE',
        type=argparse.FileType('r'),
        default=cfg('account_file', type=File),
        help='filename containing accounts (one per line)')

    acct_group.add_argument(
        '--metadata',
        metavar='ATTR',
        nargs='?',
        const=True,
        help='summarize metadata that can be used in filters')

    acct_group.add_argument(
        '--include',
        metavar='ATTR=VAL',
        action=AppendAttributeValuePair,
        default=cfg('include', type=Dict(Str, List(Any)), default={}),
        help='include filter for accounts')

    acct_group.add_argument(
        '--exclude',
        metavar='ATTR=VAL',
        action=AppendAttributeValuePair,
        default=cfg('exclude', type=Dict(Str, List(Any)), default={}),
        help='exclude filter for accounts')

    parser.add_argument(
        '--threads',
        metavar="N",
        type=int,
        default=cfg('threads', type=Int, default=10),
        help='number of concurrent threads to use')

    parser.add_argument(
        '--force',
        action='store_true',
        help='do not prompt user if # of accounts is > 1')

    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s ' + awsrun.__version__)

    parser.add_argument(
        '--log-level',
        default=cfg('log_level', type=Choice('DEBUG', 'INFO', 'WARN', 'ERROR'), default='ERROR'),
        choices=['DEBUG', 'INFO', 'WARN', 'ERROR'],
        help='set the logging level')

    parser.add_argument(
        '--cmd-path',
        action=AppendWithoutDefault,
        metavar='PATH',
        default=cfg('cmd_path', type=List(Str), default=[csp.default_command_path()]),
        help='directory or python package used to find commands')

    # Parse only the _known_ arguments as there may be additional args specified
    # by the user that are intended for consumption by the account loader plugin
    # or the auth plugin. We save the remaining args and will pass those to the
    # plugin manager responsible for loading the plugins.
    args, remaining_argv = parser.parse_known_args()

    # With the log level now available from the CLI options, setup logging so it
    # can be used immediately by the various python modules in this package.
    logging.basicConfig(
        level=args.log_level,
        format='%(asctime)s %(name)s %(levelname)s [%(threadName)s] %(message)s')

    # STAGE 2 Argument Processing (see description above).

    # The plugin manager will load the two plugins and handle command line
    # parsing of any arguments registered by the plugins.
    plugin_mgr = PluginManager(config, parser, args, remaining_argv)
    plugin_mgr.parse_args('Accounts', default='awsrun.plugins.accts.Identity')
    plugin_mgr.parse_args('Credentials', default=csp.default_session_provider())

    # STAGE 3 Argument Processing (see description above).

    # The help flag is added to the parser _after_ loading all of the plugins
    # because plugins can register their own flags, which means if the help flag
    # were added before this point, and a user passed the -h flag, it would not
    # include descriptions for any of the args registered by the plugins.
    parser.add_argument('-h', '--help', action='help')
    parser.add_argument('command', nargs='?', help='command to execute')
    parser.add_argument('arguments', nargs=argparse.REMAINDER, default=[], help='arguments for command')

    # Now we parse the remaining args that were not consumed by the plugins,
    # which will typically include the awsrun command name and any of its args.
    # If there are extra args or unknown args, parse_args will exit here with an
    # error message and usage string. Note that we obtain the remaining unused
    # argv from the plugin manager as well as the namespace to add these last
    # arguments.
    args = parser.parse_args(plugin_mgr.remaining_argv, plugin_mgr.args)

    # Use the plugin manager to create the actual account loader that will be
    # used to load accounts and metadata for accounts.
    account_loader = plugin_mgr.instantiate('Accounts', must_be=AccountLoader)

    # Check to see if user is inquiring about the metadata associated with
    # accounts. If they pass --metadata by itself, print out a list of all
    # possible attribute names. If they pass an arg to --metadata, such as
    # "--metadata BU", then print out all the possible values of that attr,
    # so they can build filters for it.
    if args.metadata:
        attrs = account_loader.attributes()
        if args.metadata in attrs:
            print(f"Metadata values for '{args.metadata}' attribute:\n")
            print('\n'.join(sorted(attrs[args.metadata])))
        elif attrs:
            print('Valid metadata attributes:\n')
            print('\n'.join(sorted(attrs)))
        else:
            print('No metadata attributes available')
        sys.exit(0)

    # Check to see if the user wants to load additional accounts from a file
    # specified on the command line. If so, the account IDs will be appended to
    # any accounts defined on the command line or in the user config.
    if args.account_file:
        args.accounts.extend(a.strip() for a in args.account_file if not (a.isspace() or a.startswith('#')))

    # Obtain a list of account *objects* for the specified account IDs. The
    # resulting objects will depend upon the account loader plugin used. Some
    # plugins will return rich objects with attributes containing metadata and
    # others may just return a simple list of IDs as strings. The point is that
    # this is an opaque object that will be passed to the runner and then to the
    # command being run.
    accounts = account_loader.accounts(args.accounts, args.include, args.exclude)

    # If we get to here and there are still 0 accounts, that means there were
    # no accounts specified via --accounts, no accounts specified in the user
    # config, no accounts specified in a separate file, or none of the
    # specified accounts matched the filters, so we just exit.
    if not accounts:
        print('No accounts selected', file=sys.stderr)
        sys.exit(1)

    # The command manager will be used to search, parse command arguments, and
    # instantiate the command that was specified on the CLI. It can also provide
    # a list of all commands found in the paths provided.
    command_mgr = CommandManager.from_paths(*args.cmd_path)

    # If no command was supplied, then print the list of accounts that were
    # selected along with a list of all the valid and known commands. This
    # allows users to test filters to see which accounts will be acted upon.
    if not args.command:
        _print_accounts(accounts)
        _print_valid_commands(command_mgr.commands())
        sys.exit(1)

    # STAGE 4 Argument Processing (see description above). When the command
    # manager loads the command, it will create a new argument parser, so
    # command author's can define any arguments they might want. After this
    # step, all command line arguments have been fully processed.
    try:
        command = command_mgr.instantiate_command(
            args.command,
            args.arguments,
            partial(config.get, 'Commands', args.command))

    # Most exceptions are passed upwards, but we explicitly catch a failure when
    # trying to instantiate the command selected by the user, so we can include a
    # list of valid commands that the command manager knows about. The exception
    # re-raised so it will be handled by the same error handling logic in main().
    except Exception:
        _print_valid_commands(command_mgr.commands(), out=sys.stderr)
        raise

    # Safety check to make sure user knows they are impacting more than one
    # account. This can be disabled with the -f flag.
    if len(accounts) > 1 and not args.force:
        _ask_for_confirmation(accounts)

    # Load up a session provider to hand out creds for the runner.
    session_provider = plugin_mgr.instantiate('Credentials', must_be=SessionProvider)

    # This is the main entry point into the awsrun API. Note: the entirety of
    # awsrun can be used without the need of the CLI. One only needs a list of
    # accounts, an awsrun.runner.Command, and an awsrun.session.SessionProvider.
    runner = AccountRunner(session_provider, args.threads)
    elapsed = runner.run(command, accounts, key=account_loader.acct_id)

    # Show a quick summary on how long the command took to run.
    pluralize = 's' if len(accounts) != 1 else ''
    print(f'\nProcessed {len(accounts)} account{pluralize} in {timedelta(seconds=elapsed)}', file=sys.stderr)


def _print_valid_commands(commands, out=sys.stdout):
    """Pretty print a table of commands.

    The argument is a dict where keys are the names and values are CLICommand
    classes from the command modules.
    """
    if not commands:
        print('No commands found, did you specify the correct --cmd-path?', file=out)
        return

    print('The following are the available commands:\n', file=out)
    max_cmd_len = max(len(name) for name in commands.keys())
    for name in sorted(commands.keys()):
        # By convention, as documented in user documentation, class docstring
        # is used when printing a summary of commands.
        docstring = commands[name].__doc__ or ''
        print(f'{name:{max_cmd_len}}  {docstring}', file=out)
    print(file=out)


def _print_accounts(accts, out=sys.stdout):
    """Print the list of accounts."""
    count = len(accts)
    print(f'{count} account{"s" if count != 1 else ""} selected:\n', file=out)
    print(', '.join(str(a) for a in accts), file=out, end='\n\n')


def _ask_for_confirmation(accts):
    """Prompt user for confirmation and list accounts to be acted upon."""
    _print_accounts(accts, out=sys.stderr)
    print('Proceed (y/n)? ', flush=True, end='', file=sys.stderr)
    answer = input()
    if not answer.lower() in ['y', 'yes']:
        print('Exiting', file=sys.stderr)
        sys.exit(0)


class _CSP:
    """Represents a Cloud Service Provider (CSP) default settings.

    This class provides the default user configuration path, default command
    path, and the default session provider. It also includes a factory method
    to create an instance based on the filename of the CLI script itself. This
    is used to adapt the CLI behavior based on the CSP based solely on the
    name.

    To add a new CSP to awsrun, the following must be completed:

    1. Create a new submodule called `aws.commands.csp` where `csp` is the name
       of the CSP being added. For example, `aws.commands.gcp`. In this module,
       define one or more command submodules. For example, to build an command
       called "access_check", create `aws.commands.gcp.access_check.py` with a
       `CLICommand` class defined. See top-level `awsrun` documentation on how
       to build commands.

    2. Create a new submodule called `aws.plugins.creds.csp` where `csp` is the
       name of the CSP being added. For example, `aws.commands.creds.gcp`. In
       this module, define one or more plug-ins that return an instance of a
       `awsrun.session.SessionProvider`. See top-level `awsrun` documentation
       on how to build plug-ins.
    """

    @classmethod
    def from_prog_name(cls, prog_name):
        """Return CSP instance based on prog_name."""

        # Identify the CSP name from the name of the installed CLI tool. The
        # installed CLI will be called "awsrun" or "azurerun".
        csp = Path(prog_name).name.replace('run', '')
        if csp not in ['aws', 'azure']:
            raise Exception(f'unknown variant: {csp}')
        return cls(csp)

    def __init__(self, name):
        self.name = name

    def config_filename(self):
        """Returns the path to the user configuration."""
        env_var = self.name.upper() + 'RUN_CONFIG'
        dotfile = '.' + self.name.lower() + 'run.yaml'
        return os.environ.get(env_var, Path.home() / dotfile)

    def default_command_path(self):
        """Returns the path to the builtin commands submodule."""
        return 'awsrun.commands.' + self.name.lower()

    def default_session_provider(self):
        """Returns the module name of the builtin Profile session provider."""
        return 'awsrun.plugins.creds.' + self.name.lower() + '.Profile'


if __name__ == '__main__':
    main()
