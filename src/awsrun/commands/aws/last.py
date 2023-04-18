#
# Copyright 2023 FMR LLC <opensource@fmr.com>
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
instructions to interact with the TUI.

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
import warnings
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import partial
from itertools import chain, cycle
from typing import Optional

from awsrun.argparse import AppendAttributeValuePair
from awsrun.config import Bool, Dict, Int, List, Str
from awsrun.runner import RegionalCommand

try:
    import pyperclip
    from colorama import Fore, Style, init
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.message import Message
    from textual.reactive import reactive
    from textual.widgets import Button, DataTable, Footer, Header, Input, Static

except ImportError:
    sys.exit(
        """
The 'last' command requires dependencies not installed by default with
awsrun. Please install them with the following command:

    pip install awsrun[last]
"""
    )


# Textual enables ResourceWarnings, which is not the python default,
# so we disable them as we get warnings from boto library that we
# cannot control.
warnings.simplefilter("ignore", ResourceWarning)


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
    ):
        super().__init__(regions)

        # Event settings
        self.start = start
        self.end = end
        self.max_events = max_events
        self.attributes = {} if attributes is None else attributes

        # TUI settings
        self.interactive = interactive

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
            return events

        cf_map = defaultdict(lambda: next(COLOR_FUNCTIONS))
        return "".join(cf_map[e.username()](f"{acct}/{region}:  {e}\n") for e in events)

    def _retrieve_events(self, ct):
        events = []
        event_ids = set()
        for page in _lookup_events(
            ct, start=self.start, end=self.end, attrs=self.attributes
        ):
            for event in page["Events"]:
                event_id = event["EventId"]

                # Check to make sure AWS is not returning duplicate events.
                # I've seen this happen sometimes, so let's ignore the dups.
                if event_id in event_ids:
                    continue
                event_ids.add(event_id)

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
            return

        self.events.append(get_result())

    def post_hook(self):
        if not self.interactive:
            return

        # Let's fire up the TUI!
        app = EventViewer(list(chain(*self.events)))
        app.run()


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
        """Return True if the event contains `s` (case-insenstive)."""

        s = s.lower()
        try:
            next(
                _deep_finder(
                    self.event, lambda n: isinstance(n, str) and s in n.lower()
                )
            )
            return True
        except StopIteration:
            return False

    def has_error(self):
        return "errorCode" in self.ct_event

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

    def event_id(self):
        return self.event["EventId"]

    def to_json(self):
        """Return event as JSON string."""
        return json.dumps(self.event, default=str, indent=4)

    def to_row(self):
        return (
            self.event.get("EventTime", ""),
            self.event.get("EventSource", ""),
            self.event.get("EventName", ""),
            self.ct_event.get("errorCode", ""),
        )

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


class _RootType(_UserIdentityType):  # pyright: ignore
    def _parse_username(self):
        # Docs state that Root does not have a username unless an alias has
        # been set for the account, so we try to print the username, if not,
        # we return "ROOT".
        return self.user_identity.get("userName", "ROOT")


class _AWSAccountType(_UserIdentityType):  # pyright: ignore
    def _parse_username(self):
        acct = self.user_identity.get("accountId", "NO_ACCOUNT_ID")
        principal = self.user_identity.get("principalId", "NO_PRINCIPAL_ID")
        return f"{acct}/{_strip_to(':', principal)}"


class _UnknownType(_UserIdentityType):  # pyright: ignore
    def _parse_username(self):
        acct = self.user_identity.get("accountId", "NO_ACCOUNT_ID")
        return f"{acct}/unknown"


class _AWSServiceType(_UserIdentityType):  # pyright: ignore
    def _parse_username(self):
        return self.user_identity.get("invokedBy", "NO_USERNAME")


class _AssumedRoleType(_UserIdentityType):  # pyright: ignore
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
    logical AND. A term may be prefixed with an optional '-' to exclude events
    containing the term. Terms are case insensitive and are matched as substrings
    in a CloudTrail event including both keys and values.

    For example, to search for CloudTrail events that had errors:

        errorcode

    To search for errors excluding S3 issues:

        errorcode -s3

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


#############################################################################
# Textual TUI
#############################################################################


