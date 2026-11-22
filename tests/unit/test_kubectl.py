#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

import argparse
from functools import partial

import pytest

from awsrun.commands.aws import kubectl
from awsrun.config import Config


@pytest.fixture(autouse=True)
def fake_binaries(mocker):
    """Pretend kubectl and aws are installed so the command can be built."""
    mocker.patch.object(kubectl.shutil, "which", return_value="/usr/bin/fake")


def build(argv, command_config=None):
    config = Config({"Commands": {"kubectl": command_config or {}}})
    cfg = partial(config.get, "Commands", "kubectl")
    parser = argparse.ArgumentParser(prog="kubectl")
    return kubectl.CLICommand.from_cli(parser, argv, cfg)


def test_output_defaults_to_none():
    cmd = build(["--region", "us-east-1", "get", "pods"])
    assert cmd.output is None
    assert cmd.namespaces == ["default"]
    assert cmd.kubectl_args == ["get", "pods"]


def test_namespace_in_config_does_not_break_output():
    """A list of namespaces in the config must not be read as the output format."""
    cmd = build(
        ["--region", "us-east-1", "get", "pods"],
        {"namespace": ["kube-system", "prod"]},
    )
    assert cmd.namespaces == ["kube-system", "prod"]
    assert cmd.output is None


def test_output_is_read_from_its_own_config_key():
    cmd = build(["--region", "us-east-1", "get", "pods"], {"output": "json"})
    assert cmd.output == "json"


def test_output_flag_overrides_config():
    cmd = build(
        ["--region", "us-east-1", "--output", "yaml", "get", "pods"],
        {"output": "json"},
    )
    assert cmd.output == "yaml"


@pytest.mark.parametrize("flag", ["token", "kubeconfig", "as-group", "server"])
def test_prohibited_flag_is_named_in_the_error(flag, capsys):
    with pytest.raises(SystemExit):
        build(["--region", "us-east-1", f"--{flag}", "value", "get", "pods"])
    assert f"--{flag}" in capsys.readouterr().err
