#
# Copyright 2019 FMR LLC <opensource@fmr.com>
#
# SPDX-License-Identifier: MIT
#
"""Display the status of Direct Connects and VIFs.

## Overview

The `dx_status` command displays a list of Direct Connects found as well as a
summary of each including a sparkline showing the past 1 hour 95th percentile.

    $ awsrun --account 100200300400 dx_status --region us-west-2
    100200300400/us-west-2: dxcon-xxxxxx00 DC1 to US-WEST         AVAILABLE  1 Gbps  234 VIFs (2 down)
    100200300400/us-west-2: ▂▂▂▃▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▁▂▁▂▂ ConnectionBpsIngress
    100200300400/us-west-2: ▁▁▁▂▂▁▂▂▁▂▁▁▁▁▁▁▁▂▁▁▁▁▁▁▁▂▂▁▁▁▁▂▂▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ConnectionBpsEgress
    100200300400/us-west-2: ▁▁▁▁▁▁▁█▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁█▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁██▁▁█▁▁▁▁▁▁▁ ConnectionState

    100200300400/us-west-2: dxcon-xxxxxx01 DC1 to US-WEST         AVAILABLE  1 Gbps  143 VIFs (6 down)
    100200300400/us-west-2: ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ConnectionBpsIngress
    100200300400/us-west-2: ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ConnectionBpsEgress
    100200300400/us-west-2: ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ConnectionState
    ...

For a larger visualization with more detail, use `--height` options to specify
the number of lines to use. For example:

    $ awsrun --account 100200300400 dx_status --region us-west-2 --height 5
    100200300400/us-west-2: dxcon-xxxxxx00 DC1 to US-WEST         AVAILABLE  1 Gbps  234 VIFs (2 down)
    1,000,000,000 ┼
    800,000,000   ┤
    600,000,000   ┤            ╭╮
    400,000,000   ┤╭╮  ╭──╮  ╭╮│╰╮╭╮╭╮╭─────╮╭─╮╭╮  ╭─╮╭╮ ╭──╮╭─╮  ╭╮       ╭╮
    200,000,000   ┼╯╰──╯  ╰──╯╰╯ ╰╯╰╯╰╯     ╰╯ ╰╯╰──╯ ╰╯╰─╯  ╰╯ ╰──╯╰───────╯│
              0   ┤                                                          ╰  ConnectionBpsIngress
    1,000,000,000 ┼
    800,000,000   ┤
    600,000,000   ┤
    400,000,000   ┤                      ╭╮
    200,000,000   ┤╭──────╮╭─────────────╯╰╮╭──────╮╭───────────╮╭───╮     ╭─╮
              0   ┼╯      ╰╯               ╰╯      ╰╯           ╰╯   ╰─────╯ ╰  ConnectionBpsEgress
    ...

To disable the visualization altogether, specify a `0` height:

    $ awsrun --account 100200300400 dx_status --region us-west-2 --height 0
    100200300400/us-west-2: dxcon-xxxxxx00 DC1 to US-WEST         AVAILABLE  1 Gbps  234 VIFs (2 down)
    100200300400/us-west-2: dxcon-xxxxxx01 DC1 to US-WEST         AVAILABLE  1 Gbps  143 VIFs (6 down)
    100200300400/us-west-2: dxcon-xxxxxx02 DC2 to US-WEST         AVAILABLE  1 Gbps  233 VIFs (1 down)
    100200300400/us-west-2: dxcon-xxxxxx03 DC2 to US-WEST         AVAILABLE  1 Gbps  143 VIFs (2 down)

Use the `--hours` or `--days` flags to specify the range for the graphs. In
addition, by default, the 95th percentile is used as an aggregation, but the
`--stat` flag can specify either "Average", "Mimimum", "Maximum", "p90",
"p95", "p99", "p99.9". For example, to view the 99th percentile over the past
week:

    $ awsrun --account 100200300400 dx_status --region us-west-2 --days 7 --stat p99.9
    100200300400/us-west-2: dxcon-xxxxxx00 DC1 to US-WEST         AVAILABLE  1 Gbps  234 VIFs (2 down)
    100200300400/us-west-2: ▂▃▃▃▂▃▄▃▃▂▃▄▃▅▃▃▄▃▃▃▃▃▃▃▄▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▄▃▃▃▃▄▃▃▃▃▂▂▃▂▂▂▂▃▃▂ ConnectionBpsIngress
    100200300400/us-west-2: ▂▂▂▂▂▂▂▂▂▂▃▃▂▂▂▂▂▂▂▂▂▂▂▃▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▃▂▂▂▂▂▂▂▂▂▂▁▂▂▂▂▂▂▂▁ ConnectionBpsEgress
    100200300400/us-west-2: ▁▁▁▁▁▁▁█▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁█▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁██▁▁█▁▁▁▁▁▁▁ ConnectionState

    100200300400/us-west-2: dxcon-xxxxxx01 DC1 to US-WEST         AVAILABLE  1 Gbps  143 VIFs (6 down)
    100200300400/us-west-2: ▄▄▄▄▄▄▄▄▄▄▄▃▄▁▁▁▁▁▁▄▃▁▁▁▁▁▁▄▄▄▄▄▄▄▄▄▃▂▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ConnectionBpsIngress
    100200300400/us-west-2: ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ConnectionBpsEgress
    100200300400/us-west-2: ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ConnectionState

    100200300400/us-west-2: dxcon-xxxxxx02 DC2 to US-WEST         AVAILABLE  1 Gbps  233 VIFs (1 down)
    100200300400/us-west-2: ▂▄▃▅▇▃▃▃▂▆▄▄▃▆▆▃▃▅▄▃▃▃▂▂▂▂▅▄▄▃▂▃▄▂▅▃▃▂▂▂▃▂▂▂▃▂▃▂▃▂▃▂▂▂▂▂▂▃▂▂ ConnectionBpsIngress
    100200300400/us-west-2: ▁▂▂▂▂▁▁▁▁▂▂▂▂▂▃▃▂▃▃▂▂▂▁▁▁▁▁▁▂▁▁▁▁▁▁▂▂▂▂▁▁▁▁▂▂▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ConnectionBpsEgress
    100200300400/us-west-2: ▁▁▁▁▁▁▁▁▁▁▁█▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁█▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ConnectionState

    100200300400/us-west-2: dxcon-xxxxxx03 DC2 to US-WEST         AVAILABLE  1 Gbps  143 VIFs (2 down)
    100200300400/us-west-2: ▃▆▄▃▃▃▃▃▃▃▃▃▅▂▁▂▁▁▁▄▃▂▂▂▃▁▁▃▄▃▅▄▃▃▃▃▃▂▂▁▂▁▁▁▁▁▁▁▁▂▁▁▁▂▂▁▁▁▁▁ ConnectionBpsIngress
    100200300400/us-west-2: ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ConnectionBpsEgress
    100200300400/us-west-2: ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁█▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ConnectionState

By default, the scale of the y-axis is fixed to the bandwidth of the circuit
regardless of utilization, so it is easy to distinguish a lightly utilized
circuit from a heavily utilized circuit. To use a variable scale on the
y-axis, use the `--auto-scale` option:

    $ awsrun --account 100200300400 dx_status --region us-west-2 --height 5 --auto-scale
    100200300400/us-west-2: dxcon-xxxxxx00 DC1 to US-WEST         AVAILABLE  1 Gbps  234 VIFs (2 down)
    387,713,776  ┼                           ╭╮               ╭╮
    310,171,021  ┤    ╭╮     ╭╮   ╭────╮   ╭╮││       ╭─╮ ╭─╮╭╯│
    232,628,266  ┼───╮│╰─────╯╰╮╭─╯    ╰───╯╰╯╰───────╯ ╰╮│ ╰╯ ╰───╮╭────────
    155,085,510  ┤   ╰╯        ╰╯                        ╰╯        ╰╯
    77,542,755   ┤
    0            ┤                                                             ConnectionBpsIngress
    241,639,270  ┼           ╭╮
    193,311,416  ┤       ╭───╯│╭───────╮ ╭╮  ╭╮           ╭─╮ ╭╮
    144,983,562  ┤╭╮╭─╮╭╮│    ╰╯       ╰─╯╰╮╭╯│╭────╮╭────╯ ╰─╯╰─────╮ ╭────╮
    96,655,708   ┼╯╰╯ ╰╯╰╯                 ╰╯ ╰╯    ╰╯               ╰─╯    ╰
    48,327,854   ┤
    0            ┤                                                             ConnectionBpsEgress


## Reference

### Synopsis

    $ awsrun [options] dx_status [command options]

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      dx_status:
        verbose: BOOLEAN
        stat: ("Average" | "Minimum" | "Maximum" | "p90" | "p95" | "p99" | "p99.9")
        height: INT
        auto_scale: BOOLEAN
        hours: INT
        days: INT
        region:
          - STRING

### Command Options
Some options can be overridden on the awsrun CLI via command line flags. In
those cases, the CLI flags are specified next to the option name below:

`verbose`, `--verbose`
: Include a line of output for each VIF associated with the Direct Connect,
which contains the VIF ID, VLAN, owning account, and the Direct Connect it is
associated with. The default value is False.

`stat`, `--stat STRING`
: Specifies the aggregation function for the bandwidth utilization sparklines
and charts. By default, the 95th percentile is used, but this can be one of the
values specified in the configuration section above.

`height`, `--height INT`
: Controls how Direct Connect utilization is shown. A value of `0` will prevent
any utilization information from being shown (and is faster as it avoids making
CloudWatch calls). A value of `1`, the default, will display utilization as a
sparkline that consumes one line of output. To use an ASCII-based chart instead,
specify a value greater than `1` to indicate how many rows in height the charts
should occupy.

`auto_scale`, `--auto-scale`
: By default, the maximum y-axis value for the bandwidth utilization sparklines
and charts is the total bandwidth of the Direct Connect. This makes it easy to
compare multiple circuits as the graphs are all based on the percentage of the
bandwidth being used. Alternatively, specifying this option will result in a
y-axis that is set to the maximum value for each sparkline/chart. While useful
to get more precise graphs, it makes comparing mulitple circuits more difficult.

`hours`, `--hours INT`
: Specifies how many hours of utilization data to retrieve from CloudWatch. The
default value is 1-hour. This option is mutually exclusive with the `days`
option discussed next.

`days`, `--days INT`
: Specifies how many days of utilization days to retrieve from CloudWatch. This
option is mutually exclusive with the `hours` option. There is no default value
as `hours` is used instead.

`region`, `--region REGION`
: Run the command in the specified regions. When specifying multiple values on
the command line, use multiple flags for each value.


"""
import io
import re
import sys
from collections import defaultdict

