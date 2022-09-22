#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Adapter for the Azure Command Line Interface (CLI).

## Overview

The `az` command plug-in is a thin wrapper around the standard [Azure
CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) provided by
Azure. This allows Azure CLI commands to be executed across multiple
subscriptions in a concurrent manner. By creating an adapter, azurerun
simplifies account selection through azurerun's advanced filtering capabilities.

For example, to list all of the VNETs in two Azure subscriptions using the
standard Azure CLI tool, a user would run the following two commands
sequentially:

    $ az network vnet list --subscription 00000000-0000-0000-0000-000000000000 --output table
    Name   ResourceGroup      Location    NumSubnets   Prefixes
    -----  -----------------  ----------  -----------  -----------
    vnet1  centralus-network  centralus   1            10.0.0.0/24
    vnet2  eastus2-network    eastus2     1            10.0.1.0/24

    $ az network vnet list --subscription 11111111-1111-1111-1111-111111111111 --output table
    Name   ResourceGroup      Location    NumSubnets   Prefixes
    -----  -----------------  ----------  -----------  -----------
    vnet1  centralus-network  centralus   1            10.0.5.0/24
    vnet2  eastus1-network    eastus1     1            10.0.6.0/24
    vnet3  eastus2-network    eastus2     1            10.0.7.0/24

By using the azurerun `az` command, the results can be fetched concurrently for
both accounts with a single command.  The default output is the concatenation of
the results from the individual Azure CLI invocations:

```sh
$ azurerun --account 00000000-0000-0000-0000-000000000000 --account 11111111-1111-1111-1111-111111111111 az network vnet list --output table
Name   ResourceGroup      Location    NumSubnets   Prefixes
-----  -----------------  ----------  -----------  -----------
vnet1  centralus-network  centralus   1            10.0.0.0/24
vnet2  eastus2-network    eastus2     1            10.0.1.0/24

Name   ResourceGroup      Location    NumSubnets   Prefixes
-----  -----------------  ----------  -----------  -----------
vnet1  centralus-network  centralus   1            10.0.5.0/24
vnet2  eastus1-network    eastus1     1            10.0.6.0/24
vnet3  eastus2-network    eastus2     1            10.0.7.0/24
```

## Reference

### Synopsis

    $ azurerun [options] az [command options]

The command options can be any of the options used with the standard Azure CLI
command with one minor difference. The user does not provide a `--subscription`
argument. Instead, one should use one of the azurerun mechanisms to specify the
subscriptions to process. This might be one or more `--account` flags or the use
of the metadata `--include` filter for example.

Note: Users must first sign in with the native Azure CLI `login` command to
obtain the necessary credentials

    $ az login

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      az:
        azurerun_output_dir: STRING
        azurerun_annotate: ("json" | "yaml" | "tsv" | "table")

### Command Options

Some options can be overridden on the azurerun CLI via command line flags. In
those cases, the CLI flags are specified next to the option name below:

`azurerun_output_dir`, `--azurerun-output-dir`
:  Save both the standard output and standard error for each account processed
in the specified directory. The files called will be called `ACCOUNT.stdout.log`
and `ACCOUNT.stderr.log`. If the directory does not exist, it is created.

`azurerun_annotate`, `--azurerun-annotate`
:  Specifies the output format for the Azure CLI command and annotates that
format appropriately with account information. Must be one of "json", "yaml",
"table", or "tsv". See user guide for more information.

## User Guide

The follow section is a user guide on how to use the `az` command effectively.

### Output Formats

As stated before, the output from the azurerun `az` command is the same as that
from the Azure CLI tool with the exception that results are concatenated
together.  Most Azure CLI commands provide several different output formats:
`tsv`, `table`, `json`, and `yaml`, which are specified by the `--output`
option. These can be used with this wrapper as well.

JSON results:

    $ azurerun --account 00000000-0000-0000-0000-000000000000 --account 11111111-1111-1111-1111-111111111111 az network vnet list --output json
    [
      { "name": "vnet1", "resourceGroup": "centralus-network", ... },
      { "name": "vnet2", "resourceGroup": "eastus2-network", ... }
    ]
    [
      { "name": "vnet1", "resourceGroup": "centralus-network", ... },
      { "name": "vnet2", "resourceGroup": "eastus1-network", ... }
      { "name": "vnet3", "resourceGroup": "eastus2-network", ... }
    ]

