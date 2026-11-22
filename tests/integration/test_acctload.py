#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

import json
from datetime import datetime, timedelta, timezone

import pytest
import yaml
from freezegun import freeze_time

from awsrun import acctload


@pytest.fixture(autouse=True)
def _cache_home(tmpdir, monkeypatch):
    """Keep the account cache of each test in its own temporary directory."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmpdir))


def cache_file(*source):
    """Returns the path of the cache file for accounts loaded from a source."""
    return acctload._default_cache_file(300, *source)


JSON_URL = "http://example.com/acct.json"
YAML_URL = "http://example.com/acct.yaml"


@pytest.fixture()
def expected_from_loader():
    return [
        {"id": "100200300400", "env": "prod", "status": "active"},
        {"id": "200300400100", "env": "nonprod", "status": "active"},
        {"id": "300400100200", "env": "dev", "status": "suspended"},
    ]


@pytest.fixture()
def csv_string():
    return """id, env, status
        "100200300400", prod, active
        "200300400100", nonprod, active
        "300400100200", dev, suspended
        """


@pytest.fixture()
def json_string():
    return """
    [
        {
            "id": "100200300400",
            "env": "prod",
            "status": "active"
        },
        {
            "id": "200300400100",
            "env": "nonprod",
            "status": "active"
        },
        {
            "id": "300400100200",
            "env": "dev",
            "status": "suspended"
        }
    ]
    """


@pytest.fixture()
def yaml_string():
    return """
- id: '100200300400'
  env: prod
  status: active
- id: '200300400100'
  env: nonprod
  status: active
- id: '300400100200'
  env: dev
  status: suspended