from awsrun.cloudwatch import CWMetrics
from awsrun.config import Bool, Choice, Type
from awsrun.runner import RegionalCommand

try:
    import colorama
    from asciichartpy import plot
    from colorama import Fore, Style
    from sparkline import sparkify

except ImportError:
    sys.exit(
        """
The 'dx_status' command requires dependencies not installed by default with
awsrun. Please install them with the following command:

    pip install awsrun[dx-status]
"""
    )


class CLICommand(RegionalCommand):
    """Display the status of Direct Connects and VIFs."""

    @classmethod
    def regional_from_cli(cls, parser, argv, cfg):
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="include each VIF and its status in output",
            default=cfg("verbose", type=Bool),
        )

        stats = ["Average", "Minimum", "Maximum", "p90", "p95", "p99", "p99.9"]
        parser.add_argument(
            "--stat",
            metavar="STAT",
            choices=stats,
            help="aggregate on STAT: " + ", ".join(stats),
            default=cfg("stat", type=Choice(*stats), default="p95"),
        )

        parser.add_argument(
            "--height",
            type=int,
            metavar="LINES",
            help="height of chart in LINES, a sparkline is used if 1, no charts if 0",
            default=cfg("height", type=PosInt, default=1),
        )

        parser.add_argument(
            "--auto-scale",
            action="store_true",
            help="do not use the maximum circuit b/w as height of y-axis",
            default=cfg("auto_scale", type=Bool, default=False),
        )

        timespec = parser.add_mutually_exclusive_group()
        timespec.add_argument(
            "--hours",
            type=int,
            help="retrieve metrics from HOURS ago",
            default=cfg("hours", type=PosInt),
        )
        timespec.add_argument(
            "--days",
            type=int,
            help="retrieve metrics from DAYS ago",
            default=cfg("days", type=PosInt),
        )

        args = parser.parse_args(argv)
        return cls(**vars(args))

    def __init__(self, regions, height, hours, days, stat, auto_scale, verbose):
        super().__init__(regions)

        if hours is None and days is None:
            hours = 1

        self.last = hours * 3600 if hours else days * 3600 * 24
        self.stat = stat
        self.height = height
        self.auto_scale = auto_scale
        self.verbose = verbose

        colorama.init()

    def regional_execute(self, session, acct, region):
        out = io.StringIO()
        prefix = f"{acct}/{region}:"
        cw = session.client("cloudwatch", region_name=region)
        dx = session.client("directconnect", region_name=region)

        # Build a map of connections keyed by the connection ID. This will be
        # used in our code below when we need to look up connection details.
        conn_by_id = {}
        for c in dx.describe_connections()["connections"]:
            conn_by_id[c["connectionId"]] = c

        # If there are no connections, then return with an empty string so
        # nothing is displayed to the user. Remember, the execute method must
        # return a string that the default collector prints to the console.
        if not conn_by_id:
            return ""

        # Build a map of vifs keyed by the connection ID. For each connection,
        # there can zero or more VIFs associated with it, so the values of
        # this dict are lists.
        vifs_by_conn = defaultdict(list)
        for vif in dx.describe_virtual_interfaces()["virtualInterfaces"]:
            c_id = vif["connectionId"]
            vifs_by_conn[c_id].append(vif)

        # Only load the metrics from CloudWatch if a chart is being requested.
        # Recall, the height parameter states how many lines to use for the
        # chart. If the value is zero, the does not want a chart, so no need
        # to load data. We load all data at once, instead of as we loop over
        # each connection, because CloudWatch has much more efficient APIs for
        # bulk data loads.
        metrics = None
        if self.height > 0:
            metrics = self._load_dx_metrics(cw, conn_by_id.keys())

        # With all of the data loaded, let's now iterate over the list of
        # connections sorted by name, and start printing stuff to the screen.
        for c_id, conn in sorted(
            conn_by_id.items(), key=lambda c: c[1]["connectionName"]
        ):
            vifs = vifs_by_conn[c_id]

            if self.verbose:
                for vif in vifs:
                    print(f"{prefix} {_vif2str(vif, conn)}", file=out)

            print(f"{prefix} {_conn2str(conn, vifs)}", file=out)

            if metrics:
                _print_conn_metrics(
                    conn,
                    metrics[c_id],
                    height=self.height,
                    auto_yaxis=self.auto_scale,
                    prefix=prefix,
                    file=out,
                )

        return out.getvalue()

    def _load_dx_metrics(self, cw, connections):
        """Load the dx metrics for connections from CloudWatch.

        The ingress bps, egress bps, and connection state are loaded.

        `cw` is a CloudWatch client and `connections` is a list of Direct
        Connect connection IDs. Returns a nested map with c_id and then
        metric_name as keys. The values are functions, which when invoked,
        will return a generator of (datetime, metric_value) tuples.
        """
        cwm = CWMetrics(cw, last=self.last)

        metrics = defaultdict(dict)
        for c_id in connections:
            dimension = {"ConnectionId": c_id}

            for name in ["ConnectionBpsIngress", "ConnectionBpsEgress"]:
                get_values = cwm.add_metric("AWS/DX", name, dimension, self.stat)
                metrics[c_id][name] = get_values

            # This metric must use Minimum or you'll never see outages
            for name in ["ConnectionState"]:
                get_values = cwm.add_metric("AWS/DX", name, dimension, "Minimum")
                # Due to late binding of closure, we capture in default arg
                metrics[c_id][name] = lambda f=get_values: (
                    (t, invert(v)) for t, v in f()
                )

        cwm.bulk_load()
        return metrics


