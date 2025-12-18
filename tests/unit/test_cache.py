#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

# pylint: disable=redefined-outer-name,missing-docstring

import json
import os
import random
import time
from datetime import timedelta

import pytest
from freezegun import freeze_time

from awsrun import cache


class TestExpiringValue:
    """Tests for ExpiringValue."""

    def test_caching(self):
        with freeze_time() as frozen_datetime:
            ev = cache.ExpiringValue(random.random, max_age=300)
            initial_value = ev.value()

            frozen_datetime.tick(delta=timedelta(seconds=60))
            assert ev.value() == initial_value, (
                "value was different, should have been cached"
            )

            # Fast forward to 5 minutes after we first cached the value
            frozen_datetime.tick(delta=timedelta(seconds=241))
            second_value = ev.value()
            assert second_value != initial_value, (
                "value was the same, should have expired"
            )

            # Make sure the second value was cached
            frozen_datetime.tick(delta=timedelta(seconds=60))
            assert ev.value() == second_value, (
                "value was different, should have been cached"
            )

    def test_no_caching(self):
        ev = cache.ExpiringValue(random.random, max_age=0)
        value1 = ev.value()
        value2 = ev.value()
        value3 = ev.value()
        assert len({value1, value2, value3}) == 3, "values should not be cached"


class TestValueWithExpiry:
    """Tests for the ValueWithExpiry wrapper class."""

    def test_ttl_sets_expires_at(self):
        with freeze_time("2025-01-01 12:00:00") as frozen_datetime:
            wrapper = cache.ValueWithExpiry("test_value", ttl=3600)
            assert wrapper.value == "test_value"
            # expires_at should be current time + ttl
            expected_expiry = time.time() + 3600
            assert wrapper.expires_at == expected_expiry

    def test_expires_at_sets_directly(self):
        wrapper = cache.ValueWithExpiry("test_value", expires_at=1234567890)
        assert wrapper.value == "test_value"
        assert wrapper.expires_at == 1234567890

    def test_must_specify_ttl_or_expires_at(self):
        with pytest.raises(ValueError, match="Must specify either ttl or expires_at"):
            cache.ValueWithExpiry("test_value")

    def test_cannot_specify_both_ttl_and_expires_at(self):
        with pytest.raises(ValueError, match="Cannot specify both ttl and expires_at"):
            cache.ValueWithExpiry("test_value", ttl=3600, expires_at=1234567890)

    def test_repr(self):
        wrapper = cache.ValueWithExpiry("test_value", expires_at=1234567890)
        assert (
            repr(wrapper)
            == "ValueWithExpiry(value='test_value', expires_at=1234567890)"
        )


class TestExpiringValueWithDynamicExpiry:
    """Tests for ExpiringValue with ValueWithExpiry."""

    def test_dynamic_expiry_with_ttl(self):
        with freeze_time() as frozen_datetime:
            call_count = 0

            def refresh_fn():
                nonlocal call_count
                call_count += 1
                # Return value with 60 second TTL
                return cache.ValueWithExpiry({"token": f"token_{call_count}"}, ttl=60)

            ev = cache.ExpiringValue(
                refresh_fn, max_age=300
            )  # max_age ignored when wrapper used
            initial_value = ev.value()
            assert initial_value == {"token": "token_1"}

            # After 30 seconds, should still be cached
            frozen_datetime.tick(delta=timedelta(seconds=30))
            assert ev.value() == {"token": "token_1"}

            # After 61 seconds total, should expire (using wrapper's 60s TTL, not 300s max_age)
            frozen_datetime.tick(delta=timedelta(seconds=31))
            assert ev.value() == {"token": "token_2"}

    def test_dynamic_expiry_with_expires_at(self):
        with freeze_time() as frozen_datetime:
            call_count = 0

            def refresh_fn():
                nonlocal call_count
                call_count += 1
                # Return value with absolute expiry 120 seconds from now
                return cache.ValueWithExpiry(
                    {"token": f"token_{call_count}"}, expires_at=time.time() + 120
                )

            ev = cache.ExpiringValue(refresh_fn, max_age=300)
            initial_value = ev.value()
            assert initial_value == {"token": "token_1"}

            # After 100 seconds, should still be cached
            frozen_datetime.tick(delta=timedelta(seconds=100))
            assert ev.value() == {"token": "token_1"}

            # After 121 seconds total, should expire
            frozen_datetime.tick(delta=timedelta(seconds=21))
            assert ev.value() == {"token": "token_2"}

    def test_mixed_plain_and_wrapped_values(self):
        """Test that switching between plain values and wrapped values works."""
        with freeze_time() as frozen_datetime:
            call_count = 0
            use_dynamic_expiry = False

            def refresh_fn():
                nonlocal call_count
                call_count += 1
                if use_dynamic_expiry:
                    return cache.ValueWithExpiry(f"wrapped_{call_count}", ttl=30)
                return f"plain_{call_count}"

            ev = cache.ExpiringValue(refresh_fn, max_age=60)

            # First call returns plain value
            assert ev.value() == "plain_1"

            # Force refresh with wrapped value
            use_dynamic_expiry = True
            assert ev.value(refresh=True) == "wrapped_2"

            # Should expire after 30 seconds (wrapper TTL)
            frozen_datetime.tick(delta=timedelta(seconds=31))
            use_dynamic_expiry = False
            assert ev.value() == "plain_3"