"""


@pytest.fixture()
def _json_cache(_cache_home):
    content = """
    [
        {
            "id": "100200300400",
            "env": "prod",
            "status": "active"
        },
        {
            "id": "200300400100",
            "env": "nonprod",
            "status": "active"
        },
        {
            "id": "300400100200",
            "env": "dev",
            "status": "suspended"
        }
    ]
    """
    for path in (cache_file("json", JSON_URL), cache_file("yaml", YAML_URL)):
        path.write_text(content, encoding="utf-8")


@pytest.mark.parametrize("max_age", [0, 300])
def test_json_loader_without_cache(tmpdir, mocker, expected_from_loader, max_age):
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = expected_from_loader
    mock_get = mocker.patch("requests.Session.get", return_value=mock_resp)
    mock_mal = mocker.patch("awsrun.acctload.MetaAccountLoader.__init__")

    url = "http://example.com/accts.json"
    acctload.JSONAccountLoader(url, max_age=max_age)

    # requests.get should be called as no cache exists on the filesystem
    mock_get.assert_called_once()
    (url_called,), _ = mock_get.call_args
    assert url == url_called

    # Make sure the accts were loaded and passed to the MetaAccountLoader
    (accts,), _ = mock_mal.call_args
    assert accts == expected_from_loader

    if max_age == 0:
        # Make sure it did not cache data if max age was 0
        with pytest.raises(FileNotFoundError):
            with open(cache_file("json", url), encoding="utf-8") as f:
                pass

    else:
        # Make sure the json loader cached the results if max age > 0
        with open(cache_file("json", url), encoding="utf-8") as f:
            cached_accts = json.load(f)
        assert accts == cached_accts


@pytest.mark.parametrize("max_age", [0, 300])
def test_yaml_loader_without_cache(
    tmpdir, mocker, yaml_string, expected_from_loader, max_age
):
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.text = yaml_string
    mock_get = mocker.patch("requests.Session.get", return_value=mock_resp)
    mock_mal = mocker.patch("awsrun.acctload.MetaAccountLoader.__init__")

    url = "http://example.com/accts.yaml"
    acctload.YAMLAccountLoader(url, max_age=max_age)

    # requests.get should be called as no cache exists on the filesystem
    mock_get.assert_called_once()
    (url_called,), _ = mock_get.call_args
    assert url == url_called

    # Make sure the accts were loaded and passed to the MetaAccountLoader
    (accts,), _ = mock_mal.call_args
    assert accts == expected_from_loader

    if max_age == 0:
        # Make sure it did not cache data if max age was 0
        with pytest.raises(FileNotFoundError):
            with open(cache_file("yaml", url), encoding="utf-8") as f:
                pass

    else:
        # Make sure the yaml loader cached the results if max age > 0
        with open(cache_file("yaml", url), encoding="utf-8") as f:
            cached_accts = yaml.safe_load(f)
        assert accts == cached_accts


@pytest.mark.parametrize("max_age", [0, 300])
def test_csv_loader_without_cache(
    tmpdir, mocker, csv_string, expected_from_loader, max_age
):
    mock_resp = mocker.Mock()
    mock_resp.status_code = 400
    mock_resp.text = csv_string
    mock_get = mocker.patch("requests.Session.get", return_value=mock_resp)
    mock_mal = mocker.patch("awsrun.acctload.MetaAccountLoader.__init__")

    url = "http://example.com/accts.csv"
    acctload.CSVAccountLoader(url, max_age=max_age)

    # requests.get should be called as no cache exists on the filesystem
    mock_get.assert_called_once()
    (url_called,), _ = mock_get.call_args
    assert url == url_called

    # Make sure the accts were loaded and passed to the MetaAccountLoader
    (accts,), _ = mock_mal.call_args
    # csv loader returns a list of OrderedDicts, but json loader returns a list
    # of dicts, so to share the fixture between tests, we convert the ordered
    # dicts to plain dicts.
    accts = [dict(a) for a in accts]
    assert accts == expected_from_loader

    if max_age == 0:
        # Make sure it did not cache data if max age was 0
        with pytest.raises(FileNotFoundError):
            with open(cache_file("csv", url, ","), encoding="utf-8") as f:
                pass

    else:
        # Make sure the json loader cached the results if max age > 0
        with open(cache_file("csv", url, ","), encoding="utf-8") as f:
            cached_accts = json.load(f)
        assert accts == cached_accts


def test_json_loader_with_cache(tmpdir, mocker, _json_cache, expected_from_loader):
    mock_get = mocker.patch("requests.get")
    mock_mal = mocker.patch("awsrun.acctload.MetaAccountLoader.__init__")

    acctload.JSONAccountLoader(JSON_URL, max_age=86400)

    # requests.get should not be called as a cache exists on the filesystem
    mock_get.assert_not_called()

    # Make sure the accts were loaded and passed to the MetaAccountLoader
    (accts,), _ = mock_mal.call_args
    assert accts == expected_from_loader


def test_yaml_loader_with_cache(tmpdir, mocker, _json_cache, expected_from_loader):
    mock_get = mocker.patch("requests.get")
    mock_mal = mocker.patch("awsrun.acctload.MetaAccountLoader.__init__")

    acctload.YAMLAccountLoader(YAML_URL, max_age=86400)

    # requests.get should not be called as a cache exists on the filesystem
    mock_get.assert_not_called()

    # Make sure the accts were loaded and passed to the MetaAccountLoader
    (accts,), _ = mock_mal.call_args
    assert accts == expected_from_loader


def test_json_loader_with_expired_cache(
    tmpdir, mocker, _json_cache, expected_from_loader
):
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = expected_from_loader
    mock_get = mocker.patch("requests.Session.get", return_value=mock_resp)

    # We'll compare the times of the date file before and after to ensure
    # the file was replaced with a newer version.
    cache_date_before = cache_file("json", JSON_URL).stat().st_mtime

    # Fast-forward the time to the future by a day and a few seconds beyond
    # when the cache is valid, which will force a fresh fetch of data.
    with freeze_time(datetime.now(timezone.utc) + timedelta(days=1, seconds=5)):
        acctload.JSONAccountLoader(JSON_URL, max_age=86400)

    # requests.get should be called when cache is expired to refresh it
    mock_get.assert_called_once()

    # Compare the date of the cache file to make sure it was updated
    cache_date_after = cache_file("json", JSON_URL).stat().st_mtime
    assert cache_date_before < cache_date_after

    # Make sure the json loader cached the results
    with open(cache_file("json", JSON_URL), encoding="utf-8") as f:
        cached_accts = json.load(f)
    assert cached_accts == expected_from_loader


def test_yaml_loader_with_expired_cache(
    tmpdir, mocker, _json_cache, yaml_string, expected_from_loader
):
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.text = yaml_string
    mock_get = mocker.patch("requests.Session.get", return_value=mock_resp)

    # We'll compare the times of the date file before and after to ensure
    # the file was replaced with a newer version.
    cache_date_before = cache_file("yaml", YAML_URL).stat().st_mtime

    # Fast-forward the time to the future by a day and a few seconds beyond
    # when the cache is valid, which will force a fresh fetch of data.
    with freeze_time(datetime.now(timezone.utc) + timedelta(days=1, seconds=5)):
        acctload.YAMLAccountLoader(YAML_URL, max_age=86400)

    # requests.get should be called when cache is expired to refresh it
    mock_get.assert_called_once()

    # Compare the date of the cache file to make sure it was updated
    cache_date_after = cache_file("yaml", YAML_URL).stat().st_mtime
    assert cache_date_before < cache_date_after

    # Make sure the json loader cached the results
    with open(cache_file("yaml", YAML_URL), encoding="utf-8") as f:
        cached_accts = yaml.safe_load(f)
    assert cached_accts == expected_from_loader


@pytest.mark.parametrize(
    "delimiter, csv_content",
    [
        (
            None,
            """id, env, status
