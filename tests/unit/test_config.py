#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#

# pylint: disable=redefined-outer-name,missing-docstring

import json

import pytest
import yaml

from awsrun import config


@pytest.fixture(scope="session")
def basic_config():
    return {
        "Options": {"level": 0, "debug": False, "verbose": True},
        "Characters": {
            "Professor X": {
                "affiliation": "X-Men",
                "powers and abilities": ["telepathy", "intelligence"],
                "weight": 190,
                "active": True,
            },
            "Cyclops": {
                "affiliation": "X-Men",
                "powers and abilities": ["optic blasts"],
                "weight": 220,
                "active": True,
            },
            "Empty": None,
        },
    }


@pytest.fixture(scope="session")
def json_config(tmp_path_factory, basic_config):
    filename = tmp_path_factory.getbasetemp() / "conf.json"
    with filename.open("w") as f:
        json.dump(basic_config, f)
    return filename


@pytest.fixture(scope="session")
def yaml_config(tmp_path_factory, basic_config):
    filename = tmp_path_factory.getbasetemp() / "conf.yaml"
    with filename.open("w") as f:
        yaml.dump(basic_config, f)
    return filename


@pytest.mark.parametrize(
    "keys, default, type_, expected",
    [
        (["Options", "verbose"], None, None, True),
        (["Options", "debug"], None, None, False),
        (["Options", "debug"], True, None, False),
        (["Options", "level"], None, None, 0),
        (["Options", "level"], 0, None, 0),
        (["Options", "level"], 100, None, 0),
        (["Options", "does not exist"], None, None, None),
        (["Options", "does not exist"], 200, config.Int, 200),
        (["Options", "does not exist"], True, None, True),
        (["Characters", "Professor X", "weight"], 0, config.Int, 190),
        (["Characters", "Professor X", "weight"], 0, config.Const(190), 190),
        (["Characters", "Professor X", "does not exist"], 0, config.Int, 0),
        (["Characters", "Missing Char", "weight"], 0, config.Int, 0),
        (
            ["Characters", "Professor X", "powers and abilities"],
            None,
            config.List(config.Str),
            ["telepathy", "intelligence"],
        ),
    ],
)
def test_get_with_valid_types(yaml_config, keys, default, type_, expected):
    c = config.Config.from_file(yaml_config)
    assert c.get(*keys, default=default, type=type_) == expected


@pytest.mark.parametrize(
    "keys",
    [
        ["does not exist"],
        ["Options", "does not exist"],
        ["Characters", "does not exist", "weight"],
        ["Characters", "Professor X", "does not exist"],
        ["Characters", "Professor X", "weight", "does not exist"],
        ["Characters", "Empty", "does not exist"],
    ],
)
def test_get_must_exist(yaml_config, keys):
    c = config.Config.from_file(yaml_config)
    with pytest.raises(ValueError):
        assert c.get(*keys, must_exist=True)


@pytest.mark.parametrize(
    "keys, default, type_",
    [
        (["Options", "verbose"], None, config.Str),
        (["Options", "does not exist"], 10, config.Bool),
        (["Characters", "Professor X", "weight"], 0, config.Bool),
        (["Characters", "Professor X", "weight"], 0, config.Const(1000)),
        (["Characters", "Professor X", "does not exist"], 0, config.Bool),
        (
            ["Characters", "Professor X", "powers and abilities"],
            None,
            config.List(config.Int),
        ),
    ],
)
def test_get_with_invalid_types(yaml_config, keys, default, type_):
    c = config.Config.from_file(yaml_config)
    with pytest.raises(TypeError):
        c.get(*keys, default=default, type=type_)


def test_register_filetype(tmp_path):
    filename = tmp_path / "test.conf"
    with filename.open("w") as f:
        f.write('{"key": "value"}')

    # Should raise as no default .conf handler exists
    with pytest.raises(ValueError):
        c = config.Config.from_file(filename)

    # Let's register a .conf handler and try again
    config.Config.register_filetype(config.JSONConfig, ".conf", ".config")
    c = config.Config.from_file(filename)
    assert c.get("key") == "value"


