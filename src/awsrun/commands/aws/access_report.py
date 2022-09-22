#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Test role access to the accounts specified.

## Overview

The access_report command will display the number of accounts that the IAM
role does not have access to.  For example:

    $ awsrun --account 100200300400 --account 200300400100 access_report
    Success: 2, Failures: 0

Note: no output is generated until all accounts have been tested, so it may look
like the command is hanging when processing a large number of accounts. With the
`--verbose` option, a success message is generated for each account as soon as
it has been processed:

    $ awsrun --include Env=DEV access_report --verbose
    400100200300: successful
    100200300400: successful
    200300400100: successful
    Success: 3, Failures: 2

    Unsuccessful attempts:
    300200100400
    300100400200

## Reference

### Synopsis

    $ awsrun [options] access_report [command options]

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      access_report:
        verbose: BOOLEAN

### Command Options

Some options can be overridden on the awsrun CLI via command line flags. In
those cases, the CLI flags are specified next to the option name below:

`verbose`, `--verbose`
:  Display a message as each account is tested. By default, no output is
generated until all accounts have been processed.
"""

from awsrun.config import Bool
from awsrun.runner import Command


class CLICommand(Command):
    """Test role access to the accounts specified."""

    @classmethod
    def from_cli(cls, parser, argv, cfg):
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            default=cfg("verbose", type=Bool, default=False),
            help="display accounts while being processed",
        )

        args = parser.parse_args(argv)
        return cls(**vars(args))

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.total = 0
        self.no_access = []

    def execute(self, session, acct):
        if self.verbose:
            return f"{acct}: successful\n"
        return None

    def collect_results(self, acct, get_result):
        self.total += 1
        try:
            result = get_result()
        except Exception:  # pylint: disable=broad-except
            self.no_access.append(acct)
            return

        if result:
            print(result, end="", flush=True)

    def post_hook(self):
        unsuccessful = len(self.no_access)
        successful = self.total - unsuccessful

        print(f"Success: {successful}, Failures: {unsuccessful}")

        if unsuccessful:
            print("\nUnsuccessful attempts:")
            for acct in self.no_access:
                print(acct)
