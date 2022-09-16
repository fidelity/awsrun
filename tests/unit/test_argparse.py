#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#

import argparse

import pytest

from awsrun.argparse import (AppendAttributeValuePair, AppendWithoutDefault,
                             from_str_to)


@pytest.mark.parametrize(
    "type, test, expected",
    [
        ("str", "value", "value"),
        ("int", "10", 10),
        ("float", "0.5", 0.5),
        ("bool", "yes", True),
        ("bool", "y", True),
        ("bool", "true", True),
        ("bool", "True", True),
        ("bool", "1", True),
        ("bool", "anything_else", False),
        ("SomeType", "value", "value"),
    ],
)
def test_from_str_to(type, test, expected):
    assert from_str_to(type)(test) == expected


@pytest.mark.parametrize(
    "default, args, expected",
    [
        (["east"], "", ["east"]),
        (["east"], "--region west", ["west"]),
        (["east"], "--region west --region central", ["west", "central"]),
        (["east"], "--region east", ["east"]),
        (["east"], "--region east --region west", ["east", "west"]),
        (None, "", None),
        ([], "", []),
        ([], "--region west", ["west"]),
    ],
)
def test_append_without_default_action(default, args, expected):
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", action=AppendWithoutDefault, default=default)
    assert parser.parse_args(args.split()).region == expected


@pytest.mark.parametrize(
    "args, expected_exception",
    [
        ("--region", argparse.ArgumentError),
    ],
)
def test_append_without_default_action_failure(args, expected_exception):
    parser = argparse.ArgumentParser(exit_on_error=False)
    parser.add_argument("--region", action=AppendWithoutDefault, default=["east"])
    with pytest.raises(expected_exception):
        parser.parse_args(args.split())


@pytest.mark.parametrize(
    "args, expected",
    [
        ("-f env=prod", {"env": ["prod"]}),
        ("-f env=dev,qa,prod", {"env": ["dev", "qa", "prod"]}),
        ("-f env=dev,qa -f env=prod", {"env": ["dev", "qa", "prod"]}),
        (
            "-f env=dev,qa,prod -f status=active",
            {"env": ["dev", "qa", "prod"], "status": ["active"]},
        ),
        ("-f level=1,2,3", {"level": ["1", "2", "3"]}),
        ("-f level=int:1,2,3", {"level": [1, 2, 3]}),
        ("-f level=float:1,2,3", {"level": [1.0, 2.0, 3.0]}),
        ("-f level=bool:1,2,3", {"level": [True, False, False]}),
    ],
)
def test_append_attribute_value_pair_action(args, expected):
    parser = argparse.ArgumentParser()
    parser.add_argument("--flag", "-f", action=AppendAttributeValuePair)
    assert parser.parse_args(args.split()).flag == expected


@pytest.mark.parametrize(
    "args, expected_exception",
    [
        ("-f", argparse.ArgumentError),
        ("-f level=int:1,not_a_number,3", SystemExit),
    ],
)
def test_append_attribute_value_pair_action_failure(args, expected_exception):
    parser = argparse.ArgumentParser(exit_on_error=False)
    parser.add_argument("--flag", "-f", action=AppendAttributeValuePair)
    with pytest.raises(expected_exception):
        parser.parse_args(args.split())
