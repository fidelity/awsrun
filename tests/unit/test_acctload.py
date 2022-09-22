#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#

# pylint: disable=redefined-outer-name,missing-docstring

import pytest

from awsrun import acctload


@pytest.mark.parametrize("test_input", ["100200300400", "", "1"])
def test_identity_loader_acct_id(test_input):
    loader = acctload.IdentityAccountLoader()
    assert loader.acct_id(test_input) == test_input


@pytest.mark.parametrize(
    "test_input, expected",
    [
        (None, []),
        ([], []),
        (
            ["100200300400", "100200300400", "200300400100"],
            ["100200300400", "200300400100"],
        ),
    ],
)
def test_identity_loader_accounts(test_input, expected):
    loader = acctload.IdentityAccountLoader()
    assert set(loader.accounts(acct_ids=test_input)) == set(expected)


@pytest.mark.parametrize(
    "filter_kwargs",
    [
        {"include": {"id": ["100200300400"]}},
        {"exclude": {"id": ["100200300400"]}},
        {"include": {"id": ["100200300400"]}, "exclude": {"id": ["100200300400"]}},
    ],
)
def test_identity_loader_accounts_with_filters(filter_kwargs):
    loader = acctload.IdentityAccountLoader()
    with pytest.raises(AttributeError):
        loader.accounts(["100200300400"], **filter_kwargs)


def test_identity_loader_attributes():
    loader = acctload.IdentityAccountLoader()
    assert not loader.attributes()


@pytest.fixture()
def one_acct_list():
    return [{"id": "10", "bu": "a", "env": "prd"}]


@pytest.fixture()
def many_acct_list():
    return [
        {"id": "100200300400", "env": "prod", "status": "active"},
        {"id": "200300400100", "env": "nonprod", "status": "active"},
        {"id": "300400100200", "env": "dev", "status": "suspended"},
    ]


@pytest.mark.parametrize(
    "test_input, include, exclude, expected",
    [
        (["100200300400"], {}, {}, set(["100200300400"])),
        (["100200300400"], {"status": ["suspended"]}, {}, set()),
        (
            ["300400100200", "100200300400"],
            {},
            {},
            set(["300400100200", "100200300400"]),
        ),
        (
            ["300400100200", "100200300400"],
            {},
            {"status": ["suspended"]},
            set(["100200300400"]),
        ),
        (["300400100200", "100200300400"], {"env": ["dev"]}, {}, set(["300400100200"])),
        ([], {}, {}, set(["100200300400", "200300400100", "300400100200"])),
        ([], {"env": ["prod", "nonprod"]}, {}, set(["100200300400", "200300400100"])),
        (
            [],
            {"status": ["active", "no_such_value"]},
            {},
            set(["100200300400", "200300400100"]),
        ),
        (
            [],
            {"status": ["active"]},
            {"env": ["nonprod", "dev"]},
            set(["100200300400"]),
        ),
        ([], {"status": ["active"]}, {"env": ["nonprod", "dev", "prod"]}, set()),
        (
            [],
            {"status": ["active", "suspended"]},
            {"status": ["active", "no_such_value"]},
            set(["300400100200"]),
        ),
    ],
)
def test_meta_account_loader_accounts(
    many_acct_list, test_input, include, exclude, expected
):
    mal = acctload.MetaAccountLoader(many_acct_list)
    accts = mal.accounts(acct_ids=test_input, include=include, exclude=exclude)
    acct_ids = {a.id for a in accts}
    assert acct_ids == expected


def test_meta_account_loader_filters_with_multi_word_attr_names():
    d = [
        {"id": "100200300400", "acct status": "active account"},
        {"id": "200300400100", "acct status": "account suspended"},
        {"id": "300400100200", "acct status": "active account"},
    ]
    mal = acctload.MetaAccountLoader(d)
    acct = mal.accounts(exclude={"acct_status": ["active account"]})[0]
    assert acct.id == "200300400100"


def test_meta_account_loader_accounts_missing_ids():
    d = [
        {"id": "100200300400", "status": "active"},
        {"id": "200300400100"},
        {"id": "300400100200", "env": "dev", "status": "active"},
    ]
    mal = acctload.MetaAccountLoader(d)
    acct = mal.accounts(acct_ids=["200300400100"])[0]
    assert acct.id == "200300400100"

    # These should not raise exceptions as the MetaAccountLoader adds missing
    # keys so all account objects have all attributes.
    assert acct.env is None
    assert acct.status is None


def test_meta_account_loader_accounts_by_invalid_id(many_acct_list):
    mal = acctload.MetaAccountLoader(many_acct_list)
    with pytest.raises(acctload.AccountsNotFoundError) as e:
        mal.accounts(acct_ids=["100200300400", "no_such_id", "200300400100"])
    assert e.value.missing_acct_ids == ["no_such_id"]


