#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Display the Public IPs in an account.

## Overview

The list_public_ips command displays each public IP in a VPC. This will include
both elastic IPs owned by an account and public IPs owned by Amazon
(non-elastic):

    $ awsrun -r us-east-1 -a 100200300400 list_public_ips
    100200300400/us-east-1: id=vpc-aabbccdd owner=100200300400: 18.xx.xx.xx, 18.xx.xx.xx
    100200300400/us-east-1: id=vpc-bbccddaa owner=100200300400: 34.xx.xx.xx, 54.xx.xx.xx

## Reference

### Synopsis

    $ awsrun [options] list_public_ips [command options]

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      list_public_ips:
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
from collections import defaultdict

from awsrun.runner import RegionalCommand


class CLICommand(RegionalCommand):
    """Display the public IPs in an account."""

    def regional_execute(self, session, acct, region):
        out = io.StringIO()
        ec2 = session.resource("ec2", region_name=region)

        public_ips = defaultdict(list)
        for vpc in ec2.vpcs.all():
            for ni in vpc.network_interfaces.all():
                # I've opened a bug report for boto3 as the following lines
                # should, in my opinion, find all public IPs. For some reason
                # the association reference is None in some cases when the
                # association_attribute contains an association:
                # https://github.com/boto/boto3/issues/2180
                #
                # if ni.association:
                #     public_ips[vpc.id].append(ni.association.public_ip)

                if ni.association_attribute:
                    ip = ni.association_attribute.get("PublicIp")
                    if ip:
                        public_ips[(vpc.id, vpc.owner_id)].append(ip)

        # We include the owner id in the output as sometimes a VPC has been
        # shared, so the owner is not necessarily the same as the account we
        # are processing.
        for (vpc_id, owner_id), ips in public_ips.items():
            print(
                f'{acct}/{region}: id={vpc_id} owner={owner_id} ips={", ".join(ips)}',
                file=out,
            )

        return out.getvalue()
