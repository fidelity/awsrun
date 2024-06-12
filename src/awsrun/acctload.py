#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Loads account objects and metadata for those accounts.

## Overview

This module provides an `AccountLoader` which is responsible for loading objects
that represent accounts and attaching metadata associated with those accounts to
the objects as attributes. Users will pass this list of objects to
`awsrun.runner.AccountRunner.run`, which schedules the concurrent execution of a
command across this list of accounts. Each account object is made available to
the `awsrun.runner.Command.execute` method allowing users to pass whatever
objects and metadata they choose to their commands.

Several concrete implementations of the `AccountLoader` abstract base class are
provided by this module: `IdentityAccountLoader`, `CSVAccountLoader`,
`JSONAccountLoader`, and `YAMLAccountLoader`. These loaders are used by the
`awsrun.cli` to obtain the list of accounts and to filter those accounts by
metadata attributes specified on the command line. The CLI instantiates a loader
by calling the the plug-ins defined in `awsrun.plugins.accts`.

The `IdentityAccountLoader` is intended for use when no additional metadata is
to be associated with accounts. It simply returns account objects that are
strings of account IDs. `CSVAccountLoader` loads accounts and metadata from CSVs
while `JSONAccountLoader` and `YAMLAccountLoader` do so via JSON and YAML
respectively. Data is loaded from URLs and support file-based URLs for local
data. The CSV, JSON, and YAML loaders are subclasses of `MetaAccountLoader`.

The `MetaAccountLoader` provides a convenient object wrapper to an account and
its metadata which is made available via attributes on the object. Users can
utilize this loader to build their own loaders to pull data from databases or
other CMDBs. The `MetaAccountLoader` only requires a list of dicts representing
accounts and their metadata.  Under the covers, the loader dynamically creates a
subclass of `AbstractAccount`, which provides a lightweight object interface to
the dict.

