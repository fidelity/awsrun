#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Display the Virtual Networks (VNETs) configured in a subscription.

## Overview

The list_vnets command displays each VNET configured as well as the list of
CIDR blocks associated with it. For example:

    $ azurerun --account 00000000-0000-0000-0000-000000000000 list_vnets
    00000000-0000-0000-0000-000000000000/eastus2: vnet=my-prd-vnet cidrs=10.0.1.0/24, 10.0.2.0/26
    $

## Reference

### Synopsis

    $ azurerun [options] list_vnets [command options]
"""

import io

from azure.mgmt.network import NetworkManagementClient

from awsrun.runner import Command


class CLICommand(Command):
    """Display VNETs configured in accounts."""

    def execute(self, session, acct):
        out = io.StringIO()
        nmc = NetworkManagementClient(session, acct)

        for vnet in nmc.virtual_networks.list_all():
            cidrs = ", ".join(vnet.address_space.address_prefixes)
            print(f"{acct}/{vnet.location}: vnet={vnet.name} cidrs={cidrs}", file=out)

        return out.getvalue()
