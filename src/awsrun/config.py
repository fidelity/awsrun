#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Provides a YAML/JSON config file reader with type-checked values.

## Overview

`Config` is a convenient representation of values stored within a dict, which
may contain other dicts. It provides for default values, mandatory values, as
well as the ability to type-check values using type specifications.  `Config`
can be subclassed to provide parsers for various configuration file types. This
module includes `JSONConfig` and `YAMLConfig` implementations. These file types
are registered with the `Config` class, so users can use the `Config.from_file`
factory method, which takes a filename and loads the configuration using the
appropriate implementation based on the file extension. Users can also register
their own subclasses via `Config.register_filetype`.

## Type Checking

Type checking of values is done via a set of type objects and classes defined in
this module. This provides a means to ensure that values in the configuration
are of the correct type.  Numerous simple types are provided by pre-defined type
objects: `Str`, `Int`, `Bool`, `Float`, `File`, `IP`, and `Dotted`. Several type
classes are provided that can be instantiated to create more complex types:
`StrMatch`, `Any`, `List`, and `Dict`. In addition, the combinators `Not`,
`And`, and `Or` can be used to combine any of these types.  For example, the
following type matches a dict with keys as strings and values as a list of ints
or floats:

    Dict(Str, List(Or(Int, Float)))

## Reading Values

Assuming the file 'test.yaml' contains the following YAML:

    verbose: true
    engine:
        cpus: 4
        threads: 10
    ip_addr: 10.0.0.1
    directories:
        - /tmp
        - /var/tmp

`Config.get` is used to read values from the configuration. For example, to load
the above file and read values from it:

    c = Config.from_file('test.yaml')

    # Read top-level keys
    assert c.get('verbose', type=Bool) == True
    assert c.get('ip_addr', type=IP, must_exist=True) == '10.0.0.1'
    assert c.get('directories', type=List(Str), default=[]) == ['/tmp', '/var/tmp']

    # Read a hierarchical value by specifying multiple keys
    assert c.get('engine', 'threads', type=Int, default=5) == 10

If any of the values do not match the expected type, a `TypeError` is raised.
Users can define their own custom types by subclassing `Type`. Only two methods
need to be implemented: `type_check` and `__str__`. Review the implementation of
the included types if building your own.