def invert(n):
    """Return 1 if n is 0, 0 if n is 1, otherwise n."""
    if n == 0:
        return 1
    if n == 1:
        return 0
    return n  # NaN case


def bps(bandwidth):
    """Convert the bandwidth string to an integer in bits per second.

    The supported units include: Gbps, Mbps, Kbps, and bps (all case
    insenstive). If the bandwidth string does not have a numeric component or
    uses an unsuppored unit, a ValueError is raised.
    """
    match = re.match(r"(\d+)\s*(\w+)", bandwidth)
    if not match:
        raise ValueError("bandwidth not in form of 10Mbps")

    bw, units = match.groups()
    bw = int(bw)
    units = units.lower()

    if units == "gbps":
        return bw * 1000000000
    if units == "mbps":
        return bw * 1000000
    if units == "kbps":
        return bw * 1000
    if units == "bps":
        return bw

    raise ValueError("unsupported unit, must be Gbps, Mbps, Kbps, Bps")


def _vif2str(vif, conn):
    c_name = conn["connectionName"]
    v_id = vif["virtualInterfaceId"]
    v_owner = vif["ownerAccount"]
    v_state = vif["virtualInterfaceState"].upper()
    v_vlan = vif["vlan"]

    # A private VIF will be connected to either a VGW or a DXGW, so one of these
    # will be the empty string
    v_gwid = vif["virtualGatewayId"]
    v_dxgwid = vif["directConnectGatewayId"]
    gwid = v_gwid if v_gwid else f"dxgw {v_dxgwid}"

    return f"{v_id} on {gwid} vlan {v_vlan} owned by {v_owner} on {c_name} is {v_state}"