### Annotating the Output

In some cases, the output from an Azure CLI command does not contain enough
information to identify the subscription it came from. When using the standard
Azure CLI tool, this is not a problem because it only operates on a single
subscription. The azurerun command, however, operates on multiple subscriptions
simultaneously displaying the output as each is processed. How is one supposed
to discern one result from another?

To solve that problem, this azurerun command plug-in can annotate the output by
using the `--azurerun-annotate` flag.  This flag takes one parameter, which is
the output format to be annotated: `tsv`, `table`, `json` or `yaml`. When using
this flag, it is redundant and unnecessary to provide the `--output` option. By
using the annotation feature, it is trivial to identify which account the output
came from.

When annotating tsv and table output, each line is prefixed with the
subscription of where the result came from. For example:

    $ azurerun --account 00000000-0000-0000-0000-000000000000 --account 11111111-1111-1111-1111-111111111111 az network vnet list --azurerun-annotate table
    00000000-0000-0000-0000-000000000000: Name   ResourceGroup      Location    NumSubnets   Prefixes
    00000000-0000-0000-0000-000000000000: -----  -----------------  ----------  -----------  -----------
    00000000-0000-0000-0000-000000000000: vnet1  centralus-network  centralus   1            10.0.0.0/24
    00000000-0000-0000-0000-000000000000: vnet2  eastus2-network    eastus2     1            10.0.1.0/24

    11111111-1111-1111-1111-111111111111: Name   ResourceGroup      Location    NumSubnets   Prefixes
    11111111-1111-1111-1111-111111111111: -----  -----------------  ----------  -----------  -----------
    11111111-1111-1111-1111-111111111111: vnet1  centralus-network  centralus   1            10.0.5.0/24
    11111111-1111-1111-1111-111111111111: vnet2  eastus1-network    eastus1     1            10.0.6.0/24
    11111111-1111-1111-1111-111111111111: vnet3  eastus2-network    eastus2     1            10.0.7.0/24

JSON and YAML output is annotated by wrapping & embedding the JSON output from
Azure CLI in a new JSON object with two keys: `Account` and `Results`, where
`Results` contains the output from the Azure CLI:

    $ azurerun --account 00000000-0000-0000-0000-000000000000 --account 11111111-1111-1111-1111-111111111111 az network vnet list --azurerun-annotate json
    {
      "Subscription": "00000000-0000-0000-0000-000000000000",
      "Results": [
        { "name": "vnet1", "resourceGroup": "centralus-network", ... },
        { "name": "vnet2", "resourceGroup": "eastus2-network", ... }
      ]
    }
    {
      "Subscription": "11111111-1111-1111-1111-111111111111",
      "Results": [
        { "name": "vnet1", "resourceGroup": "centralus-network", ... },
        { "name": "vnet2", "resourceGroup": "eastus1-network", ... }
        { "name": "vnet3", "resourceGroup": "eastus2-network", ... }
      ]
    }

### Output to a Directory

In addition to the output that is sent to the console, the standard output and
error of each Azure CLI command can be saved to a directory by specifying the
`--azurerun-output-dir DIR` option. If `DIR` does not exist, it will be created.
The standard output will be saved in a file named `ACCOUNT.stdout.log`.  If
there was output sent to standard error, it is saved in `ACCOUNT.stderr.log`.

    $ azurerun --account 00000000-0000-0000-0000-000000000000 --account 11111111-1111-1111-1111-111111111111 az network vnet list --azurerun-annotate table --azurerun-output-dir /tmp/azure
    00000000-0000-0000-0000-000000000000: Name   ResourceGroup      Location    NumSubnets   Prefixes
    00000000-0000-0000-0000-000000000000: -----  -----------------  ----------  -----------  -----------
    00000000-0000-0000-0000-000000000000: vnet1  centralus-network  centralus   1            10.0.0.0/24
    00000000-0000-0000-0000-000000000000: vnet2  eastus2-network    eastus2     1            10.0.1.0/24

    11111111-1111-1111-1111-111111111111: Name   ResourceGroup      Location    NumSubnets   Prefixes
    11111111-1111-1111-1111-111111111111: -----  -----------------  ----------  -----------  -----------
    11111111-1111-1111-1111-111111111111: vnet1  centralus-network  centralus   1            10.0.5.0/24
    11111111-1111-1111-1111-111111111111: vnet2  eastus1-network    eastus1     1            10.0.6.0/24
    11111111-1111-1111-1111-111111111111: vnet3  eastus2-network    eastus2     1            10.0.7.0/24

    $ ls -l /tmp/azure
    -rw-r--r--  1 me  wheel  122 Jan 30 11:13 00000000-0000-0000-0000-000000000000.stdout
    -rw-r--r--  1 me  wheel  180 Jan 30 11:13 11111111-1111-1111-1111-111111111111.stdout

