#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Display the VPC attributes associated with a VPC.

## Overview

The vpc_attribute command displays the VPC attributes and values for each VPC.
At the time of this writing, there are only two attributes that AWS defines in
a VPC: enableDnsSupport and enableDnsHostnames. By default, the vpc_attribute
command will show the value for both of these attributes.  For example:

    $ awsrun --account 100200300400 vpc_attribute --region us-east-1
    100200300400/us-east-1: vpc=vpc-aabbccdd enableDnsSupport=True enableDnsHostnames=False

To limit the output to a specific attribute, provide the name of the attribute
as a positional argument to the vpc_attribute command.  For example, to show
only the status of enableDnsSupport:

    $ awsrun --account 100200300400 vpc_attribute --region us-east-1 enableDnsSupport
    100200300400/us-east-1: vpc=vpc-aabbccdd enableDnsSupport=True

## Reference

### Synopsis

    $ awsrun [options] list_vpc_attribute [command options] ATTR ...

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      list_public_ips:
        attribute:
          - ("enableDnsSupport" | "enableDnsHostnames")
        region:
          - STRING

### Command Options

Some options can be overridden on the awsrun CLI via command line flags. In
those cases, the CLI flags are specified next to the option name below:

`attribute`, `<positional_args>`
:  Limit the output to the specified VPC attributes. When specifying on the
command line, use one or more positional arguments to provide the values.

`region`, `--region`
:  Run the AWS CLI command in the specified regions. When specifying multiple
values on the command line, use multiple flags for each value.
"""

import io

from awsrun.config import List, Str
from awsrun.runner import RegionalCommand


class CLICommand(RegionalCommand):
    """Display VPC attributes such as DNS settings for accounts."""

    @classmethod
    def regional_from_cli(cls, parser, argv, cfg):
        parser.add_argument(
            "attribute",
            nargs="*",
            help="vpc attributes to query",
            default=cfg(
                "attribute",
                type=List(Str),
                default=["enableDnsSupport", "enableDnsHostnames"],
            ),
        )

        args = parser.parse_args(argv)
        return cls(**vars(args))

    def __init__(self, regions, attribute):
        super().__init__(regions)
        self.attributes = attribute

    def regional_execute(self, session, acct, region):
        out = io.StringIO()
        ec2 = session.resource("ec2", region_name=region)

        for vpc in ec2.vpcs.all():
            print(
                f"{acct}/{region}: id={vpc.vpc_id} owner={vpc.owner_id} ",
                end="",
                file=out,
            )
            for attr in self.attributes:
                flag = _vpc_attribute(attr, vpc)
                print(f"{attr}={flag} ", end="", file=out)
            print(file=out)

        return out.getvalue()


def _vpc_attribute(attr, vpc):
    # Oddly, the AWS API for describe_vpc_attribute expects an attribute that
    # starts with lowercase, but the response object contains the attribute key
    # capitalized, so that's why this is not as simple as it should be.
    result = vpc.describe_attribute(Attribute=attr)
    attr = attr[0].upper() + attr[1:]  # Capitalize first letter
    if attr not in result:
        return None
    return result[attr]["Value"]
