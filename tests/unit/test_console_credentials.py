#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests that the console command never sends long-term credentials anywhere."""

from types import SimpleNamespace

import pytest

from awsrun.commands.aws import console


class Session:
    def __init__(self, creds):
        self._creds = creds

    def get_credentials(self):
        return self._creds


@pytest.mark.parametrize(
    "creds",
    [
        pytest.param(None, id="no-credentials"),
        pytest.param(object(), id="object-without-attributes"),
        pytest.param(
            SimpleNamespace(access_key="AKIA", secret_key="long-term", token=None),
            id="iam-user-keys",
        ),
        pytest.param(
            SimpleNamespace(access_key="AKIA", secret_key="long-term", token=""),
            id="empty-token",
        ),
    ],
)
def test_non_federated_credentials_are_never_sent(mocker, creds):
    get = mocker.patch.object(console.requests, "get")
    cmd = console.CLICommand("us-east-1", "/console/home")

    result = cmd.execute(Session(creds), "100200300400")

    assert result == "100200300400: can only be used with federated auth types"
    get.assert_not_called()


def test_temporary_credentials_are_sent_to_aws_only(mocker):
    response = SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {"SigninToken": "tok"}
    )
    get = mocker.patch.object(console.requests, "get", return_value=response)
    creds = SimpleNamespace(access_key="ASIA", secret_key="temp", token="session")

    result = console.CLICommand("us-east-1", "/console/home").execute(
        Session(creds), "100200300400"
    )

    get.assert_called_once()
    assert get.call_args.args[0] == "https://signin.aws.amazon.com/federation"
    assert '"sessionToken": "session"' in get.call_args.kwargs["params"]["Session"]
    assert result.startswith(
        "100200300400: https://signin.aws.amazon.com/federation?Action=login"
    )
    # Neither the secret key nor the session token is echoed to the user.
    assert "temp" not in result
    assert "session" not in result.split("SigninToken")[0]
