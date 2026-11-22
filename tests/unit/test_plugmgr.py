#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

import argparse

import pytest

from awsrun.acctload import AccountLoader
from awsrun.config import Config
from awsrun.plugmgr import PluginManager

IDENTITY = "awsrun.plugins.accts.Identity"


def make_manager(config=None):
    parser = argparse.ArgumentParser()
    return PluginManager(Config(config or {}), parser, argparse.Namespace(), [])


def test_instantiate_after_parse_args_uses_default():
    pm = make_manager()
    pm.parse_args("Accounts", default=IDENTITY)
    assert isinstance(pm.instantiate("Accounts", must_be=AccountLoader), AccountLoader)


def test_instantiate_without_parse_args_uses_default():
    """instantiate() promises to call parse_args() implicitly."""
    pm = make_manager()
    loader = pm.instantiate("Accounts", default=IDENTITY, must_be=AccountLoader)
    assert isinstance(loader, AccountLoader)


def test_instantiate_without_parse_args_uses_config():
    pm = make_manager({"Accounts": {"plugin": IDENTITY}})
    assert isinstance(pm.instantiate("Accounts", must_be=AccountLoader), AccountLoader)


def test_instantiate_rejects_wrong_type():
    pm = make_manager()
    with pytest.raises(TypeError, match="did not build"):
        pm.instantiate("Accounts", default=IDENTITY, must_be=str)