class Events:
    """Internal representation of the list of filtered events in TUI."""

    def __init__(self, events):
        self.unfiltered_events = events
        self.filter_expr = ""
        self._load_events(events)

    def _load_events(self, events):
        # Need to keep events as a list as we cannot recreate it
        # from the values of the event_by_user or we lose the
        # order of the events as the timestamp is not granular.
        self.events = events
        self.events_by_key = {e.event_id(): e for e in self.events}
        self.events_by_user = defaultdict(list)
        for e in self.events:
            self.events_by_user[e.username()].append(e)

    def all(self):
        return self.events

    def users(self):
        return self.events_by_user.keys()

    def by_user(self, user):
        return self.events_by_user.get(user, [])

    def by_id(self, event_id) -> Optional[_UserIdentityType]:
        return self.events_by_key.get(event_id)

    def filter(self, expr):
        if not expr:  # empty string?
            events = self.unfiltered_events
        else:
            events = _filter_events(self.unfiltered_events, expr)

        self.filter_expr = expr
        self._load_events(events)
        return len(self.events)


class Popup(Container):
    """An offscreen popup for a single input box."""

    DEFAULT_CSS = """
Popup {
    transition: offset 500ms in_out_cubic;
    padding: 0 2 1 2;
    width: 65;
    height: auto;
    background: $panel;
    color: $text;
}
Popup:focus-within {
    offset: 0 0;
}
Popup.offscreen {
    offset-y: 100%;
}
Popup Static {
    padding: 0 2 0 2;
}
Popup Horizontal {
    padding: 1 2 0 2;
    height: auto;
}
Popup Input {
    width: 4fr;
    margin-right: 1;
}
Popup Button {
    width: 1fr;
    min-width: 5;
}
    """

    class Changed(Message):
        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    class Closed(Message):
        pass

    def __init__(self, prompt, help_md):
        self.prompt = prompt
        self.help_md = help_md
        super().__init__(classes="offscreen")

    def compose(self) -> ComposeResult:
        yield Static(Markdown(self.help_md))
        with Horizontal():
            yield Input(placeholder=self.prompt)
            yield Button("Close", variant="primary")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.post_message(self.Changed(event.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(self.Closed())


FILTER_MESSAGE = """
## Filter Evenets

- Search terms are **case-insensitive**
- Terms are matched using a logical **AND**
- To **exclude** a term, prefix with a **hypen** (**-**)
- **Substrings** in both keys and values are searched
"""


class FilterPopup(Popup):
    # Class needed for the textual "magic" on_filter_popup_changed handler
    class Changed(Popup.Changed):
        pass

    # Class needed for the textual "magic" on_filter_popup_closed handler
    class Closed(Popup.Closed):
        pass

    def __init__(self):
        super().__init__("Enter expression then press ENTER", FILTER_MESSAGE)


EXPORT_MESSAGE = """
## Export Events

- Events matching the current filter are exported
- If no filter is specified, then all are exported
- Events exported as JSON
"""


class ExportPopup(Popup):
    # Class needed for the textual "magic" on_export_popup_changed handler
    class Changed(Popup.Changed):
        pass

    # Class needed for the textual "magic" on_export_popup_closed handler
    class Closed(Popup.Closed):
        pass

    def __init__(self):
        super().__init__("Enter filename then press ENTER", EXPORT_MESSAGE)


class RowTable(Container):
    DEFAULT_CSS = """
RowTable > DataTable {
  border: solid $accent-lighten-2;
  border-title-align: left;
  height: 100%;
}
RowTable > DataTable:focus {
  border: solid $secondary;
}
RowTable > DataTable > .datatable--header {
  text-style: bold;
  color: $accent-lighten-2;
  background: black 0%;
}
RowTable > DataTable > .datatable--cursor {
  color: $accent-lighten-2;
  text-style: bold;
  background: black 0%;
}
RowTable > DataTable > .datatable--hover {
  background: black 0%;
}
RowTable > DataTable > .datatable--header-hover {
  color: $accent-lighten-2;
  background: black 0%;
}
    """

    contents = reactive([], always_update=True)

    class SelectionChanged(Message):
        def __init__(self, row_key):
            self.row_key = row_key
            super().__init__()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        event.stop()
        event.control.border_subtitle = (
            f"{event.cursor_row + 1} of {len(event.control.rows)}"
        )
        self.post_message(self.SelectionChanged(event.row_key))

    def __init__(self, *col_names):
        self.col_names = col_names
        super().__init__()

    def compose(self) -> ComposeResult:
        yield DataTable()

    def focus(self):
        self.query_one(DataTable).focus()

    def on_mount(self):
        dt = self.query_one(DataTable)
        dt.cursor_type = "row"
        dt.add_columns(*self.col_names)


class UserTable(RowTable):
    DEFAULT_CSS = """
UserTable {
  height: 1fr;
}
    """

    # Class needed for the textual "magic" on_user_table_selection_changed handler
    class SelectionChanged(RowTable.SelectionChanged):
        pass

    def __init__(self):
        super().__init__("Principal")

    def on_mount(self):
        dt = self.query_one(DataTable)
        dt.show_header = False
        dt.border_title = "Users"

    def watch_contents(self, users):
        dt = self.query_one(DataTable)
        dt.clear()
        for user in users:
            dt.add_row(user, key=user)
        dt.scroll_home()
        dt.border_subtitle = f"0 of {len(users)}"


class EventTable(RowTable):
    DEFAULT_CSS = """
EventTable {
  height: 2fr;
}
    """

    # Class needed for the textual "magic" on_event_table_selection_changed handler
    class SelectionChanged(RowTable.SelectionChanged):
        pass

    def __init__(self):
        super().__init__("Time", "Source", "Event", "Error?")

    def on_mount(self):
        self.query_one(DataTable).border_title = "Events"

    def watch_contents(self, events):
        dt = self.query_one(DataTable)
        dt.clear()
        for event in events:
            row = event.to_row()
            if event.has_error():
                error = dt.app.get_css_variables()["error"]
                row = [f"[{error}]{c}[/]" for c in row]
            dt.add_row(*row, key=event.event_id())
        dt.scroll_home()
        dt.border_subtitle = f"0 of {len(events)}"


class EventViewer(App):
    CSS = """
Screen {
  align: center bottom;
  overflow: hidden;
  layers: base filter export;
}
FilterPopup {
    layer: filter;
}
ExportPopup {
    layer: export;
}
#main {
  layout: horizontal;
}
.vertical #main {
  layout: vertical;
}
#left {
  width: 1fr;
}
.vertical #left {
  height: 2fr;
}
.hidden {
  display: none;
}
    """

    TITLE = "CloudTrail Viewer"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "copy", "Copy"),
        ("e", "export_popup", "Export"),
        ("f", "filter_popup", "Filter"),
        ("l", "toggle_layout", "Layout"),
        ("u", "toggle_users", "Users"),
        ("d", "toggle_dark", "Toggle dark mode"),
    ]

    total_count = reactive(0)
    filtered_count = reactive(0)

    theme = {
        "dark": Syntax.get_theme("dracula"),
        "light": Syntax.get_theme("friendly"),
    }

    def __init__(self, events):
        super().__init__()
        self.events = Events(events)

    def compose(self) -> ComposeResult:
        yield FilterPopup()  # Hidden off-screen initially
        yield ExportPopup()  # Hidden off-screen initially
        yield Header()
        yield Horizontal(
            Vertical(UserTable(), EventTable(), id="left"),
            EventDetail(),
            id="main",
        )
        yield Footer()

    def on_mount(self):
        self.query_one(Header).tall = True
        self.query_one(FilterPopup).disabled = True
        self.query_one(ExportPopup).disabled = True
        self.total_count = self.filtered_count = len(self.events.all())
        self.populate_data_tables()

    def populate_data_tables(self, focus=True):
        ut = self.query_one(UserTable)
        et = self.query_one(EventTable)
        ed = self.query_one(EventDetail)

        if not self.events.all():
            ut.contents = et.contents = []
            ed.event = None

        elif not ut.has_class("hidden"):
            ut.contents = sorted(self.events.users(), key=str.lower)
            if focus:
                ut.focus()

        else:
            et.contents = self.events.all()
            if focus:
                et.focus()

    def action_toggle_dark(self):
        self.dark = not self.dark

        # In EventDetail we define "event" as reactive with always_update,
        # so this will force watch_event to be called which redraws the JSON
        # with the correct theme. We need to do this as the content of the
        # Static widget with our JSON is colored by rich which does not know
        # about dark mode. So when user toggles, we need to syntax highlight
        # the JSON with an appropriate theme.
        ed = self.query_one(EventDetail)
        ed.event = ed.event

    def action_toggle_layout(self):
        self.toggle_class("vertical")

    def action_copy(self):
        ed = self.query_one(EventDetail)
        if ed.event:
            pyperclip.copy(ed.event.to_json())

    def action_filter_popup(self):
        self.show_popup(FilterPopup)

    def action_export_popup(self):
        self.show_popup(ExportPopup)

    def action_toggle_users(self):
        ut = self.query_one(UserTable)
        ut.toggle_class("hidden")
        self.populate_data_tables()

    def dismiss_popup(self, name):
        p = self.query_one(name)
        p.disabled = True
        p.add_class("offscreen")
        self.set_focus(self.original_focus)
        self.refresh(repaint=True, layout=True)

    def show_popup(self, name):
        self.original_focus = self.query_one("*:focus")
        p = self.query_one(name)
        p.disabled = False
        p.remove_class("offscreen")
        p.query_one(Input).focus()

    def on_filter_popup_closed(self, _) -> None:
        self.dismiss_popup(FilterPopup)

    def on_filter_popup_changed(self, event: FilterPopup.Changed) -> None:
        # Only update the UI if the expression is different
        if event.value != self.events.filter_expr:
            self.filtered_count = self.events.filter(event.value)
            self.query_one(EventDetail).filter_expr = event.value
            self.populate_data_tables(focus=False)
        self.dismiss_popup(FilterPopup)

    def on_export_popup_closed(self, _) -> None:
        self.dismiss_popup(ExportPopup)

    def on_export_popup_changed(self, event: ExportPopup.Changed) -> None:
        try:
            with open(event.value, "w") as out:
                json.dump(
                    [e.event for e in self.events.all()],
                    default=str,
                    indent=4,
                    fp=out,
                )
            self.dismiss_popup(ExportPopup)
        except Exception:
            self.bell()

    def on_user_table_selection_changed(self, message: UserTable.SelectionChanged):
        et = self.query_one(EventTable)
        user = message.row_key
        if user:
            et.contents = self.events.by_user(user)

    def on_event_table_selection_changed(self, message: EventTable.SelectionChanged):
        ed = self.query_one(EventDetail)
        event_key = message.row_key
        if event_key:
            event = self.events.by_id(event_key)
            ed.event = event

    def watch_total_count(self):
        self.update_sub_title()

    def watch_filtered_count(self):
        self.update_sub_title()

    def update_sub_title(self):
        s = f"{self.total_count} events loaded"
        if self.filtered_count != self.total_count:
            s += f", {self.filtered_count} matched"
        self.sub_title = s