@pytest.mark.parametrize("acct_id", ["100200300400", "200300400100", "300400100200"])
def test_meta_account_loader_acct_id(many_acct_list, acct_id):
    mal = acctload.MetaAccountLoader(many_acct_list)
    accts = mal.accounts(acct_ids=(acct_id,))
    assert len(accts) == 1
    assert mal.acct_id(accts[0]) == acct_id


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ([{"id": "10"}], [{"id": "10"}]),
        ([{"id": "10"}, {"id": "20"}], [{"id": "10"}, {"id": "20"}]),
        (
            [{"id": "10", "bu": "a"}, {"id": "20", "bu": "b"}],
            [{"id": "10", "bu": "a"}, {"id": "20", "bu": "b"}],
        ),
    ],
)
def test_load_basic_with_list_of_accts(test_input, expected):
    mal = acctload.MetaAccountLoader(test_input)
    assert mal.accts == expected, "dicts are not equal"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ({"10": {"id": "10"}}, [{"id": "10"}]),
        ({"10": {"id": "10"}, "20": {"id": "20"}}, [{"id": "10"}, {"id": "20"}]),
        (
            {"10": {"bu": "a"}, "20": {"bu": "b"}},
            [{"id": "10", "bu": "a"}, {"id": "20", "bu": "b"}],
        ),
        (
            {"10": {"bu": "a"}, "20": {"bu": "b"}},
            [{"id": "10", "bu": "a"}, {"id": "20", "bu": "b"}],
        ),
    ],
)
def test_load_basic_with_dict_of_accts(test_input, expected):
    mal = acctload.MetaAccountLoader(test_input)
    assert mal.accts == expected, "dicts are not equal"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        (
            [{"id": "10", "@bu": "a"}, {"id": "20", "@bu": "b"}],
            [{"id": "10", "_bu": "a"}, {"id": "20", "_bu": "b"}],
        ),
        (
            [{"id": "10", "00bu": "a"}, {"id": "20", "00bu": "b"}],
            [{"id": "10", "_00bu": "a"}, {"id": "20", "_00bu": "b"}],
        ),
    ],
)
def test_load_with_key_rewriting(test_input, expected):
    mal = acctload.MetaAccountLoader(test_input)
    assert mal.accts == expected, "dict key names not rewritten"


@pytest.mark.parametrize(
    "test_input",
    [
        [{"ID": "10"}],
        [{"bu": "10"}, {"bu": "20"}],
        [{"id": "10", "bu": "a"}, {"ID": "20", "bu": "b"}],
    ],
)
def test_load_without_default_id_attribute(test_input):
    with pytest.raises(ValueError):
        acctload.MetaAccountLoader(test_input)


@pytest.mark.parametrize("test_input", ["id", "ID", "acctId"])
def test_load_with_custom_id_attribute(test_input):
    d = {}
    d[test_input] = "10"
    mal = acctload.MetaAccountLoader([d], id_attr=test_input)
    assert mal.acct_id(mal.accounts()[0]) == "10", "custom id did not return acct #"


@pytest.mark.parametrize("test_input", [None, ""])
def test_load_with_bad_custom_id_attribute(test_input, one_acct_list):
    with pytest.raises(ValueError):
        acctload.MetaAccountLoader(one_acct_list, id_attr=test_input)


@pytest.mark.parametrize(
    "test_input",
    [{"999999999999": {"id": "100200300400", "env": "dev", "status": "active"}}],
)
def test_load_with_nonmatching_acct_key(test_input):
    with pytest.raises(ValueError):
        acctload.MetaAccountLoader(test_input)


@pytest.mark.parametrize(
    "test_input",
    [
        {True: {"env": "dev", "status": "active"}},
        {100200300400: {"env": "dev", "status": "active"}},
    ],
)
def test_load_with_invalid_acct_id(test_input):
    with pytest.raises(ValueError):
        acctload.MetaAccountLoader(test_input)


@pytest.mark.parametrize(
    "str_template, expected",
    [
        (None, "10"),
        ("", "10"),
        ("hello", "hello"),
        ("{id}", "10"),
        ("{bu}", "a"),
        ("acct={id}", "acct=10"),
        ("{id}/{bu}/{env}", "10/a/prd"),
    ],
)
def test_load_with_custom_str_template(str_template, one_acct_list, expected):
    mal = acctload.MetaAccountLoader(one_acct_list, str_template=str_template)
    assert str(mal.accounts()[0]) == expected, "str() output does not match expected"


