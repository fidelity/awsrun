#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

import argparse
import json

import pytest

from awsrun import acctload
from awsrun.acctload import AccountLoader
from awsrun.config import Config
from awsrun.plugmgr import PluginManager


def url_loader(tmp_path, argv=None, **options):
    data = tmp_path / "accts.json"
    data.write_text(
        json.dumps([{"id": "100200300400", "env": "prod"}]), encoding="utf-8"
    )
    opts = {"url": data.as_uri(), "id_attr": "id", "max_age": 0}
    opts.update(options)
    config = Config(
        {"Accounts": {"plugin": "awsrun.plugins.accts.URLLoader", "options": opts}}
    )
    pm = PluginManager(
        config, argparse.ArgumentParser(), argparse.Namespace(), argv or []
    )
    return pm.instantiate("Accounts", must_be=AccountLoader)


@pytest.mark.parametrize("auth", ["none", "basic", "digest", "ntlm"])
def test_url_loader_accepts_documented_auth_types(tmp_path, auth):
    loader = url_loader(
        tmp_path, auth=auth, auth_options={"username": "user", "password": "pw"}
    )
    assert [loader.acct_id(a) for a in loader.accounts()] == ["100200300400"]


def test_url_loader_rejects_unknown_auth_in_config(tmp_path):
    with pytest.raises(TypeError, match="auth"):
        url_loader(tmp_path, auth="ntml")


def test_url_loader_rejects_unknown_auth_flag(tmp_path, capsys):
    with pytest.raises(SystemExit):
        url_loader(tmp_path, argv=["--loader-auth", "kerberos"])
    assert "--loader-auth" in capsys.readouterr().err


def test_url_loader_rejects_unknown_parser_flag(tmp_path, capsys):
    with pytest.raises(SystemExit):
        url_loader(tmp_path, argv=["--loader-parser", "xml"])
    assert "--loader-parser" in capsys.readouterr().err


def test_url_loader_auth_flag_overrides_config(tmp_path):
    loader = url_loader(tmp_path, argv=["--loader-auth", "none"], auth="basic")
    assert len(loader.accounts()) == 1


class FakeCompleted:
    def __init__(self, stdout=b"[]", stderr=b""):
        self.stdout = stdout
        self.stderr = stderr


def test_azure_cli_loader_runs_resolved_path(mocker):
    """On Windows 'az' is 'az.cmd', which can only be started by its full path."""
    resolved = "C:/Program Files/Azure CLI/az.cmd"
    mocker.patch.object(acctload.shutil, "which", return_value=resolved)
    subs = [
        {"id": "sub-1", "name": "azure-retail-prod", "state": "Enabled"},
        {"id": "sub-2", "name": "other", "state": "Enabled"},
    ]
    run = mocker.patch.object(
        acctload.subprocess,
        "run",
        return_value=FakeCompleted(stdout=json.dumps(subs).encode()),
    )

    loader = acctload.AzureCLIAccountLoader(
        name_regexp=r"^azure-(?P<bu>[^-]+)-(?P<env>.*)"
    )

    assert run.call_args.args[0] == [resolved, "account", "list", "--all"]
    accts = {loader.acct_id(a): a for a in loader.accounts()}
    assert set(accts) == {"sub-1", "sub-2"}
    assert accts["sub-1"].bu == "retail"
    assert accts["sub-1"].env == "prod"
    assert accts["sub-2"].bu is None


def test_azure_cli_loader_requires_az(mocker):
    mocker.patch.object(acctload.shutil, "which", return_value=None)
    with pytest.raises(FileNotFoundError, match="Azure CLI"):
        acctload.AzureCLIAccountLoader()


def test_azure_cli_loader_reports_stderr(mocker):
    mocker.patch.object(acctload.shutil, "which", return_value="/usr/bin/az")
    mocker.patch.object(
        acctload.subprocess, "run", return_value=FakeCompleted(stderr=b"az login")
    )
    with pytest.raises(RuntimeError, match="az login"):
        acctload.AzureCLIAccountLoader()