If multiple keys with the same name exist, the behavior is undefined when
retrieving values. Depending on your Python version, you may get one or the
other.
"""

import ipaddress
import json
import logging
import re
from functools import reduce
from pathlib import Path

import yaml

LOG = logging.getLogger(__name__)

# pylint: disable=unidiomatic-typecheck
#
# Because isinstance(True, int) is true, we do not rely on isinstance for our
# type checking in this module as we want to match exact types. We don't want to
# consider subclasses and True should not type check successfully against an
# int.


class Config:
    """A `Config` can read type-checked values from a Python dictionary.

    This class provides an interface to read values from a dictionary while
    providing for default values, mandatory values, as well as the ability to
    type-check values. In addition, it can be used to dynamically instantiate
    classes specified in the configuration. Finally, the class also contains a
    registry of configuration parsers based on file extensions, so users can
    load configs from files.
    """

    _filetypes = {}

    @classmethod
    def register_filetype(cls, config_class, *extensions):
        """Register a parser for files with one of the specified extensions.

        The registry is used to find the appropriate config parser when a
        user invokes the `Config.from_file` factory method. Extensions should be
        specified as '.ext'. Subsequent registrations for the same extension
        will override the prior registration.
        """
        for ext in extensions:
            cls._filetypes[ext] = config_class

    @classmethod
    def from_file(cls, filename, must_exist=False):
        """Factory method to Load a `Config` from a filename.

        This method uses the extension of the filename to determine the
        configuration parser that should be used to instantiate a `Config`
        object. If `must_exist` is true, a `FileNotFoundError` is raised if the
        filename does not exist, otherwise an empty `Config` is returned.
        """
        path = Path(filename)

        if not path.is_file():
            if must_exist:
                raise FileNotFoundError(f"Config file not found: {filename}")
            return Config({})

        if path.suffix not in cls._filetypes:
            raise ValueError(f"Unregistered file type extension: {path.suffix}")

        with path.open(encoding="utf-8") as f:
            return cls._filetypes[path.suffix](f)

    def __init__(self, d):
        self.conf = d

    def get(self, *keys, default=None, type=None, must_exist=False):
        """Return the specified value from the `Config`.

        Specify the value to read by providing the keys required to reach the
        value in the configuration. If the value is not found at the specified
        key path, `None` or the `default` value is returned unless the
        `must_exist` flag is `True`, in which case a `ValueError` is raised.

        Values can be optionally type-checked to ensure it matches the specified
        type. If the `type` matches the value in the configuration, the value is
        returned, otherwise a `TypeError` is raised. Types are specified by
        passing a `Type` object. There are numerous type objects defined in this
        module. For example:

            c.get('path', 'to', 'value', type=Int)
            c.get('path', 'to', 'value', type=Bool)
            c.get('path', 'to', 'value', type=Float)
            c.get('path', 'to', 'value', type=Str)
            c.get('path', 'to', 'value', type=StrMatch(r'^\\d+-\\d+$'))
            c.get('path', 'to', 'value', type=IP)
            c.get('path', 'to', 'value', type=List(IP))
            c.get('path', 'to', 'value', type=List(Str))
            c.get('path', 'to', 'value', type=List(Dict(Int, Str)))
            c.get('path', 'to', 'value', type=Dict(Str, Int))
            c.get('path', 'to', 'value', type=Or(Int, Float))
            c.get('path', 'to', 'value', type=And(StrMatch(r'\\d+'), StrMatch(r'[A-Z]')))
            c.get('path', 'to', 'value', type=Not(Or(Int, Float)))
        """
        # pylint: disable=redefined-builtin

        # This one-liner will recursively follow a list of keys into a
        # dictionary and return the value. If a key does not exist, return an
        # empty dict.
        try:
            value = reduce(lambda a, p: a.get(p, {}), keys, self.conf)
        except AttributeError as e:
            raise ValueError(
                f"Error in config: {'->'.join(keys[:-1])}: not a dictionary"
            ) from e

        # If value is {} that means the key doesn't exist. If the must_exist
        # flag was passed, then we raise a descriptive ValueError, otherwise we
        # set it to the default.
        if value == {}:
            if must_exist:
                raise ValueError(f"Error in config: {'->'.join(keys)}: must be set")
            value = default

        # If no value has been set in the config and none has been provided as a
        # default, then return None.
        if value is None:
            return value

        # If no type has been specified, then return the value in the config or
        # the default without doing any type checking.
        if not type:
            return value

        # Only return the value if it type checks correctly.
        if type.type_check(value):
            return value

        # Finally, all other cases indicate a type error.
        raise TypeError(
            f"Error in config: {'->'.join(keys)}: not a {type}: {repr(value)}"
        )


EmptyConfig = Config({})
"""Singleton representing an empty `Config`."""


class YAMLConfig(Config):
    """Loads a YAML configuration from a stream."""

    def __init__(self, stream):
        super().__init__(yaml.safe_load(stream))


class JSONConfig(Config):
    """Loads a JSON configuration from a stream."""

    def __init__(self, stream):
        super().__init__(json.load(stream))


Config.register_filetype(JSONConfig, ".json", ".jsn")
Config.register_filetype(YAMLConfig, ".yaml", ".yml")


class Type:
    """Represents a type that can be used in type-check comparisons."""

    def type_check(self, obj):
        """Returns true if obj is a type matching this `Type`."""
        raise NotImplementedError

    def __str__(self):
        """Returns a string representing this `Type`."""
        raise NotImplementedError


class Not(Type):
    """Represents a type that is not a type of `config_type`.

    `config_type` must be an instance of `Type`.  For example:

        Not(Str)
        Not(StrMatch(r'\\d+'))
        Not(List(Int))
    """

    def __init__(self, config_type):
        self.config_type = config_type

    def type_check(self, obj):
        return not self.config_type.type_check(obj)

    def __str__(self):
        return "not " + str(self.config_type)


class Or(Type):
    """Represents a type that is one of the `config_types`.

    `config_type` must be an instance of `Type`.  For example:

        Or(Int, Float)
        Or(StrMatch(r'^file:'), StrMatch(r'^https?:'))
    """

    def __init__(self, *config_types):
        self.config_types = config_types

    def type_check(self, obj):
        return any(t.type_check(obj) for t in self.config_types)

    def __str__(self):
        s = " or ".join(str(t) for t in self.config_types)
        return "(" + s + ")"


class And(Type):
    """Represents a type that is all of the `config_types`.

    `config_type` must be an instance of `Type`.  For example:

        And(StrMatch(r'\\d'), StrMatch(r'[!@#$%^&*()]'))
    """

    def __init__(self, *config_types):
        self.config_types = config_types

    def type_check(self, obj):
        return all(t.type_check(obj) for t in self.config_types)

    def __str__(self):
        s = " and ".join(str(t) for t in self.config_types)
        return "(" + s + ")"


class Const(Type):
    """Represents a constant value."""

    def __init__(self, const):
        self.const = const

    def type_check(self, obj):
        # Why do we bother checking the types if we are just going to test
        # equality of the objects afterwards? Because True == 1 in python, so if
        # we did not check types, then this would report incorrect results.
        # Likewise, we cannot use isinstance here either as a bool is a subclass
        # of int, so it would also report incorrect results.
        if type(obj) != type(self.const):  # noqa: E721
            return False
        return obj == self.const

    def __str__(self):
        return f"constant '{self.const}'"


class Choice(Or):
    """Represents a choice of constants."""

    def __init__(self, *constants):
        super().__init__(*[Const(c) for c in constants])


class Scalar(Type):
    """Represents a type that is a scalar matching `type`.

    `type` must be one of the builtin Python scalar types. For example:

        Scalar(str)
        Scalar(int)
        Scalar(bool)
    """

    def __init__(self, type_):
        self.type = type_

    def type_check(self, obj):
        return type(obj) == self.type  # noqa: E721

    def __str__(self):
        return self.type.__name__


class StrMatch(Type):
    """Represents a string matching `pattern`.

    `pattern` is matched using `re.search` so anchors should be explicit.
    """

    def __init__(self, pattern):
        self.pattern = pattern

    def type_check(self, obj):
        if type(obj) != str:  # noqa: E721
            return False
        return bool(re.search(self.pattern, obj))

    def __str__(self):
        return f"str matching '{self.pattern}'"


class IpAddress(Type):
    """Represents a string matching an IP address (v4 or v6)."""

    def type_check(self, obj):
        if type(obj) != str:  # noqa: E721
            return False
        try:
            ipaddress.ip_address(obj)
            return True
        except ValueError:
            return False

    def __str__(self):
        return "IPv4 or IPv6 address"


class IpNetwork(Type):
    """Represents a string matching an IP network (v4 or v6)."""

    def type_check(self, obj):
        if type(obj) != str:  # noqa: E721
            return False
        try:
            ipaddress.ip_network(obj)
            return True
        except ValueError:
            return False

    def __str__(self):
        return "IPv4 or IPv6 network"


class FileType(Type):
    """Represents a string pointing to an existing file."""

    def type_check(self, obj):
        if type(obj) != str:  # noqa: E721
            return False
        return Path(obj).exists()

    def __str__(self):
        return "existing file"


class AnyType(Type):
    """Represents any type."""

    def type_check(self, obj):
        return True

    def __str__(self):
        return "any type"


Str = Scalar(str)
"""Singleton representing a str."""

Int = Scalar(int)
"""Singleton representing an int."""

Bool = Scalar(bool)
"""Singleton representing a bool."""

Float = Scalar(float)
"""Singleton representing a float."""

Any = AnyType()
"""Singleton representing any type."""

File = FileType()
"""Singleton representing an existing filename."""

IP = IpAddress()
"""Singleton representing an IP address (v4 or v6)."""

IPNet = IpNetwork()
"""Singleton representing an IP network (v4 or v6)."""

Dotted = StrMatch(r"^[^.]+(\.[^.]+)*$")
"""Singleton representing a dotted Python path."""

URL = StrMatch(r"^[^:]+://")
"""Singleton representing a URL in the form of xxxx://."""


class List(Type):
    """Represents a list containing elements of `element_type`.

    `element_type` must be an instance of `Type`. For example:

        List(Str)
        List(Int)
        List(Dict(Str, Int))
        List(StrMatch(r'^https?://'))
    """

    def __init__(self, element_type):
        self.element_type = element_type

    def type_check(self, obj):
        if type(obj) != list:  # noqa: E721
            return False
        return all(self.element_type.type_check(e) for e in obj)

    def __str__(self):
        return f"list of {self.element_type}"


class Dict(Type):
    """Represents a dict containing keys of `key_type` and values of `value_type`.

    `key_type` and `value_type` must be instances of `Type`. For example:

        Dict(Str, Str)
        Dict(Str, List(IP))
        Dict(Str, List(Or(Int, Float)))
    """

    def __init__(self, key_type, value_type):
        self.key_type = key_type
        self.value_type = value_type

    def type_check(self, obj):
        if type(obj) != dict:  # noqa: E721
            return False
        return all(self.key_type.type_check(k) for k in obj.keys()) and all(
            self.value_type.type_check(v) for v in obj.values()
        )

    def __str__(self):
        return f"dict with {self.key_type} keys and {self.value_type} values"
