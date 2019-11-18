#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Display the Internet Gateways (IGWs) attached to an account.

## Overview

The list_igws command displays all of the IGWs within an account as well as any
attachments to VPCs it may have:

    $ awsrun --account 100200300400 list_igws --region us-east-1
    100200300400/us-east-1: id=igw-abc123 attachments=1 vpcs=vpc-0aa3212b
    100200300400/us-east-1: id=igw-123abc attachments=1 vpcs=vpc-0bb1231c
    $

If an account has no IGWs, no output is produced for that account.

## Reference

### Synopsis

    $ awsrun [options] list_igws [command options]

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      list_igws:
        region:
          - STRING

### Command Options

Some options can be overridden on the awsrun CLI via command line flags. In
those cases, the CLI flags are specified next to the option name below:

`region`, `--region`
:  Run the AWS CLI command in the specified regions. When specifying multiple
values on the command line, use multiple flags for each value.
"""

import io

from awsrun.runner import RegionalCommand


class CLICommand(RegionalCommand):
    """Display IGWs attached in accounts."""

    def regional_execute(self, session, acct, region):
        out = io.StringIO()
        ec2 = session.resource("ec2", region_name=region)

        for igw in ec2.internet_gateways.all():
            igw_id = igw.internet_gateway_id
            attachments = [
                a["VpcId"] for a in igw.attachments if a["State"] == "available"
            ]

            print(
                f"{acct}/{region}: id={igw_id} attachments={len(attachments)}",
                end="",
                file=out,
            )
            if attachments:
                print(f' vpcs={", ".join(attachments)}', end="", file=out)

            print(file=out)

        return out.getvalue()
