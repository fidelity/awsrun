#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Adapter for the AWS Command Line Interface (CLI).

## Overview

The `aws` command plug-in is a thin wrapper around the standard [AWS
CLI](https://docs.aws.amazon.com/cli/latest/reference/index.html) provided by
AWS. This allows AWS CLI commands to be executed across multiple accounts in a
concurrent manner. By creating an adapter, awsrun eliminates the need for the
user to download credentials to their ~/.aws/credentials file and simplifies
account selection through awsrun's advanced filtering capabilities.

For example, to list all of the SNS topics in two AWS accounts using the
standard AWS CLI tool, a user would need to obtain the credentials for those two
accounts and update their local credentials file, and then run the following two
commands sequentially:

    $ aws --profile 100200300400 --region us-west-2 --output text sns list-topics
    TOPICS  arn:aws:sns:us-west-2:100200300400:topic-a
    TOPICS  arn:aws:sns:us-west-2:100200300400:topic-b

    $ aws --profile 400300200100 --region us-west-2 --output text sns list-topics
    TOPICS  arn:aws:sns:us-west-2:400300200100:topic-x
    TOPICS  arn:aws:sns:us-west-2:400300200100:topic-y
    TOPICS  arn:aws:sns:us-west-2:400300200100:topic-z

By using the awsrun `aws` command, the results can be fetched concurrently for
both accounts with a single command, and without the need for the user to
install credentials for each account in their ~/.aws/credentials file. The
default output is the concatenation of the results from the individual AWS CLI
invocations:

    $ awsrun --account 100200300400 --account 400300200100 aws --region us-west-2 --output text sns list-topics
    TOPICS  arn:aws:sns:us-west-2:100200300400:topic-a
    TOPICS  arn:aws:sns:us-west-2:100200300400:topic-b
    TOPICS  arn:aws:sns:us-west-2:400300200100:topic-x
    TOPICS  arn:aws:sns:us-west-2:400300200100:topic-y
    TOPICS  arn:aws:sns:us-west-2:400300200100:topic-z

## Reference

### Synopsis

    $ awsrun [options] aws [command options]

The command options can be any of the options used with the standard AWS CLI
command with two minor differences. The user does not have to provide the
`--profile` flags. Why? awsrun provides the credentials for each account
selected using the one of the `awsrun.plugins.creds.aws` plug-ins. The second
difference is that users can specify more than one `--region` argument to run
the command across multiple regions.

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      aws:
        awsrun_output_dir: STRING
        awsrun_annotate: ("json" | "table" | "text")
        region:
          - STRING

### Command Options

Some options can be overridden on the awsrun CLI via command line flags. In
those cases, the CLI flags are specified next to the option name below:

`awsrun_output_dir`, `--awsrun-output-dir`
:  Save both the standard output and standard error for each account and
region processed in the specified directory. The files called will be called
`ACCOUNT-REGION.stdout.log` and `ACCOUNT-REGION.stderr.log`. If the directory
does not exist, it is created.

`awsrun_annotate`, `--awsrun-annotate`
:  Specifies the output format for the AWS CLI command and annotates that
format appropriately with account and region information. Must be one of
"json", "table", or "text". See user guide for more information.

`region`, `--region`
:  Run the AWS CLI command in the specified regions. When specifying multiple
values on the command line, use multiple flags for each value.

## User Guide

The follow section is a user guide on how to use the `aws` command effectively.

### Output Formats

As stated before, the output from the awsrun `aws` command is the same as that
from the AWS CLI tool with the exception that results are concatenated together.
Most AWS CLI commands provide three different output formats: `text`, `table`,
and `json`, which are specified by the `--output` option. These can be used with
this plug-in as well.

JSON results:

    $ awsrun --account 100200300400 --account 400300200100 aws --region us-west-2 --output json sns list-topics
    {
        "Topics": [
            {
                "TopicArn": "arn:aws:sns:us-west-2:100200300400:topic-name-a"
            },
            {
                "TopicArn": "arn:aws:sns:us-west-2:100200300400:topic-name-b"
            }
        ]
    }
    {
        "Topics": [
            {
                "TopicArn": "arn:aws:sns:us-west-2:400300200100:topic-name-x"
            },
            {
                "TopicArn": "arn:aws:sns:us-west-2:400300200100:topic-name-y"
            },
            {
                "TopicArn": "arn:aws:sns:us-west-2:400300200100:topic-name-z"
            }
        ]
    }

Table results:

    $ awsrun --account 100200300400 --account 400300200100 aws --region us-west-2 --output table sns list-topics
    --------------------------------------------------------------
    |                         ListTopics                         |
    +------------------------------------------------------------+
    ||                          Topics                          ||
    |+----------------------------------------------------------+|
    ||                         TopicArn                         ||
    |+----------------------------------------------------------+|
    ||  arn:aws:sns:us-west-2:100200300400:topic-name-a         ||
    ||  arn:aws:sns:us-west-2:100200300400:topic-name-b         ||
    |+----------------------------------------------------------+|
    --------------------------------------------------------------
    |                         ListTopics                         |
    +------------------------------------------------------------+
    ||                          Topics                          ||
    |+----------------------------------------------------------+|
    ||                         TopicArn                         ||
    |+----------------------------------------------------------+|
    ||  arn:aws:sns:us-west-2:400300200100:topic-name-x         ||
    ||  arn:aws:sns:us-west-2:400300200100:topic-name-y         ||
    ||  arn:aws:sns:us-west-2:400300200100:topic-name-z         ||
    |+----------------------------------------------------------+|


### Annotating the Output

In some cases, the output from an AWS CLI command does not contain enough
information to identify the account it came from. When using the standard AWS
CLI tool, this is not a problem because it only operates on a single account.
The awsrun command, however, operates on multiple accounts simultaneously
displaying the output as each account is processed. How is one supposed to
discern one result from another?

To solve that problem, this awsrun command plug-in can annotate the output by
using the `--awsrun-annotate` flag.  This flag takes one parameter, which is the
output format to be annotated: `text`, `table`, or `json`. When using this flag,
it is redundant and unnecessary to provide the `--output` option. By using the
annotation feature, it is trivial to identify which account and region the
output came from.

When annotating text and table output, each line is prefixed with the account
and region of where the result came from. Here are the text and table examples
from above with annotations enabled:

    $ awsrun --account 100200300400 --account 400300200100 aws --region us-west-2 --awsrun-annotate text sns list-topics
    100200300400/us-west-2: TOPICS  arn:aws:sns:us-west-2:100200300400:topic-a
    100200300400/us-west-2: TOPICS  arn:aws:sns:us-west-2:100200300400:topic-b
    400300200100/us-west-2: TOPICS  arn:aws:sns:us-west-2:400300200100:topic-x
    400300200100/us-west-2: TOPICS  arn:aws:sns:us-west-2:400300200100:topic-y
    400300200100/us-west-2: TOPICS  arn:aws:sns:us-west-2:400300200100:topic-z

    $ awsrun --account 100200300400 --account 400300200100 aws --region us-west-2 --awsrun-annotate table sns list-topics
    100200300400/us-west-2: --------------------------------------------------------------
    100200300400/us-west-2: |                         ListTopics                         |
    100200300400/us-west-2: +------------------------------------------------------------+
    100200300400/us-west-2: ||                          Topics                          ||
    100200300400/us-west-2: |+----------------------------------------------------------+|
    100200300400/us-west-2: ||                         TopicArn                         ||
    100200300400/us-west-2: |+----------------------------------------------------------+|
    100200300400/us-west-2: ||  arn:aws:sns:us-west-2:100200300400:topic-name-a         ||
    100200300400/us-west-2: ||  arn:aws:sns:us-west-2:100200300400:topic-name-b         ||
    100200300400/us-west-2: |+----------------------------------------------------------+|
    400300200100/us-west-2: --------------------------------------------------------------
    400300200100/us-west-2: |                         ListTopics                         |
    400300200100/us-west-2: +------------------------------------------------------------+
    400300200100/us-west-2: ||                          Topics                          ||
    400300200100/us-west-2: |+----------------------------------------------------------+|
    400300200100/us-west-2: ||                         TopicArn                         ||
    400300200100/us-west-2: |+----------------------------------------------------------+|
    400300200100/us-west-2: ||  arn:aws:sns:us-west-2:400300200100:topic-name-x         ||
    400300200100/us-west-2: ||  arn:aws:sns:us-west-2:400300200100:topic-name-y         ||
    400300200100/us-west-2: ||  arn:aws:sns:us-west-2:400300200100:topic-name-z         ||
    400300200100/us-west-2: |+----------------------------------------------------------+|

JSON output is annotated by wrapping embedding the JSON output from AWS CLI in a
new JSON object with three keys: `Account`, `Region`, and `Results`, where
`Results` contains the output from the AWS CLI.

    $ awsrun --account 100200300400 --account 400300200100 aws --region us-west-2 --awsrun-annotate json sns list-topics
    {
        "Account": "100200300400",
        "Region": "us-west-2",
        "Results": {
            "Topics": [
                {
                    "TopicArn": "arn:aws:sns:us-west-2:100200300400:topic-name-a"
                },
                {
                    "TopicArn": "arn:aws:sns:us-west-2:100200300400:topic-name-b"
                }
            ]
        }
    }
    {
        "Account": "400300200100",
        "Region": "us-west-2",
        "Results": {
            "Topics": [
                {
                    "TopicArn": "arn:aws:sns:us-west-2:400300200100:topic-name-x"
                },
                {
                    "TopicArn": "arn:aws:sns:us-west-2:400300200100:topic-name-y"
                },
                {
                    "TopicArn": "arn:aws:sns:us-west-2:400300200100:topic-name-z"
                }
            ]
        }
    }

### Output to a Directory

In addition to the output that is sent to the console, the standard output and
error of each AWS CLI command can be saved to a directory by specifying the
`--awsrun-output-dir DIR` option. If `DIR` does not exist, it will be created.
The standard output will be saved in a file named `ACCOUNT-REGION.stdout.log`. If
there was output sent to standard error, it is saved in `ACCOUNT-REGION.stderr.log`.

    $ awsrun --account 100200300400 --account 400300200100 aws --region us-west-2 --awsrun-output-dir /tmp/aws --awsrun-annotate text sns list-topics
    100200300400/us-west-2: TOPICS  arn:aws:sns:us-west-2:100200300400:topic-a
    100200300400/us-west-2: TOPICS  arn:aws:sns:us-west-2:100200300400:topic-b
    400300200100/us-west-2: TOPICS  arn:aws:sns:us-west-2:400300200100:topic-x
    400300200100/us-west-2: TOPICS  arn:aws:sns:us-west-2:400300200100:topic-y
    400300200100/us-west-2: TOPICS  arn:aws:sns:us-west-2:400300200100:topic-z

    $ ls -l /tmp/aws
    -rw-r--r--  1 me  wheel  122 Jul 28 11:13 100200300400-us-west-2.stdout
    -rw-r--r--  1 me  wheel  180 Jul 28 11:13 400300200100-us-west-2.stdout

Annotations are not added to the output sent to the files. The files contain the
raw output that came direct from the AWS CLI invocation:

    $ cat /tmp/aws/100200300400-us-west-2.stdout
    TOPICS  arn:aws:sns:us-west-2:100200300400:topic-a
    TOPICS  arn:aws:sns:us-west-2:100200300400:topic-b

### Note about Option Names

In most cases, awsrun command plug-ins do not prefix their option names with
`--awsrun-` because the command options must come after the command on the
command line, so there is a clear distinction between awsrun options and command
options:

    $ awsrun --account 400300200100 command --region us-west-2 --flag --option value
             ^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                        |              |              |
                  awsrun options    command    command options

As a result, there is no namespace collision with core awsrun options and
command options. However, in the case of this `aws` command, the two option
names are prefixed with `--awsrun-` because they are specified alongside AWS CLI
options and arguments. This is to avoid naming collisions with AWS CLI options:

    $ awsrun --account 100200300400 aws --region us-west-2 --awsrun-annotate text sns list-topics
             ^^^^^^^^^^^^^^^^^^^^^^ ^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                        |            |                     |
                  awsrun options  command    AWS CLI args and Plug-in options

### Tips on Parsing JSON Output

When collecting output across many accounts, it can be very helpful to limit the
output from AWS CLI to the elements you are seeking using the builtin AWS CLI
`--query` option. Usage of this feature is beyond the scope of this document,
but details can be found in the [AWS CLI
Documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-usage-output.html#cli-usage-output-filter).
For example, here is the truncated output of the `ec2 describe-vpcs` AWS CLI
command as executed by awsrun aws command:

    $ awsrun --account 100200300400 --account 400300200100 aws --region us-west-2 --awsrun-annotate json ec2 describe-vpcs
    {
        "Account": "100200300400",
        "Region": "us-west-2",
        "Results": {
            "Vpcs": [
                {
                    "CidrBlock": "10.10.124.0/23",
                    "DhcpOptionsId": "dopt-dcf20ed3942e77d9",
                    "State": "available",
                    "VpcId": "vpc-0ff9d61630c8bac7",
                    ...
                }
            ]
        }
    }
    {
        "Account": "400300200100",
        "Region": "us-west-2",
        "Results": {
            "Vpcs": [
                {
                    "CidrBlock": "10.10.224.0/24",
                    "DhcpOptionsId": "dopt-aaea912755d7c81c",
                    "State": "available",
                    "VpcId": "vpc-b1bb4c799a70d523",
                    ...
                }
            ]
        }
    }

Using the AWS CLI `--query` option allows one to filter the output. To list only
the primary `CidrBlock` associated with each VPC, use the filter
`'Vpcs[].CidrBlock'`:

    $ awsrun --account 100200300400 --account 400300200100 aws --region us-west-2 --awsrun-annotate json ec2 describe-vpcs --query 'Vpcs[].CidrBlock'
    {
        "Account": "100200300400",
        "Region": "us-west-2",
        "Results": [
            "10.10.124.0/23"
        ]
    }
    {
        "Account": "400300200100",
        "Region": "us-west-2",
        "Results": [
            "10.10.224.0/24"
        ]
    }

The same could be accomplished with other tools such as
[jq](https://stedolan.github.io/jq/). These tools can be invaluable when parsing
the aggregated JSON output. Using `jq` to parse the full output of `ec2
describe-vpcs`, the list of CIDR blocks can be extracted by:

    $ awsrun --account 100200300400 --account 400300200100 aws --region us-west-2 --awsrun-annotate json ec2 describe-vpcs | jq '{acct: .Account, region: .Region, cidrs: [.Results.Vpcs[].CidrBlock]}'
    {
        "acct": "100200300400",
        "region": "us-west-2",
        "cidrs": [
            "10.10.124.0/23"
        ]
    }
    {
        "acct": "400300200100",
        "region": "us-west-2",
        "cidrs": [
            "10.10.224.0/24"
        ]
    }
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from collections import ChainMap
from pathlib import Path

from awsrun.config import StrMatch
from awsrun.runner import RegionalCommand

LOG = logging.getLogger(__name__)


class CLICommand(RegionalCommand):
    """Execute aws cli commands concurrently."""

    @classmethod
    def regional_from_cli(cls, parser, argv, cfg):
        """Parse command line arguments provided to this command."""

        # Note: normally one would not prefix an awsrun command's arguments with
        # '--awsrun-', but this is a special exception because there could be
        # valid awscli args interspersed among the awsrun command flags. To
        # avoid namespace collisions, the aws command args are prefixed.
        parser.add_argument(
            "--awsrun-output-dir",
            metavar="DIR",
            default=cfg("awsrun_output_dir"),
            help="output directory to write results to separate files",
        )

        parser.add_argument(
            "--awsrun-annotate",
            choices=["json", "text", "table"],
            default=cfg("awsrun_annotate", type=StrMatch("^(json|text|table)$")),
            help="annotate each result with account / region",
        )

        # Let's gobble up any --profile or --output flags passed to the awscli
        # command. We don't include these flags in the help message as they are
        # really part of the awscli tool. We capture profile flags to remind
        # users not to specify them. As for output flag, this is captured so we
        # can make sure user does not try to specify a different output if they
        # selected --awsrun-annotate. The types need to match.
        parser.add_argument("--profile", help=argparse.SUPPRESS)
        parser.add_argument("--output", help=argparse.SUPPRESS)

        # We parse the known args and then collect the rest as those will be
        # passed to the awscli command later.
        args, remaining_args = parser.parse_known_args(argv)

        if args.profile:
            parser.error(
                "Do not specify --profile aws CLI flag, it is supplied by awsrun"
            )

        if args.awsrun_annotate and args.output and args.awsrun_annotate != args.output:
            parser.error(
                "When specifying --awsrun-annotate, you do not need the --output flag"
            )

        return cls(
            remaining_args,
            regions=args.regions,
            output=args.output,
            output_dir=args.awsrun_output_dir,
            annotate=args.awsrun_annotate,
        )

    def __init__(
        self, awscli_args, regions, output=None, output_dir=None, annotate=False
    ):
        super().__init__(regions)
        self.awscli_path = shutil.which("aws")
        self.awscli_args = awscli_args
        self.output = output
        self.annotate = annotate
        self.output_dir = Path(output_dir) if output_dir else None

        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        if not self.awscli_path:
            raise FileNotFoundError(
                "error: Have you installed the AWS CLI? https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html"
            )

    def regional_execute(self, session, acct, region):
        """Invoke an AWS CLI command for an account and region."""

        # We need to assemble a valid AWS cli command line that can be executed
        # by the operating system. The instance variable awscli_args contains
        # all arguments that follow 'aws': awsrun -r us-east-1 aws ... We will
        # provide the --region argument as we know the region we are processing.
        # We will also provide --output if the user has asked us to annotate an
        # output type. This ensures we override any user settings that the AWS
        # cli tool may pick up from ~/.aws/config.
        cmd = [self.awscli_path, "--region", region]
        if self.annotate:
            cmd += ["--output", self.annotate]
        elif self.output:
            cmd += ["--output", self.output]
        cmd += self.awscli_args
        LOG.info("%s-%s: AWS CLI command: %s", acct, region, cmd)

        # Before we can execute the AWS cli tool, we need to set a few env vars
        # with our creds. Normally, the AWS cli expects this file to exist in
        # the user's home directory at ~/.aws/credentials.
        creds = session.get_credentials()

        new_vars = {
            "AWS_ACCESS_KEY_ID": creds.access_key,
            "AWS_SECRET_ACCESS_KEY": creds.secret_key,
            "AWS_SESSION_TOKEN": creds.token if creds.token else "",
        }

        env = ChainMap(new_vars, os.environ)

        # We call run() and capture stdout and stderr from the command's
        # output. Note: all the output is stored in memory, and then printed
        # in collect_results. This means that if you run an AWS cli command
        # that generates huge amounts of data, it'll all be stored in
        # memory. Why don't we stream tho output from a pipe? We could use
        # Popen directly, but if we returned from execute() before reading
        # all of the results, then the worker will start another account, so
        # in essence, all of the accounts will be "executed" immediately
        # resulting in potentially many many AWS cli command processes
        # running waiting for us to read the output.

        result = subprocess.run(
            cmd,
            env=env,
            check=False,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Lastly, we return the ProcessCompleted object from the run() method.
        # Recall, an awsrun command can return anything if you provide your own
        # collect_results method.
        return result

    def regional_collect_results(self, acct, region, get_result):
        """Print the results to the console and files if specified."""

        def annotate_lines(text, file=sys.stdout):
            for line in filter(None, text.split("\n")):
                print(f"{acct}/{region}: {line}", file=file, flush=True)

        def annotate_json(text):
            try:
                d = {
                    "Account": str(acct),
                    "Region": region,
                    "Results": json.loads(text),
                }
                json.dump(d, sys.stdout, indent=4)
                print()
            except json.decoder.JSONDecodeError:
                annotate_lines(
                    "Result of AWS CLI command is not valid JSON", file=sys.stderr
                )

        try:
            # Let's get the return value from the execute method, which is the
            # ProcessCompleted object from the subprocess.run() method above ...
            result = get_result()

        except Exception as e:  # pylint: disable=broad-except
            # ... unless there was an exception in which case it is raised by
            # the call to get_result and we handle it here.
            LOG.info("%s/%s: error: %s", acct, region, e, exc_info=True)
            annotate_lines(f"error: {e}", file=sys.stderr)
            return

        # Print stderr from AWS CLI always annotating the lines
        annotate_lines(result.stderr, file=sys.stderr)

        # Print stdout from AWS CLI annotating when appropriate
        if not self.annotate:
            print(result.stdout, end="", flush=True)
        elif self.annotate == "json":
            annotate_json(result.stdout)
        elif self.annotate in ["text", "table"]:
            annotate_lines(result.stdout)

        # Save stdout and stderr from AWS CLI to disk if requested
        if self.output_dir:
            # Recall, the acct object passed to execute() can be anything. The
            # str() method should provide us a unique means of identifying the
            # account, but we need to escape any slashes if we use this as part
            # of a filename so pathlib doesn't interpret as directories.
            escaped = re.sub(r"[\\/]", "_", str(acct))
            name = self.output_dir / f"{escaped}-{region}"

            def save(suffix, text):
                with name.with_suffix(suffix).open("w") as out:
                    out.write(text)

            save(".stdout.log", result.stdout)
            if result.stderr:
                save(".stderr.log", result.stderr)
