#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

import pytest

from awsrun.cli import _CSP


@pytest.mark.parametrize(
    "prog_name, expected",
    [
        ("awsrun", "aws"),
        ("azurerun", "azure"),
        ("/usr/local/bin/awsrun", "aws"),
        ("/usr/local/bin/azurerun", "azure"),
        ("awsrun.exe", "aws"),
        ("AZURERUN.EXE", "azure"),
        ("awsrun-script.py", "aws"),
        ("/site-packages/awsrun/cli.py", "aws"),
        ("/site-packages/awsrun/__main__.py", "aws"),
    ],
)
def test_csp_from_prog_name(prog_name, expected):
    assert _CSP.from_prog_name(prog_name).name == expected


@pytest.mark.parametrize("prog_name", ["gcprun", "python", "run", ""])
def test_csp_from_unknown_prog_name(prog_name):
    with pytest.raises(Exception, match="unknown variant"):
        _CSP.from_prog_name(prog_name)


def test_csp_defaults():
    csp = _CSP("azure")
    assert csp.default_command_path() == "awsrun.commands.azure"
    assert csp.default_session_provider() == "awsrun.plugins.creds.azure.Default"


def test_csp_config_filename_from_env(monkeypatch):
    monkeypatch.setenv("AWSRUN_CONFIG", "/tmp/custom.yaml")
    assert _CSP("aws").config_filename() == "/tmp/custom.yaml"
