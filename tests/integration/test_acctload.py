#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml
from freezegun import freeze_time

from awsrun import acctload


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
def json_cache(tmpdir):
    with open(tmpdir.join("awsrun.dat"), "w") as f:
        f.write(
            """
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
        )


@pytest.mark.parametrize("max_age", [0, 300])
def test_json_loader_without_cache(tmpdir, mocker, expected_from_loader, max_age):
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = expected_from_loader
    mock_get = mocker.patch("requests.Session.get", return_value=mock_resp)
    mock_mal = mocker.patch("awsrun.acctload.MetaAccountLoader.__init__")
    mocker.patch("tempfile.gettempdir", return_value=tmpdir)

    url = "http://example.com/accts.json"
    acctload.JSONAccountLoader(url, max_age=max_age)

    # requests.get should be called as no cache exists on the filesystem
    mock_get.assert_called_once()
    (url_called,), kwargs = mock_get.call_args
    assert url == url_called

    # Make sure the accts were loaded and passed to the MetaAccountLoader
    (accts,), kwargs = mock_mal.call_args
    assert accts == expected_from_loader

    if max_age == 0:
        # Make sure it did not cache data if max age was 0
        with pytest.raises(FileNotFoundError):
            open(tmpdir.join("awsrun.dat"))

    else:
        # Make sure the json loader cached the results if max age > 0
        with open(tmpdir.join("awsrun.dat")) as f:
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
    mocker.patch("tempfile.gettempdir", return_value=tmpdir)

    url = "http://example.com/accts.yaml"
    acctload.YAMLAccountLoader(url, max_age=max_age)

    # requests.get should be called as no cache exists on the filesystem
    mock_get.assert_called_once()
    (url_called,), kwargs = mock_get.call_args
    assert url == url_called

    # Make sure the accts were loaded and passed to the MetaAccountLoader
    (accts,), kwargs = mock_mal.call_args
    assert accts == expected_from_loader

    if max_age == 0:
        # Make sure it did not cache data if max age was 0
        with pytest.raises(FileNotFoundError):
            open(tmpdir.join("awsrun.dat"))

    else:
        # Make sure the yaml loader cached the results if max age > 0
        with open(tmpdir.join("awsrun.dat")) as f:
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
    mocker.patch("tempfile.gettempdir", return_value=tmpdir)

    url = "http://example.com/accts.csv"
    acctload.CSVAccountLoader(url, max_age=max_age)

    # requests.get should be called as no cache exists on the filesystem
    mock_get.assert_called_once()
    (url_called,), kwargs = mock_get.call_args
    assert url == url_called

    # Make sure the accts were loaded and passed to the MetaAccountLoader
    (accts,), kwargs = mock_mal.call_args
    # csv loader returns a list of OrderedDicts, but json loader returns a list
    # of dicts, so to share the fixture between tests, we convert the ordered
    # dicts to plain dicts.
    accts = [dict(a) for a in accts]
    assert accts == expected_from_loader

    if max_age == 0:
        # Make sure it did not cache data if max age was 0
        with pytest.raises(FileNotFoundError):
            open(tmpdir.join("awsrun.dat"))

    else:
        # Make sure the json loader cached the results if max age > 0
        with open(tmpdir.join("awsrun.dat")) as f:
            cached_accts = json.load(f)
        assert accts == cached_accts


def test_json_loader_with_cache(tmpdir, mocker, json_cache, expected_from_loader):
    mock_get = mocker.patch("requests.get")
    mock_mal = mocker.patch("awsrun.acctload.MetaAccountLoader.__init__")
    mocker.patch("tempfile.gettempdir", return_value=tmpdir)

    acctload.JSONAccountLoader("http://example.com/acct.json", max_age=86400)

    # requests.get should not be called as a cache exists on the filesystem
    mock_get.assert_not_called()

    # Make sure the accts were loaded and passed to the MetaAccountLoader
    (accts,), kwargs = mock_mal.call_args
    assert accts == expected_from_loader


def test_yaml_loader_with_cache(tmpdir, mocker, json_cache, expected_from_loader):
    mock_get = mocker.patch("requests.get")
    mock_mal = mocker.patch("awsrun.acctload.MetaAccountLoader.__init__")
    mocker.patch("tempfile.gettempdir", return_value=tmpdir)

    acctload.YAMLAccountLoader("http://example.com/acct.yaml", max_age=86400)

    # requests.get should not be called as a cache exists on the filesystem
    mock_get.assert_not_called()

    # Make sure the accts were loaded and passed to the MetaAccountLoader
    (accts,), kwargs = mock_mal.call_args
    assert accts == expected_from_loader


def test_json_loader_with_expired_cache(
    tmpdir, mocker, json_cache, expected_from_loader
):
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = expected_from_loader
    mock_get = mocker.patch("requests.Session.get", return_value=mock_resp)
    mocker.patch("tempfile.gettempdir", return_value=tmpdir)

    # We'll compare the times of the date file before and after to ensure
    # the file was replaced with a newer version.
    cache_date_before = Path(tmpdir.join("awsrun.dat")).stat().st_mtime

    # Fast-forward the time to the future by a day and a few seconds beyond
    # when the cache is valid, which will force a fresh fetch of data.
    with freeze_time(datetime.utcnow() + timedelta(days=1, seconds=5)):
        acctload.JSONAccountLoader("http://example.com/acct.json", max_age=86400)

    # requests.get should be called when cache is expired to refresh it
    mock_get.assert_called_once()

    # Compare the date of the cache file to make sure it was updated
    cache_date_after = Path(tmpdir.join("awsrun.dat")).stat().st_mtime
    assert cache_date_before < cache_date_after

    # Make sure the json loader cached the results
    with open(tmpdir.join("awsrun.dat")) as f:
        cached_accts = json.load(f)
    assert cached_accts == expected_from_loader


def test_yaml_loader_with_expired_cache(
    tmpdir, mocker, json_cache, yaml_string, expected_from_loader
):
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.text = yaml_string
    mock_get = mocker.patch("requests.Session.get", return_value=mock_resp)
    mocker.patch("tempfile.gettempdir", return_value=tmpdir)

    # We'll compare the times of the date file before and after to ensure
    # the file was replaced with a newer version.
    cache_date_before = Path(tmpdir.join("awsrun.dat")).stat().st_mtime

    # Fast-forward the time to the future by a day and a few seconds beyond
    # when the cache is valid, which will force a fresh fetch of data.
    with freeze_time(datetime.utcnow() + timedelta(days=1, seconds=5)):
        acctload.YAMLAccountLoader("http://example.com/acct.yaml", max_age=86400)

    # requests.get should be called when cache is expired to refresh it
    mock_get.assert_called_once()

    # Compare the date of the cache file to make sure it was updated
    cache_date_after = Path(tmpdir.join("awsrun.dat")).stat().st_mtime
    assert cache_date_before < cache_date_after

    # Make sure the json loader cached the results
    with open(tmpdir.join("awsrun.dat")) as f:
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

    url = "file://" + csv_file.as_posix()

    if delimiter:
        acctload.CSVAccountLoader(url, delimiter=delimiter)
    else:
        acctload.CSVAccountLoader(url)

    (accts,), kwargs = mock_mal.call_args
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

    url = "file://" + json_file.as_posix()

    acctload.JSONAccountLoader(url, max_age=0)

    (accts,), kwargs = mock_mal.call_args
    assert accts == expected_from_loader


def test_yaml_account_loader_with_file_url(
    tmp_path, mocker, yaml_string, expected_from_loader
):
    yaml_file = tmp_path / "accts.yaml"
    with yaml_file.open("w") as f:
        f.write(yaml_string)
    mock_mal = mocker.patch("awsrun.acctload.MetaAccountLoader.__init__")

    url = "file://" + yaml_file.as_posix()

    acctload.YAMLAccountLoader(url, max_age=0)

    (accts,), kwargs = mock_mal.call_args
    assert accts == expected_from_loader