Two exceptions are defined in this module. `AccountsNotFoundError` is raised
when `AccountLoader.accounts` cannot find one of the accounts explicitly
requested by the caller. The other exception, `InvalidFormatTemplateError`, is
raised when the format string passed to `MetaAccountLoader` constructor refers
to attributes that are not present in the accounts being loaded.
"""

import csv
import io
import itertools
import json
import keyword
import logging
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from functools import reduce
from pathlib import Path

import requests
import yaml
from requests.auth import AuthBase
from requests_file import FileAdapter

from awsrun.cache import PersistentExpiringValue

LOG = logging.getLogger(__name__)


class AccountLoader:
    """Abstract base class to load objects representing accounts.

    An `AccountLoader` is responsible for building objects representing accounts
    and attaching metadata attributes to those accounts as well as providing a
    mechanism to obtain the account ID from one of those objects.

    Subclasses must provide implementations for `acct_id`, `attributes`, and
    `accounts`.
    """

    def acct_id(self, acct):
        """Returns the account ID as a string associated with the `acct` object."""
        raise NotImplementedError

    def attributes(self):
        """Returns a dict of all metadata attribute names and values."""
        raise NotImplementedError

    def accounts(self, acct_ids=None, include=None, exclude=None):
        """Returns a list of account objects representing accounts and metadata.

        Without any arguments, all accounts are returned. A list of `acct_ids`
        may be provided to limit the list to accounts matching the account IDs.
        Duplicate account IDs do not result in duplicate account objects. To
        filter the list based on account metadata, `include` and `exclude` dicts
        can be specified identifying the keys and matching values.
        """
        raise NotImplementedError


class IdentityAccountLoader(AccountLoader):
    """An `AccountLoader` that uses strings of IDs to represent accounts.

    This class does not load accounts from an external data source such as a
    file, database, or web server. Because the account objects created by this
    class are simple strings, there is no additional metadata associated with an
    account, nor is it possible to filter accounts by metadata.

    This class is used by the `awsrun.cli` when a user does not provide their
    own `AccountLoader` via the configuration file. It allows users to use
    awsrun without needing an external source of accounts because account
    objects are simply represented as strings of account IDs that can be
    specified on the CLI.

    This is the most basic `AccountLoader` and is useful if one does not have
    want to adorn accounts IDs with additional data. It does mean that the
    account object passed to `Command.execute` is simply a string representing
    the account ID.
    """

    def acct_id(self, acct):
        """Returns the account ID associated with the `acct` object.

        This is an identity function as the account ID of an account object
        loaded by this class is the account object itself, thus `acct` returned.
        """
        return acct

    def attributes(self):
        """Returns a dict of all metadata attribute names and values.

        `IdentityAccountLoader` builds account objects that are simply strings
        representing the ID of an account. Because there is no other metadata
        associated with these objects, this method returns an empty dict.
        """
        return {}

    def accounts(self, acct_ids=None, include=None, exclude=None):
        """Returns a list of account objects.

        Without any arguments, no accounts are returned because this class does
        not load a list of accounts from an external data source. Instead, this
        method returns the same list of `acct_ids` as the list of account
        objects without duplicates. It is an identity function. Because there
        are no loaded accounts, use of `include` and `exclude` parameters will
        raise an AttributeError.
        """
        if include or exclude:
            raise AttributeError("Cannot use filters as no attributes are defined")

        if acct_ids is None:
            return []

        return list(set(acct_ids))


class MetaAccountLoader(AccountLoader):
    """An `AccountLoader` that loads account objects from dicts of metadata.

    This class dynamically creates a `AbstractAccount` subclass customized to
    represent a group of accounts that share common metadata attributes. For
    each account represented in `accts`, an object of this subclass is created.
    Each account object is then associated with attributes corresponding to the
    metadata associated with the account as well as a custom string formatter.

    The `accts` parameter must be a list of account dicts containing key/values
    representing the metadata associated with an account:

        accts = [
            {'id': '100200300400', 'env': 'prod', 'status': 'active'},
            {'id': '200300400100', 'env': 'prod', 'status': 'suspended'},
            {'id': '300400100200', 'env': 'dev', 'status': 'active'},
        ]
        loader = MetaAccountLoader(accts)

    Alternatively, `accts` can be a dict that contains a list of account dicts
    within:

        accts = {
            '100200300400': {'env': 'prod', 'status': 'active'},
            '200300400100': {'env': 'prod', 'status': 'suspended'},
            '300400100200': {'env': 'dev', 'status': 'active'},
        }
        loader = MetaAccountLoader(accts)

    In either case, the account loader will build account objects with the
    following attribute names: `id`, `env`, `status`. These can be accessed via
    object notation:

        accts = loader.accounts()

        # Let's inspect the 1st account object and its metadata
        assert accts[0].id == '100200300400'
        assert accts[0].env == 'prod'
        assert accts[0].status == 'active'

    Note: the account dicts contained within `accts` are the backing store for
    the account objects created to avoid copying. In addition, the keys may be
    mutated by depending on the values of other parameters passed to the
    constructor. If this is not desired, then pass a deep copy of `accts` to the
    constructor.

    If the list of account dicts is embedded within the dict, the `path`
    parameter can be used to extract the list. It should be a list of string
    keys to follow. For example, given this dict of accounts:

        accts = {
            'Accounts': {
                '100200300400': {'env': 'prod', 'status': 'active'},
                '200300400100': {'env': 'prod', 'status': 'suspended'},
                '300400100200': {'env': 'dev', 'status': 'active'},
            }
        }
        loader = MetaAccountLoader(accts, path=['Accounts'])

        accts = {
            'AWS': {
                'Accounts': [
                    {'id': '100200300400', 'env': 'prod', 'status': 'active'},
                    {'id': '200300400100', 'env': 'prod', 'status': 'suspended'},
                    {'id': '300400100200', 'env': 'dev', 'status': 'active'},
                ]
            }
        }
        loader = MetaAccountLoader(accts, path=['AWS', 'Accounts'])

    It is important that the attribute name representing the account ID is
    provided via the `id_attr` parameter, so `MetaAccountLoader.acct_id` can
    return the account ID for a given account object. By default, the value of
    `id_attr` is the string `'id'`. The following would require `acct` to be
    specified as the value of the `id_attr` argument:

        accts = [
            {'acct': '100200300400', 'env': 'prod', 'status': 'active'},
            {'acct': '200300400100', 'env': 'prod', 'status': 'suspended'},
            {'acct': '300400100200', 'env': 'dev', 'status': 'active'},
        ]

        loader = MetaAccountLoader(accts, id_attr='acct')
        objs = loader.accounts(acct_ids=['200300400100'])
        assert [loader.acct_id(a) for a in objs] == ['200300400100']

    The account loader builds account objects with the following attributes in
    the example above: acct, env, status. In cases where the dict keys are not
    valid Python identifiers, they are munged. Leading digits are prefixed with
    underscores, non-alpha numeric characters are replaced with underscores, and
    keywords are appended with an underscore:

        accts = [
            {'id': '100200300400', '@env': 'prod', '00st@tus': 'active'},
            {'id': '200300400100', '@env': 'prod', '00st@tus': 'suspended'},
            {'id': '300400100200', '@env': 'dev', '00st@tus': 'active'},
        ]
        loader = acctload.MetaAccountLoader(accts)
        acct = loader.accounts(acct_ids=['200300400100'])[0]
        assert acct._env == 'prod'
        assert acct._00st_tus == 'active'

    Even if some of the dict keys are missing, the account objects will still
    have the attribute, but its value will be None. This ensures that an
    exception is not raised when accessing a non-existent key:

        accts = [
            {'id': '100200300400', 'status': 'active'},
            {'id': '200300400100', },
            {'id': '300400100200', 'env': 'dev', 'status': 'active'},
        ]
        loader = acctload.MetaAccountLoader(accts)
        acct = loader.accounts(acct_ids=['200300400100'])[0]
        assert acct.id == '200300400100'
        assert acct.env is None
        assert acct.status is None

    In addition to the attributes defined, the account objects will have a
    default `__str__` implementation that generates a string representing the
    account ID of the account. This can be overridden by providing a
    `str_template` parameter. For example, the following string templates would
    generate the following:

        '{id}'                =>  '100200300400'  # default
        '{id}/{env}'          =>  '100200300400/prod'
        'acct={id}'           =>  'acct=100200300400'
        '{id}-{env}-{status}' =>  '100200300400-prod-active'

    By default, all attributes from the account dicts are included in the
    generated account objects. These can be overridden by specifying lists of
    attribute names in `include_attrs` and/or `exclude_attrs`. The attribute
    name representing the account ID must be include in the selected attribute
    names. In addition, all of the attributes referenced in `str_template`.
    """

    def __init__(
        self,
        accts,
        id_attr="id",
        path=None,
        str_template=None,
        include_attrs=None,
        exclude_attrs=None,
    ):
        if not id_attr:
            raise ValueError("Must provide a non-None id_attr name")

        self.id_attr = id_attr
        self.path = [] if path is None else path
        self.str_template = str_template or "{" + id_attr + "}"
        self.include_attrs = [] if include_attrs is None else include_attrs
        self.exclude_attrs = [] if exclude_attrs is None else exclude_attrs

        # Build a custom Account class with class variable _str_template set,
        # which is used by the  __str__ implementation.  Instead of dynamically
        # creating a custom class, a predefined Account class could have been
        # made and its class variable _str_template could have simply been set.
        # But, this would limit a user from loading accounts from different
        # dicts that might contain different metadata keys. Dynamically creating
        # the class allows a custom class attribute for each.
        self.CustomAccount = type(
            "Account", (AbstractAccount,), {"__slots__": "_attrs"}
        )
        self.CustomAccount._str_template = (  # type: ignore
            self.str_template
        )  # pylint: disable=protected-access

        self.accts, self.attrs = self._parse(accts)
        LOG.info(
            "loaded %d accounts with the metadata attributes: %s",
            len(self.accts),
            self.attrs,
        )

    def acct_id(self, acct):
        """Returns the account ID associated with the `acct` object.

        The `acct` parameter must be an account object that was created by an
        instance of this `MetaAccountLoader` via `MetaAccountLoader.accounts`.
        This method returns the string representing the account ID of the
        account object.
        """
        return getattr(acct, self.id_attr)

    def attributes(self):
        """Returns a dict of all metadata attribute names and values.

        This method returns the metadata associated with the account objects
        created by this instance of `MetaAccountLoader`. The keys of the
        returned dict are the attribute names attached to the account objects.
        The value of each key is a set representing all of the possible values
        assigned to that attribute. For example:

            accts = [
                {'id': '100200300400', 'env': 'prod', 'status': 'active'},
                {'id': '200300400100', 'env': 'prod', 'status': 'suspended'},
                {'id': '300400100200', 'env': 'dev', 'status': 'active'},
            ]
            loader = acctload.MetaAccountLoader(accts)
            attrs = loader.attributes()
            assert attrs['env'] == {'prod', 'dev'}
            assert attrs['status'] == {'active', 'suspended'}
            assert attrs['id'] == {'100200300400', '200300400100', '300400100200'}
        """
        d = defaultdict(set)
        for acct in self.accts:
            for attr, value in acct.items():
                d[attr].add(value)
        return d

    def accounts(self, acct_ids=None, include=None, exclude=None):
        """Returns a list of account objects.

        Without any arguments, account objects for all accounts are returned. A
        list of `acct_ids` may be provided to limit the list to accounts
        matching the account IDs. If one or more specified account IDs is
        missing, `AccountsNotFoundError` is raised.

        The returned list of accounts can be filtered further by providing dicts
        for `include` and `exclude` parameters that specify attributes and a
        list of values for those attributes that must match. For example,
        assuming the following accounts:

            accts = [
                {'id': '100200300400', 'env': 'prod', 'status': 'active'},
                {'id': '200300400100', 'env': 'prod', 'status': 'suspended'},
                {'id': '300400100200', 'env': 'dev', 'status': 'active'},
            ]
            loader = acctload.MetaAccountLoader(accts)

        To filter active accounts, use the following:

            include = {'status': ['active']}

        To filter active *and* production accounts:

            include = {'status': ['active'], 'env': ['prod']}

        To filter production accounts, but not suspended:

            include = {'env': ['prod']}
            exclude = {'status': ['suspended']}

        To filter active *or* suspended accounts, but not dev accounts:

            include = {'status': ['active', 'suspended']}
            exclude = {'env': ['dev']}

        Both `include` and `exclude` filters are applied after the initial
        account list has been determined, which is all accounts unless it was
        first limited by `acct_ids`. Then, the `include` filter is applied,
        followed by the `exclude` filter. If a filter dict has multiple keys,
        then *each* key must match. A key matches if at least *one* of the
        values matches as illustrated in the examples above. If a filter refers
        to an invalid attribute name, `AttributeError` is raised. Finally, if
        `include` is not set, then all accounts are matched. Likewise, if
        `exclude` is not set, then no accounts are excluded.
        """
        accts = self.accts
        acct_ids = [] if acct_ids is None else acct_ids
        include = {} if include is None else include
        exclude = {} if exclude is None else exclude

        # Limit our account list to the requested IDs
        if acct_ids:
            requested = set(acct_ids)
            all_ids = (a[self.id_attr] for a in self.accts)

            missing_acct_ids = requested.difference(all_ids)
            if missing_acct_ids:
                raise AccountsNotFoundError(list(missing_acct_ids))

            accts = (a for a in self.accts if a[self.id_attr] in requested)

        # Make sure the filters contain valid attribute names
        for attr in itertools.chain(include.keys(), exclude.keys()):
            if attr not in self.attrs:
                raise AttributeError(f"Invalid attribute '{attr}' in filter")

        # Limit our account list by the user-supplied filters
        return [
            self.CustomAccount(a) for a in accts if self._filter(a, include, exclude)
        ]

    @staticmethod
    def _filter(acct, include, exclude):
        """Filter accounts based on `include` and `exclude` dicts.

        The `include` filter is applied first, followed by the `exclude` filter.
        If a filter has multiple keys, then *each* key must match. A key matches
        if at least *one* of the values matches.  Finally, if `include` is not
        set, then all accounts are matched. Likewise, if `exclude` is not set,
        then no accounts are excluded.
        """

        # This internal representation of an account is a dict here, not the
        # same as the account object that is created via `MetaAccountLoader`
        # which is why we used dict notation when accessing the account.
        def test(dictionary, default):
            if not dictionary:
                return default
            return all(
                any(acct[attr] == v for v in values)
                for attr, values in dictionary.items()
            )

        included = test(include, True)
        excluded = test(exclude, False)
        return included and not excluded

    def _parse(self, accts):
        """Returns a tuple of a a list of account dicts and a set of valid attribute names."""

        # If accts is a dict that was created from JSON, the accounts we are
        # interested might be stored under a key within, so use the path
        # provided by the user to select them.
        if isinstance(accts, dict) and self.path:
            accts = self._select_path(accts)

        # If accts is still a dict, that likely means we have a dict where the
        # keys are account IDs and the values are dicts of key/value data
        # associated with an account.
        if isinstance(accts, dict):
            accts = self._convert_dict_of_accts_to_list(accts)

        # If accts is still not a list of dicts of key/value account data, then
        # the user has provided an invalid list of accounts.
        if not isinstance(accts, list):
            raise TypeError(
                f"Account list must be a list of dicts or dict of dicts: {accts}"
            )

        self._ensure_id_attr_exists(accts)
        self._ensure_ids_are_strings(accts)
        self._normalize_attribute_names(accts)
        attrs = self._filter_attribute_names(accts)
        self._ensure_valid_str_template(attrs)

        return accts, attrs

    def _select_path(self, accts):
        """Returns the object found by indexing into accts using each element
        of `self.path`.

        If indexing fails, a `ValueError` is raised. For example, if `self.path` is
        `['results', 'accounts']`, then:

            self._select_path({
                'results': {
                    'accounts': {
                        [1, 2, 3, 4]
                    }
                }
            })

            => [1, 2, 3, 4]
        """
        try:
            return reduce(lambda d, p: d[p], self.path, accts)
        except Exception as e:
            raise ValueError(
                "Cannot find accounts, did you specify the correct path?"
            ) from e

    def _convert_dict_of_accts_to_list(self, accts):
        """Converts a dict of accounts to a list of accounts.

        The keys of the input dict should be account IDs and the values should
        be another dict of account metadata. For example, given the input and
        `self.id_attr` equal to `'id'`, then:

            _convert_dict_accts_to_list({
                '100200300400': {'id': '100200300400', 'env': 'prod'},
                '200300400100': {'id': '200300400100', 'env': 'nonprod'}})

            => [{'id': '100200300400', 'env': 'prod'},
                {'id': '200300400100', 'env': 'nonprod'}]

        This method will unsure that `self.id_attr` is included in the metadata
        if it was not part of the account dict data. For example, given the
        input and `self.id_attr` equal to `'id'`, then:

            _convert_dict_accts_to_list({
                '100200300400': {'env': 'prod'},
                '200300400100': {'env': 'nonprod'}})

            => [{'id': '100200300400', 'env': 'prod'},
                {'id': '200300400100', 'env': 'nonprod'}]
        """
        for key, acct in accts.items():
            if not isinstance(acct, dict):
                raise TypeError(
                    "Accounts are not dicts, did you specify the correct path?"
                )

            if self.id_attr not in acct:
                acct[self.id_attr] = key

            if key != acct[self.id_attr]:
                raise ValueError(
                    f"Account IDs do not match: '{key}' != '{acct[self.id_attr]}'"
                )

        return list(accts.values())

    def _ensure_ids_are_strings(self, accts):
        """Raises `ValueError` if account ID is not a string."""
        for acct in accts:
            acct_id = acct[self.id_attr]
            if not isinstance(acct_id, str):
                raise ValueError(f"Account ID '{acct_id}' is not a string of digits")

    def _ensure_id_attr_exists(self, accts):
        """Raises `ValueError` if `self.id_attr` is not in each account dict."""
        for acct in accts:
            if self.id_attr not in acct:
                raise ValueError(f"No '{self.id_attr}' attribute in account '{acct}'")

    def _ensure_valid_str_template(self, attrs):
        """Raises `InvalidFormatTemplateError` if `self.str_template` contains
        invalid attributes that are not present in the account dicts.
        """
        tokens = re.findall(r"\{(\w+)(?::[^}]+)?\}", self.str_template, re.ASCII)
        unknown = set(tokens).difference(attrs)
        if unknown:
            raise InvalidFormatTemplateError(unknown, list(attrs))

    def _normalize_attribute_names(self, accts):
        """Renames keys of acct dicts if invalid Python attribute names.

        This function modifies the accts dict in place.
        """
        for acct in accts:
            _convert_keys_to_valid_attribute_names(acct)

    def _filter_attribute_names(self, accts):
        """Returns the set of selected attributes based on include/exclude filters
        as well as adds missing keys or deletes unused keys.

        This function modifies the accts dict in place.
        """
        if self.include_attrs and self.id_attr not in self.include_attrs:
            raise ValueError(f"Must include '{self.id_attr}' in include_attrs")
        if self.id_attr in self.exclude_attrs:
            raise ValueError(f"Cannot exclude '{self.id_attr}' from exclude_attrs")

        # Create a set of attribute names used across all acct dicts
        attrs = set()
        for acct in accts:
            attrs.update(acct.keys())

        # Filter that full set based on the include/exclude lists
        if self.include_attrs:
            attrs = attrs.intersection(self.include_attrs)
        attrs = attrs.difference(self.exclude_attrs)

        # Using the filtered attribute set, update the acct dicts in place
        for acct in accts:
            insert_keys, delete_keys = [], []
            for key in acct:
                delete_keys = [k for k in acct if k not in attrs]
                insert_keys = [k for k in attrs if k not in acct]
            for key in insert_keys:
                acct[key] = None
            for key in delete_keys:
                acct.pop(key, None)

        # Return the filtered attribute set
        return attrs


class CSVAccountLoader(MetaAccountLoader):
    """Returns an `AccountLoader` with accounts loaded from a CSV file/url.

    Loaded accounts will include metadata associated with each account in the
    CSV document retrieved from the `url`. File based URLs can be used to load
    data from a local file. To cache the CSV results, specify the number of
    seconds via `max_age`. By default, the data in not cached.

    The delimiter used in the file can be changed via the `delimiter` parameter.
    The default value is comma. The column names, specified on the first row of
    the CSV file, will become attributes on the loaded account objects. Given
    the following CSV file:

         id, env, status
         100200300400, prod, active
         200300400100, non-prod, active
         300400100200, non-prod, suspended

    The account loader will build account objects with the following attribute
    names: `id`, `env`, `status`. For example, assume the above CSV file is
    called `accts.csv`:

        loader = CSVAccountLoader('accts.csv')
        accts = loader.accounts()

        # Let's inspect the 1st account object and its metadata
        assert accts[0].id == '100200300400'
        assert accts[0].env == 'prod'
        assert accts[0].status == 'active'

    CSVAccountLoader is a subclass of the `MetaAccountLoader`, which is passed a
    set of account dicts loaded from the CSV. As such, the remainder of the
    parameters in the constructor -- `id_attr`, `str_template`, `include_attrs`,
    and `exclude_attrs` -- are defined in the constructor of
    `MetaAccountLoader`.
    """

    def __init__(
        self,
        url,
        max_age=0,
        delimiter=",",
        id_attr="id",
        str_template=None,
        include_attrs=None,
        exclude_attrs=None,
        no_verify=False,
    ):
        include_attrs = [] if include_attrs is None else include_attrs
        exclude_attrs = [] if exclude_attrs is None else exclude_attrs

        session = requests.Session()
        session.mount("file://", FileAdapter())

        def load_cache():
            r = session.get(url, verify=not no_verify)
            r.raise_for_status()
            buf = io.StringIO(r.text.strip())
            return list(csv.DictReader(buf, delimiter=delimiter, skipinitialspace=True))

        cache_file = Path(tempfile.gettempdir(), "awsrun.dat")
        accts = PersistentExpiringValue(load_cache, cache_file, max_age=max_age)

        super().__init__(
            accts.value(),
            id_attr=id_attr,
            str_template=str_template,
            include_attrs=include_attrs,
            exclude_attrs=exclude_attrs,
        )


class JSONAccountLoader(MetaAccountLoader):
    """Returns an `AccountLoader` with accounts loaded from JSON.

    Loaded accounts will include metadata associated with each account in the
    JSON document retrieved from the `url`. File based URLs can be used to load
    data from a local file. To cache the JSON results, specify the number of
    seconds via `max_age`. By default, the data is not cached. Given the
    following JSON:

        {
            "Accounts": [
                {"id": "100200300400", "env": "prod", "status": "active"},
                {"id": "200300400100", "env": "non-prod", "status": "active"},
                {"id": "300400100200", "env": "non-prod", "status": "suspended"}
            ]
        }

    The account loader will build account objects with the following attribute
    names: `id`, `env`, `status`. Assume the above JSON is returned from
    http://example.com/accts.json:

        loader = JSONAccountLoader('http://example.com/accts.json', path=['Accounts'])
        accts = loader.accounts()

        # Let's inspect the 1st account object and its metadata
        assert accts[0].id == '100200300400'
        assert accts[0].env == 'prod'
        assert accts[0].status == 'active'

    JSONAccountLoader is a subclass of the `MetaAccountLoader`, which loads
    accounts from a set of dicts. As such, the remainder of the parameters in
    the constructor -- `id_attr`, `path`, `str_template`, `include_attrs`, and
    `exclude_attrs` -- are defined in the constructor of `MetaAccountLoader`.
    """

    def __init__(
        self,
        url,
        max_age=0,
        id_attr="id",
        path=None,
        str_template=None,
        include_attrs=None,
        exclude_attrs=None,
        no_verify=False,
    ):
        path = [] if path is None else path
        include_attrs = [] if include_attrs is None else include_attrs
        exclude_attrs = [] if exclude_attrs is None else exclude_attrs

        session = requests.Session()
        session.mount("file://", FileAdapter())

        def load_cache():
            r = session.get(url, verify=not no_verify)
            r.raise_for_status()
            return r.json()

        cache_file = Path(tempfile.gettempdir(), "awsrun.dat")
        accts = PersistentExpiringValue(load_cache, cache_file, max_age=max_age)

        super().__init__(
            accts.value(),
            id_attr=id_attr,
            path=path,
            str_template=str_template,
            include_attrs=include_attrs,
            exclude_attrs=exclude_attrs,
        )


class YAMLAccountLoader(MetaAccountLoader):
    """Returns an `AccountLoader` with accounts loaded from YAML.

    Loaded accounts will include metadata associated with each account in the
    YAML document retrieved from the `url`. File based URLs can be used to load
    data from a local file. To cache the YAML results, specify the number of
    seconds via `max_age`. By default, the data is not cached. Given the
    following YAML:

          Accounts:
            - id: '100200300400'
              env: prod
              status: active
            - id: '200300400100'
              env: non-prod
              status: active
            - id: '300400100200'
              env: non-prod
              status: suspended

    The account loader will build account objects with the following attribute
    names: `id`, `env`, `status`. Assume the above YAML is returned from
    http://example.com/accts.yaml:

        loader = YAMLAccountLoader('http://example.com/accts.yaml', path=['Accounts'])
        accts = loader.accounts()

        # Let's inspect the 1st account object and its metadata
        assert accts[0].id == '100200300400'
        assert accts[0].env == 'prod'
        assert accts[0].status == 'active'

    YAMLAccountLoader is a subclass of the `MetaAccountLoader`, which loads
    accounts from a set of dicts. As such, the remainder of the parameters in
    the constructor -- `id_attr`, `path`, `str_template`, `include_attrs`, and
    `exclude_attrs` -- are defined in the constructor of `MetaAccountLoader`.
    """

    def __init__(
        self,
        url,
        max_age=0,
        id_attr="id",
        path=None,
        str_template=None,
        include_attrs=None,
        exclude_attrs=None,
        no_verify=False,
    ):
        path = [] if path is None else path
        include_attrs = [] if include_attrs is None else include_attrs
        exclude_attrs = [] if exclude_attrs is None else exclude_attrs

        session = requests.Session()
        session.mount("file://", FileAdapter())

        def load_cache():
            r = session.get(url, verify=not no_verify)
            r.raise_for_status()
            return yaml.safe_load(r.text)

        cache_file = Path(tempfile.gettempdir(), "awsrun.dat")
        accts = PersistentExpiringValue(load_cache, cache_file, max_age=max_age)

        super().__init__(
            accts.value(),
            id_attr=id_attr,
            path=path,
            str_template=str_template,
            include_attrs=include_attrs,
            exclude_attrs=exclude_attrs,
        )


class AzureCLIAccountLoader(MetaAccountLoader):
    """Creates an `awsrun.acctload.AccountLoader` with accounts loaded from the Azure CLI.

    The following metadata is attached to each account: `id` (str), `name`
    (str), `cloudName` (str), `tenantId` (str), `homeTenantId` (str), `state`
    (str), and `isDefault` (bool). In addition, the name of an Azure
    subscription can be parsed for additional metadata attributes. For example,
    assume the following Azure subscription names:

    - azure-retail-prod
    - azure-retail-nonprod
    - azure-wholesale-prod
    - azure-wholesale-nonprod

    Setting the `name_regexp` argument to the following regexp
    `^azure-(?P<bu>[^-]+)-(?P<env>.*)` will attach the `bu` and `env` metadata
    attributes as well. More precisely, each **named** capture group in the
    pattern becomes an available metadata attribute. If a subscription name does
    not match the pattern, the additional attributes will be set to `None`.
    """

    def __init__(self, name_regexp=None):
        if not shutil.which("az"):
            raise FileNotFoundError(
                "error: Please install the Azure CLI and ensure 'az' is in your path"
            )

        # Check to make sure it's a valid regexp. Don't catch exception as
        # azurerun will catch it and report to user.
        if name_regexp:
            try:
                name_regexp = re.compile(name_regexp)
            except re.error as e:
                raise ValueError(f"Subscription name regexp invalid: {e}") from e
            if not name_regexp.groupindex:
                raise ValueError("Subscription name regexp has no named capture groups")

        # Use the Azure CLI to get the list of subscriptions the user has access
        # to. It is up to the user to run az login. If they don't we'll print
        # that error.
        result = subprocess.run(
            ["az", "account", "list", "--all"], capture_output=True, check=True
        )

        # The Azure CLI always returns 0, so we must check to see if anything
        # was sent to stderr.
        if result.stderr:
            raise RuntimeError(result.stderr.decode("utf-8"))

        accts = []
        for subscription in json.loads(result.stdout):
            # Remove non-scalar elements
            subscription.pop("user", None)
            subscription.pop("managedByTenants", None)

            if not name_regexp:
                accts.append(subscription)
                continue

            match = name_regexp.search(subscription.get("name"))
            if match:
                for k, v in match.groupdict().items():
                    subscription[k] = v
            else:
                LOG.info(
                    "%s does not match %s",
                    name_regexp.pattern,
                    subscription.get("name"),
                )
            accts.append(subscription)

        super().__init__(accts)


class CSVParser:
    """Returns a list of dicts from a buffer of CSV text.

    To override options passed to `csv.DictReader`, specify them as keyword
    arguments in the constructor. By default, the `delimiter` is `","` and
    `skipinitialspace` is `True`.
    """

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.kwargs.setdefault("delimiter", ",")
        self.kwargs.setdefault("skipinitialspace", True)

    def __call__(self, text):
        buf = io.StringIO(text.strip())
        return list(csv.DictReader(buf, **self.kwargs))


class JSONParser:
    """Returns a list or dict from a buffer of JSON-formatted text.

    To override options passed to `json.loads`, specify them as keyword
    arguments in the constructor.
    """

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __call__(self, text):
        return json.loads(text, **self.kwargs)


class YAMLParser:
    """Returns a list or dict from a buffer of YAML-formatted text.

    To override options passed to `yaml.safe_load`, specify them as keyword
    arguments in the constructor.
    """

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __call__(self, text):
        return yaml.safe_load(text, **self.kwargs)


class HTTPOAuth2(AuthBase):
    """Attaches an OAuth2 bearer token to the given `requests.Request` object.

    Use `token_url` to specify the token provider's URL. The `client_id` and
    `client_secret` specify the credentials used to authenticate with the
    token provider. Three additional keyword parameters are accepted:

    `scope`
    : Default is "AppIdClaimsTrust".

    `grant_type`
    : Default is "client_credentials".

    `intent`
    : Default is "awsrun account loader plugin"
    """

    def __init__(
        self,
        token_url,
        username,
        password,
        scope="AppIdClaimsTrust",
        grant_type="client_credentials",
        intent="awsrun account loader plugin",
    ):
        self.url = token_url
        self.data = {}
        self.data["client_id"] = username
        self.data["client_secret"] = password
        self.data["scope"] = scope
        self.data["grant_type"] = grant_type
        self.data["intent"] = intent

    def _get_token(self):
        resp = requests.post(self.url, data=self.data)
        resp.raise_for_status()
        return resp.json()["access_token"]

    def __call__(self, req):
        req.headers["Authorization"] = f"Bearer {self._get_token()}"
        return req


class URLAccountLoader(MetaAccountLoader):
    """Returns an `AccountLoader` with accounts loaded from a URL.

    Loaded accounts will include metadata associated with each account in the
    document retrieved from the `url`. File based URLs can be used to load
    data from a local file. This data will be parsed as JSON by default. To
    override, use `parser` to specify a callable that accepts the text and
    returns a list or dict of accounts (see `MetaAccountLoader`). To cache the
    results, specify a non-zere number of seconds in `max_age`.  The default
    location on disk is the system temp directory in a file called
    `awsrun.dat`, which can be overrided via `cache_path`.

    Given the following JSON:

        {
            "Accounts": [
                {"id": "100200300400", "env": "prod", "status": "active"},
                {"id": "200300400100", "env": "non-prod", "status": "active"},
                {"id": "300400100200", "env": "non-prod", "status": "suspended"}
            ]
        }

    The account loader will build account objects with the following attribute
    names: `id`, `env`, `status`. Assume the above JSON is returned from
    http://example.com/accts.json:

        loader = URLAccountLoader('http://example.com/accts.json', path=['Accounts'])
        accts = loader.accounts()

        # Let's inspect the 1st account object and its metadata
        assert accts[0].id == '100200300400'
        assert accts[0].env == 'prod'
        assert accts[0].status == 'active'

    URLAccountLoader is a subclass of the `MetaAccountLoader`, which loads
    accounts from a set of dicts. As such, the remainder of the parameters in
    the constructor -- `id_attr`, `path`, `str_template`, `include_attrs`, and
    `exclude_attrs` -- are defined in the constructor of `MetaAccountLoader`.
    """

    def __init__(
        self,
        url,
        parser=JSONParser(),
        auth=None,
        max_age=0,
        id_attr="id",
        path=None,
        str_template=None,
        include_attrs=None,
        exclude_attrs=None,
        no_verify=False,
        cache_path=None,
    ):

        session = requests.Session()
        session.mount("file://", FileAdapter())

        def load_cache():
            r = session.get(url, auth=auth, verify=not no_verify)
            r.raise_for_status()
            return parser(r.text)

        if not cache_path:
            cache_path = Path(tempfile.gettempdir(), "awsrun.dat")

        accts = PersistentExpiringValue(load_cache, cache_path, max_age=max_age)

        super().__init__(
            accts.value(),
            id_attr=id_attr,
            path=[] if path is None else path,
            str_template=str_template,
            include_attrs=[] if include_attrs is None else include_attrs,
            exclude_attrs=[] if exclude_attrs is None else exclude_attrs,
        )


class AbstractAccount:
    """Abstract base class used by `MetaAccountLoader` to represent an account and its metadata.

    This class is dynamically subclassed by the account loader to create a
    unique `Account` class to hold account data. It is a lightweight subclass
    that contains a single fixed slot called `_attrs`, which is used to store a
    reference to the original account dicts passed to the constructor of
    `MetaAccountLoader`. The subclass allows for direct object access of those
    attributes by providing a `__getattr__` implementation.  In addition, a
    customized `__str__` implementation is provided based on the format string
    specified as a class attribute called `_str_template`.

    Although not meant to be used directly by users, here is an example showing
    the features of this abstract base class:

        class Account(AbstractAccount):
            _str_template = 'acct={id}'

        d = {'id': '100200300400', 'env': 'prod', 'status': 'active'}
        acct = Account(d)

        assert acct.id == '100200300400'
        assert acct.env == 'prod'
        assert acct.status == 'active'
        assert str(acct) == 'acct=100200300400'
        assert repr(acct) == 'Account(id="100200300400", env="prod", status="active")'
    """

    _str_template = None
    __slots__ = ("_attrs",)

    def __init__(self, attributes):
        self._attrs = attributes

    def __getattr__(self, name):
        value = self._attrs.get(name)
        if not value and name not in self._attrs:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )
        return value

    def __eq__(self, other):
        return self._attrs == other._attrs  # pylint: disable=protected-access

    def __repr__(self):
        pairs = (f"{k}={repr(v)}" for k, v in self._attrs.items())
        return f'Account({", ".join(pairs)})'

    def __str__(self):
        if not self._str_template:
            raise NotImplementedError(
                f"'{type(self).__name__}' class has no variable 'str_template'"
            )
        return self._str_template.format(**self._attrs)


class AccountsNotFoundError(Exception):
    """Raised if an account ID was not found.

    The `missing_acct_ids` attribute contains the missing IDs of the accounts not
    found.
    """

    def __init__(self, missing_acct_ids):
        self.missing_acct_ids = missing_acct_ids
        super().__init__(f'Account IDs not found: {", ".join(missing_acct_ids)}')


class InvalidFormatTemplateError(Exception):
    """Raised if the format template specified refers to unknown account
    attributes.

    The `valid_attrs` attribute contains a list of valid attribute names, and
    `unknown_attrs` contains a list of the unknown attribute names used in the
    format string of the Account object.
    """

    def __init__(self, unknown, valid):
        self.unknown_attrs = unknown
        self.valid_attrs = valid

        def quote(attrs):
            return ", ".join(["'" + a + "'" for a in attrs])

        super().__init__(
            f"Unknown attributes in format template: {quote(unknown)}. Valid attributes are: {quote(valid)}"
        )


def _convert_keys_to_valid_attribute_names(d):
    """Replace keys that are invalid Python identifiers or keywords with
    valid object attribute names.

    This function is useful when converting a dict to an object where its
    attributes are the dict keys. Because Python attribute names have
    restrictions, this function munges any dict keys that are not valid
    attribute names. For efficiency, the dictionary is modified in place.
    """
    invalid_keys = [k for k in d.keys() if not k.isidentifier() or keyword.iskeyword(k)]
    for key in invalid_keys:
        d[_make_valid_attribute_name(key)] = d.pop(key)


def _make_valid_attribute_name(s):
    """Return a string that is a valid Python attribute name.

    Leading digits are prefixed with underscores, non-alpha numeric characters
    are replaced with underscores, and keywords are appended with an underscore.
    This function ensures the string can be used as a valid object attribute
    name.
    """
    if not s.isidentifier():
        s = re.sub(r"[^0-9a-zA-Z_]", r"_", s)
        s = re.sub(r"^([0-9]+)", r"_\1", s)
    if keyword.iskeyword(s):
        s = s + "_"
    return s
