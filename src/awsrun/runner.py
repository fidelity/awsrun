#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Executes a `Command` across one or more accounts concurrently.

## Overview

This module defines two core classes: `Command` and `AccountRunner`.  `Command`
is a user-defined computation to be executed concurrently across one or more
accounts by the `AccountRunner`. Typically, commands are simply a set of boto3
calls, or similar cloud SDK calls, to be run within an account using credentials
provided by a `awsrun.session.SessionProvider` from the `awsrun.session` module.
All commands must be subclasses of `Command`. For cloud SDKs that have
regional-based APIs , such as AWS and its boto3 library, the abstract base class
`RegionalCommand` is provided to simplify the execution of commands across
regions.

*Note: When building a `Command` for use via the `awsrun.cli` tool, the subclass
of the command must be called `CLICommand` and must be in its own module, so the
`awsrun.cmdmgr` can find and load it.*

## Basic Usage

The following is a full example that demonstrates how to use the awsrun library
to programmatically execute the included `awsrun.commands.aws.access_report`
command for two accounts using credentials stored in local config files with the
`awsrun.session.aws.CredsViaProfile` session provider:

    from awsrun.runner import AccountRunner
    from awsrun.session.aws import CredsViaProfile
    from awsrun.commands.aws import access_report

    session_provider = CredsViaProfile()
    account_runner = AccountRunner(session_provider)

    cmd = access_report.CLICommand()
    account_runner.run(cmd, ['111222333444', '222333444111'])

The `AccountRunner.run` method will block until the command has been executed
for each account. After the command has finished, the same `AccountRunner` can
be used to execute additional commands. A new instance is not required for each
command invocation.

## User-Defined Commands

Users may define their own custom commands. The next example demonstrates how to
write a simple `Command` that will print a list of VPCs IDs to the console for
the same accounts in two AWS regions:

    from awsrun.runner import AccountRunner, Command
    from awsrun.session import CredsViaProfile

    class VpcInfoCommand(Command):
        def __init__(self, regions):
            self.regions = regions

        def execute(self, session, acct):
            result = ''
            for region in self.regions:
                ec2 = session.resource('ec2', region_name=region)
                vpc_ids = ', '.join(vpc.id for vpc in ec2.vpcs.all())
                result += f'{acct}/{region}: {vpc_ids}\\n'
            return result

    cmd = VpcInfoCommand(['us-east-1', 'us-west-2'])
    session_provider = CredsViaProfile()
    account_runner = AccountRunner(session_provider)
    account_runner.run(cmd, ['111222333444', '222333444111'])

The returned value from `Command.execute` is printed to the console because the
default implementation of `Command.collect_results`. This may be fine for a
command intended to be run from the included `awsrun.cli` tool, but is likely
undesirable for programmatic use. The next section will present other options
for the collection of results intended for non-CLI uses.

Because AWS uses regional API calls, the above example can be rewritten using
`RegionalCommand` to abstract away the explicit looping over regions and the
accumulation of results, which simplifies the building of commands intended for
use with AWS. The key differences include `RegionalCommand.regional_execute`,
which takes an extra argument containing the name of the region being processed,
and the elimination of the constructor as the regional command provides a
default constructor:

    from awsrun.runner import AccountRunner, RegionalCommand
    from awsrun.session import CredsViaProfile

    class VpcInfoCommand(RegionalCommand):
        def regional_execute(self, session, acct, region):
            ec2 = session.resource('ec2', region_name=region)
            vpc_ids = ', '.join(vpc.id for vpc in ec2.vpcs.all())
            return f'{acct}/{region}: {vpc_ids}\\n'

    cmd = VpcInfoCommand(['us-east-1', 'us-west-2'])
    session_provider = CredsViaProfile()
    account_runner = AccountRunner(session_provider)
    account_runner.run(cmd, ['111222333444', '222333444111'])

## Collecting Results

