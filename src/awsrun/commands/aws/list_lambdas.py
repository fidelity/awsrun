#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""
Display the Lambda functions deployed within an account.

## Overview

The list_lambdas command displays the name of the Lambda function, the role the
function assumes, and whether or not the Lambda is a public function. A public
function is one that is not bound to a VPC and thus has direct access to the
Internet. For example:

    $ awsrun --account 100200300400 list_lambdas --region us-east-1
    100200300400/us-east-1: name=event_transmitter runtime=python3.6 role=arn:aws:iam::100200300400:role/logger public=False
    100200300400/us-east-1: name=event_collector role=arn:aws:iam::100200300400:role/logger public=True

The `--summary` flag will summarize by the IAM role associated with the Lambda
function. For example:

    $ awsrun --account 100200300400 list_lambdas --region us-east-1 --summary
    100200300400/us-east-1: role=arn:aws:iam::100200300400:role/logger total=2 private=1 public=1

## Reference

### Synopsis

    $ awsrun [options] list_lambdas [command options]

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      list_lambdas:
        summary: BOOLEAN
        region:
          - STRING

### Command Options

Some options can be overridden on the awsrun CLI via command line flags. In
those cases, the CLI flags are specified next to the option name below:

`summary`, `--summary`
:  Print only a summary of Lambda functions per execution role.

`region`, `--region`
:  Run the AWS CLI command in the specified regions. When specifying multiple
values on the command line, use multiple flags for each value.
"""

import io
from collections import defaultdict

from awsrun.config import Bool
from awsrun.runner import RegionalCommand


class CLICommand(RegionalCommand):
    """Display Lambda functions deployed in accounts."""

    @classmethod
    def regional_from_cli(cls, parser, argv, cfg):
        parser.add_argument(
            "--summary",
            "-s",
            action="store_true",
            help="display summary by role",
            default=cfg("summary", type=Bool),
        )

        args = parser.parse_args(argv)
        return cls(**vars(args))

    def __init__(self, regions, summary):
        super().__init__(regions)
        self.show_summary_only = summary

    def regional_execute(self, session, acct, region):
        out = io.StringIO()
        by_role = defaultdict(list)

        aws_lambda = session.client("lambda", region_name=region)
        paginator = aws_lambda.get_paginator("list_functions")

        for fn_page in paginator.paginate():
            for fn in fn_page["Functions"]:
                if self.show_summary_only:
                    by_role[fn["Role"]].append(fn)
                    continue
                print(
                    f'{acct}/{region}: name={fn["FunctionName"]} runtime={fn["Runtime"]} role={fn["Role"]} public={_is_public(fn)}',
                    file=out,
                )

        if self.show_summary_only:
            for role in by_role:
                total = len(by_role[role])
                public = len([fn for fn in by_role[role] if _is_public(fn)])
                print(
                    f"{acct}/{region}: role={role} total={total} private={total - public} public={public}",
                    file=out,
                )

        return out.getvalue()


def _is_public(fn):
    if "VpcConfig" not in fn:
        return True
    return len(fn["VpcConfig"]["SubnetIds"]) == 0
