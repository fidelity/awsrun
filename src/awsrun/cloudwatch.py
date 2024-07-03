"""Provides a means of retrieving metrics from AWS CloudWatch.

This module provides the `CWMetrics` class that can be used to retrieve up to
500 metrics in a single AWS CloudWatch API call. Queue one or more metrics for
retrieval via `CWMetrics.add_metric`, and then invoke `CWMetrics.bulk_load` to
make the request to AWS. The results for each metric can be retrieved by
invoking the callable returned by `CWMetrics.add_metric`. For example:

    client = session.client("cloudwatch", region_name="us-east-1")
    cwm = CWMetrics(client, last=3600 * 16, samples=8)
    get_avg = cwm.add_metric("AWS/DX", "ConnectionBpsEgress", {"ConnectionId": "dxcon-xxxxxxx"}, "Average")
    get_p95 = cwm.add_metric("AWS/DX", "ConnectionBpsEgress", {"ConnectionId": "dxcon-xxxxxxx"}, "p95")
    get_max = cwm.add_metric("AWS/DX", "ConnectionBpsEgress", {"ConnectionId": "dxcon-xxxxxxx"}, "Maximum")

    # Make a single call to AWS to retrieve all metric data
    cwm.bulk_load()

    # All data has been loaded, let's print it out
    print("AVERAGE")
    for datetime, value in get_avg():
        print(datetime, value)

    print("P95")
    for datetime, value in get_p95():
        print(datetime, value)

    print("Maximum")
    for datetime, value in get_max():
        print(datetime, value)

"""

import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

_LOG = logging.getLogger(__name__)

# AWS limits the number of metric requets per call to get_metric_data.
_MAX_METRICS = 500


class _MetricResult:
    """Lightweight container to hold metric results."""

    __slots__ = ("timestamps", "values")

    def __init__(self, timestamps=None, values=None):
        self.timestamps = [] if timestamps is None else timestamps
        self.values = [] if values is None else values