The final example demonstrates how to collect the results from all of the
accounts and invocations of `Command.execute`, which is common if one wants to
compute an aggregated value or access to the data after `AccountRunner.run` has
completed processing all accounts. To do so, a custom `Command.collect_results`
must be defined. The following example accumulates the list of VPCs in the
specified regions:

    from collections import defaultdict
    from awsrun.runner import AccountRunner, Command
    from awsrun.session import CredsViaProfile

    class VpcInfoCommand(Command):
        def __init__(self, regions):
            self.regions = regions
            self.vpcs_by_region = defaultdict(list)

        def execute(self, session, acct):
            result = {}
            for region in self.regions:
                ec2 = session.resource('ec2', region_name=region)
                result[region] = [vpc.id for vpc in ec2.vpcs.all()]
            return result

        def collect_results(self, acct, get_result):
            for region, vpc_ids in get_result().items():
                self.vpcs_by_region[region].extend(vpc_ids)

    cmd = VpcInfoCommand(['us-east-1', 'us-west-2'])
    session_provider = CredsViaProfile()
    account_runner = AccountRunner(session_provider)
    account_runner.run(cmd, ['111222333444', '222333444111'])

    for region, vpc_ids in cmd.vpcs_by_region.items():
        # Do something with region and list of vpc_ids

This highlights an important aspect of a `Command`. One must not mutate instance
variables without synchronization from within `Command.execute`. Remember, the
`AccountRunner` is concurrently executing the same command across multiple
accounts, so unsynchronized access may lead to data corruption or race
conditions. Instead, command authors should implement `Command.collect_results`,
which is guaranteed to be called sequentially after each account has been
processed, thus allowing users to safely mutate instance variables from within
the method.

The above example can also be rewritten using `RegionalCommand` like the prior
section to abstract away the explicit looping over regions and the accumulation
of results, which simplifies the implementation of this command intended for
AWS. When subclassing `RegionalCommand`, if the constructor is overridden, you
must invoke the parent's constructor passing it the list of `regions` to
process. In addition, the other difference is the region parameter on the
`RegionalCommand.regional_execute` and
`RegionalCommand.regional_collect_results` methods:

    from collections import defaultdict
    from awsrun.runner import AccountRunner, RegionalCommand
    from awsrun.session import CredsViaProfile

    class VpcInfoCommand(RegionalCommand):
        def __init__(self, regions):
            super().__init__(regions)
            self.vpcs_by_region = defaultdict(list)

        def regional_execute(self, session, acct, region):
            ec2 = session.resource('ec2', region_name=region)
            return [vpc.id for vpc in ec2.vpcs.all()]

        def regional_collect_results(self, acct, region, get_result):
            self.vpcs_by_region[region].extend(get_result())

    cmd = VpcInfoCommand(['us-east-1', 'us-west-2'])
    session_provider = CredsViaProfile()
    account_runner = AccountRunner(session_provider)
    account_runner.run(cmd, ['111222333444', '222333444111'])