class TestPersistentExpiringValueWithDynamicExpiry:
    """Tests for PersistentExpiringValue with ValueWithExpiry."""

    def test_dynamic_expiry_persisted(self, tmp_path):
        with freeze_time() as frozen_datetime:
            cache_file = tmp_path / "test.dat"
            call_count = 0

            def refresh_fn():
                nonlocal call_count
                call_count += 1
                return cache.ValueWithExpiry({"token": f"token_{call_count}"}, ttl=60)

            ev = cache.PersistentExpiringValue(refresh_fn, cache_file, max_age=300)
            initial_value = ev.value()
            assert initial_value == {"token": "token_1"}
            assert cache_file.exists()

            # After 30 seconds, should still be cached
            frozen_datetime.tick(delta=timedelta(seconds=30))
            assert ev.value() == {"token": "token_1"}

            # After 61 seconds total, should expire (using wrapper's 60s TTL)
            frozen_datetime.tick(delta=timedelta(seconds=31))
            assert ev.value() == {"token": "token_2"}

    def test_dynamic_expiry_survives_reload(self, tmp_path):
        """Test that dynamic expiry is restored when loading from disk."""
        with freeze_time() as frozen_datetime:
            cache_file = tmp_path / "test.dat"

            def refresh_fn():
                return cache.ValueWithExpiry({"token": "original"}, ttl=120)

            # Create first instance and cache the value
            ev1 = cache.PersistentExpiringValue(refresh_fn, cache_file, max_age=300)
            assert ev1.value() == {"token": "original"}

            # Simulate time passing
            frozen_datetime.tick(delta=timedelta(seconds=60))

            # Create new instance (simulating process restart)
            def refresh_fn_new():
                return cache.ValueWithExpiry({"token": "refreshed"}, ttl=120)

            ev2 = cache.PersistentExpiringValue(refresh_fn_new, cache_file, max_age=300)

            # Should load cached value and restore dynamic expiry
            assert ev2.value() == {"token": "original"}

            # After another 61 seconds (121 total), should expire
            frozen_datetime.tick(delta=timedelta(seconds=61))
            assert ev2.value() == {"token": "refreshed"}

    def test_backwards_compatible_with_plain_cache_files(self, tmp_path):
        """Test that existing cache files without metadata still work."""
        cache_file = tmp_path / "test.dat"

        # Manually create a cache file in the old format (no metadata)
        with cache_file.open("w", encoding="utf-8") as f:
            json.dump({"legacy": "data"}, f)

        # Set file mtime to 400 seconds in the past so it's already expired
        old_mtime = time.time() - 400
        os.utime(str(cache_file), (old_mtime, old_mtime))

        call_count = 0

        def refresh_fn():
            nonlocal call_count
            call_count += 1
            return {"new": f"data_{call_count}"}

        ev = cache.PersistentExpiringValue(refresh_fn, cache_file, max_age=300)

        # File is older than max_age, should refresh
        assert ev.value() == {"new": "data_1"}
        assert call_count == 1

        # Now create a fresh file that's not expired
        cache_file2 = tmp_path / "test2.dat"
        with cache_file2.open("w", encoding="utf-8") as f:
            json.dump({"legacy": "data"}, f)

        # mtime is now (just created), so not expired
        call_count = 0
        ev2 = cache.PersistentExpiringValue(refresh_fn, cache_file2, max_age=300)

        # File is fresh, should load legacy data
        assert ev2.value() == {"legacy": "data"}
        assert call_count == 0, "Should not have called refresh_fn"

    def test_dynamic_expiry_with_zero_max_age_still_caches(self, tmp_path):
        """Test that ValueWithExpiry causes caching even when max_age=0."""
        with freeze_time() as frozen_datetime:
            cache_file = tmp_path / "test.dat"
            call_count = 0

            def refresh_fn():
                nonlocal call_count
                call_count += 1
                return cache.ValueWithExpiry({"token": f"token_{call_count}"}, ttl=60)

            ev = cache.PersistentExpiringValue(refresh_fn, cache_file, max_age=0)
            assert ev.value() == {"token": "token_1"}
            assert cache_file.exists(), (
                "File should be created when using ValueWithExpiry"
            )

            # Should still be cached after 30 seconds
            frozen_datetime.tick(delta=timedelta(seconds=30))
            assert ev.value() == {"token": "token_1"}
            assert call_count == 1, "Should not have called refresh_fn again"

    def test_expiry_file_created_and_removed(self, tmp_path):
        """Test that expiry file is created when using dynamic expiry and removed otherwise."""
        cache_file = tmp_path / "test.dat"
        expiry_file = tmp_path / "test.dat.expiry"

        call_count = 0
        use_dynamic_expiry = True

        def refresh_fn():
            nonlocal call_count
            call_count += 1
            if use_dynamic_expiry:
                return cache.ValueWithExpiry({"token": f"token_{call_count}"}, ttl=60)
            return {"token": f"token_{call_count}"}

        ev = cache.PersistentExpiringValue(refresh_fn, cache_file, max_age=300)

        # First call with dynamic expiry - expiry file should be created
        ev.value()
        assert cache_file.exists()
        assert expiry_file.exists(), (
            "Expiry file should be created when using ValueWithExpiry"
        )

        # Force refresh without dynamic expiry - expiry file should be removed
        use_dynamic_expiry = False
        ev.value(refresh=True)
        assert cache_file.exists()
        assert not expiry_file.exists(), (
            "Expiry file should be removed when not using ValueWithExpiry"
        )

    def test_corrupted_expiry_file_raises_error(self, tmp_path):
        """Test that a corrupted expiry file raises an error instead of silently failing."""
        cache_file = tmp_path / "test.dat"
        expiry_file = tmp_path / "test.dat.expiry"

        # Create cache file with valid data
        with cache_file.open("w", encoding="utf-8") as f:
            json.dump({"token": "cached"}, f)

        # Create corrupted expiry file
        expiry_file.write_text("not_a_valid_timestamp", encoding="utf-8")

        def refresh_fn():
            return {"token": "refreshed"}

        ev = cache.PersistentExpiringValue(refresh_fn, cache_file, max_age=300)

        with pytest.raises(ValueError):
            ev.value()


class TestPersistentExpiringValue:
    """Tests for PersistentExpiringValue."""

    def test_caching(self, tmp_path):
        with freeze_time() as frozen_datetime:
            cache_file = tmp_path / "test.dat"
            assert not cache_file.exists()

            ev = cache.PersistentExpiringValue(random.random, cache_file, max_age=300)
            initial_value = ev.value()
            assert cache_file.exists()

            frozen_datetime.tick(delta=timedelta(seconds=60))
            assert ev.value() == initial_value, (
                "value was different, should have been cached"
            )

            # Fast forward to 5 minutes after we first cached the value
            frozen_datetime.tick(delta=timedelta(seconds=241))
            second_value = ev.value()
            assert second_value != initial_value, (
                "value was the same, should have expired"
            )

            # Because freezegun cannot adjust the time of the OS and timestamps
            # of files, we'll have to update the mtime of the cache file ourself.
            mtime = time.mktime(frozen_datetime().timetuple())
            os.utime(str(cache_file), (mtime, mtime))

            # Make sure the second value was cached
            frozen_datetime.tick(delta=timedelta(seconds=60))
            assert ev.value() == second_value, (
                "value was different, should have been cached"
            )

    def test_no_caching(self, tmp_path):
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
