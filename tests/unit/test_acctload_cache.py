#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for where and how the account loaders cache what they download."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from awsrun import acctload, cache
from awsrun.session import aws as session_aws

POSIX = os.name != "nt"


@pytest.fixture
def cache_home(tmp_path, monkeypatch):
    """Point the user's cache directory at a temporary directory."""
    home = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CACHE_HOME", str(home))
    return home


def write_accounts(path, *ids):
    path.write_text(json.dumps([{"id": i} for i in ids]), encoding="utf-8")
    return path.as_uri()


def ids(loader):
    return sorted(loader.acct_id(a) for a in loader.accounts())


# -- default cache file --------------------------------------------------------


def test_default_cache_file_is_in_user_cache_dir(cache_home):
    path = acctload._default_cache_file(300, "json", "https://example.com/a.json")
    assert path.parent == cache_home / "awsrun"
    assert path.name.startswith("accts-")
    assert path.suffix == ".json"


def test_default_cache_file_falls_back_to_home(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(acctload.Path, "home", classmethod(lambda cls: tmp_path))
    path = acctload._default_cache_file(300, "json", "https://example.com/a.json")
    assert path.parent == tmp_path / ".cache" / "awsrun"


def test_default_cache_file_is_stable_per_source(cache_home):
    first = acctload._default_cache_file(300, "json", "https://example.com/a.json")
    again = acctload._default_cache_file(60, "json", "https://example.com/a.json")
    assert first == again


@pytest.mark.parametrize(
    "other",
    [
        ("json", "https://example.com/b.json"),
        ("yaml", "https://example.com/a.json"),
        ("csv", "https://example.com/a.json", ","),
        ("csv", "https://example.com/a.json", ";"),
    ],
)
def test_default_cache_file_differs_per_source(cache_home, other):
    base = acctload._default_cache_file(300, "json", "https://example.com/a.json")
    assert acctload._default_cache_file(300, *other) != base


def test_cache_dir_is_not_created_when_caching_is_disabled(cache_home):
    acctload._default_cache_file(0, "json", "https://example.com/a.json")
    assert not cache_home.exists()


def test_cache_dir_is_created_when_caching_is_enabled(cache_home):
    path = acctload._default_cache_file(300, "json", "https://example.com/a.json")
    assert path.parent.is_dir()
    if POSIX:
        assert path.parent.stat().st_mode & 0o777 == 0o700


def test_cache_dir_falls_back_to_private_temp_dir(cache_home, monkeypatch, tmp_path):
    """An unwritable home must not stop awsrun from running."""
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    monkeypatch.setattr(acctload.tempfile, "tempdir", str(tmp))
    real_mkdir = Path.mkdir

    def mkdir(self, *args, **kwargs):
        if cache_home in self.parents or self == cache_home:
            raise PermissionError("read-only home")
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(acctload.Path, "mkdir", mkdir)
    path = acctload._default_cache_file(300, "json", "https://example.com/a.json")

    assert path.parent.is_dir()
    assert path.parent.parent == tmp
    assert path.parent.name.startswith("awsrun-")
    if POSIX:
        assert path.parent.stat().st_mode & 0o777 == 0o700


# -- loaders -------------------------------------------------------------------


def test_each_url_gets_its_own_cache(cache_home, tmp_path):
    """Accounts cached for one URL must never be returned for another."""
    url_a = write_accounts(tmp_path / "a.json", "111111111111")
    url_b = write_accounts(tmp_path / "b.json", "222222222222")

    assert ids(acctload.JSONAccountLoader(url_a, max_age=300)) == ["111111111111"]
    assert ids(acctload.JSONAccountLoader(url_b, max_age=300)) == ["222222222222"]
    assert ids(acctload.JSONAccountLoader(url_a, max_age=300)) == ["111111111111"]
    assert len(list((cache_home / "awsrun").glob("accts-*.json"))) == 2


def test_loader_types_do_not_share_a_cache(cache_home, tmp_path):
    json_url = write_accounts(tmp_path / "accts.json", "111111111111")
    csv_file = tmp_path / "accts.csv"
    csv_file.write_text("id,env\n333333333333,prod\n", encoding="utf-8")

    assert ids(acctload.JSONAccountLoader(json_url, max_age=300)) == ["111111111111"]
    assert ids(acctload.CSVAccountLoader(csv_file.as_uri(), max_age=300)) == [
        "333333333333"
    ]
    url_loader = acctload.URLAccountLoader(
        json_url, parser=acctload.JSONParser(), max_age=300
    )
    assert ids(url_loader) == ["111111111111"]
    assert len(list((cache_home / "awsrun").glob("accts-*.json"))) == 3


def test_cached_accounts_are_reused_within_max_age(cache_home, tmp_path):
    source = tmp_path / "a.json"
    url = write_accounts(source, "111111111111")
    assert ids(acctload.JSONAccountLoader(url, max_age=300)) == ["111111111111"]

    write_accounts(source, "999999999999")
    assert ids(acctload.JSONAccountLoader(url, max_age=300)) == ["111111111111"]
    assert ids(acctload.JSONAccountLoader(url, max_age=0)) == ["999999999999"]


def test_nothing_is_written_when_caching_is_disabled(cache_home, tmp_path):
    url = write_accounts(tmp_path / "a.json", "111111111111")
    assert ids(acctload.JSONAccountLoader(url)) == ["111111111111"]
    assert not cache_home.exists()


@pytest.mark.parametrize("max_age", [0, 300])
def test_file_planted_in_shared_temp_dir_is_ignored(
    cache_home, tmp_path, monkeypatch, max_age
):
    """Another user of the machine must not be able to choose the accounts."""
    shared_tmp = tmp_path / "shared-tmp"
    shared_tmp.mkdir()
    monkeypatch.setattr(acctload.tempfile, "tempdir", str(shared_tmp))
    planted = [{"id": "666666666666"}]
    (shared_tmp / "awsrun.dat").write_text(json.dumps(planted), encoding="utf-8")
    (shared_tmp / "awsrun.dat.expiry").write_text("inf", encoding="utf-8")

    url = write_accounts(tmp_path / "a.json", "111111111111")
    for loader in (
        acctload.JSONAccountLoader(url, max_age=max_age),
        acctload.YAMLAccountLoader(url, max_age=max_age),
        acctload.URLAccountLoader(url, parser=acctload.JSONParser(), max_age=max_age),
    ):
        assert ids(loader) == ["111111111111"]

    # The planted files were neither used nor replaced.
    assert json.loads((shared_tmp / "awsrun.dat").read_text()) == planted
    assert sorted(p.name for p in shared_tmp.iterdir()) == [
        "awsrun.dat",
        "awsrun.dat.expiry",
    ]


def test_explicit_cache_path_is_honoured(cache_home, tmp_path):
    url = write_accounts(tmp_path / "a.json", "111111111111")
    cache_path = tmp_path / "my-cache.json"
    loader = acctload.URLAccountLoader(
        url, parser=acctload.JSONParser(), max_age=300, cache_path=cache_path
    )
    assert ids(loader) == ["111111111111"]
    assert json.loads(cache_path.read_text()) == [{"id": "111111111111"}]
    assert not cache_home.exists()


# -- writing the cache file ----------------------------------------------------


def test_save_leaves_only_the_cache_file(tmp_path):
    path = tmp_path / "cache.json"
    ev = cache.PersistentExpiringValue(lambda: {"a": 1}, path, max_age=300)
    assert ev.value() == {"a": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["cache.json"]
    assert json.loads(path.read_text()) == {"a": 1}


@pytest.mark.skipif(not POSIX, reason="POSIX file modes")
def test_saved_cache_is_private(tmp_path):
    path = tmp_path / "cache.json"
    cache.PersistentExpiringValue(lambda: {"a": 1}, path, max_age=300).value()
    assert path.stat().st_mode & 0o777 == 0o600


def test_failed_save_keeps_previous_cache_and_cleans_up(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text('{"old": true}', encoding="utf-8")
    ev = cache.PersistentExpiringValue(lambda: {"bad": object()}, path, max_age=300)

    with pytest.raises(TypeError):
        ev.value(refresh=True)

    assert json.loads(path.read_text()) == {"old": True}
    assert [p.name for p in tmp_path.iterdir()] == ["cache.json"]


@pytest.mark.skipif(not POSIX, reason="symlinks need privileges on Windows")
def test_save_does_not_follow_symlink_at_old_temp_name(tmp_path):
    """The old fixed '<name>.tmp' could be pre-created as a symlink."""
    victim = tmp_path / "victim.txt"
    victim.write_text("important", encoding="utf-8")
    path = tmp_path / "cache.dat"
    (tmp_path / "cache.tmp").symlink_to(victim)

    cache.PersistentExpiringValue(lambda: {"a": 1}, path, max_age=300).value()

    assert victim.read_text() == "important"
    assert json.loads(path.read_text()) == {"a": 1}


# -- timeouts ------------------------------------------------------------------


def test_account_loaders_use_a_timeout(cache_home, tmp_path, mocker):
    url = write_accounts(tmp_path / "a.json", "111111111111")
    get = mocker.spy(requests.Session, "get")

    acctload.JSONAccountLoader(url)
    acctload.YAMLAccountLoader(url)
    acctload.URLAccountLoader(url, parser=acctload.JSONParser())
    csv_file = tmp_path / "a.csv"
    csv_file.write_text("id\n1\n", encoding="utf-8")
    acctload.CSVAccountLoader(csv_file.as_uri())

    assert get.call_count == 4
    for call in get.call_args_list:
        assert call.kwargs["timeout"] == acctload._HTTP_TIMEOUT


def test_oauth2_account_loader_token_request_uses_a_timeout(mocker):
    response = SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {"access_token": "t"}
    )
    post = mocker.patch.object(acctload.requests, "post", return_value=response)
    auth = acctload.HTTPOAuth2(
        username="client", password="secret", token_url="https://idp.example/token"
    )
    request = requests.Request("GET", "https://example.com/accts").prepare()
    assert auth(request).headers["Authorization"] == "Bearer t"
    assert post.call_args.kwargs["timeout"] == acctload._HTTP_TIMEOUT


@pytest.mark.parametrize("http_method", ["GET", "POST"])
def test_saml_request_uses_a_timeout(mocker, http_method):
    response = SimpleNamespace(status_code=500, text="")
    send = mocker.patch.object(
        requests.Session, http_method.lower(), return_value=response
    )
    provider = session_aws.CredsViaSAML(
        role="Role",
        url="https://idp.example/sso",
        auth=requests.auth.HTTPBasicAuth("pete", "pw"),
        http_method=http_method,
    )
    with pytest.raises(session_aws.IDPInvalidResponseException):
        provider.assertion()
    assert send.call_args.kwargs["timeout"] == session_aws._HTTP_TIMEOUT
    assert send.call_args.kwargs["verify"] is True


def test_oauth2_token_request_uses_a_timeout(mocker):
    response = SimpleNamespace(status_code=500, text="")
    post = mocker.patch.object(requests.Session, "post", return_value=response)
    provider = session_aws.CredsViaOAuth2ROPC(
        role="Role", url="https://idp.example/token", username="pete", password="pw"
    )
    with pytest.raises(session_aws.IDPInvalidResponseException):
        provider.token()
    assert post.call_args.kwargs["timeout"] == session_aws._HTTP_TIMEOUT
