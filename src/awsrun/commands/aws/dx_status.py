"""Display the status of Direct Connects and VIFs.

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
"""
import io
import re
import sys
from collections import defaultdict

import colorama
from asciichartpy import plot
from colorama import Fore, Style
from sparkline import sparkify

from awsrun.cloudwatch import CWMetrics
from awsrun.config import Bool, Choice, Type
from awsrun.runner import RegionalCommand


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

            if self.height > 0:
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
    elif n == 1:
        return 0
    else:  # NaN case
        return n


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

    return f"{v_id} vlan {v_vlan} owned by {v_owner} on {c_name} is {v_state}"


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

        elif height > 1:
            opts = {
                "minimum": 0,
                "height": height,
                "format": "{:14,.0f} ",
            }
            # The asciichartpy module is a bit wonky and not really idiomatic
            # python as they just pass a giant dictionary of options (typical of
            # javascript land). Do not provide a "maximum" key with a value of
            # None. If use wants auto-scaling, don't provide the key at all.
            if max_yaxis is not None:
                opts["maximum"] = max_yaxis

            chart = plot(values, opts)
        print(_format_metric(name, chart, color=colors.pop()), file=file)
    print(file=file)


def _format_metric(name, chart, color=Fore.BLACK):
    return f"{Style.DIM}{color}{chart} {name}{Style.RESET_ALL}"


# Type definition for awsrun.config to validate positive numbers.
class PositiveInt(Type):
    def type_check(self, obj):
        return isinstance(obj, int) and obj > 0

    def __str__(self):
        return "positive non-zero integer"


PosInt = PositiveInt()