class EventDetail(Container, can_focus=True):
    DEFAULT_CSS = """
EventDetail {
  width: 1fr;
  overflow: auto scroll;
  border: solid $accent-lighten-2;
  border-title-align: left;
}
EventDetail:focus {
  border: solid $secondary;
}
.vertical EventDetail {
  height: 2fr;
}
EventDetail > Static {
  width: auto;
  min-width: 1fr;
}
    """

    # We need always update for toggling of themes to work.
    event: reactive[Optional[_UserIdentityType]] = reactive[
        Optional[_UserIdentityType]
    ](None, always_update=True)

    def __init__(self):
        super().__init__()
        self.filter_expr = ""

    def on_mount(self):
        self.border_title = "Event Detail"

    def compose(self) -> ComposeResult:
        yield Static()

    def watch_event(self, event):
        content = event.to_json() if event else ""
        matching_lines = self._find_matching_lines(content)

        self.query_one(Static).update(
            Syntax(
                content,
                "json",
                theme=EventViewer.theme["dark" if self.app.dark else "light"],
                highlight_lines=matching_lines,
                line_numbers=True,
            )
        )

    def _find_matching_lines(self, content):
        terms = [t.lower() for t in self.filter_expr.split() if not t.startswith("-")]
        matching_lines = set()
        for n, line in enumerate(content.split("\n"), start=1):
            for term in terms:
                if term in line.lower():
                    matching_lines.add(n)

        return matching_lines