def test_register_filetype_with_wrong_handler(tmp_path):
    filename = tmp_path / "test.conf"
    with filename.open("w") as f:
        f.write("key: value")

    # Since we just wrote a YAML file, using the JSONConfig should fail
    config.Config.register_filetype(config.JSONConfig, ".conf", ".config")
    with pytest.raises(json.decoder.JSONDecodeError):
        config.Config.from_file(filename)


def test_from_file_with_json(json_config):
    c = config.Config.from_file(json_config)
    assert c.get("Options", "verbose") is True


def test_from_file_with_yaml(yaml_config):
    c = config.Config.from_file(yaml_config)
    assert c.get("Options", "verbose") is True


@pytest.mark.parametrize(
    "const_value, test_input, expected",
    [
        ("test", "test", True),
        ("test", "not test", False),
        ("test", 10, False),
        (10, 10, True),
        (10, 20, False),
        (10, 10.0, False),
        (10, "test", False),
        (1.0, 1.0, True),
        (1.0, 1, False),
        (True, True, True),
        (True, False, False),
        (True, "test", False),
        ([], [], True),
        (["test"], ["test"], True),
        (["test"], [], False),
        (["test"], [10, 20], False),
        ({}, {}, True),
        ({"test": 10}, {"test": 10}, True),
        ({"test": 10}, {"test": 20}, False),
        ({"test": 10}, {"x": 10}, False),
    ],
)
def test_const_type(const_value, test_input, expected):
    assert config.Const(const_value).type_check(test_input) == expected
    assert str(config.Const(const_value)) == f"constant '{const_value}'"


@pytest.mark.parametrize(
    "choices, test_input, expected",
    [
        (["a", "b", "c"], "b", True),
        (["a", "b", "c"], "d", False),
        (["a", "b", "c"], 10, False),
        ([10, 20], 10, True),
        ([10, 20], 30, False),
        ([10], 10, True),
        ([10], 30, False),
        (["a", 10], "b", False),
        (["a", 10], "a", True),
        (["a", 10], 10, True),
        ([], 30, False),
        ([], 30, False),
    ],
)
def test_choice_type(choices, test_input, expected):
    assert config.Choice(*choices).type_check(test_input) == expected
    assert (
        str(config.Choice(*choices))
        == "(" + " or ".join([f"constant '{c}'" for c in choices]) + ")"
    )


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("test", True),
        (10, False),
        (1.0, False),
        (True, False),
        ([], False),
        ({}, False),
    ],
)
def test_str_type(test_input, expected):
    assert config.Str.type_check(test_input) == expected
    assert str(config.Str) == "str"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("test", False),
        (10, True),
        (1.0, False),
        (True, False),
        ("/does/not/exist", False),
        ([], False),
        ({}, False),
    ],
)
def test_int_type(test_input, expected):
    assert config.Int.type_check(test_input) == expected
    assert str(config.Int) == "int"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("test", False),
        (10, False),
        (1.0, False),
        (True, True),
        (False, True),
        ("/does/not/exist", False),
        ([], False),
        ({}, False),
    ],
)
def test_bool_type(test_input, expected):
    assert config.Bool.type_check(test_input) == expected
    assert str(config.Bool) == "bool"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("test", False),
        (10, False),
        (1.0, True),
        (True, False),
        ("/does/not/exist", False),
        ([], False),
        ({}, False),
    ],
)
def test_float_type(test_input, expected):
    assert config.Float.type_check(test_input) == expected
    assert str(config.Float) == "float"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("test", True),
        (10, True),
        (1.0, True),
        (True, True),
        ("/does/not/exist", True),
        ([], True),
        ({}, True),
    ],
)
def test_any_type(test_input, expected):
    assert config.Any.type_check(test_input) == expected
    assert str(config.Any) == "any type"


