#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Provides additional actions and formatters for the builtin argparse module."""

import argparse
import builtins
import re


class RawAndDefaultsFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    """Mixin of ArgumentDefaultsHelpFormatter and RawDescriptionHelpFormatter.

    The argparse module does not allow for easy combinations of help formatters.
    This class combines the raw formatter along with the default args formatter,
    which is used by awsrun CLI.
    """


class AppendWithoutDefault(argparse.Action):
    """Argparse action to append to a list without the default.

    Out of the box, when using argparse to `append` options to a list, if a
    default has been provided in `add_argument`, then any options provided on
    the command line will be appended to that default list. For example, notice
    that `central` remains in the list:

        >>> parser = argparse.ArgumentParser()
        >>> parser.add_argument('--region', action='append', default=['central'])
        >>> parser.parse_args('--region east --region west'.split())
        Namespace(region=['central', 'east', 'west'])

    This class provides an argparse action that will only use the default value
    if no other values were provided on the command line. For example:

        >>> parser = argparse.ArgumentParser()
        >>> parser.add_argument('--region', action=AppendWithoutDefault, default=['central'])
        >>> parser.parse_args('--region east --region west'.split())
        Namespace(region=['east', 'west'])
        >>> parser.parse_args('')
        Namespace(region=['central'])
    """

    def __init__(self, *args, **kwargs):
        self.has_been_called = False
        super().__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        current = [] if not self.has_been_called else getattr(namespace, self.dest)
        current.append(values)
        setattr(namespace, self.dest, current)
        self.has_been_called = True


class AppendAttributeValuePair(argparse.Action):
    """Argparse action to construct a dict of key/value pairs.

    Parses command line options into a dict of key/value pairs where multiple
    options and/or values are appended to the appropriate key/value pair. Option
    must be in either `name=val1,val2,etc` format or `name=type:val1,val2,etc`
    where `type` is one of `str`, `int`, `float`, or `bool`. The first format
    assumes a type of `str`. Examples will best illustrate use:

        >>> import argparse
        >>> parser = argparse.ArgumentParser()
        >>> parser.add_argument('--flag', '-f', action=AppendAttributeValuePair)
        >>> def test(arg_string):
        ...   return parser.parse_args(arg_string.split()).flag
        ...
        >>> test('-f env=prod')
        {'env': ['prod']}

    More than one value can be provided on the right-hand side of the `=`:

        >>> test('-f env=dev,qa,prod')
        {'env': ['dev', 'qa', 'prod']}

    The option can be provided multiple times. If the left-hand side of the `=`
    is different, a new key is added to the dict:

        >>> test('-f env=dev,qa,prod -f status=active')
        {'env': ['dev', 'qa', 'prod'], 'status': ['active']}

    If the left-hand side is the same as a previous, the values are appended to
    the existing key in the dict:

        >>> test('-f env=dev -f env=qa,prod')
        {'env': ['dev', 'qa', 'prod']}

    The type of the comma separated values defaults to strings, but can be
    converted to ints, floats, or bools:

        >>> test('-f level=1,2,3')
        {'level': ['1', '2', '3']}

        >>> test('-f level=int:1,2,3')
        {'level': [1, 2, 3]}

        >>> test('-f level=float:1,2,3')
        {'level': [1.0, 2.0, 3.0]}

        >>> test('-f level=bool:1,2,3')
        {'level': [True, False, False]}
    """

    def __call__(self, parser, namespace, values, option_string=None):
        match = re.match(r"([^=]+)=(?:(str|int|float|bool):)?(.+)", values)  # type: ignore
        if not match:
            parser.error(f"{option_string}: expected attr=val1,val2,etc")

        name, value_type, comma_sep_values = match.groups()
        cast = from_str_to(value_type)

        # Note: getattr below will always return a value because the argparse
        # Action sets the namespace attribute with a default value. That default
        # value may be None or a user-supplied dict. This means we can't use the
        # default parameter to getattr as the attribute will always exist.
        d = getattr(namespace, self.dest)

        # If it is None, then create a dict to store the parsed results.
        if d is None:
            d = {}

        # Normally I would use a defaultdict(list) when checking for a key
        # and setting a default value, but this cannot be used here as the
        # default provided by the user via parser.add_argument(default=...)
        # may be a regular dict, so we have to explicitly check for the name.
        if name not in d:
            d[name] = []

        try:
            d[name].extend(cast(v.strip()) for v in comma_sep_values.split(","))

        except ValueError:  # cast might throw an error
            parser.error(f"{option_string}: invalid {value_type} in {match.group()}")

        setattr(namespace, self.dest, d)


def from_str_to(type_):
    """Return a cast function to convert a string to a builtin type.

    The `type` parameter is the name of the type as a string. Returns the
    builtin Python cast function if `type` is "str", "int", or "float". If
    `type` is "bool", the returned cast function will return `True` for the
    values "y", "yes", "true", and "1" (case insensitive), otherwise it will
    return `False`. For any other `type` specified, the builtin `str`
    function is returned.

        >>> f = from_str_to("str")
        >>> f("hello")
        "hello"

        >>> f = from_str_to("int")
        >>> f("10")
        10

        >>> f = from_str_to("float")
        >>> f("10")
        10.0

        >>> f = from_str_to("bool")
        >>> [f(s) for s in ['yes', 'no', 'true', 'false']]
        [True, False, True, False]
    """
    if type_ in ("str", "int", "float"):
        return getattr(builtins, type_)
    if type_ == "bool":
        return lambda s: s.lower() in ("y", "yes", "true", "True", "1")
    return str
