#
# Copyright 2022 FMR LLC <opensource@fmr.com>
#
# SPDX-License-Identifier: MIT
#
"""Display Direct Connect maintenance events from AWS Health.

## Overview

The dx_maint command displays a summary of Direct Connect maintenance events
available from the AWS Health service sorted by the time AWS published the
event, which is not necessarily the start of maintenance.  Only recent events
(past 7 days) and upcoming events are displayed by default.

    $ awsrun --account 111222333444 --account 222111444333 dx_maint --region us-east-1 --region us-west-2
    111222333444 us-east-1 2021-11-19 09:11 CST closed MAINTENANCE_CANCELLED 2021-11-23 02:11 CST -> 2021-11-23 06:11 CST dxcon-aaaaaaaa available
    111222333444 us-west-2 2021-12-07 05:12 CST closed MAINTENANCE_COMPLETE 2021-12-07 03:12 CST -> 2021-12-07 07:12 CST dxcon-bbbbbbbb available
    111222333444 us-east-1 2022-01-18 02:01 CST closed MAINTENANCE_COMPLETE 2022-01-17 22:01 CST -> 2022-01-18 02:01 CST dxcon-cccccccc available
    222111444333 us-east-1 2022-01-31 21:01 CST upcoming MAINTENANCE_SCHEDULED 2022-02-14 22:02 CST -> 2022-02-15 02:02 CST dxcon-dddddddd available
    111222333444 us-east-1 2022-02-01 21:02 CST upcoming MAINTENANCE_SCHEDULED 2022-02-08 22:02 CST -> 2022-02-09 02:02 CST dxcon-eeeeeeee available

For non-emergency maintenance events that occurred in the past, the default
output only shows the COMPLETED or CANCELLED event to minimize on noise. For
emergency maintenance events, both the SCHEDULED and COMPLETED/CANCELLED events
are displayed as AWS doesn't link the scheduling and completion events for
emergency events.  To see all events, specify the `--verbose` flag.

To obtain a more historical listing, provide the `--days` option with an integer
number of days to show. The default value is seven (7).

Events for all Direct Connect connections are returned by default. To request
information for specific connections, provide one or more `--dx` options with
the Direct Connect ID.

    $ awsrun --account 111222333444 dx_maint --dx dxcon-aaaaaa --dx dxcon-bbbbbb --region us-east-1
    111222333444 us-east-1 2021-11-19 09:11 CST closed MAINTENANCE_CANCELLED 2021-11-23 02:11 CST -> 2021-11-23 06:11 CST dxcon-aaaaaaaa available
    111222333444 us-west-2 2021-12-07 05:12 CST closed MAINTENANCE_COMPLETE 2021-12-07 03:12 CST -> 2021-12-07 07:12 CST dxcon-bbbbbbbb available

## Reference

### Synopsis

    $ awsrun [options] dx_maint [command options]

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      dx_maint:
        days: INT
        no_color: BOOLEAN
        verbose: BOOLEAN
        dx_conn_ids:
          - STRING

### Command Options
Some options can be overridden on the awsrun CLI via command line flags. In
those cases, the CLI flags are specified next to the option name below:

`verbose`, `--verbose`
: Do not suppress the original SCHEDULED event for a maintenance that has
already been completed or cancelled.  By default, dx_maint only shows the last
meaningful event.

`no_color`, `--no-color`
: Do not colorize the output to the terminal. By default, columns are colorized
for readability.

`days`, `--days INT`
: Specifies how many days ago to show closed events. By default, only the past
seven days of closed events are displayed.  Regardless of this value, all open
events are always shown.

`dx_conn_ids`, `--dx DXCON_ID`
: Display events only for the specified Direct Connect connection IDs. When
specifying multiple values on the command line, use multiple flags for each
value.

"""

import itertools
import logging
import re
import sys
from datetime import datetime, timedelta

from awsrun.config import Bool, Int, List, Str
from awsrun.runner import RegionalCommand, get_paginated_resources

try:
    import colorama
    from colorama import Fore, Style

