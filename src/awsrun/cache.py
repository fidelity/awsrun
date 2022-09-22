#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Provides the ability to cache single values.

## Overview

The module provides the `AbstractExpiringValue` abstract base class, which is
responsible for the lazy loading of a value that is cached for a finite amount
of time. The base class provides the core functionality that depends on the
subclass's implementation of `is_expired`, `load`, and `save`.

Two concrete implementations are provided in this module. The first,
`ExpiringValue`, caches the value in memory, while the second,
`PersistentExpiringValue` caches the value to disk as JSON. The following
example demonstrates how to use this `ExpiringValue`:

    >>> import time
    >>> ev = ExpiringValue(refresh_fn=time.ctime, max_age=10)
    >>> ev.value(); time.sleep(5); ev.value(); time.sleep(5); ev.value()
    'Sat Jul 13 15:04:30 2019'
    'Sat Jul 13 15:04:30 2019'
    'Sat Jul 13 15:04:40 2019'

The first two timestamps are the same because `value` was 5 seconds apart, which
is before the value would have expired, and thus the cached result is returned.
The third value, however, is ten seconds later because by the time the third
invocation of `value` took place, the original value expired after 10 seconds.
"""

import json
import logging
import threading
import time
from pathlib import Path

LOG = logging.getLogger(__name__)


class AbstractExpiringValue:
    """Abstract base class to represent a value that expires.

    An `AbstractExpiringValue` represents a lazily loaded value that will expire
    over time. The constructor takes a `refresh_fn` function of zero arguments,
    which is called to obtain the value to be cached for `max_age` seconds.

    At the time of instantiation, the value is not retrieved, it is only
    retrieved the first time the value method is invoked. Likewise, the value is
    not refreshed at the time it expires, but only the next time the value
    method is called. This class is thread-safe. Subclasses must provide
    implementations for `is_expired`, `load`, and `save`.
    """

    def __init__(self, refresh_fn, max_age):
        self._refresh_fn = refresh_fn
        self._max_age = max_age
        self._lock = threading.Lock()

    def value(self, refresh=False):
        """Returns the value.

        The first time this method is called, the value will be obtained by
        calling the `refresh_fn` supplied in the constructor. Subsequent
        invocations of this method will return the cached value until it
        expires. If you set `refresh` parameter to `True`, the value will be
        refreshed and the expiration will be reset before being returned.
        """
        with self._lock:
            if not refresh and not self.is_expired():
                return self.load()

            value = self._refresh_fn()
            self.save(value)
            LOG.info("refreshed data and saved in cache")
            return value

    def is_expired(self):
        """Returns `True` if the value needs to be refreshed, `False` otherwise.

        If this returns `True` during the invocation of
        `AbstractExpiringValue.value`, the `refresh_fn` will be called, followed
        by `save`, to renew the cached value. When this returns `False`, `load`
        is invoked instead to return the value from the cache.
        """
        raise NotImplementedError

    def load(self):
        """Returns the value from the cache.

        If `is_expired` returns `False` during the invocation of
        `AbstractExpiringValue.value`, this method is invoked to return the
        value from the cache.
        """
        raise NotImplementedError

    def save(self, value):
        """Saves the value to the cache.

        If `is_expired` returns `True` during the invocation of
        `AbstractExpiringValue.value`, this method is invoked to save the new
        value to the cache.
        """
        raise NotImplementedError


class ExpiringValue(AbstractExpiringValue):
    """Represents a lazily loaded value that will expire over time.

    An `ExpiringValue` represents a lazily loaded value that will expire over
    time and is cached in memory. The constructor takes a `refresh_fn` function
    of zero arguments, which is called to obtain the value to be cached for
    `max_age` seconds.

    At the time of instantiation, the value is not retrieved, it is only
    retrieved the first time the value method is invoked. Likewise, the value is
    not refreshed at the time it expires, but only the next time the value
    method is called. This class is thread-safe.
    """

    def __init__(self, refresh_fn, max_age):
        super().__init__(refresh_fn, max_age)
        self._value = None
        self._expiry = 0

    def is_expired(self):
        return time.time() >= self._expiry

    def load(self):
        LOG.debug("Loading data from cache")
        return self._value

    def save(self, value):
        LOG.debug("Saving value to cache")
        self._value = value
        self._expiry = time.time() + self._max_age


class PersistentExpiringValue(ExpiringValue):
    """Represents an expiring value that will be persisted to disk as JSON.

    A `PersistentExpiringValue` represents a lazily loaded value that will
    expire over time and is cached to disk as JSON. The constructor takes a
    `refresh_fn` function of zero arguments, which is called to obtain the value
    to be cached for `max_age` seconds to the file specified by the `path` --
    either a string or a `pathlib.Path` object.

    At the time of instantiation, the value is not retrieved, it is only
    retrieved the first time the value method is invoked. Likewise, the value is
    not refreshed at the time it expires, but only the next time the value
    method is called. This class is thread-safe. If the value cannot be
    persisted as JSON, a TypeError is thrown.
    """

    def __init__(self, refresh_fn, path, max_age):
        super().__init__(refresh_fn, max_age)
        self._path = path if isinstance(path, Path) else Path(path)

    def is_expired(self):
        if not self._path.exists():
            return True
        last_modification = self._path.stat().st_mtime
        return time.time() > last_modification + self._max_age

    def load(self):
        LOG.debug("Loading cached data from %s", self._path)
        with self._path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def save(self, value):
        # No need to persist the file if max_age is 0 seconds.
        if self._max_age == 0:
            return

        LOG.debug("Saving data to cache file %s", self._path)
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as file:
            json.dump(value, file)

        # Pathlib.replace uses os.replace which is atomic on POSIX systems
        tmp.replace(self._path)