@pytest.mark.parametrize(
    "str_template", ["{this_key_is_not_in_the_dict}", "{id}/{neither_is_this_one}"]
)
def test_load_with_bad_custom_str_template(str_template, one_acct_list):
    with pytest.raises(acctload.InvalidFormatTemplateError):
        acctload.MetaAccountLoader(one_acct_list, str_template=str_template)


@pytest.mark.parametrize(
    "include_attrs, expected",
    [
        (["id"], [{"id": "10"}]),
        (["id", "bu"], [{"id": "10", "bu": "a"}]),
        (["bu", "id"], [{"id": "10", "bu": "a"}]),
        (["id", "bu", "env"], [{"id": "10", "bu": "a", "env": "prd"}]),
        (["id", "not_there"], [{"id": "10"}]),
    ],
)
def test_load_with_include_attrs(include_attrs, one_acct_list, expected):
    mal = acctload.MetaAccountLoader(one_acct_list, include_attrs=include_attrs)
    assert mal.accts == expected, "dicts are not equal"
    assert set(mal.attributes()) == set(expected[0].keys())


@pytest.mark.parametrize(
    "id_attr, include_attrs",
    [(None, ["bu", "env"]), ("id", ["bu", "env"]), ("acctId", ["id", "bu", "env"])],
)
def test_load_with_include_attrs_that_doesnt_have_the_id_attr(
    id_attr, include_attrs, one_acct_list
):
    with pytest.raises(ValueError):
        acctload.MetaAccountLoader(
            one_acct_list, id_attr=id_attr, include_attrs=include_attrs
        )


@pytest.mark.parametrize(
    "exclude_attrs, expected",
    [
        ([], [{"id": "10", "bu": "a", "env": "prd"}]),
        (["bu"], [{"id": "10", "env": "prd"}]),
        (["bu", "env"], [{"id": "10"}]),
        (["bu", "env", "not_there"], [{"id": "10"}]),
    ],
)
def test_load_with_exclude_attrs(exclude_attrs, one_acct_list, expected):
    mal = acctload.MetaAccountLoader(one_acct_list, exclude_attrs=exclude_attrs)
    assert mal.accts == expected, "dicts are not equal"
    assert set(mal.attributes()) == set(expected[0].keys())


@pytest.mark.parametrize(
    "path, test_input, expected",
    [
        (None, [{"id": "10"}], [{"id": "10"}]),
        (["accounts"], {"accounts": [{"id": "10"}]}, [{"id": "10"}]),
        (["csp", "accounts"], {"csp": {"accounts": [{"id": "10"}]}}, [{"id": "10"}]),
    ],
)
def test_load_with_path(path, test_input, expected):
    mal = acctload.MetaAccountLoader(test_input, path=path)
    assert mal.accts == expected, "dicts are not equal"


@pytest.mark.parametrize(
    "path, test_input, expected",
    [
        (None, {"accounts": [{"id": "10"}]}, TypeError),
        ([], {"accounts": [{"id": "10"}]}, TypeError),
        (["csp", "accounts"], {"csp": {"accts": [{"id": "10"}]}}, ValueError),
    ],
)
def test_load_with_invalid_path(path, test_input, expected):
    with pytest.raises(expected):
        acctload.MetaAccountLoader(test_input, path=path)


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ({}, {}),
        ({"id": True}, {"id": True}),
        ({"Id": True, "Name": "pete"}, {"Id": True, "Name": "pete"}),
        ({"@Id": True, "Name": "pete"}, {"_Id": True, "Name": "pete"}),
        ({"Id": True, "0Name": "pete"}, {"Id": True, "_0Name": "pete"}),
        ({"@Id": True, "0Name": "pete"}, {"_Id": True, "_0Name": "pete"}),
    ],
)
def test_convert_keys_to_valid_attribute_names(test_input, expected):
    # pylint: disable=protected-access
    acctload._convert_keys_to_valid_attribute_names(test_input)
    assert test_input == expected, "dict key names not rewritten"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("name", "name"),
        ("Name", "Name"),
        ("NAME", "NAME"),
        ("n1me", "n1me"),
        ("nam3", "nam3"),
        ("1name", "_1name"),
        ("123name", "_123name"),
        ("_name", "_name"),
        ("_1name", "_1name"),
        ("__name", "__name"),
        ("n@me", "n_me"),
        ("@name", "_name"),
        ("@name@", "_name_"),
        ("@@name", "__name"),
        ("if", "if_"),
        ("while", "while_"),
        ("While", "While"),
        ("0then", "_0then"),
    ],
)
def test_make_valid_attribute_name(test_input, expected):
    # pylint: disable=protected-access
    assert acctload._make_valid_attribute_name(test_input) == expected
