#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Display the IAM roles in an account and its trust relationships.

## Overview

The list_iam_roles command will display the IAM roles in an account. By
default, all roles in an account are displayed:

    $ awsrun --account 100200300400 list_iam_roles
    100200300400: arn=arn:aws:iam::100200300400:role/viewer
    100200300400: arn=arn:aws:iam::100200300400:role/logger
    ...

The `--role` flag will limit the output to the specified role name.  Matching is
done on the name portion of the role ARN. For example:

    $ awsrun --account 100200300400 list_iam_roles --role logger
    100200300400: arn=arn:aws:iam::100200300400:role/logger

Multiple roles can be filtered by specifying multiple `--role` flags:

    $ awsrun --account 100200300400 list_iam_roles --role viewer --role logger
    100200300400: arn=arn:aws:iam::100200300400:role/viewer
    100200300400: arn=arn:aws:iam::100200300400:role/logger

The `--trust` flag will also include the trust relationships contained within
the assume role policy document attached to the role:

    $ awsrun --account 100200300400 list_iam_roles --trust
    100200300400: arn=arn:aws:iam::100200300400:role/viewer trusted=arn:aws:iam::100200300400:saml-provider/prodsaml
    100200300400: arn=arn:aws:iam::100200300400:role/logger trusted=lambda.amazonaws.com

## Reference

### Synopsis

    $ awsrun [options] list_iam_roles [command options]

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      list_iam_roles:
        role:
          - STRING
        trust: BOOLEAN

### Command Options

Some options can be overridden on the awsrun CLI via command line flags. In
those cases, the CLI flags are specified next to the option name below:

`role`, `--role`
:  Limit output to roles matching the specified role names. When specifying
multiple values on the command line, use multiple flags for each value.

`trust`, `--trust`
:  Display the trust relationships along with each role.
"""

import io

from awsrun.config import Bool, List, Str
from awsrun.runner import Command


class CLICommand(Command):
    """Display the IAM roles in an account and its trust relationships."""

    @classmethod
    def from_cli(cls, parser, argv, cfg):
        parser.add_argument(
            "--role",
            "-r",
            action="append",
            help="Limit results to role name",
            default=cfg("role", type=List(Str), default=[]),
        )
        parser.add_argument(
            "--trust",
            "-t",
            action="store_true",
            help="List trust relationships for each role",
            default=cfg("trust", type=Bool),
        )

        args = parser.parse_args(argv)
        return cls(**vars(args))

    def __init__(self, role, trust):
        self.role_filter = role
        self.trust = trust

    def execute(self, session, acct):
        out = io.StringIO()
        iam = session.resource("iam")

        for role in iam.roles.all():
            if self.role_filter and role.name not in self.role_filter:
                continue

            output = f"{acct}: arn={role.arn}"
            if self.trust:
                arns = _trusted_arns(role.assume_role_policy_document)
                output += " trusted=" + ", ".join(arns)
            print(output, file=out)

        return out.getvalue()


# Return a list of trusted principal ARNs
def _trusted_arns(policy):
    if not policy:
        return []

    arns = []
    for statement in policy.get("Statement", []):
        if not statement.get("Effect", "") == "Allow":
            continue
        for arn in statement.get("Principal", {}).values():
            if isinstance(arn, list):
                arns.extend(arn)
            else:
                arns.append(arn)

    return arns
