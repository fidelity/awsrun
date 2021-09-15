#
# Copyright 2019 FMR LLC <opensource@fmr.com>
#
# SPDX-License-Identifier: MIT
#
"""Display the last CloudTrail events in an account.

## Overview

`last` provides an easier way to review CloudTrail events in either an
interactive or non-interactive manner depending on whether or not the
`--interactive` flag was supplied. In both cases, the events are grouped
together by the user that caused them.

With no addition arguments besides specification of `--region`, the last
command retrieves the past one hour of write events up to a maximum of 1,000
events per account/region pair. Newest events are shown at the top. If output
is not being redirected, events from the same user are displayed in the same
color.

    $ awsrun --account 100200300400 last --region us-east-1
    Loading events, 1000 max per acct/region, use --max-events to change
    100200300400/us-east-1:  2020-04-08 00:43:43-05:00  logs.amazonaws.com  CreateLogGroup  ECSClusterRole/i-XXXXXXXXXXXXXXXXX
    100200300400/us-east-1:  2020-04-08 00:43:39-05:00  logs.amazonaws.com  CreateLogGroup  ECSClusterRole/i-XXXXXXXXXXXXXXXXX
    100200300400/us-east-1:  2020-04-08 00:43:38-05:00  logs.amazonaws.com  CreateLogGroup  ECSClusterRole/i-XXXXXXXXXXXXXXXXX
    100200300400/us-east-1:  2020-04-08 00:43:35-05:00  logs.amazonaws.com  CreateLogGroup  ECSClusterRole/i-XXXXXXXXXXXXXXXXX

The first column of output is the account/region where the event was
collected. The second column is the event timestamp. The third column is the
event source. The fourth column is the event name. And the last column is the
"user" that generated the event.

Users can specify time ranges using `--start` and `--end` flags. These take
ISO 8601 formatted dates: `2020-04-07T22:30:00-0500`.  When specifying a time
range, use either `--last` HOURS or `--start`/`--end` flags, but not both at
same time. If none of these flags are specified, the past hour of events is
retrieved by default. For example, the following command retrieves a 1-minute
window of write events:

    $ awsrun --account 100200300400 last --region us-east-1 --start 2020-04-07T00:20:00-0500 --end 2020-04-07T00:21:00-0500

As stated before, only write events are retrieved, but Users can filter events
by any of the supported lookup attributes in CloudTrail via the `--attribute`:
EventId, EventName, ReadOnly, Username, ResourceType, ResourceName,
EventSource, or AccessKeyId. To filter on console logins for the past 12
hours:

    $ awsrun --account 100200300400 last --region us-east-1 --hours 12 --attribute EventName=ConsoleLogin
    Loading events, 1000 max per acct/region, use --max-events to change
    100200300400/us-east-1:  2020-04-08 00:56:17-05:00  signin.amazonaws.com  ConsoleLogin  Operator/user@example.com

Two shorthand attribute filters exist. The `--all` flag will select all events
including the read-only events.  The `--console` flag will filter on console
logins as above:

    $ awsrun --account 100200300400 last --region us-east-1 --hours 12 --console
    Loading events, 1000 max per acct/region, use --max-events to change
    100200300400/us-east-1:  2020-04-08 00:56:17-05:00  signin.amazonaws.com  ConsoleLogin  Operator/user@example.com

To minimize memory footprint and load on AWS servers, a maximum of 1,000
events are pulled from an account/region pair. Use the `--max-events` flag to
override the value.

Finally, for a TUI (terminal user interface) that lets you interactively
explore events, specify the `--interactive` flag. Follow the on-screen
instructions to interact with the TUI. By default, the TUI uses a horizontal
layout. Specify the `--vertical` option to change to a vertical layout. The
color used in the TUI can be changed via the `--color` option. Valid choices
include blue, green, cyan, magenta, red, and white.

## Reference

### Synopsis

    $ awsrun [options] last [command options]

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      last:
        hours: INT
        max_events: INT
        region:
          - STRING
        all: BOOLEAN
        console: BOOLEAN
        attributes:
          STRING:
            - STRING
        interactive: BOOLEAN
        vertical: BOOLEAN
        color: STRING

### Command Options
Some options can be overridden on the awsrun CLI via command line flags. In
those cases, the CLI flags are specified next to the option name below:

`hours`, `--hours INT`
: Specifies the how many hours of events to retrieve. The default value is 1
hour. Note: The number of events retrieved will not exceed `max_events`.

`max_events`, `--max-events INT`
: Specifies the upper limit on the number of events to retrieve on a per account
per region basis. The default value is 1,000 events.

`region`, `--region REGION`
: Run the command in the specified regions. When specifying multiple values on
the command line, use multiple flags for each value.

`all`, `--all`
: Retrieve all CloudTrail events including read-only events. The default value
is False. This option is mutually exclusive with the `console` and `attributes`
options.

`console`, `--console`
: Retrieve only console login CloudTrail events. The default is value is False.
This option is mutually exclusive with the `all` and `attributes` options.

`attributes`, `--attribute KEY=VALUE`
: Retrieve only CloudTrail events matching the attribute key and value. The
possible key values are: `EventId`, `EventName`, `ReadOnly`, `Username`,
`ResourceType`, `ResourceName`, `EventSource`, and `AccessKeyId`. Due to
limitations in the CloudTrail API, only one attribute can be specified. This
option is mutually exclusive with the `all` and `console` options.

`interactive`, `--interactive`
: Open an interactive TUI (terminal user interface) instead of printing events
to the console. The default value is False.

`vertical`, `--vertical`
: When using the `interactive` mode in a taller but narrow terminal, place the
event detail widget under the other for a single column grid layout. The default
value is False.

`color`, `--color COLOR`
: Specify a color scheme to use when in interactive mode. Possible values
include: white, yellow, red, cyan, magenta, green, blue. The default value is
cyan.

The following is a sample configuration to add a permanent filter in your
configuration file for `DeleteStack` events using the `attributes` configuration
option:

    Commands:
      last:
        attributes:
          EventName:
            - DeleteStack

"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import partial
from itertools import chain, cycle

import py_cui
from colorama import Fore, Style, init

from awsrun.argparse import AppendAttributeValuePair
from awsrun.config import Bool, Choice, Dict, Int, Str, List
from awsrun.runner import RegionalCommand


# Lookup attributes supported by AWS CloudTrail
LOOKUP_ATTRIBUTES = [
    "EventId",
    "EventName",
    "ReadOnly",
    "Username",
    "ResourceType",
    "ResourceName",
    "EventSource",
    "AccessKeyId",
]


class CLICommand(RegionalCommand):
    """Displays the last CloudTrail events in an account."""

    @classmethod
    def regional_from_cli(cls, parser, argv, cfg):
        time_spec = parser.add_argument_group("Time specification")
        time_spec.add_argument(
            "--hours",
            metavar="N",
            type=int,
            default=cfg("hours", type=Int),
            help="retrieve the last N hours of events",
        )
        time_spec.add_argument(
            "--start",
            type=_isodate,
            help="lookup events starting at YYYY-MM-DDTHH:MM:SS-00:00",
        )
        time_spec.add_argument(
            "--end",
            type=_isodate,
            help="lookup events ending at YYYY-MM-DDTHH:MM:SS-00:00",
        )

        parser.add_argument(
            "--max-events",
            metavar="N",
            type=int,
            default=cfg("max_events", type=Int, default=1000),
            help="limit # of events retrieved",
        )

        filters = parser.add_argument_group("Event filters")
        mut_excl = filters.add_mutually_exclusive_group()
        mut_excl.add_argument(
            "--all",
            action="store_true",
            default=cfg("all", type=Bool, default=False),
            help="include read-only events",
        )
        mut_excl.add_argument(
            "--console",
            action="store_true",
            default=cfg("console", type=Bool, default=False),
            help="include only ConsoleLogin events",
        )
        mut_excl.add_argument(
            "--attribute",
            "-a",
            dest="attributes",
            action=AppendAttributeValuePair,
            default=cfg("attributes", type=Dict(Str, List(Str)), default={}),
            help="filter using attribute in form of ATTR=VALUE",
        )

        tui = parser.add_argument_group("TUI options")
        tui.add_argument(
            "--interactive",
            "-i",
            action="store_true",
            default=cfg("interactive", type=Bool, default=False),
            help="enter interactive mode to view results",
        )
        tui.add_argument(
            "--vertical",
            action="store_true",
            default=cfg("vertical", type=Bool, default=False),
            help="use vertical layout for TUI",
        )
        tui.add_argument(
            "--color",
            choices=TUI_COLOR_THEMES,
            default=cfg("color", type=Choice(*TUI_COLOR_THEMES), default="cyan"),
            help=f"use color scheme: {', '.join(TUI_COLOR_THEMES)}",
        )

        args = parser.parse_args(argv)

        # If user doesn't specify any filters, then exclude the read-only
        # events as there are far too many of these typically. While our
        # argument parser can support multipe key and values, the AWS
        # CloudTrail API is lacking considerably in ability to specify
        # filters. One can only use a single lookup attribute and that
        # attribute can only have a single value. We allow the user to
        # explicity set their own filter or use one of our the shorthand
        # filters such as --all or --console.

        if not (args.all or args.console or args.attributes):
            args.attributes["ReadOnly"] = ["false"]

        elif args.console:
            args.attributes["EventName"] = ["ConsoleLogin"]

        elif len(args.attributes) > 1:
            parser.error(f"only one lookup attribute may be used per AWS")

        elif any(len(v) > 1 for v in args.attributes.values()):
            parser.error(f"only one lookup value may be specified per AWS")

        elif any(a not in LOOKUP_ATTRIBUTES for a in args.attributes):
            parser.error(
                f"invalid attribute, must be one of {', '.join(LOOKUP_ATTRIBUTES)}"
            )

        # If no time spec flags provided, default to last of 1 hour of events.
        if not (args.hours or args.start or args.end):
            args.hours = 1

        # If only --hours was specified, then compute a start and end time as
        # our CLICommand doesn't support --last.
        if args.hours and not (args.start or args.end):
            args.end = datetime.now(timezone.utc)
            args.start = args.end - timedelta(hours=args.hours)

        elif args.hours and (args.start or args.end):
            parser.error("must specify either --hours OR --start/--end flags")

        elif not (args.start and args.end):
            parser.error("must specify both --start and --end flags")

        # Only allow use of TUI options with --interactive flag
        if args.vertical and not args.interactive:
            parser.error("can only use --vertical with --interactive mode")

        del args.all
        del args.hours
        del args.console
        return cls(**vars(args))

    def __init__(
        self,
        regions,
        start=None,
        end=None,
        attributes=None,
        max_events=1000,
        interactive=False,
        vertical=False,
        color="blue",
    ):
        super().__init__(regions)

        # Event settings
        self.start = start
        self.end = end
        self.max_events = max_events
        self.attributes = {} if attributes is None else attributes

        # TUI settings
        self.interactive = interactive
        self.vertical = vertical
        self.color = TUI_COLOR_THEMES.get(color, py_cui.WHITE_ON_BLACK)

        # Dict of events by "username", which we'll define as the unique
        # identifier for a particular session.
        self.events_by_user = defaultdict(list)

        # List of all events in reverse chronological order. We wouldn't have
        # to keep this list if event timestamps were more granular than a
        # second. Given that they are not, it's not possible to accurately
        # reconstruct the series of events from a dict of events by user.
        self.events = []

    def pre_hook(self):
        print(
            f"Loading events, {self.max_events} max per acct/region, use --max-events to change",
            file=sys.stderr,
        )

        if not self.interactive:
            init()  # colorama only needed for the noninteractive version

    def regional_execute(self, session, acct, region):
        ct = session.client("cloudtrail", region_name=region)
        events = self._retrieve_events(ct)

        if self.interactive:
            events_by_user = defaultdict(list)
            for e in events:
                events_by_user[e.username()].append(e)
            return events, events_by_user

        cf_map = defaultdict(lambda: next(COLOR_FUNCTIONS))
        return "".join(cf_map[e.username()](f"{acct}/{region}:  {e}\n") for e in events)

    def _retrieve_events(self, ct):
        events = []
        for page in _lookup_events(
            ct, start=self.start, end=self.end, attrs=self.attributes
        ):
            for event in page["Events"]:
                event["CloudTrailEvent"] = json.loads(event["CloudTrailEvent"])
                events.append(_UserIdentityType.new(event))
                if self.interactive:
                    print(".", end="", file=sys.stderr, flush=True)
                if len(events) >= self.max_events:
                    return events
        return events

    def regional_collect_results(self, acct, region, get_result):
        if not self.interactive:
            return super().regional_collect_results(acct, region, get_result)

        events, events_by_user = get_result()
        self.events.append(events)
        for username, events in events_by_user.items():
            self.events_by_user[username].extend(events)

    def post_hook(self):
        if not self.interactive:
            return

        # User wants the TUI, so let's fire it up! Keep in mind, the Python
        # library I found to make the TUI is barely alpha, so I've had to work
        # around many of its limitations that I will submit to the author.
        if self.vertical:
            root = _MyCUI(4, 1)
            user_list = root.add_my_scroll_menu(f"Usernames", 0, 0)
            event_list = root.add_my_scroll_menu("Events", 1, 0)
            event_detail = root.add_my_scroll_menu("Event Detail", 2, 0, row_span=2)

        else:  # Default hybrid layout
            root = _MyCUI(3, 4)
            user_list = root.add_my_scroll_menu(f"Usernames", 0, 0, column_span=2)
            event_list = root.add_my_scroll_menu(
                "Events", 1, 0, row_span=2, column_span=2
            )
            event_detail = root.add_my_scroll_menu(
                "Event Detail", 0, 2, row_span=3, column_span=2
            )

        root.toggle_unicode_borders()
        root.set_title("CloudTrail Events")
        root.set_status_bar_text("Press - q - to exit. TAB to move between widgets.")

        # Override the default behavior and allow TAB to switch between
        # widgets and activate widgets.
        focus = cycle(root.widgets.values())

        def select_next_widget():
            root.move_focus(next(focus))

        root.add_key_command(py_cui.keys.KEY_TAB, select_next_widget)

        # Configure our user list
        def update_event_list():
            event_list.clear()
            event_list.add_item_list(self.events_by_user[user_list.get()])
            event_list.title = f"Events ({len(event_list.get_item_list())})"
            update_event_detail()

        def unfilter_event_list():
            event_list.clear()
            all_events = sorted(
                chain(*self.events), reverse=True, key=lambda e: e.event["EventTime"]
            )
            event_list.add_item_list(all_events)
            event_list.title = f"Events ({len(all_events)})"
            update_event_detail()

        user_list.add_key_command(py_cui.keys.KEY_TAB, select_next_widget)
        user_list.add_key_command(py_cui.keys.KEY_ENTER, update_event_list)
        user_list.add_key_command(py_cui.keys.KEY_BACKSPACE, unfilter_event_list)
        user_list.add_key_command(py_cui.keys.KEY_PAGE_UP, user_list.page_up)
        user_list.add_key_command(py_cui.keys.KEY_PAGE_DOWN, user_list.page_down)
        user_list.add_key_command(py_cui.keys.KEY_Q_LOWER, lambda: root.stop())
        user_list.title = f"Usernames ({len(self.events_by_user.keys())})"
        user_list.set_focus_text(
            "Press - q - to exit. TAB to move between widgets. ENTER to filter events. BACKSPACE to show all."
        )
        user_list.set_selected_color(self.color)
        user_list.add_item_list(
            sorted(self.events_by_user.keys(), key=lambda s: s.lower())
        )

        # Configure our event list
        def update_event_detail():
            event_detail.clear()
            event_detail.add_item_list(event_list.get().to_json().split("\n"))

        event_list.add_key_command(py_cui.keys.KEY_TAB, select_next_widget)
        event_list.add_key_command(py_cui.keys.KEY_ENTER, update_event_detail)
        event_list.add_key_command(py_cui.keys.KEY_PAGE_UP, event_list.page_up)
        event_list.add_key_command(py_cui.keys.KEY_PAGE_DOWN, event_list.page_down)
        event_list.add_key_command(py_cui.keys.KEY_Q_LOWER, lambda: root.stop())
        event_list.set_focus_text(
            "Press - q - to exit. TAB to move between widgets. ENTER to display event detail."
        )
        event_list.set_selected_color(self.color)
        if user_list.get():
            update_event_list()

        # Configure our event detail
        event_detail.add_key_command(py_cui.keys.KEY_TAB, select_next_widget)
        event_detail.add_key_command(py_cui.keys.KEY_PAGE_UP, event_detail.page_up)
        event_detail.add_key_command(py_cui.keys.KEY_PAGE_DOWN, event_detail.page_down)
        event_detail.add_key_command(py_cui.keys.KEY_Q_LOWER, lambda: root.stop())
        event_detail.set_focus_text("Press - q - to exit. TAB to move between widgets.")
        event_detail.set_selected_color(self.color)
        if event_list.get():
            update_event_detail()

        select_next_widget()

        # Fire up the main event loop
        root.start()


class _UserIdentityType:
    """Represents a custom event object based on the user identity type.

    The event object wraps an event dict with a convenience method to compute
    the username for a given event. CloudTrail events seem to be a mess when it
    comes to normalizing the username (at least in our environment). The purpose
    of this class is to provide a means to extract a reasonable username from an
    event that can be used to group events together via the `username` method.

    The factory method `new` should be used to create instances of this type. It
    will dispatch to a custom subclass based on the user type. If no custom
    subclass exists, an instance of this class is created. If one wants to add
    new user types, just follow the patterns of the existing subclasses.
    """

    @classmethod
    def new(cls, event):
        user_type = event["CloudTrailEvent"]["userIdentity"].get("type", "AWSService")
        klass = globals().get(f"_{user_type}Type", cls)
        return klass(event)

    def __init__(self, event):
        self.event = event
        self.ct_event = event["CloudTrailEvent"]
        self.user_identity = self.ct_event["userIdentity"]

    def type(self):
        """Return the user identity type if present, otherwise NO_TYPE."""
        return self.user_identity.get("type", "NO_TYPE")

    def username(self):
        """Return a the username associated with an event."""
        if self.event["EventName"].startswith("AssumeRole"):
            user = self._parse_username_from_request_params()
            if user:
                return user
        return self._parse_username()

    def _parse_username(self):
        return self.event.get(
            "Username", self.user_identity.get("userName", "NO_USERNAME")
        )

    def _find_resource(self, type_, default=None):
        for resource in self.event["Resources"]:
            if resource["ResourceType"] == type_:
                return resource["ResourceName"]
        return default

    def _parse_username_from_request_params(self):
        params = self.ct_event.get("requestParameters", {})
        arn = params.get("roleArn")
        session_name = params.get("roleSessionName")
        if arn and session_name:
            return _strip_to("/", arn, greedy=True) + "/" + session_name

    def to_json(self):
        return json.dumps(self.event, default=str, indent=4)

    def __str__(self):
        src = self.event.get("EventSource", "")
        time = self.event.get("EventTime", "")
        name = self.event.get("EventName", "")
        return f"{time}  {src:25.25} {name:30.30} {self.username()}"


#############################################################################
# These classes are for custom handling of different user identity types. you
# want to provide a custom username for a cloudtrail user identity type,
# define your subclass below following the naming convention.
#############################################################################


class _RootType(_UserIdentityType):
    def _parse_username(self):
        # Docs state that Root does not have a username unless an alias has
        # been set for the account, so we try to print the username, if not,
        # we return "ROOT".
        return self.user_identity.get("userName", "ROOT")


class _AWSAccountType(_UserIdentityType):
    def _parse_username(self):
        acct = self.user_identity.get("accountId", "NO_ACCOUNT_ID")
        principal = self.user_identity.get("principalId", "NO_PRINCIPAL_ID")
        return f"{acct}/{_strip_to(':', principal)}"


class _AWSServiceType(_UserIdentityType):
    def _parse_username(self):
        return self.user_identity.get("invokedBy", "NO_USERNAME")


class _AssumedRoleType(_UserIdentityType):
    def _parse_username(self):
        # For an assumed role type, we get username from the arn because it's
        # the only thing consistent throughout the other type of events, which
        # allows us to match a sequence of events.
        arn = self.user_identity.get("arn")
        if arn:
            return _strip_to("/", arn)
        return self.event.get("Username")


#############################################################################
# Helper functions
#############################################################################


def _isodate(string):
    return datetime.strptime(string, "%Y-%m-%dT%H:%M:%S%z")


def _strip_to(char, string, greedy=False):
    pos = string.rfind(char) if greedy else string.find(char)
    return string[pos + 1 :]


def _strip_after(char, string, greedy=False):
    pos = string.rfind(char) if greedy else string.find(char)
    return string if pos == -1 else string[:pos]


def _lookup_events(ct, start, end, attrs=None):
    attrs = {} if attrs is None else attrs
    return ct.get_paginator("lookup_events").paginate(
        LookupAttributes=[
            {"AttributeKey": k, "AttributeValue": v}
            for k, vs in attrs.items()
            for v in vs
        ],
        StartTime=start,
        EndTime=end,
    )


def _colorize(color, string):
    return f"{color}{string}{Style.RESET_ALL}"


# An infinite list of partially applied colorize functions
COLOR_FUNCTIONS = cycle(
    [
        partial(_colorize, f"{s}{c}")
        for s in ("", Style.DIM, Style.BRIGHT)
        for c in (
            Fore.BLUE,
            Fore.GREEN,
            Fore.YELLOW,
            Fore.RED,
            Fore.MAGENTA,
            Fore.CYAN,
            Fore.WHITE,
        )
    ]
)

# Make available any of the colors defined in py_cui
TUI_COLOR_THEMES = {
    _strip_after("_", k).lower(): v
    for k, v in vars(py_cui).items()
    if k.endswith("_ON_BLACK")
}


#############################################################################
# This code is for deficiencies in the py_cui library. I will actually make a
# PR for the author of that project at some point.
#############################################################################


class _MyCUI(py_cui.PyCUI):
    def add_my_scroll_menu(
        self, title, row, column, row_span=1, column_span=1, padx=1, pady=0
    ):
        id = "Widget{}".format(len(self.widgets.keys()))
        new_scroll_menu = _MyScrollMenu(
            id, title, self.grid, row, column, row_span, column_span, padx, pady
        )
        self.widgets[id] = new_scroll_menu
        if self.selected_widget is None:
            self.set_selected_widget(id)
        return new_scroll_menu


class _MyScrollMenu(py_cui.widgets.ScrollMenu):
    def __init__(
        self,
        id,
        title,
        grid,
        row,
        column,
        row_span,
        column_span,
        padx,
        pady,
        to_str=str,
    ):
        super().__init__(
            id, title, grid, row, column, row_span, column_span, padx, pady
        )
        self.to_str = to_str

    def page_up(self):
        shift_by = self.height - (2 * self.pady) - 3

        new_top_view = self.top_view - shift_by
        new_selected_item = self.selected_item - shift_by

        self.top_view = 0 if new_top_view < 0 else new_top_view
        self.selected_item = 0 if new_selected_item < 0 else new_selected_item

    def page_down(self):
        shift_by = self.height - (2 * self.pady) - 3
        last_item_idx = len(self.view_items) - 1

        new_top_view = self.top_view + shift_by
        new_selected_item = self.selected_item + shift_by

        self.top_view = (
            new_top_view - shift_by if new_top_view > last_item_idx else new_top_view
        )
        self.selected_item = (
            last_item_idx if new_selected_item > last_item_idx else new_selected_item
        )

    def draw(self):
        super(py_cui.widgets.ScrollMenu, self).draw()

        self.renderer.set_color_mode(
            self.selected_color if self.selected else self.color
        )
        self.renderer.draw_border(self)

        counter = self.pady + 1
        line_counter = 0
        for line in (self.to_str(i) for i in self.view_items):
            if line_counter < self.top_view:
                line_counter = line_counter + 1
            else:
                if counter >= self.height - self.pady - 1:
                    break
                if line_counter == self.selected_item:
                    self.renderer.draw_text(
                        self, line, self.start_y + counter, selected=True
                    )
                else:
                    self.renderer.draw_text(self, line, self.start_y + counter)
                counter = counter + 1
                line_counter = line_counter + 1

        self.renderer.unset_color_mode(
            self.selected_color if self.selected else self.color
        )
        self.renderer.reset_cursor(self)