except ImportError:
    sys.exit(
        """
The 'dx_maint' command requires dependencies not installed by default with
awsrun. Please install them with the following command:

    pip install awsrun[dx-maint]
"""
    )


LOG = logging.getLogger(__name__)


class CLICommand(RegionalCommand):
    """Display Direct Connect maintenance events"""

    @classmethod
    def regional_from_cli(cls, parser, argv, cfg):
        parser.add_argument(
            "--days",
            type=int,
            default=cfg("days", type=Int, default=7),
            help="How many days of past maintenance to display",
        )
        parser.add_argument(
            "--dx",
            dest="requested_dxs",
            action="append",
            default=cfg("dx_conn_ids", type=List(Str), default=[]),
            help="Direct Connect ID",
        )
        parser.add_argument(
            "--no-color",
            action="store_true",
            default=cfg("no_color", type=Bool, default=False),
            help="Disable color in terminal output",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            default=cfg("verbose", type=Bool, default=False),
            help="Do not suppress the original SCHEDULED events",
        )
        args = parser.parse_args(argv)
        return cls(**vars(args))

    def __init__(self, regions, days, requested_dxs, verbose=False, no_color=False):
        super().__init__(regions)
        self.from_time = datetime.now().astimezone() - timedelta(days=days)
        self.verbose = verbose
        self.enable_color = not no_color
        self.requested_dxs = requested_dxs
        self.all_results = []
        if self.enable_color:
            colorama.init()

    def regional_execute(self, session, acct, region):
        # Retrieve the DX connections for the region as we'll use these as a
        # filter when retrieving the affected entities from the AWS Health API.
        dx_conns = {}
        dxc = session.client("directconnect", region_name=region)
        for conn in dxc.describe_connections()["connections"]:
            id_ = conn["connectionId"]
            LOG.info("%s/%s: found DX %s", acct, region, id_)

            # If user didn't request specific DXs, then we add it to our list,
            # but if they did request a specific DX, only add it if it matches.
            if (not self.requested_dxs) or (id_ in self.requested_dxs):
                dx_conns[id_] = conn

        # No need to make any AWS Health API calls if there are no DXs for this
        # acct/region as we won't find any events, so let's just move to the
        # next acct/region.
        if not dx_conns:
            return []

        # Health is a global service with an endpoint in us-east-1 only. Access
        # it from there regardless of the RegionalCommand region.  We pull all
        # events for the given region starting at the time specified.
        health = session.client("health", region_name="us-east-1")
        events = get_paginated_resources(
            health,
            "describe_events",
            "events",
            filter={
                "regions": [region],
                "startTimes": [{"from": self.from_time}],
            },
        )

        # Convert the list of events into a dict of events keyed by the ARN.
        # We'll use this dict when we pull the list of affected entities later
        # as each enitity refers to the ARN of the event it is impacted by.
        event_arns = {e["arn"]: e for e in events}
        LOG.info("%s/%s: found %d health events", acct, region, len(event_arns))

        # No need to go further if there are no events for this acct/region, so
        # let's just move to the next acct/region.
        if not event_arns:
            return []

        # Now we will pull the list of affected entities from the Health API. We
        # will use an event filter to limit our query to the ARNs of the events
        # we pulled from above as well as the DX connections as entity filters.
        # The only trick here is that the AWS API only allows 10 events at a
        # time in the event filter and up to 99 entities in the entity filter.
        # So we need to repeatedly make multiple calls.
        entities = []
        for arns_chunk in chunk(event_arns.keys(), 10):  # AWS API limits 10 events
            for conns_chunk in chunk(dx_conns.keys(), 99):  # AWS API limits 99 entities
                partial_entities = get_paginated_resources(
                    health,
                    "describe_affected_entities",
                    "entities",
                    # Sometimes the AWS API returns "UNKNOWN" as the entityValue
                    # even though we requested only entities matching our direct
                    # connects. So we use the predicate below to exclude any
                    # entities not in our direct connect list.
                    lambda e: e["entityValue"] in dx_conns,
                    filter={
                        "eventArns": arns_chunk,
                        "entityValues": conns_chunk,
                    },
                )
                entities.extend(partial_entities)

        LOG.info("%s/%s: found %d affected entities", acct, region, len(entities))

        # We reverse sort the affected entities by the last updated time. This
        # is the last time AWS updated the associated event. We do this because
        # we only want the most recent maintenance event for a DX. For example,
        # after an event has passed, we would normally see a SCHEDULED event
        # followed by a COMPLETED or CANCELLED event. In this case, we only care
        # about the COMPLETED or CANCELLED event (unless user has specified
        # verbose output). So, by reverse sorting by time, we use a set to keep
        # track if we've already seen an entity for a given DX and event.
        entities.sort(key=lambda e: e["lastUpdatedTime"], reverse=True)

        results = []
        already_seen = set()
        for entity in entities:
            arn = entity["eventArn"]
            dx_id = entity["entityValue"]
            dx = dx_conns[dx_id]
            event = event_arns[arn]
            event_hash = re.sub("^.*_", "", arn)
            if self.verbose or (dx_id, event_hash) not in already_seen:
                already_seen.add((dx_id, event_hash))
                results.append((acct, region, dx, event))

        # Results is a list of tuples for each affected entity / event.  We
        # return this and use awsrun collect_results lifecycle method to safely
        # collect results from one or more concurrently running awsrun threads
        # processing accounts.
        return results

    def regional_collect_results(self, acct, region, get_result):
        try:
            # Accumulate all of the results (tuples of acct, region, dx, and
            # event) into a single list that we'll consume later in the awsrun
            # post hook method.  The awsrun collect results lifecycle method is
            # guaranteed to run serially in the main thread after a worker
            # thread has finished processing an accout from the execute method.
            # This is why it is safe to modify the all_results instance variable
            # in this method, but not the execute method above.
            self.all_results.extend(get_result())

        except Exception as e:  # pylint: disable=broad-except
            LOG.warning("%s/%s: error: %s", acct, region, e, exc_info=True)
            print(f"{acct}/{region}: error: {e}", flush=True, file=sys.stderr)

    def post_hook(self):
        # The awsrun post hook is called once after all accounts have been
        # processed. At this point, we have collected everything we need in the
        # all_results instance variable. We sort this list by the last update
        # time as we want to display the maintenance events in the order they
        # were published by AWS. You might ask why don't we sort by the
        # maintenance start time?  Because AWS sometimes does not publish a
        # start time for an event (I have no idea why).
        self.all_results.sort(key=lambda r: r[3]["lastUpdatedTime"])

        for acct, region, dx, event in self.all_results:
            for color, field in (
                (None, acct),
                (None, region),
                (Fore.MAGENTA, date(event.get("lastUpdatedTime"))),
                (Fore.CYAN, event["statusCode"]),
                (Style.BRIGHT, shorten(event["eventTypeCode"])),
                (Fore.RED, date(event.get("startTime"))),
                (None, "->"),
                (Fore.GREEN, date(event.get("endTime"))),
                (Fore.BLUE, dx["connectionId"]),
                (Fore.MAGENTA, dx["connectionState"]),
                (Fore.YELLOW, dx["connectionName"]),
            ):
                if self.enable_color and color:
                    field = colorize(color, field)
                print(field, end=" ")
            print()


def chunk(it, n):
    """Yield successive n-sized chunks from it.

    >>> l = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    >>> list(chunk(l, 3))
    [(1, 2, 3), (4, 5, 6), (7, 8, 9)]
    >>> list(chunk(l, 2))
    [(1, 2), (3, 4), (5, 6), (7, 8), (9,)]
    """
    it = iter(it)
    return iter(lambda: tuple(itertools.islice(it, n)), ())


def colorize(color, string):
    """Return a string wrapped with ASCII color."""
    return f"{color}{string}{Style.RESET_ALL}"


def date(date_time):
    """Return a human readable string for a datetime object."""
    return date_time.strftime("%Y-%m-%d %H:%m %Z") if date_time else "not provided"


def shorten(event_type):
    """Trim 'AWS_DIRECTCONNECT_' from event_type name."""
    return re.sub("^AWS_DIRECTCONNECT_", "", event_type)
