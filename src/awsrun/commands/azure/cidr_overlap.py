#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Display overlapping CIDR blocks between VNETs.

## Overview

The cidr_overlap command displays the overlapping CIDR blocks across VNETs.
An overlapping CIDR block is one that is contained partially or wholly within
another.

    $ azurerun --account 00000000-0000-0000-0000-000000000000 --account 11111111-1111-1111-1111-111111111111 cidr_overlap
    2 accounts selected:

    00000000-0000-0000-0000-000000000000, 11111111-1111-1111-1111-111111111111

    Proceed (y/n)? y
    Found CIDR 00000000-0000-0000-0000-000000000000/eastus2/10.10.180.0/24
    Found CIDR 11111111-1111-1111-1111-111111111111/eastus2/10.10.180.0/24
    OVERLAP! 00000000-0000-0000-0000-000000000000/eastus2/10.10.180.0/24 <<<>>> 11111111-1111-1111-1111-111111111111/eastus2/10.10.180.0/24

## Reference

### Synopsis

    $ azurerun [options] cidr_overlap [command options]

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      cidr_overlap:
        exclude_block:
          - STRING

### Command Options

Some options can be overridden on the azurerun CLI via command line flags. In
those cases, the CLI flags are specified next to the option name below:

`exclude_block`, `--exclude-block`
:  Exclude the CIDR blocks from consideration. When specifying more than one
block via the command line flag, use a `--exclude-block` flag for each block.
"""

from ipaddress import ip_network

from azure.mgmt.network import NetworkManagementClient

from awsrun.config import IPNet, List
from awsrun.runner import Command


class _CIDR:
    def __init__(self, subscription, location, vnet, block):
        self.subscription = subscription
        self.location = location
        self.vnet = vnet
        self.block = block

    def __str__(self):
        return f"{self.subscription}/{self.location}/{self.block}"

    def __lt__(self, other):
        return self.block < other.block

    def __eq__(self, other):
        return self.block == other.block

    def overlaps(self, other):
        """Return `True` if `other` overlaps with this CIDR."""
        # If the VNETs are the same, then there is no overlap. This can happen
        # when a VNET is shared between accounts. Each account will have the
        # same CDIR block, so we make sure they aren't the same VNET.
        if self.vnet == other.vnet:
            return False
        return self.block.overlaps(other.block)


class CLICommand(Command):
    """Display VNETs configured in accounts."""

    @classmethod
    def from_cli(cls, parser, argv, cfg):
        parser.add_argument(
            "--exclude-block",
            action="append",
            dest="exclude_blocks",
            default=cfg("exclude_block", type=List(IPNet), default=[]),
            help="exclude CIDR blocks from check",
        )

        args = parser.parse_args(argv)
        return cls(**vars(args))

    def __init__(self, exclude_blocks):
        super().__init__()
        self.exclude_blocks = [ip_network(b) for b in exclude_blocks]
        self.cidrs = []

    def execute(self, session, acct):
        nmc = NetworkManagementClient(session, acct)
        return [
            (c, vnet.location, vnet.id)
            for vnet in nmc.virtual_networks.list_all()
            for c in vnet.address_space.address_prefixes
        ]

    def collect_results(self, acct, get_result):
        for block, location, vnet_id in get_result():
            block = ip_network(block)
            if any(block.overlaps(e) for e in self.exclude_blocks):
                continue
            cidr = _CIDR(acct, location, vnet_id, block)
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
