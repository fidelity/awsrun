#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Display the Route53 hosted zones in an account.

## Overview

The list_hosted_zones command displays private and public hosted zones
configured in an account.  For example:

    $ awsrun --account 100200300400 list_hosted_zones --region us-east-1
    100200300400/us-east-1: zone=example.com. #rr=3 private=False
    $

## Reference

### Synopsis

    $ awsrun [options] list_hosted_zones [command options]

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      list_hosted_zones:
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
    """Display the Route53 hosted zones in an account."""

    def regional_execute(self, session, acct, region):
        out = io.StringIO()

        route53 = session.client("route53", region_name=region)
        paginator = route53.get_paginator("list_hosted_zones")

        for zone_page in paginator.paginate():
            for zone in zone_page["HostedZones"]:
                name = zone["Name"]
                rrcount = zone["ResourceRecordSetCount"]
                isprivate = zone["Config"]["PrivateZone"]
                print(
                    f"{acct}/{region}: zone={name} #rr={rrcount} private={isprivate}",
                    file=out,
                )

        return out.getvalue()
