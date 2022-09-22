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
import py_cui.keys
from colorama import Fore, Style, init

from awsrun.argparse import AppendAttributeValuePair
from awsrun.config import Bool, Choice, Dict, Int, List, Str
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
            parser.error("only one lookup attribute may be used per AWS")

        elif any(len(v) > 1 for v in args.attributes.values()):
            parser.error("only one lookup value may be specified per AWS")

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
            super().regional_collect_results(acct, region, get_result)

        events, events_by_user = get_result()
        self.events.append(events)
        for username, events in events_by_user.items():
            self.events_by_user[username].extend(events)

    def post_hook(self):
        if not self.interactive:
            return

        # Let's fire up the TUI!

        # These contain the list of events being displayed by the TUI widgets.
        # By default, all events are shown for a specific unless the user
        # applies a filter.
        events = self.events
        events_by_user = self.events_by_user

        # This contains the current query expression to filter events. We only
        # save a reference to this, so we can prepopulate the filter popup box
        # with the last expression the user used. This makes it easy for a user
        # to keep tweaking long exressions without having to type it over and
        # over again.
        current_filter_expression = ""

        # Our layout consists of three panes: user list, event list, and event
        # detail.  We support a vertical layout where all three are stacked
        # vertically in the terminal for those with narrow terminals ...
        if self.vertical:
            root = py_cui.PyCUI(4, 1)
            user_list = root.add_scroll_menu("Usernames", 0, 0)
            event_list = root.add_scroll_menu("Events", 1, 0)
            event_detail = root.add_scroll_menu("Event Detail", 2, 0, row_span=2)

        # ... but the default layout consists of the user and event list
        # stacked vertically on the left side of the screen with the event
        # detail pane taking the full height on the right side.
        else:
            root = py_cui.PyCUI(3, 4)
            user_list = root.add_scroll_menu("Usernames", 0, 0, column_span=2)
            event_list = root.add_scroll_menu("Events", 1, 0, row_span=2, column_span=2)
            event_detail = root.add_scroll_menu(
                "Event Detail", 0, 2, row_span=3, column_span=2
            )

        root.toggle_unicode_borders()
        root.set_title("CloudTrail Events")
        root.set_status_bar_text("Press 'q' to exit. TAB to switch panes.")

        # py_cui has an odd navigation mechanism where the TUI is either in
        # overview mode or focus mode.  In overview mode, users navigate with
        # arrow keys to navigate between widgets, and then press RETURN to
        # enter focus mode. Focus mode allows users to interact with the widget
        # only until the user presses ESC to return to overview mode. I find
        # this non-intuitive, so let's provide a mappting for TAB to cycle
        # between widgets and place them in focus mode automatically.
        focus = cycle(filter(None, root.get_widgets().values()))

        def select_next_widget():
            root.move_focus(next(focus))

        root.add_key_command(py_cui.keys.KEY_TAB, select_next_widget)

        # Filter the event list objects in the outer scope that are used by
        # widgets to display content. This function is called as a result of
        # the user entering a query expression in the filtering popup.
        def filter_event_lists(expr):
            nonlocal events
            nonlocal events_by_user

            if not expr.strip():
                events = self.events
                events_by_user = self.events_by_user
                return

            events_by_user = defaultdict(list)
            for user, events in self.events_by_user.items():
                events = _filter_events(events, expr)
                if events:
                    events_by_user[user] = events

            events = []  # List of lists
            for sublist in self.events:
                events.append(_filter_events(sublist, expr))

        # Callback used when user presses key to open filtering popup. By
        # default, py_cui returns the user to overview mode after the popup is
        # dismissed. We save the widget that was in focus before the popup, so
        # we can refocus on it afterwards.
        def show_filter_popup():
            # pylint: disable=protected-access
            original_widget = root.get_selected_widget()

            def popup_callback(s):
                nonlocal current_filter_expression
                current_filter_expression = s
                filter_event_lists(s)
                update_user_list()
                if original_widget:
                    root.move_focus(original_widget)

            root.show_text_box_popup("Filter expression:", popup_callback)
            # Workaround until upstream allows setting initial text.
            root._popup.set_text(current_filter_expression)
            # Workaround until upstream py_cui fixes bug
            root._popup._initial_cursor = (
                root._popup.get_start_position()[0] + root._popup.get_padding()[0] + 2
            )

        def update_user_list():
            user_list.clear()
            user_list.add_item_list(
                sorted(events_by_user.keys(), key=lambda s: s.lower())
            )
            user_list.set_title(f"Usernames ({len(events_by_user.keys())})")
            update_event_list()

        def update_event_list():
            event_list.clear()
            if user_list.get():
                event_list.add_item_list(events_by_user[user_list.get()])
            event_list.set_title(f"Events ({len(event_list.get_item_list())})")
            update_event_detail()

        def update_event_detail():
            event_detail.clear()
            event = event_list.get()
            if event:
                event_detail.add_item_list(event.to_json().split("\n"))

        def unfilter_event_list():
            event_list.clear()
            all_events = sorted(
                chain(*events), reverse=True, key=lambda e: e.event["EventTime"]
            )
            event_list.add_item_list(all_events)
            event_list.set_title(f"Events ({len(all_events)})")
            update_event_detail()

        user_list.set_selected_color(self.color)
        user_list.set_focus_border_color(self.color)
        user_list.add_key_command(py_cui.keys.KEY_TAB, select_next_widget)
        user_list.add_key_command(py_cui.keys.KEY_ENTER, update_event_list)
        user_list.add_key_command(py_cui.keys.KEY_BACKSPACE, unfilter_event_list)
        user_list.add_key_command(py_cui.keys.KEY_F_LOWER, show_filter_popup)
        user_list.add_key_command(py_cui.keys.KEY_Q_LOWER, root.stop)
        user_list.set_focus_text(
            "Press 'q' to exit. TAB to switch panes. RET for user events. BACKSPACE for all events. 'f' to filter."
        )

        event_list.set_selected_color(self.color)
        event_list.set_focus_border_color(self.color)
        event_list.add_key_command(py_cui.keys.KEY_TAB, select_next_widget)
        event_list.add_key_command(py_cui.keys.KEY_ENTER, update_event_detail)
        event_list.add_key_command(py_cui.keys.KEY_F_LOWER, show_filter_popup)
        event_list.add_key_command(py_cui.keys.KEY_Q_LOWER, root.stop)
        event_list.set_focus_text(
            "Press 'q' to exit. TAB to switch panes. RET for event detail. 'f' to filter."
        )

        event_detail.set_selected_color(self.color)
        event_detail.set_focus_border_color(self.color)
        event_detail.add_key_command(py_cui.keys.KEY_TAB, select_next_widget)
        event_detail.add_key_command(py_cui.keys.KEY_F_LOWER, show_filter_popup)
        event_detail.add_key_command(py_cui.keys.KEY_Q_LOWER, root.stop)
        event_detail.set_focus_text(
            "Press 'q' to exit. TAB to switch panes. 'f' to filter."
        )

        # Load the widgets with data and select the user list.
        update_user_list()
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
        """Return a concrete implementation of `_UserIdentityType`."""
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

    def contains(self, s):
        """Return True if the event contains `s`."""

        try:
            next(_deep_finder(self.ct_event, lambda n: isinstance(n, str) and s in n))
            return True
        except StopIteration:
            return False

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
        return None

    def to_json(self):
        """Return event as JSON string."""
        return json.dumps(self.event, default=str, indent=4)

    def __str__(self):
        src = self.event.get("EventSource", "")
        time = self.event.get("EventTime", "")
        name = self.event.get("EventName", "")
        error = self.ct_event.get("errorCode", "")
        if error:
            error = f"ERROR: {error}"
        return f"{time}  {src:25.25} {name:30.30} {self.username()}  {error}"


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


def _filter_events(events, query):
    """Return list of events filtered by query expression.

    Query expression may consist of one or more terms. Terms are matched using
    logical OR. A term may be prefixed with an optional '-' to exclude events
    containing the term. Terms are case sensitive and are matched as substrings
    in a CloudTrail event including both keys and values.

    For example, to search for CloudTrail events that had errors:

        errorCode

    To search for errors excluding S3 issues:

        errorCode -s3

    To search for errors excluding S3 that are due to rate limiting:

        errorCode -s3 RequestLimitExceeded

    Technically, the above could be shortened:

        -s3 RequestLimitExceeded
    """
    terms = query.split()
    for term in terms:
        if term.startswith("-"):
            events = [e for e in events if not e.contains(term[1:])]
        else:
            events = [e for e in events if e.contains(term)]
    return events


def _deep_finder(node, predicate):
    """Return a generator that yields keys or objects matching `predicate`."""
    if isinstance(node, dict):
        for k, v in node.items():
            if predicate(k):
                yield k
            yield from _deep_finder(v, predicate)
    elif isinstance(node, list):
        for e in node:
            yield from _deep_finder(e, predicate)
    else:
        if predicate(node):
            yield node


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