Annotations are not added to the output sent to the files. The files contain the
raw output that came direct from the Azure CLI invocation:

    $ cat /tmp/azure/00000000-0000-0000-0000-000000000000.stdout
    Name   ResourceGroup      Location    NumSubnets   Prefixes
    -----  -----------------  ----------  -----------  -----------
    vnet1  centralus-network  centralus   1            10.0.0.0/24
    vnet2  eastus2-network    eastus2     1            10.0.1.0/24

### Note about Option Names

In most cases, azurerun command plug-ins do not prefix their option names with
`--azurerun-` because the command options must come after the command on the
command line, so there is a clear distinction between azurerun options and
command options:

    $ azurerun --account 00000000-0000-0000-0000-000000000000 command --flag --option value
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                    |                            |              |
                             azurerun options                 command    command options

As a result, there is no namespace collision with core azurerun options and
command options. However, in the case of this `az` command, the two option names
are prefixed with `--azurerun-` because they are specified alongside Azure CLI
options and arguments. This is to avoid naming collisions with Azure CLI
options:

    $ azurerun --account 00000000-0000-0000-0000-000000000000 az network vnet list --azurerun-annotate table
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                    |                         |                       |
                             azurerun options              command     Azure CLI args & Plug-in options
"""

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from awsrun.config import StrMatch
from awsrun.runner import Command

LOG = logging.getLogger(__name__)


class CLICommand(Command):
    """Execute Azure CLI commands concurrently."""

    @classmethod
    def from_cli(cls, parser, argv, cfg):
        """Parse command line arguments provided to this command."""

        # Note: normally one would not prefix an azurerun command's arguments
        # with '--azurerun-', but this is a special exception because there
        # could be valid az CLI args interspersed among the azurerun command
        # flags. To avoid namespace collisions, the az command args are
        # prefixed.
        parser.add_argument(
            "--azurerun-output-dir",
            metavar="DIR",
            default=cfg("azurerun_output_dir"),
            help="output directory to write results to separate files",
        )

        parser.add_argument(
            "--azurerun-annotate",
            choices=["yaml", "json", "tsv", "table"],
            default=cfg("azurerun_annotate", type=StrMatch("^(yaml|json|tsv|table)$")),
            help="annotate each result with subscription",
        )

        # Let's gobble up any --output flags passed to the az CLI command. The
        # output flag is captured so we can make sure user does not try to
        # specify a different output if they selected --azurerun-annotate. The
        # types need to match.
        parser.add_argument("--output", help=argparse.SUPPRESS)

        # We parse the known args and then collect the rest as those will be
        # passed to the az CLI command later.
        args, remaining_args = parser.parse_known_args(argv)

        if (
            args.azurerun_annotate
            and args.output
            and args.azurerun_annotate != args.output
        ):
            parser.error(
                "When specifying --azurerun-annotate, you do not need the --output flag"
            )

        return cls(
            remaining_args,
            output=args.output,
            output_dir=args.azurerun_output_dir,
            annotate=args.azurerun_annotate,
        )

    def __init__(self, azurecli_args, output=None, output_dir=None, annotate=False):
        super().__init__()
        self.azurecli_args = azurecli_args
        self.output = output
        self.annotate = annotate
        self.output_dir = Path(output_dir) if output_dir else None

        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        path = shutil.which("az")
        if path:
            self.azurecli_path = path
        else:
            raise FileNotFoundError(
                "error: Have you installed the Azure CLI? https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
            )

    def execute(self, session, acct):
        """Invoke an Azure CLI command for an account."""

        # We need to assemble a valid Azure CLI command line that can be
        # executed by the operating system. The instance variable azureCLI_args
        # contains all arguments that follow 'az': azurerun az ... We will
        # provide --output if the user has asked us to annotate an output type.
        # This ensures we override any user settings that the Azure CLI tool may
        # pick up from ~/.azure directory.
        cmd = [self.azurecli_path]
        cmd += self.azurecli_args
        cmd += ["--subscription", str(acct)]
        if self.annotate:
            cmd += ["--output", self.annotate]
        elif self.output:
            cmd += ["--output", self.output]
        LOG.info("%s: Azure CLI command: %s", acct, cmd)

        # Although the execute method receives a valid credential in the
        # `session` argument, I've not found a way to pass that to the az CLI
        # command. It doesn't matter though as az CLI users will simply use `az
        # login` before running this azurerun wrapper.

        # We call run() and capture stdout and stderr from the command's output.
        # Note: all the output is stored in memory, and then printed in
        # collect_results. This means that if you run an az CLI command that
        # generates huge amounts of data, it'll all be stored in memory. Why
        # don't we stream tho output from a pipe? We could use Popen directly,
        # but if we returned from execute() before reading all of the results,
        # then the worker will start another account, so in essence, all of the
        # accounts will be "executed" immediately resulting in potentially many
        # many Azure CLI command processes running waiting for us to read the
        # output.

        result = subprocess.run(
            cmd,
            check=False,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Lastly, we return the ProcessCompleted object from the run() method.
        # Recall, an azurerun command can return anything if you provide your
        # own collect_results method.
        return result

    def collect_results(self, acct, get_result):
        """Print the results to the console and files if specified."""

        def annotate_lines(text, delimiter=": ", file=sys.stdout, separator=False):
            for line in filter(None, text.split("\n")):
                print(f"{acct}{delimiter}{line}", file=file, flush=True)
            if separator and not text == "\n":
                print()

        def annotate_json(text):
            try:
                d = {
                    "Subscription": str(acct),
                    "Results": json.loads(text),
                }
                json.dump(d, sys.stdout, indent=4)
                print()
            except json.decoder.JSONDecodeError:
                annotate_lines(
                    "Result of Azure CLI command is not valid JSON", file=sys.stderr
                )

        def annotate_yaml(text):
            try:
                d = {
                    "Subscription": str(acct),
                    "Results": yaml.safe_load(text),
                }
                yaml.safe_dump(d, sys.stdout, indent=4)
                print("...")  # end of yaml document separator
            except yaml.representer.RepresenterError:
                annotate_lines(
                    "Result of Azure CLI command is not valid JSON", file=sys.stderr
                )

        try:
            # Let's get the return value from the execute method, which is the
            # ProcessCompleted object from the subprocess.run() method above ...
            result = get_result()

        except Exception as e:  # pylint: disable=broad-except
            # ... unless there was an exception in which case it is raised by
            # the call to get_result and we handle it here.
            LOG.info("%s: error: %s", acct, e, exc_info=True)
            annotate_lines(f"error: {e}", file=sys.stderr)
            return

        # Print stderr from Azure CLI always annotating the lines
        annotate_lines(result.stderr, file=sys.stderr)

        # Print stdout from Azure CLI annotating when appropriate
        if not self.annotate:
            if result.stdout not in ["", "\n"]:  # skip blank output
                print(
                    result.stdout,
                    end="\n" if self.output == "table" else "",
                    flush=True,
                )
        elif self.annotate == "json":
            annotate_json(result.stdout)
        elif self.annotate == "yaml":
            annotate_yaml(result.stdout)
        elif self.annotate == "table":
            annotate_lines(result.stdout, separator=True)
        elif self.annotate == "tsv":
            annotate_lines(result.stdout, delimiter="\t")

        # Save stdout and stderr from Azure CLI to disk if requested
        if self.output_dir:
            # Recall, the acct object passed to execute() can be anything. The
            # str() method should provide us a unique means of identifying the
            # account, but we need to escape any slashes if we use this as part
            # of a filename so pathlib doesn't interpret as directories.
            escaped = re.sub(r"[\\/]", "_", str(acct))
            name = self.output_dir / f"{escaped}"

            def save(suffix, text):
                with name.with_suffix(suffix).open("w") as out:
                    out.write(text)

            save(".stdout.log", result.stdout)
            if result.stderr:
                save(".stderr.log", result.stderr)