def test_good_file_type(json_config):
    assert config.File.type_check(str(json_config))
    assert not config.File.type_check("/does/not/exist")
    assert str(config.File) == "existing file"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("test", False),
        (10, False),
        (1.0, False),
        (True, False),
        ("/does/not/exist", False),
        ([], False),
        ({}, False),
    ],
)
def test_bad_file_type(test_input, expected):
    assert config.File.type_check(test_input) == expected
    assert str(config.File) == "existing file"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("10.10.1.1", True),
        ("10.0.0.0", True),
        ("10.0.0", False),
        ("10.0.0.0/24", False),
        ("10.0.0.0/32", False),
        ("test", False),
        (10, False),
        (1.0, False),
        (True, False),
        ("/does/not/exist", False),
        ([], False),
        ({}, False),
    ],
)
def test_ip_address_type(test_input, expected):
    assert config.IP.type_check(test_input) == expected
    assert str(config.IP) == "IPv4 or IPv6 address"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("10.10.1.1", True),
        ("10.0.0.0", True),
        ("10.0.0.0/24", True),
        ("10.0.0.0/32", True),
        ("test", False),
        (10, False),
        (1.0, False),
        (True, False),
        ("/does/not/exist", False),
        ([], False),
        ({}, False),
    ],
)
def test_ip_network_type(test_input, expected):
    assert config.IPNet.type_check(test_input) == expected
    assert str(config.IPNet) == "IPv4 or IPv6 network"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("test", True),
        ("test.more", True),
        ("test.more.and.more", True),
        ("test.", False),
        ("test.more.", False),
        ("test.more.and.more.", False),
        (10, False),
        (1.0, False),
        (True, False),
        ([], False),
        ({}, False),
    ],
)
def test_dotted_str_type(test_input, expected):
    assert config.Dotted.type_check(test_input) == expected
    assert str(config.Dotted) == "str matching '^[^.]+(\\.[^.]+)*$'"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("1024", True),
        ("not a number", False),
        (10, False),
        (1.0, False),
        (True, False),
        ([], False),
        ({}, False),
    ],
)
def test_str_match_type(test_input, expected):
    assert config.StrMatch(r"^\d+$").type_check(test_input) == expected


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("test", False),
        (10, False),
        (1.0, False),
        (True, False),
        ([], True),
        (["test"], True),
        (["test", "test"], True),
        ([10, 20], False),
        ([10, "test", False], False),
        ({}, False),
    ],
)
def test_list_type(test_input, expected):
    assert config.List(config.Str).type_check(test_input) == expected
    assert str(config.List(config.Str)) == "list of str"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("test", False),
        (10, False),
        (1.0, False),
        (True, False),
        ([], False),
        ({}, True),
        ({"key": "value"}, False),
        ({"key": 100}, True),
    ],
)
def test_dict_type(test_input, expected):
    assert config.Dict(config.Str, config.Int).type_check(test_input) == expected
    assert (
        str(config.Dict(config.Str, config.Int)) == "dict with str keys and int values"
    )


@pytest.mark.parametrize(
    "test_input, expected",
    [("test", False), (10, True), (1.0, True), (True, True), ([], True), ({}, True)],
)
def test_not_type(test_input, expected):
    assert config.Not(config.Str).type_check(test_input) == expected
    assert str(config.Not(config.Str)) == "not str"


@pytest.mark.parametrize(
    "test_input, expected",
    [("test", False), (10, True), (1.0, True), (True, False), ([], False), ({}, False)],
)
def test_or_type(test_input, expected):
    assert config.Or(config.Int, config.Float).type_check(test_input) == expected
    assert str(config.Or(config.Int, config.Float)) == "(int or float)"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("test", False),
        ("p@ssword", False),
        ("p@ssw0rd", True),
        (10, False),
        (1.0, False),
        (True, False),
        ([], False),
        ({}, False),
    ],
)
def test_and_type(test_input, expected):
    assert (
        config.And(config.StrMatch(r"\d"), config.StrMatch(r"[!@#$%^&*]")).type_check(
            test_input
        )
        == expected
    )
    assert (
        str(config.And(config.StrMatch(r"\d"), config.StrMatch(r"[!@#$%^&*]")))
        == "(str matching '\\d' and str matching '[!@#$%^&*]')"
    )
