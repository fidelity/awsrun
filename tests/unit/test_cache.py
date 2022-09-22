#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#

# pylint: disable=redefined-outer-name,missing-docstring

import os
import random
import time
from datetime import timedelta

from freezegun import freeze_time

from awsrun import cache


def test_expiring_value_caching():
    with freeze_time() as frozen_datetime:
        ev = cache.ExpiringValue(random.random, max_age=300)
        initial_value = ev.value()

        frozen_datetime.tick(delta=timedelta(seconds=60))
        assert (
            ev.value() == initial_value
        ), "value was different, should have been cached"

        # Fast forward to 5 minutes after we first cached the value
        frozen_datetime.tick(delta=timedelta(seconds=241))
        second_value = ev.value()
        assert second_value != initial_value, "value was the same, should have expired"

        # Make sure the second value was cached
        frozen_datetime.tick(delta=timedelta(seconds=60))
        assert (
            ev.value() == second_value
        ), "value was different, should have been cached"


def test_expiring_value_no_caching():
    ev = cache.ExpiringValue(random.random, max_age=0)
    value1 = ev.value()
    value2 = ev.value()
    value3 = ev.value()
    assert len({value1, value2, value3}) == 3, "values should not be cached"


def test_persistent_expiring_value_caching(tmp_path):
    with freeze_time() as frozen_datetime:
        cache_file = tmp_path / "test.dat"
        assert not cache_file.exists()

        ev = cache.PersistentExpiringValue(random.random, cache_file, max_age=300)
        initial_value = ev.value()
        assert cache_file.exists()

        frozen_datetime.tick(delta=timedelta(seconds=60))
        assert (
            ev.value() == initial_value
        ), "value was different, should have been cached"

        # Fast forward to 5 minutes after we first cached the value
        frozen_datetime.tick(delta=timedelta(seconds=241))
        second_value = ev.value()
        assert second_value != initial_value, "value was the same, should have expired"

        # Because freezegun cannot adjust the time of the OS and timestamps
        # of files, we'll have to update the mtime of the cache file ourself.
        mtime = time.mktime(frozen_datetime().timetuple())
        os.utime(str(cache_file), (mtime, mtime))

        # Make sure the second value was cached
        frozen_datetime.tick(delta=timedelta(seconds=60))
        assert (
            ev.value() == second_value
        ), "value was different, should have been cached"


def test_persistent_expiring_value_no_caching(tmp_path):
    cache_file = tmp_path / "test.dat"
    assert not cache_file.exists()

    ev = cache.PersistentExpiringValue(random.random, cache_file, max_age=0)
    value1 = ev.value()
    assert not cache_file.exists()

    value2 = ev.value()
    assert not cache_file.exists()

    value3 = ev.value()
    assert not cache_file.exists()

    assert len({value1, value2, value3}) == 3, "values should not be cached"
