#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for how the credential plug-ins obtain and protect the password."""

import argparse
from functools import partial

import pytest

from awsrun.argparse import RawAndDefaultsFormatter
from awsrun.config import Config
from awsrun.plugins.creds import aws as creds

SECRET = "hunter2-from-somewhere"

# plug-in class, flag prefix, the session provider class it builds, and the
# name of the keyword/attribute through which that class receives the password
PLUGINS = [
    pytest.param(creds.SAML, "saml", "CredsViaSAML", id="saml"),
    pytest.param(creds.OAuth2, "oauth2", "CredsViaOAuth2ROPC", id="oauth2"),
]


class Recorder:
    """Stand-in for a session provider that makes no network calls."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def assertion(self):
        pass

    def token(self):
        pass

    def password(self):
        if "password" in self.kwargs:
            return self.kwargs["password"]
        return self.kwargs["auth"].password


@pytest.fixture(autouse=True)
def isolated(mocker, monkeypatch):
    monkeypatch.delenv("PASSWORD", raising=False)
    mocker.patch.object(creds, "CredsViaSAML", Recorder)
    mocker.patch.object(creds, "CredsViaOAuth2ROPC", Recorder)
    # Any unexpected prompt fails the test instead of blocking on stdin.
    mocker.patch.object(
        creds.getpass, "getpass", side_effect=AssertionError("unexpected prompt")
    )


def make(plugin_class, options=None):
    opts = {"role": "Role", "url": "https://idp.example.com/sso", "username": "pete"}
    opts.update(options or {})
    config = Config({"Credentials": {"options": opts}})
    parser = argparse.ArgumentParser(formatter_class=RawAndDefaultsFormatter)
    plugin = plugin_class(parser, partial(config.get, "Credentials", "options"))
    return parser, plugin


@pytest.mark.parametrize("plugin_class, prefix, provider", PLUGINS)
def test_help_does_not_show_password_from_config(plugin_class, prefix, provider):
    parser, _ = make(plugin_class, {"password": SECRET})
    text = parser.format_help()
    assert f"--{prefix}-password" in text
    assert SECRET not in text


@pytest.mark.parametrize("plugin_class, prefix, provider", PLUGINS)
def test_help_does_not_show_password_from_environment(
    plugin_class, prefix, provider, monkeypatch
):
    monkeypatch.setenv("PASSWORD", SECRET)
    parser, _ = make(plugin_class)
    assert SECRET not in parser.format_help()


@pytest.mark.parametrize("plugin_class, prefix, provider", PLUGINS)
def test_help_still_shows_other_defaults(plugin_class, prefix, provider):
    parser, _ = make(plugin_class)
    assert "(default: pete)" in parser.format_help()


@pytest.mark.parametrize("plugin_class, prefix, provider", PLUGINS)
def test_password_from_config(plugin_class, prefix, provider):
    parser, plugin = make(plugin_class, {"password": "from-config"})
    args = parser.parse_args([])
    assert getattr(args, f"{prefix}_password") is None
    assert plugin.instantiate(args).password() == "from-config"


@pytest.mark.parametrize("plugin_class, prefix, provider", PLUGINS)
def test_password_from_environment(plugin_class, prefix, provider, monkeypatch):
    monkeypatch.setenv("PASSWORD", "from-env")
    parser, plugin = make(plugin_class)
    assert plugin.instantiate(parser.parse_args([])).password() == "from-env"


@pytest.mark.parametrize("plugin_class, prefix, provider", PLUGINS)
def test_config_takes_priority_over_environment(
    plugin_class, prefix, provider, monkeypatch
):
    monkeypatch.setenv("PASSWORD", "from-env")
    parser, plugin = make(plugin_class, {"password": "from-config"})
    assert plugin.instantiate(parser.parse_args([])).password() == "from-config"


@pytest.mark.parametrize("plugin_class, prefix, provider", PLUGINS)
def test_flag_takes_priority_over_config_and_environment(
    plugin_class, prefix, provider, monkeypatch
):
    monkeypatch.setenv("PASSWORD", "from-env")
    parser, plugin = make(plugin_class, {"password": "from-config"})
    args = parser.parse_args([f"--{prefix}-password", "from-flag"])
    assert plugin.instantiate(args).password() == "from-flag"


@pytest.mark.parametrize("plugin_class, prefix, provider", PLUGINS)
def test_prompts_when_no_password_is_available(plugin_class, prefix, provider, mocker):
    prompt = mocker.patch.object(creds.getpass, "getpass", return_value="typed")
    parser, plugin = make(plugin_class)
    assert plugin.instantiate(parser.parse_args([])).password() == "typed"
    prompt.assert_called_once_with("Password for pete? ")


@pytest.mark.parametrize("plugin_class, prefix, provider", PLUGINS)
def test_password_in_config_must_be_a_string(plugin_class, prefix, provider):
    with pytest.raises(TypeError, match="password"):
        make(plugin_class, {"password": ["not", "a", "string"]})


def test_azure_help_does_not_show_password(monkeypatch):
    azure = pytest.importorskip(
        "awsrun.plugins.creds.azure", reason="requires the azure extra"
    )
    monkeypatch.setenv("PASSWORD", SECRET)
    config = Config({"Credentials": {"options": {"username": "pete@example.com"}}})
    parser = argparse.ArgumentParser(formatter_class=RawAndDefaultsFormatter)
    azure.UsernamePassword(parser, partial(config.get, "Credentials", "options"))
    text = parser.format_help()
    assert "--ad-password" in text
    assert SECRET not in text
