#
# Copyright 2021 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Display the route tables configured in a subscription.

## Overview

The list_udrs command displays all route tables defined in a subscription with
one row per route entry.

    $ azurerun --account 00000000-0000-0000-0000-000000000000 list_udrs
    00000000-0000-0000-0000-000000000000/my-route-table: bgp=N assocs=1 route=0.0.0.0/0 next_hop=Internet
    00000000-0000-0000-0000-000000000000/my-route-table: bgp=N assocs=1 route=10.10.10.10/28 next_hop=VirtualAppliance 10.20.20.20
    ...
    $

Each row contains the route table name, whether or not BGP routes are propagated
to the route table, the number of subnets the route table is associated, the
route prefix, and the next hop. If the next hop is a virtual appliance, the IP
of the appliance is provided as well.
"""

import io

from azure.mgmt.network import NetworkManagementClient

from awsrun.runner import Command


class CLICommand(Command):
    """Display UDRs configured in subscriptions."""

    def execute(self, session, acct):
        out = io.StringIO()
        nmc = NetworkManagementClient(session, acct)

        for rt in nmc.route_tables.list_all():
            bgp = "N" if rt.disable_bgp_route_propagation else "Y"

            # Azure API doesn't seem to believe in 0 length lists, sigh.
            assocs = 0 if rt.subnets is None else len(rt.subnets)

            for r in rt.routes:
                # Azure API sometimes returns None and sometimes an "", sigh.
                next_hop = r.next_hop_ip_address or ""
                print(
                    f"{acct}/{rt.name}: bgp={bgp} assocs={assocs} route={r.address_prefix} next_hop={r.next_hop_type} {next_hop}",
                    file=out,
                )

        return out.getvalue()
