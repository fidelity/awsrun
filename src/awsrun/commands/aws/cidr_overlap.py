#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Display overlapping CIDR blocks between VPCs.

## Overview

The cidr_overlap command displays the overlapping CIDR blocks across VPCs.
An overlapping CIDR block is one that is contained partially or wholly within
another.

    $ awsrun --account 100200300400 --account 200300400100 cidr_overlap --region us-east-1
    2 accounts selected:

    100200300400, 200300400100

    Proceed (y/n)? y
    Found CIDR 100200300400/us-east-1/vpc-abc/10.10.180.0/24
    Found CIDR 200300400100/us-east-1/vpc-def/10.10.180.0/24
    OVERLAP! 100200300400/us-east-1/vpc-abc/10.10.180.0/24 <<<>>> 200300400100/us-east-1/vpc-def/10.10.180.0/24

## Reference

### Synopsis

    $ awsrun [options] cidr_overlap [command options]

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      cidr_overlap:
        region:
          - STRING
        exclude_block:
          - STRING

### Command Options

Some options can be overridden on the awsrun CLI via command line flags. In
those cases, the CLI flags are specified next to the option name below:

`region`, `--region`
:  Run the AWS CLI command in the specified regions. When specifying multiple
values on the command line, use multiple flags for each value.

`exclude_block`, `--exclude-block`
:  Exclude the CIDR blocks from consideration. When specifying more than one
block via the command line flag, use a `--exclude-block` flag for each block.
"""

from ipaddress import ip_network

from awsrun.config import IPNet, List
from awsrun.runner import RegionalCommand


class _CIDR:
    def __init__(self, acct, region, vpc, block):
        self.acct = acct
        self.region = region
        self.vpc = vpc
        self.block = block

    def __str__(self):
        return f"{self.acct}/{self.region}/{self.vpc}/{self.block}"

    def __lt__(self, other):
        return self.block < other.block

    def __eq__(self, other):
        return self.block == other.block

    def overlaps(self, other):
        """Return `True` if `other` overlaps with this CIDR."""
        # If the VPCs are the same, then there is no overlap. This can happen
        # when a VPC is shared between accounts. Each account will have the
        # same CDIR block, so we make sure they aren't the same VPC.
        if self.vpc == other.vpc:
            return False
        return self.block.overlaps(other.block)


class CLICommand(RegionalCommand):
    """Display VPCs configured in accounts."""

    @classmethod
    def regional_from_cli(cls, parser, argv, cfg):
        parser.add_argument(
            "--exclude-block",
            action="append",
            dest="exclude_blocks",
            default=cfg("exclude_block", type=List(IPNet), default=[]),
            help="exclude CIDR blocks from check",
        )

        args = parser.parse_args(argv)
        return cls(**vars(args))

    def __init__(self, regions, exclude_blocks):
        super().__init__(regions)
        self.exclude_blocks = [ip_network(b) for b in exclude_blocks]
        self.cidrs = []

    def regional_execute(self, session, acct, region):
        ec2 = session.resource("ec2", region_name=region)
        return [
            (c["CidrBlock"], vpc.id)
            for vpc in ec2.vpcs.all()
            for c in vpc.cidr_block_association_set
        ]

    def regional_collect_results(self, acct, region, get_result):
        for block, vpc_id in get_result():
            block = ip_network(block)
            if any(block.overlaps(e) for e in self.exclude_blocks):
                continue
            cidr = _CIDR(acct, region, vpc_id, block)
            self.cidrs.append(cidr)
            print(f"Found CIDR {cidr}", flush=True)

    def post_hook(self):
        overlap = []

        for i in range(0, len(self.cidrs)):  # pylint: disable=consider-using-enumerate
            c1 = self.cidrs[i]
            for j in range(i + 1, len(self.cidrs)):
                c2 = self.cidrs[j]
                if c1.overlaps(c2):
                    overlap.append(sorted((c1, c2)))

        for c1, c2 in sorted(overlap, key=lambda x: x[0]):
            print(f"OVERLAP! {c1} <<<>>> {c2}")
