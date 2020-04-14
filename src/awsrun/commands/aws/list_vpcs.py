#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Display the Virtual Private Clouds (VPCs) configured in an account.

## Overview

The list_vpcs command displays each VPC configured as well as the list of
CIDR blocks associated with it. For example:

    $ awsrun --account 100200300400 list_vpcs --region us-east-1
    100200300400/us-east-1: id=vpc-aabbccdd cidrs=10.0.1.0/24, 10.0.2.0/26
    100200300400/us-east-1: id=vpc-bbccddaa cidrs=10.0.5.0/22
    $

## Reference

### Synopsis

    $ awsrun [options] list_vpcs [command options]

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      list_vpcs:
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
    """Display VPCs configured in accounts."""

    def regional_execute(self, session, acct, region):
        out = io.StringIO()
        ec2 = session.resource("ec2", region_name=region)

        for vpc in ec2.vpcs.all():
            cidrs = ", ".join(c["CidrBlock"] for c in vpc.cidr_block_association_set)
            print(
                f"{acct}/{region}: id={vpc.id} owner={vpc.owner_id} cidrs={cidrs}",
                file=out,
            )

        return out.getvalue()