"""
import functools
import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from awsrun.argparse import AppendWithoutDefault
from awsrun.config import List, Str
from awsrun.session import SessionProvider

LOG = logging.getLogger(__name__)


class Command:
    """Abstract base class that represents a command to execute on an account.

    A command is a unit of work that is executed across one or more accounts by
    the `AccountRunner`. During processing of an account, the command is
    provided a session configured with the appropriate credentials. In addition,
    the command is also provided an account object for the account being
    processed. The attributes and methods attached to the account object depend
    on what was passed to `AccountRunner.run`. This allows users to pass
    arbitrary account objects for use within their custom commands.

    All user-defined awsrun commands must be a subclass this base class. This
    class documents the contract between the awsrun framework and command
    author. For several examples on how to write custom commands, refer to the
    built-in commands included in the `awsrun.commands` module.
    """

    @classmethod
    def from_cli(cls, parser, argv, cfg):  # pylint: disable=unused-argument
        """Factory to build the command from CLI args and user configuration.

        *This method is only required if the command is intended for use with
        the `awsrun.cli` command line. Non-CLI users will not instantiate
        commands via this factory method.*

        The CLI uses `awsrun.cmdmgr` to find, load, and instantiate commands.
        This factory is called by the `awsrun.cmdmgr.CommandManager` and must
        return an instance of the command. Commands can hook into the command
        line argument processing of the main CLI. This allows command authors to
        define their own flags and arguments for the CLI. In addition, authors
        can pull values from the user configuration file via the
        `awsrun.config.Config` API.

        For reference, there are several types of awsrun CLI arguments as shown
        below:

            awsrun --account 100200300400 access_report --verbose
                   ^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^ ^^^^^^^^^
                       main args            command     cmd args

        The `parser` argument, an `argparse.ArgumentParser`, can be used to
        define flags and arguments that follow the command name in the `cmd
        args` section. After defining arguments, it is the responsibility of
        this method to parse the `argv` argument, which contains a list of
        unparsed CLI arguments. It is expected that this method will terminate
        the program if incorrect arguments are passed to the command.  For
        example, to define and parse the `--verbose` flag from the example
        above:

            @classmethod
            def from_cli(cls, parser, argv, cfg):
                parser.add_argument(
                    '--verbose', '-v',
                    action='store_true',
                    default=False,
                    help='enable verbose output')

                args = parser.parse_args(argv)

                # use args as needed, in most cases, these will be passed to
                # constructor of the command as this example shows assuming
                # this command's constructor accepts a verbose keyword arg.
                return cls(**vars(args))

        To avoid namespace collisions with flag names used by the main CLI, an
        `argparse.ArgumentError` is raised if the same option name is added to
        the `parser`. This is done to avoid unintended consequences when the
        main CLI argument parser consumes a flag in the command because it
        shares the same name.

        The `cfg` argument is a callable that implements the
        `awsrun.config.Config.get` interface allowing one to query for
        type-checked key/value pairs defined in a user configuration file. The
        keys passed to `cfg` are relative to the `Commands` section of the
        configuration and the command name. Given the following user config and
        assuming that the name of this command is `access_report`:

            Commands:
                access_report:
                    verbose: True

        To obtain the value of the `verbose` option, the `cfg` callable can be
        used as follows:

            verbose = cfg('verbose', type=Bool, default=False)

        By combining the use of `parser` and `cfg`, a command author can define
        options in both the user configuration file as well as command line
        flags to override those values. For example, the following defines the
        CLI argument called `--verbose` that will default to the value of the
        `verbose` key in the user configuration file if it exists, otherwise it
        defaults to `False`:

            @classmethod
            def from_cli(cls, parser, argv, cfg):
                parser.add_argument(
                    '--verbose', '-v',
                    action='store_true',
                    default=cfg('verbose', type=Bool, default=False),
                    help='enable verbose output')

                args = parser.parse_args(argv)

                # use args as needed, in most cases, these will be passed to
                # constructor of the command as this example shows assuming
                # this command's constructor accepts a verbose keyword arg.
                return cls(**vars(args))

        This is a common pattern when defining command arguments. Arguments are
        added to the parser with defaults taken from the user configuration
        file, which allows a user to omit the flags on the command line to make
        a better user experience.
        """
        # If the user does not provide their own from_cli method, we want to
        # make sure that we invoke parse_args for them as it will catch any help
        # flags passed to the command and print out the docstring of the module.
        parser.parse_args(argv)
        return cls()

    def pre_hook(self):
        """Invoked by `AccountRunner.run` before any processing starts.

        This method is invoked only once per invocation of `AccountRunner.run`.
        It is not executed before each account is processed, but rather once
        before any accounts are processed.

        The default implementation does nothing.
        """

    def post_hook(self):
        """Invoked by `AccountRunner.run` after all processing has completed.

        This method is invoked only once per invocation of `AccountRunner.run`.
        It is not executed after each account is processed, but rather once
        after all accounts have been processed.

        The default implementation does nothing.
        """

    def execute(self, session, acct):
        """Invoked by `AccountRunner.run` to process an account.

        This method is invoked once for each account. The `session` parameter is
        a boto3 Session object, or similar cloud SDK session-like object, with
        credentials for the account being processed. The `acct` will be the same
        object that was passed in the list of accounts to `AccountRunner.run`.

        The return value from this method can be of any type. By default, this
        value will be printed to the console if a `Command.collect_results`
        implementation is not provided. If an exception is raised during the
        execution, it will be printed to the console on standard error.

        Note the following items of importance:

        1. Command authors must implement this method. There is no default
           implementation.

        2. Recognize that this method will be invoked concurrently, so
           modification of instance variables from within this method requires
           synchronization. If accumulating results, define a custom
           `Command.collect_results` which is guaranteed to be invoked
           sequentially.

        3. Do not call `sys.exit` or the entire program will terminate. The
           proper way to exit from this method is either by returning a value or
           by raising an exception.

        4. Do not print directly to the console as output will be interspersed
           with other output from other concurrently running threads processing
           other accounts. The best practice when printing is to accumulate a
           string buffer and return the buffer at the end of the method:

                def execute(self, session, acct):
                    out = io.StringIO()

                    # Do stuff
                    print('This will be printed to the console eventually', file=out)
                    # Do more stuff

                    return out.getvalue()
        """
        raise NotImplementedError

    def collect_results(self, acct, get_result):
        """Invoked by `AccountRunner.run` after processing an account.

        This method is invoked by `AccountRunner.run` after each `acct` has been
        processed by `Command.execute`. The results from execute are provided
        via `get_result`, which is a callable that will either return the value
        returned by execute or raise an exception if one was raised. The `acct`
        parameter will be the same object that was passed in the list of
        accounts to `AccountRunner.run`.

        Note: `Command.collect_results` is guaranteed to be called sequentially
        by the main thread, so it is safe to mutate instance variables attached
        to the `Command` object from within this method. This allows command
        authors to safely accumulate results of processing within instance
        variables without the need for synchronization.

        The default implementation prints the return value of `Command.execute`
        to the console on standard output. If the command's execution raises an
        exception, it prints the exception to standard error and logs the stack
        trace at WARN log level.
        """
        try:
            print(get_result(), end="", flush=True)

        except Exception as e:  # pylint: disable=broad-except
            LOG.warning("%s: error: %s", acct, e, exc_info=True)
            print(f"{acct}: error: {e}", flush=True, file=sys.stderr)


class RegionalCommand(Command):
    """Abstract base class for commands using a regional cloud SDK.

    Cloud SDKs that are regional based, such as AWS and its boto3 library, can
    use this base class to simplify the building of commands intended to be
    executed across one or more regions. The `regions` parameter is a list of
    strings representing region names that should be processed while processing
    an account. When subclassing this class, implementers that override the
    constructor must invoke the superclass constructor with the regions to
    process. For example:

        class CLICommand(RegionalCommand):
            def __init__(self, arg1, arg2, regions):
                super().__init__(regions)
                self.arg1 = arg1
                self.arg2 = arg2

    A command is a unit of work that is executed across one or more accounts and
    regions by the `AccountRunner`. During processing of an account and region,
    the command is provided a boto3 session, or similar cloud SDK session-like
    object, configured with the appropriate credentials. In addition, the
    command is provided an account object for the account being processed. The
    attributes and methods attached to the account object depend on what was
    passed to `AccountRunner.run`. This allows users to pass arbitrary account
    objects for use within their custom commands.

    This class documents the contract between the awsrun framework and command
    author. Subclasses must implement `RegionalCommand.regional_execute`. For
    examples on how to write custom regional commands, refer to the built-in
    commands included in the `awsrun.commands` module.
    """

    @classmethod
    def from_cli(cls, parser, argv, cfg):
        # If the user does not provide their own from_cli method, we make sure
        # that we invoke parse_args and add the --region flag on their behalf.
        parser.add_argument(
            "--region",
            "-r",
            action=AppendWithoutDefault,
            default=cfg("region", type=List(Str), default=[]),
            dest="regions",
            metavar="REGION",
            help="region in which to run commands",
        )

        # Delegate out to the user defining their command
        command = cls.regional_from_cli(parser, argv, cfg)

        # Make sure that a user's subclass of the RegionalCommand has called our
        # constructor where the 'regions' instance variable is set to a non-zero
        # length list of regions to parse. On a side note, we do not use the
        # 'required' keyword with ArgumentParser because we want to allow a
        # default value to be provided via the user config file. So, we check to
        # see if this is an empty list here, and if so, then complain and exit.
        if not command.regions:
            parser.error("No regions specified")

        return command

    @classmethod
    def regional_from_cli(cls, parser, argv, cfg):  # pylint: disable=unused-argument
        """Factory to build a regional command from CLI args and user configuration.

        *This method is only required if the command is intended for use with
        the `awsrun.cli` command line. Non-CLI users will not instantiate
        commands via this factory method.*

        Refer to `Command.from_cli` for in-depth discussion on the use of this
        factory method. This method only adds the following additional behavior
        to simplify building a factory for a regional command:

        1. The `parser` has already added the `--region` and `-r` arguments to
           allow users to specify one or more regions to process via command
           line arguments. In addition, a default value can be provided via the
           user configuration under the "region" key in the specific command
           section. The values chosen by the user will be available in the
           namespace returned by the parser as `regions`. The following is used
           to register the arguments on behalf of the regional command author:

                parser.add_argument(
                    '--region', '-r',
                    action=AppendWithoutDefault,
                    default=cfg('region', type=List(Str), default=[]),
                    dest='regions',
                    metavar='REGION',
                    help='Region in which to run commands')

        2. The chosen regions must be passed to the command's constructor
           because subclasses of `RegionalCommand` must invoke its constructor,
           which requires a list of regions to process. If the instance returned
           from this factory method does not have a non-zero `regions` instance
           variable, a usage error is displayed to the user and the program
           terminates.

        When overriding this method, do not invoke the superclass method.
        """
        args = parser.parse_args(argv)
        return cls(regions=args.regions)

    def __init__(self, regions):
        self.regions = regions

    def execute(self, session, acct):
        return [
            (r, _wrap_result(self.regional_execute, session, acct, r))
            for r in self.regions
        ]

    def regional_execute(self, session, acct, region):
        """Invoked by `AccountRunner.run` to process an account / region pair.

        This method is invoked for each account and region pair. The `session`
        parameter is a boto3 Session object, or similar cloud SDK session-like
        object, with credentials for the account being processed. The `acct`
        will be the same object that was passed in the list of accounts to
        `AccountRunner.run`. `region` is a string representing the region name
        such as "us-east-1".

        The return value can be of any type. It will be, by default, printed to
        the console if a `RegionalCommand.regional_collect_results`
        implementation is not provided. If an exception is raised during the
        execution, it will be printed to the console on standard error.

        Note the following items of importance:

        1. Command authors must implement this method. There is no default
           implementation.

        2. Recognize that this method will be invoked concurrently, so
           modification of instance variables from within this method requires
           synchronization. If accumulating results, define a custom
           `RegionalCommand.regional_collect_results` which is guaranteed to be
           invoked sequentially.

        3. Although accounts are processed concurrently, the regions are
           processed sequentially for each account. This ensures that multiple
           regions for the same account are never executed at the same time. It
           provides command authors a guarantee that an account and all its
           regions will be processed sequentially. The same session object and
           credentials are provided to this method for each region being
           processed. Credentials could expire if processing of regions takes a
           significant amount of time.

        4. Do not call `sys.exit` or the entire program will terminate. The
           proper way to exit from this method is either by returning a value or
           by raising an exception.

        5. Do not print directly to the console as output will be interspersed
           with other output from other concurrently running threads processing
           other accounts. The best practice when printing is to accumulate a
           string buffer and return the buffer at the end of the method:

                def regional_execute(self, session, acct, region):
                    out = io.StringIO()

                    # Do stuff
                    print('This will be printed to the console eventually', file=out)
                    # Do more stuff

                    return out.getvalue()
        """
        raise NotImplementedError

    def collect_results(self, acct, get_result):
        try:
            for region, get_region_result in get_result():
                self.regional_collect_results(acct, region, get_region_result)

        except Exception as e:  # pylint: disable=broad-except
            LOG.warning("%s: error: %s", acct, e, exc_info=True)
            print(f"{acct}: error: {e}", flush=True, file=sys.stderr)

    def regional_collect_results(self, acct, region, get_result):
        """Invoked by `AccountRunner.run` after processing an account and region.

        This method is invoked by `AccountRunner.run` after each `acct` /
        `region` pair has been processed by `RegionalCommand.regional_execute`.
        The results from execute are provided via `get_result`, which is a
        callable that will either return the value returned by the regional
        execute method or raise an exception if one was raised. The `acct`
        parameter will be the same object that was passed in the list of
        accounts to `AccountRunner.run`.

        Note: `RegionalCommand.regional_collect_results` is guaranteed to be
        called sequentially by the main thread, so it is safe to mutate instance
        variables attached to the `RegionalCommand` object from within this
        method. This allows command authors to safely accumulate results of
        processing within instance variables without the need for
        synchronization.

        The default implementation prints the return value of
        `RegionalCommand.regional_execute` to the console on standard output. If
        the command's execution raises an exception, it prints the exception to
        standard error and logs the stack trace at WARN log level.
        """
        try:
            print(get_result(), end="", flush=True)

        except Exception as e:  # pylint: disable=broad-except
            LOG.warning("%s/%s: error: %s", acct, region, e, exc_info=True)
            print(f"{acct}/{region}: error: {e}", flush=True, file=sys.stderr)


class CommandFunctionAdapter(Command):
    """Function adapter for a `Command`.

    This adapter wraps `func` in a `Command` that collects the results of the
    function and any exceptions raised in two instance variables. These are
    available for inspection after the `AccountRunner.run` has returned. The
    `func` should have the same signature as `Command.execute` sans the self
    parameter.
    """

    def __init__(self, func):
        super().__init__()
        self.func = func

        self.results = {}
        """Dict containing results keyed by account."""

        self.errors = {}
        """Dict containing exceptions keyed by account."""

    def execute(self, session, acct):
        return self.func(session, acct)

    def collect_results(self, acct, get_result):
        try:
            self.results[acct] = get_result()
        except Exception as e:  # pylint: disable=broad-except
            self.errors[acct] = e


def execute_function(session_provider, accounts, func, key=lambda x: x, max_workers=10):
    """Executes a function across one or more accounts concurrently.

    This is a convenience function that instantiates an `AccountRunner`, wraps a
    `func` in a `CommandFunctionAdapter`, runs the command across a list of
    `accounts`, and then returns a tuple of dicts representing the results and
    errors after all accounts have been processed. The returned dicts are keyed
    by the account.

    The list of `accounts` can be a simple list of strings of account IDs or it
    can be a list of objects that represent accounts. Passing objects can be
    useful as each object is passed to `func` when processing an account. When
    using account objects, you must provide a `key` function that returns the
    account ID as a string from the account object.

    Accounts are processed concurrently using a worker pool. The default number
    of workers is specified by the `max_workers` argument, which defaults to 10.
    """
    command = CommandFunctionAdapter(func)
    AccountRunner(session_provider, max_workers=max_workers).run(
        command, accounts, key=key
    )
    return (command.results, command.errors)


class RegionalCommandFunctionAdapter(RegionalCommand):
    """Function adapter for a `RegionalCommand`.

    This adapter wraps `func` in a `RegionalCommand` that collects the results
    of the function and any exceptions raised in two instance variables. These
    are available for inspection after the `AccountRunner.run` has returned. The
    `func` should have the same signature as `RegionalCommand.execute` sans the
    self parameter.
    """

    def __init__(self, regions, func):
        super().__init__(regions)
        self.func = func

        self.results = {}
        """Dict containing results keyed by the tuple of account and region."""

        self.errors = {}
        """Dict containing exceptions keyed by tuple of account and region."""

    def regional_execute(self, session, acct, region):
        return self.func(session, acct, region)

    def regional_collect_results(self, acct, region, get_result):
        try:
            self.results[(acct, region)] = get_result()
        except Exception as e:  # pylint: disable=broad-except
            self.errors[(acct, region)] = e


def regional_execute_function(
    session_provider, accounts, regions, func, key=lambda x: x, max_workers=10
):
    """Executes a function across one or more accounts and regions concurrently.

    This is a convenience function that instantiates an `AccountRunner`, wraps a
    `func` in a `RegionalCommandFunctionAdapter`, runs the command across a list
    of `accounts` and `regions`, and then returns a tuple of dicts representing
    the results and errors after all accounts have been processed. The returned
    dicts are keyed by a tuple of account and region.

    The list of `accounts` can be a simple list of strings of account IDs or it
    can be a list of objects that represent accounts. Passing objects can be
    useful as each object is passed to `func` when processing an account. When
    using account objects, you must provide a `key` function that returns the
    account ID as a string from the account object.

    Accounts are processed concurrently using a worker pool. The default number
    of workers is specified by the `max_workers` argument, which defaults to 10.
    """
    command = RegionalCommandFunctionAdapter(regions, func)
    AccountRunner(session_provider, max_workers=max_workers).run(
        command, accounts, key=key
    )
    return (command.results, command.errors)


def max_thread_limit(count):
    """Decorator to limit maximum number of concurrent executions.

    In some cases, the author of a `Command` may wish to restrict the number of
    concurrent executions of a command, regardless of the number of workers the
    `AccountRunner` has been instantiated with. awsrun CLI users can specify the
    number of workers via the `--threads` flag, which defaults to 10.

    Use this with `Command.execute` or `RegionalCommand.regional_execute` to
    guarantee concurrent executions do not exceed the specified `count`. When
    the number of concurrent executions exceed the value, they will block until
    an existing execution has completed. For example, the following will limit
    concurrent executions to one:

        @max_thread_limit(1)
        def regional_execute(self, session, acct, region):
           pass

    Note: while this decorator can limit the number of concurrent executions, it
    will not increase the number of workers in the `AccountRunner` worker pool.
    This is a rate limiting decorator only.
    """

    def decorator(func):
        sem = threading.BoundedSemaphore(count)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with sem:
                return func(*args, **kwargs)

        return wrapper

    return decorator


def get_paginated_resources(
    client,
    paginator,
    page_key,
    predicate: Callable[[dict], bool] = lambda _: True,
    **kwargs,
):
    """Return the full list of boto3 resources via a paginator.

    `client` is a boto3 client.  `paginator` is the name (string) of the
    paginator.  `page_key` is the name (string) of the dictionary key used in
    the paginated responses.

    `predicate` is a function that determines which resources are included in
    the list.  The function takes a single argument, the resource. If it returns
    `True`, the resource is included, otherwise it is excluded.

    The remaining `kwargs` are used to specify which resources to retrieve. Some
    paginators do not require any additional arguments, but others do to
    restrict the size of the response.

    For example, to collect the list of load balancers, one might write:

        def get_lbs(client):
            lbs = []
            paginator = client.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page["LoadBalancers"]:
                    lbs.append(lb)
            return lbs

    This can be simplified by using `get_paginated_resources`:

        lbs = get_paginated_resources(client, "describe_load_balancers", "LoadBalancers")

    As another example, to collect the list of UDP listeners for a load
    balancer, one might write:

        def get_listeners(client, lb_arn):
            listeners = []
            paginator = client.get_paginator("describe_listeners")
            for page in paginator.paginate(LoadBalancerArn=lb_arn):
                for listener in page["Listeners"]:
                    if listener["Protocol"] in ["UDP", "TCP_UDP"]:
                        listeners.append(listener)
            return listeners

    This, too, can be simplified using `get_paginated_resources`:

        listeners = get_paginated_resources(
            client,
            "describe_listeners",
            "Listeners",
            lambda l: l["Protocol"] in ["UDP", "TCP_UDP"],
            LoadBalancer=lb_arn)
    """
    resources = []
    for page in client.get_paginator(paginator).paginate(**kwargs):
        for resource in page[page_key]:
            if predicate(resource):
                resources.append(resource)
    return resources


class AccountRunner:
    """Runs a `Command` across one or more accounts.

    The `AccountRunner` manages the concurrent execution of a `Command` across
    one or more cloud accounts. A thread pool is used to process the accounts.
    By default, the number of workers is 10 unless the `max_workers` argument
    has been specified.

    A single worker is responsible for processing an account. The worker obtains
    a boto3 session, or similar cloud SDK session object, with the appropriate
    credentials for the account being processed by using the `session_provider`,
    which must be a subclass of `awsrun.session.SessionProvider`.

    It then invokes `Command.execute` with the session for the account being
    processed. Any exceptions raised during the invocation of a command are
    caught to prevent the termination of other threads. The result of the
    execute method, or exceptions raised, are made available to the command.
    """

    def __init__(self, session_provider, max_workers=10):
        if not isinstance(session_provider, SessionProvider):
            raise TypeError(
                f"'{session_provider}' must be a subclass of awsrun.session.SessionProvider"
            )

        self.session_provider = session_provider
        self.max_workers = max_workers

    def run(self, cmd, accounts, key=lambda x: x):
        """Execute a command concurrently on the specified accounts.

        This method will block until all accounts have been processed. The
        return value is the number of seconds it took to process the accounts.

        The `cmd` must be a subclass of `Command`. The runner will invoke the
        `Command.pre_hook` once before it starts processing any accounts, then
        accounts are processed concurrently and `Command.execute` is invoked by
        a worker for each account. As each execute method returns, the main
        thread will invoke `Command.collect_results`, which ensures results are
        collected sequentially. Finally, after all accounts have been processed,
        `Command.post_hook` is called.

        The specified list of `accounts` can be of any type as long as the
        function specified by the `key` parameter returns a string representing
        the cloud account ID when passed one of these accounts. This allows
        users to pass any object representing an account all the way through to
        `Command.execute`. The only contract is that a `key` function must be
        provided, so workers can obtain the account ID, which is used to request
        a session for the account.

        For example, `accounts` could be a simple list of strings of AWS account
        IDs. The default value of `key` is the identity function, which returns
        the string itself satisfying the contract above. Alternatively,
        `accounts` could be a list of dicts containing metadata for an account,
        which would then be available for command authors in `Command.execute`.
        If the list of accounts specified contained the following:

            [
                {'id': '100200300400', 'env': 'prod', 'status': 'active'},
                {'id': '200300400100', 'env': 'dev', 'status': 'active'},
                {'id': '300400100200', 'env': 'dev', 'status': 'active'},
            ]

        Then, the `key` argument must be specified as `lambda x: x['id']`, which
        will return the account ID string satisfying the contract above.
        Likewise, if accounts were a list of objects that contained an `acct_id`
        attribute, `key` must be defined as `lambda x: x.acct_id` to satisfy the
        contract. If the key function does not return a string or throws an
        exception, then an `InvalidAccountIDError` is raised in the worker
        thread processing the account, which will then propagate to the
        `Command.collect_results`.
        """
        # This will ensure v1 users of awsrun aren't mixing v1 Command's with
        # the v2 framework.
        if not isinstance(cmd, Command):
            raise TypeError(f"'{cmd}' must be a subclass of awsrun.runner.Command")

        # Wrapper to ensure the user-supplied key function returns an string of
        # digits (an AWS account id). It will throw an InvalidAccountIDError
        # if there are any exceptions thrown from use of their key function.
        key = _valid_key_fn(key)

        start = time.time()
        cmd.pre_hook()

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            # The worker task processes a single account. The worker task takes
            # care to capture the result of the command's execute method. We
            # don't want a poorly written command that raises an exception to
            # terminate the main program, so the return value of the command's
            # execute method or any exception raised is wrapped in a callable
            # that is provided back to the command via its collect_results
            # method. When the callable is later invoked, it will return the
            # return value from execute or it will raise the caught exception.
            def worker_task(acct):
                try:
                    acct_id = key(acct)  # Get the acct id from the account obj
                    session = self.session_provider.session(acct_id)
                    return _wrap_result(cmd.execute, session, acct)

                except Exception as e:  # pylint: disable=broad-except
                    # NOTE: exceptions thrown by a Command's execute are not
                    # handled in this block, but in wrap_result above. This
                    # block handles exceptions that occur while obtaining a
                    # session for the account.
                    return _wrap_exception(e)

            # Submit all of the jobs for execution to the thread pool.
            f2a = {pool.submit(worker_task, a): a for a in accounts}

            # NOTE: collect_results is called by the main thread sequentially
            # after each worker completes their task. This is a guarantee for
            # Command authors as it allows them to safely update instance vars
            # in the Command because it is not safe to do so in the execute
            # method which is invoked in a concurrently running worker thread.
            for future in as_completed(f2a):
                acct = f2a[future]
                cmd.collect_results(acct, future.result())

        cmd.post_hook()
        return time.time() - start


class InvalidAccountIDError(Exception):
    """Raised if an account ID cannot be extracted from an account object.

    This is due to an invalid key function specified to `AccountRunner.run`. The
    function either did not return a string or an exception was raised. In
    either case, a valid account ID could be be obtained from the account
    object, so this account cannot be processed.
    """


def _valid_key_fn(fn):
    """Wraps a function expected to return an account ID to validate the result.

    The `AccountRunner.run` method expects to receive a user-supplied key
    function that can extract the account ID from an arbitrary object that
    represents an account. The purpose of this function is to ensure the user
    has provided a valid key function. This function wraps `fn` and validates
    that it returns a string. If it does not or an error occurs, then an
    `InvalidAccountIDError` is raised when the returned function is invoked,
    otherwise the original result of `fn` is returned.
    """

    def new_key_fn(*args, **kwargs):
        try:
            result = fn(*args, **kwargs)
        except Exception as e:
            raise InvalidAccountIDError(
                f"The key function threw an exception: {e}"
            ) from e
        if not isinstance(result, str):
            raise InvalidAccountIDError(f"Account ID is not a string: {result}")
        return result

    return new_key_fn


def _wrap_result(fn, *args, **kwargs):
    """Returns a function that encapsulates the result of `fn(*args, **kwargs)`.

    This function provides a means to capture the result of a computation
    regardless of whether or not the computation was successful. When the
    returned function is invoked, it will return the result of the original
    computation or re-raise any exception that was thrown. For example:

        >>> def test(flag):
        >>>     if flag: return 10
        >>>     raise Exception("boom!")

        >>> result = wrap_result(test, True)
        >>> result()
        10

        >>> result = wrap_result(test, False)
        >>> result()
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
          File "/awsrun/src/awsrun/runner.py", line 231, in fn
            raise exception
          File "/awsrun/src/awsrun/runner.py", line 222, in _wrap_result
            result = fn(*args, **kwargs)
          File "<stdin>", line 3, in test
        Exception: Boom!
    """
    try:
        result = fn(*args, **kwargs)
        return lambda: result
    except Exception as e:  # pylint: disable=broad-except
        return _wrap_exception(e)


def _wrap_exception(exception):
    """Returns a function that when invoked will raise `exception`."""

    def fn():
        raise exception

    return fn