class CWMetrics:
    """Retrieve one or more AWS CloudWatch metrics efficiently.

    This class uses the AWS CloudWatch get_metrics_data() API to retrieve up
    to 500 different metrics in a single API call. `client` must be a valid
    boto3 CloudWatch client. `last` is the number of seconds of data to
    retrieve. `samples` is the number of data points requested. By default,
    the `ingestion_interval` is 60 seconds. Note: this class does not support
    metrics with ingestion intervals less than 60 seconds.
    """

    def __init__(self, client, last=3600, samples=60, ingestion_interval=60):
        self._client = client
        self._last = last
        self._samples = samples
        self._ingestion_interval = ingestion_interval
        self._period = self._compute_period()
        self._beg = self._end = datetime.now()

        _LOG.info(
            "CWMetrics(client, last=%d, samples=%d, ingestion_interval=%d)",
            last,
            samples,
            ingestion_interval,
        )
        _LOG.info("Computed period: %d secs", self._period)

        # The list of metrics that have been added/requested
        self._queries = []

        # Provides a unique id for each metric (required by the CW API)
        self._counter = 0

        # Stores the results of the last bulk_load, keyed by the unique ID
        self._results = defaultdict(_MetricResult)

    def add_metric(self, namespace, name, dimensions, statistic):
        """Queue the specified CloudWatch metric for bulk loading.

        Use this method to register a metric for future retrieval via
        `CWMetric.bulk_load`. Up to 500 metrics can be added. Once a metric
        has been added, subsequent calls to `CWMetric.bulk_load` will retrieve
        it again.

        Returns a function that can be invoked after a bulk load has
        completed. It will return a generator object that yields a tuple
        containing a datetime object and a corresponding value at that time.
        Values are returned in ascending chronological order. The generator
        will yield a value for each time interval even if CloudWatch has
        missing data points. In that case, the value in the tuple will be a
        `math.nan`.
        """
        # We need to keep track of how many metrics are being retrieved as AWS
        # only permits up to 500 in a single get_metric_data call. We also
        # need a unique ID for each metric added as that is how we will match
        # the response from the CW API.
        self._counter += 1
        if self._counter > _MAX_METRICS:
            raise ValueError(f"number of metrics exceeded {_MAX_METRICS}")

        # The AWS get_metric_data call requires a unique ID for each metric
        # being retrieved. This ID is provided with the results, so the caller
        # is able to match request with response. The ID only needs to be
        # unique per call to get_metric_data, so we just use a simple counter
        # as we'll never expose this ID to callers.
        metric_id = f"id{self._counter}"

        # Convert a dict in form of {"connId": "dxcon-aaa"} to the form
        # required by AWS: [{"Name": "connId", "Value": "dxcon-aaa"}].
        dimensions = [{"Name": n, "Value": v} for n, v in dimensions.items()]

        # Create the query dict and append to the list of queries. The query
        # is not executed until later when the user calls bulk_load().
        self._queries.append(
            {
                "Id": metric_id,
                "MetricStat": {
                    "Metric": {
                        "Namespace": namespace,
                        "MetricName": name,
                        "Dimensions": dimensions,
                    },
                    "Period": int(self._period),
                    "Stat": statistic,
                },
                "ReturnData": True,
            }
        )

        # Return a closure to make it easy to retrieve results. After the user
        # has called bulk_load, this function can be executed to obtain the
        # results of the API call.
        return lambda: self._get_metric_generator(metric_id)

    def bulk_load(self):
        """Retrieve the metrics that have been queued.

        This method will make a single API call to AWS to request all of the
        requested metrics. This method may be called one or more times. Each
        call will retrieve the metrics that were requested replacing the
        results of a prior invocation.

        Returns nothing. Results for each metric can be obtained by invoking
        the callable returned from `CWMetric.add_metric`, which will return
        the data associated with the last bulk load.
        """
        if not self._queries:
            return

        self._results = defaultdict(_MetricResult)
        self._beg, self._end = self._compute_datetime_range()

        for page in self._client.get_paginator("get_metric_data").paginate(
            MetricDataQueries=self._queries,
            StartTime=self._beg.isoformat(),
            EndTime=self._end.isoformat(),
            ScanBy="TimestampAscending",
        ):
            for mdr in page["MetricDataResults"]:
                count = len(mdr["Values"])
                _LOG.info(
                    "Results for %s (%s): count=%d status=%s",
                    mdr["Label"],
                    mdr["Id"],
                    count,
                    mdr["StatusCode"],
                )
                if count > 1:
                    _LOG.info(" [0]: %s %.2f", mdr["Timestamps"][0], mdr["Values"][0])
                    _LOG.info(" [1]: %s %.2f", mdr["Timestamps"][1], mdr["Values"][1])
                    _LOG.info("[-2]: %s %.2f", mdr["Timestamps"][-2], mdr["Values"][-2])
                    _LOG.info("[-1]: %s %.2f", mdr["Timestamps"][-1], mdr["Values"][-1])

                # We use extend here because results can span multiple pages,
                # so we just keep extending to the existing lists.
                result = self._results[mdr["Id"]]
                result.values.extend(mdr["Values"])
                result.timestamps.extend(mdr["Timestamps"])

    def _get_metric_generator(self, metric_id):
        """Returns a generator to iterate over metric results.

        The generator yields (datetime, value) tuples for the results
        associated with the `metric_id`. This method is not called directly by
        users, but rather returned via a closure so we don't have to expose
        the `metric_id`.
        """
        result = self._results[metric_id]
        if not result.timestamps:
            return

        index = 0
        count = len(result.timestamps)
        clock = self._beg

        while clock < self._end:
            if index >= count or result.timestamps[index] != clock:
                yield clock, math.nan
            else:
                yield clock, result.values[index]
                index += 1

            clock += timedelta(seconds=self._period)

    def _compute_datetime_range(self):
        """Return aligned start and end datetime objects.

        Based the `last` number of seconds, the total number of `samples`, and a
        `period` in seconds, compute aligned start and end datetimes for efficient
        retrieval of metrics from CloudWatch based on the AWS API documentation.
        """

        end = datetime.now(timezone.utc)
        _LOG.info("Current time: %s", end)

        # We go back in time by the ingestion period of the stat to give
        # CloudWatch time to process the last metric because we don't want to
        # include an interval that has missing data.
        end -= timedelta(seconds=self._ingestion_interval)

        # We go back in time by an additional half-period so we make sure we
        # have enough data when aggregating a large number of data points.
        # It's unclear what data points are aggregated by AWS at time T1. Does
        # it include all points from T1 - period to T1? Or does it include all
        # points from T1 - period/2 to T1 + period/2? I believe it is the
        # latter, so we go back by half a period.
        end -= timedelta(seconds=self._period / 2)

        # Finally, we align this start time appropriately based on the period.
        end = self._align_datetime(end)
        _LOG.info("Timestamp for last metric: %s", end)

        # Add one period to the end because the end time is exclusive per AWS
        # docs and will not be included in results.
        end = end + timedelta(seconds=self._period)
        _LOG.info("Timestamp for CW end time: %s", end)

        # Compute the start time for CloudWatch, which is inclusive per AWS
        # docs, so we don't need to do any extra padding.
        beg = end - timedelta(seconds=self._period * self._samples)
        _LOG.info("Timestamp for CW beg time: %s", beg)

        return beg, end

    def _compute_period(self):
        """Return an aligned period/interval in seconds.

        Based the `last` number of seconds and the total number of `samples`
        requested, compute a valid period/interval that is aligned based on the
        AWS CloudWatch documentation.
        """
        period = self._last // self._samples

        if period < self._ingestion_interval:
            raise ValueError(f"{period}s period is less than ingestion interval")

        if self._last < 86400 * 15:
            return period - period % max(60, self._ingestion_interval)

        if self._last < 86400 * 63:
            return period - period % 300

        return period - period % 3600

    def _align_datetime(self, dt):
        """Return an aligned datetime based on last number of seconds requested.

        The AWS CloudWatch API datetimes should be aligned based on a minute,
        5-minute, or 1-hour mark depending on start time.
        """

        if self._last < 86400 * 15 and self._ingestion_interval <= 60:
            # Round down to the 1-minute
            dt = dt.replace(second=0, microsecond=0)

        elif self._last < 86400 * 63 and self._ingestion_interval <= 300:
            # Round down to the 5-minute
            dt = (dt - timedelta(minutes=dt.minute % 5)).replace(
                second=0, microsecond=0
            )
        else:
            # Round down to the hour
            dt = dt.replace(minute=0, second=0, microsecond=0)

        # AWS suggests aligning start and end times based on a multiple of the
        # period. So, with a period of 5 mins, start and end times should be
        # 12:05 and 12:35 versus 12:07 and 12:37.
        period_minute = (self._period // 60) % 60
        return dt - timedelta(
            minutes=(dt.minute % period_minute) if period_minute else dt.minute
        )


def get_metric(client, namespace, name, dimensions, statistic, last=3600, samples=60):
    """Fetch data for the specified CloudWatch metric immediately.

    This is a convenience method that should only be used if retrieving a
    single metric. If multiple metrics are desired, it is more efficient to
    use `CWMetric` instead.

    Returns a generator object that yields a tuple containing a datetime
    object and a corresponding value at that time. Values are returned in
    ascending chronological order. The generator will yield a value for each
    time interval even if CloudWatch has missing data points. In that case,
    the value in the tuple will be a `math.nan`.
    """
    cwm = CWMetrics(client, last, samples)
    get_values = cwm.add_metric(namespace, name, dimensions, statistic)
    cwm.bulk_load()
    return get_values()