100200300400, prod, active
200300400100, nonprod, active
300400100200, dev, suspended""",
        ),
        (
            ",",
            """id, env, status
100200300400, prod, active
200300400100, nonprod, active
300400100200, dev, suspended""",
        ),
        (
            "\t",
            """id\tenv\tstatus
100200300400\tprod\tactive
200300400100\tnonprod\tactive
300400100200\tdev\tsuspended""",
        ),
    ],
)
def test_csv_account_loader_with_file_url(
    tmp_path, mocker, csv_content, delimiter, expected_from_loader
):
    # Create the CSV file on disk as the csv loader will read it
    csv_file = tmp_path / "accts.csv"
    with csv_file.open("w") as f:
        f.write(csv_content)
    mock_mal = mocker.patch("awsrun.acctload.MetaAccountLoader.__init__")

    url = csv_file.as_uri()

    if delimiter:
        acctload.CSVAccountLoader(url, delimiter=delimiter)
    else:
        acctload.CSVAccountLoader(url)

    (accts,), _ = mock_mal.call_args
    # csv loader returns a list of OrderedDicts, but json loader returns a list
    # of dicts, so to share the fixture between tests, we convert the ordered
    # dicts to plain dicts.
    accts = [dict(a) for a in accts]
    assert accts == expected_from_loader


def test_json_account_loader_with_file_url(
    tmp_path, mocker, json_string, expected_from_loader
):
    json_file = tmp_path / "accts.json"
    with json_file.open("w") as f:
        f.write(json_string)
    mock_mal = mocker.patch("awsrun.acctload.MetaAccountLoader.__init__")

    url = json_file.as_uri()

    acctload.JSONAccountLoader(url, max_age=0)

    (accts,), _ = mock_mal.call_args
    assert accts == expected_from_loader


def test_yaml_account_loader_with_file_url(
    tmp_path, mocker, yaml_string, expected_from_loader
):
    yaml_file = tmp_path / "accts.yaml"
    with yaml_file.open("w") as f:
        f.write(yaml_string)
    mock_mal = mocker.patch("awsrun.acctload.MetaAccountLoader.__init__")

    url = yaml_file.as_uri()

    acctload.YAMLAccountLoader(url, max_age=0)

    (accts,), _ = mock_mal.call_args
    assert accts == expected_from_loader