def _conn2str(conn, vifs):
    c_id = conn["connectionId"]
    c_name = conn["connectionName"]
    c_state = conn["connectionState"].upper()
    c_bandwidth = " ".join(re.findall(r"[A-Za-z]+|\d+", conn["bandwidth"]))
    v_down = sum(1 for v in vifs if v["virtualInterfaceState"] == "down")

    return "".join(
        [
            Style.DIM,
            f"{c_id} ",
            Style.RESET_ALL,
            Style.BRIGHT,
            Fore.YELLOW,
            f"{c_name:22.22} ",
            Style.RESET_ALL,
            (Fore.GREEN if c_state == "AVAILABLE" else Fore.RED),
            f"{c_state:10} ",
            Fore.BLUE,
            f"{c_bandwidth:7} ",
            Fore.MAGENTA,
            f"{len(vifs):3} VIFs ",
            (Fore.RED + f"({v_down} down)" if v_down > 0 else ""),
            Fore.RESET,
        ]
    )


def _print_conn_metrics(
    conn, metrics, height=1, prefix="", auto_yaxis=True, file=sys.stdout
):
    colors = [Fore.RED, Fore.CYAN, Fore.CYAN]

    for name, get_values in metrics.items():
        values = [value for timestamp, value in get_values()]

        if name == "ConnectionState":
            max_yaxis = 1
        elif auto_yaxis:
            max_yaxis = None
        else:
            max_yaxis = bps(conn["bandwidth"])

        if height == 1:
            chart = sparkify(values, minimum=0, maximum=max_yaxis)
            print(prefix, end=" ", file=file)

        else:
            opts = {
                "min": 0,
                "height": height,
                "format": "{:14,.0f} ",
            }
            # The asciichartpy module is a bit wonky and not really idiomatic
            # python as they just pass a giant dictionary of options (typical of
            # javascript land). Do not provide a "max" key with a value of
            # None. If use wants auto-scaling, don't provide the key at all.
            if max_yaxis is not None:
                opts["max"] = max_yaxis

            chart = plot(values, opts)
        print(_format_metric(name, chart, color=colors.pop()), file=file)
    print(file=file)


def _format_metric(name, chart, color=Fore.BLACK):
    return f"{color}{chart} {name}{Style.RESET_ALL}"


# Type definition for awsrun.config to validate positive numbers.
class PositiveInt(Type):
    """Type that represents a positive integer."""

    def type_check(self, obj):
        return isinstance(obj, int) and obj > 0

    def __str__(self):
        return "positive non-zero integer"


PosInt = PositiveInt()
