#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

import argparse
import logging

import pytest

from awsrun.acctload import AccountLoader
from awsrun.config import Config
from awsrun.plugmgr import (
    PluginManager,
    _redact_argv,
    _redact_namespace,
    load_dotted_object,
)

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


def test_load_dotted_object_returns_object():
    assert load_dotted_object("awsrun.plugmgr.PluginManager") is PluginManager


def test_load_dotted_object_unknown_module():
    with pytest.raises(ImportError, match="cannot import 'no_such_pkg_xyz.Thing'"):
        load_dotted_object("no_such_pkg_xyz.Thing")


def test_load_dotted_object_unknown_attribute():
    with pytest.raises(ImportError, match="does not contain 'NoSuchPlugin'"):
        load_dotted_object("awsrun.plugmgr.NoSuchPlugin")


def test_load_dotted_object_reports_missing_dependency(tmp_path, monkeypatch):
    """A plug-in module that imports an uninstalled package must say so."""
    (tmp_path / "plugin_needing_dep.py").write_text(
        "import a_dependency_that_is_not_installed\n\nclass Thing:\n    pass\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(ImportError, match="a_dependency_that_is_not_installed"):
        load_dotted_object("plugin_needing_dep.Thing")


def test_missing_dependency_surfaces_as_config_error(tmp_path, monkeypatch):
    (tmp_path / "other_plugin_needing_dep.py").write_text(
        "import another_dependency_not_installed\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    pm = make_manager({"Accounts": {"plugin": "other_plugin_needing_dep.Thing"}})
    with pytest.raises(ValueError, match="another_dependency_not_installed"):
        pm.parse_args("Accounts")


def test_redact_namespace_masks_only_set_secrets():
    ns = argparse.Namespace(
        saml_password="hunter2",
        oauth2_password=None,
        client_secret="s3",
        session_token="tok",
        saml_username="pete",
        threads=10,
    )
    assert _redact_namespace(ns) == {
        "saml_password": "********",
        "oauth2_password": None,
        "client_secret": "********",
        "session_token": "********",
        "saml_username": "pete",
        "threads": 10,
    }


@pytest.mark.parametrize(
    "argv, expected",
    [
        ([], []),
        (["--region", "us-east-1"], ["--region", "us-east-1"]),
        (["--saml-password", "hunter2"], ["--saml-password", "********"]),
        (["--saml-password=hunter2"], ["--saml-password=********"]),
        (
            ["--loader-password", "p", "cmd", "--token", "t", "x"],
            ["--loader-password", "********", "cmd", "--token", "********", "x"],
        ),
        (["--saml-password"], ["--saml-password"]),
        (["password", "value"], ["password", "value"]),
    ],
)
def test_redact_argv(argv, expected):
    original = list(argv)
    assert _redact_argv(argv) == expected
    assert argv == original


@pytest.mark.parametrize(
    "argv",
    [
        ["--x-password", "hunter2", "--x-username", "pete"],
        ["--x-password=hunter2", "--x-username", "pete"],
        ["--x-username", "pete", "--not-mine-password", "hunter2"],
    ],
)
def test_parse_args_does_not_log_passwords(argv, caplog, tmp_path, monkeypatch):
    (tmp_path / "password_plugin_module.py").write_text(
        "from awsrun.plugmgr import Plugin\n\n\n"
        "class P(Plugin):\n"
        "    def __init__(self, parser, cfg):\n"
        "        super().__init__(parser, cfg)\n"
        "        parser.add_argument('--x-password')\n"
        "        parser.add_argument('--x-username')\n\n"
        "    def instantiate(self, args):\n"
        "        return args\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    pm = PluginManager(
        Config({}), argparse.ArgumentParser(), argparse.Namespace(), argv
    )
    with caplog.at_level(logging.DEBUG, logger="awsrun"):
        pm.parse_args("Credentials", default="password_plugin_module.P")

    assert "hunter2" not in caplog.text
    assert "pete" in caplog.text
    # The plug-in still receives the real value.
    args = pm.instantiate("Credentials")
    assert args.x_username == "pete"
    if "--not-mine-password" not in argv:
        assert args.x_password == "hunter2"
