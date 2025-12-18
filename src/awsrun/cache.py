#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
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

## Dynamic Expiration

In some cases, the expiration time is only known after the value has been
obtained (e.g., OAuth2 tokens include expiration in the response). Use
`ValueWithExpiry` to wrap the value with a custom expiration. This overrides
the `max_age` specified in the `ExpiringValue` constructor. For example:

    >>> def fetch_token():
    ...     token = {'access_token': 'EXAMPLE_TOKEN', 'expires_in': 3600}
    ...     return ValueWithExpiry(token, ttl=token['expires_in'])
    >>> ev = ExpiringValue(refresh_fn=fetch_token, max_age=0)
    >>> ev.value()
    {'access_token': 'EXAMPLE_TOKEN', 'expires_in': 3600}

The `ValueWithExpiry` wrapper supports both TTL (time-to-live in seconds) and
absolute timestamps via the `expires_at` parameter.

When using dynamic expiry, `max_age` becomes relevant if the refresh function
can return a mix of both plain values and `ValueWithExpiry` instances. When
a plain value is returned, it is cached for `max_age`. If only dynamic expiry
is used, then `max_age` is not used.
"""

import json
import logging
import threading
import time
from pathlib import Path

LOG = logging.getLogger(__name__)


class ValueWithExpiry:
    """Wrapper to return a value with a custom expiration time.

    Use this when your refresh function needs to specify its own expiration
    rather than using the default max_age. The expiry can be specified as
    either a TTL in seconds or an absolute timestamp.

    Example usage with TTL::

        def refresh_oauth_token():
            token = fetch_token()  # Returns {'access_token': '...', 'expires_in': 3600}
            return ValueWithExpiry(token, ttl=token['expires_in'])

    Example usage with absolute timestamp::

        def refresh_oauth_token():
            token = fetch_token()  # Returns {'access_token': '...', 'expires_at': 1702915200}
            return ValueWithExpiry(token, expires_at=token['expires_at'])
    """

    def __init__(self, value, *, ttl=None, expires_at=None):
        if ttl is None and expires_at is None:
            raise ValueError("Must specify either ttl or expires_at")
        if ttl is not None and expires_at is not None:
            raise ValueError("Cannot specify both ttl and expires_at")

        self.value = value
        self.expires_at = expires_at if expires_at else time.time() + ttl

    def __repr__(self):
        return f"ValueWithExpiry(value={self.value!r}, expires_at={self.expires_at})"


class AbstractExpiringValue:
    """Abstract base class to represent a value that expires.

    An `AbstractExpiringValue` represents a lazily loaded value that will expire
    over time. The constructor takes a `refresh_fn` function of zero arguments,
    which is called to obtain the value to be cached. The value is cached for
    `max_age` seconds unless the `refresh_fn` returns a `ValueWithExpiry` object
    that specifies a custom expiration time. If so, the default `max_age` is
    ignored.

    At the time of instantiation, the value is not retrieved, it is only
    retrieved the first time the value method is invoked. Likewise, the value is
    not refreshed at the time it expires, but only the next time the value
    method is called. The `value` method is thread-safe. Subclasses must provide
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

        This method is thread-safe.
        """
        with self._lock:
            if not refresh and not self.is_expired():
                return self.load()

            result = self._refresh_fn()

            # Unwrap and extract expiry if ValueWithExpiry
            if isinstance(result, ValueWithExpiry):
                value = result.value
                expiry = result.expires_at
            else:
                value = result
                expiry = None

            self.save(value, expiry)
            LOG.info("refreshed data and saved in cache")
            return value

    def is_expired(self):
        """Returns `True` if the value needs to be refreshed, `False` otherwise.

        A value needs to be refreshed when it has expired. This is determined
        by the implementation of this method. By default, the value is cached for
        `max_age` seconds or the dynamic expiry specified by the `refresh_fn`
        return value (if it is a `ValueWithExpiry` instance).

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

    def save(self, value, expiry=None):
        """Saves the value to the cache.

        If `is_expired` returns `True` during the invocation of
        `AbstractExpiringValue.value`, this method is invoked to save the new
        value to the cache. If `expiry` is provided, it specifies the absolute
        timestamp when the value should expire. Otherwise, the default `max_age`
        should be used.
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
    method is called. The `value` method is thread-safe.
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

    def save(self, value, expiry=None):
        self._value = value
        self._expiry = expiry if expiry is not None else time.time() + self._max_age
        LOG.debug("Saving value to cache, will expire at %s", time.ctime(self._expiry))


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
    method is called. The `value` method is thread-safe. If the value cannot be
    persisted as JSON, a TypeError is thrown.
    """

    def __init__(self, refresh_fn, path, max_age):
        super().__init__(refresh_fn, max_age)
        self._path = path if isinstance(path, Path) else Path(path)
        self._expiry_path = self._path.with_suffix(self._path.suffix + ".expiry")

    def is_expired(self):
        if not self._path.exists():
            return True
        # Check for explicit expiry file first
        if self._expiry_path.exists():
            expiry = float(self._expiry_path.read_text(encoding="utf-8").strip())
            return time.time() > expiry

        # Otherwise fall back to file modification time + max_age
        last_modification = self._path.stat().st_mtime
        return time.time() > last_modification + self._max_age

    def load(self):
        LOG.debug("Loading cached data from %s", self._path)
        with self._path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def save(self, value, expiry=None):
        # No need to persist the file if max_age is 0 seconds (and not dynamic).
        if self._max_age == 0 and expiry is None:
            return

        LOG.debug("Saving data to cache file %s", self._path)
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as file:
            json.dump(value, file)

        # Pathlib.replace uses os.replace which is atomic on POSIX systems
        tmp.replace(self._path)

        # Write or remove expiry file
        if expiry is not None:
            self._expiry_path.write_text(str(expiry), encoding="utf-8")
        elif self._expiry_path.exists():
            self._expiry_path.unlink()
