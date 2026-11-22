#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

import argparse
from functools import partial
from urllib.parse import parse_qs, urlparse

import pytest

from awsrun.commands.aws import console
from awsrun.config import Config


class FakeCreds:
    access_key = "AKIAEXAMPLE"
    secret_key = "secret"
    token = "token"


class FakeSession:
    def get_credentials(self):
        return FakeCreds()


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"SigninToken": "signin-token-value"}


def build(argv, command_config=None):
    config = Config({"Commands": {"console": command_config or {}}})
    cfg = partial(config.get, "Commands", "console")
    return console.CLICommand.from_cli(argparse.ArgumentParser(), argv, cfg)


def signin_params(cmd, mocker):
    get = mocker.patch.object(console.requests, "get", return_value=FakeResponse())
    result = cmd.execute(FakeSession(), "100200300400")
    assert get.call_args.kwargs["timeout"] == 10.0
    acct, _, url = result.strip().partition(": ")
    assert acct == "100200300400"
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def test_defaults(mocker):
    params = signin_params(build([]), mocker)
    assert params["Action"] == "login"
    assert params["Issuer"] == console.DEFAULT_ISSUER
    assert params["SigninToken"] == "signin-token-value"
    assert (
        params["Destination"]
        == "https://console.aws.amazon.com/console/home?region=us-east-1"
    )


def test_issuer_from_flag(mocker):
    params = signin_params(build(["--issuer", "example.com"]), mocker)
    assert params["Issuer"] == "example.com"


def test_issuer_from_config(mocker):
    params = signin_params(build([], {"issuer": "corp.example"}), mocker)
    assert params["Issuer"] == "corp.example"


def test_flag_overrides_config(mocker):
    cmd = build(["--issuer", "flag.example", "--region", "us-west-2"], {"issuer": "x"})
    params = signin_params(cmd, mocker)
    assert params["Issuer"] == "flag.example"
    assert params["Destination"].endswith("?region=us-west-2")


def test_issuer_must_be_a_string():
    with pytest.raises(TypeError):
        build([], {"issuer": ["a", "b"]})


def test_constructor_stays_backward_compatible():
    cmd = console.CLICommand("us-east-1", "/console/home")
    assert cmd.issuer == console.DEFAULT_ISSUER


def test_non_federated_credentials():
    class NoCreds:
        def get_credentials(self):
            return object()

    result = build([]).execute(NoCreds(), "100200300400")
    assert "can only be used with federated auth types" in result
