#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the files and subprocess environments of the pass-through commands."""

import argparse
import os
import threading
import time
from types import SimpleNamespace

import pytest
import yaml

from awsrun.commands.aws import aws, kubectl
from awsrun.commands.azure import az


@pytest.fixture(autouse=True)
def fake_binaries(mocker):
    """Pretend the wrapped CLIs are installed so commands can be built."""
    for module in (aws, kubectl, az):
        mocker.patch.object(module.shutil, "which", return_value="/usr/bin/fake")


def completed(stdout="out\n", stderr=""):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=0)


def filenames(path):
    return sorted(p.name for p in path.iterdir())


# -- output file names --------------------------------------------------------


def test_aws_output_files_for_plain_account(tmp_path, capsys):
    cmd = aws.CLICommand(["s3", "ls"], ["us-east-1"], output_dir=tmp_path)
    cmd.regional_collect_results(
        "100200300400", "us-east-1", lambda: completed("data\n", "warn\n")
    )
    assert filenames(tmp_path) == [
        "100200300400-us-east-1.stderr.log",
        "100200300400-us-east-1.stdout.log",
    ]
    assert (tmp_path / "100200300400-us-east-1.stdout.log").read_text() == "data\n"
    assert (tmp_path / "100200300400-us-east-1.stderr.log").read_text() == "warn\n"


def test_aws_output_files_keep_dotted_account_names_apart(tmp_path, capsys):
    """A dot in the account name must not swallow the rest of the file name."""
    cmd = aws.CLICommand(["s3", "ls"], ["us-east-1"], output_dir=tmp_path)
    for acct, region in [
        ("team.prod", "us-east-1"),
        ("team.prod", "us-west-2"),
        ("team.dev", "us-east-1"),
    ]:
        cmd.regional_collect_results(
            acct, region, lambda a=acct, r=region: completed(f"{a} {r}\n")
        )

    assert filenames(tmp_path) == [
        "team.dev-us-east-1.stdout.log",
        "team.prod-us-east-1.stdout.log",
        "team.prod-us-west-2.stdout.log",
    ]
    assert (tmp_path / "team.prod-us-west-2.stdout.log").read_text() == (
        "team.prod us-west-2\n"
    )


def test_aws_output_file_escapes_slashes(tmp_path, capsys):
    cmd = aws.CLICommand(["s3", "ls"], ["us-east-1"], output_dir=tmp_path)
    cmd.regional_collect_results("org/team", "us-east-1", completed)
    assert filenames(tmp_path) == ["org_team-us-east-1.stdout.log"]


def test_az_output_files_keep_dotted_subscription_names_apart(tmp_path, capsys):
    cmd = az.CLICommand(["vm", "list"], output_dir=tmp_path)
    cmd.collect_results("retail.prod", lambda: completed("prod\n"))
    cmd.collect_results("retail.dev", lambda: completed("dev\n", "warn\n"))
    assert filenames(tmp_path) == [
        "retail.dev.stderr.log",
        "retail.dev.stdout.log",
        "retail.prod.stdout.log",
    ]
    assert (tmp_path / "retail.prod.stdout.log").read_text() == "prod\n"


def make_kubectl(**overrides):
    kwargs = {
        "kubectl_args": ["get", "pods"],
        "regions": ["us-east-1"],
        "clusters": ["cluster1"],
        "namespaces": ["default"],
        "list_clusters": False,
        "output": None,
        "awsrun_output_dir": None,
        "awsrun_annotate": None,
    }
    kwargs.update(overrides)
    return kubectl.CLICommand(**kwargs)


def test_kubectl_output_files_keep_dotted_account_names_apart(tmp_path, capsys):
    cmd = make_kubectl(awsrun_output_dir=tmp_path)
    for acct in ("team.prod", "team.dev"):
        result = kubectl._Result(f"{acct}\n", None, "cluster1", "default")
        cmd.regional_collect_results(acct, "us-east-1", lambda r=result: [r])

    assert filenames(tmp_path) == [
        "team.dev-us-east-1-cluster1-default.stdout.log",
        "team.prod-us-east-1-cluster1-default.stdout.log",
    ]


def test_kubectl_output_dir_given_as_a_string_is_created(tmp_path, capsys):
    """The command line and the config file supply the directory as a string."""
    out_dir = tmp_path / "does" / "not" / "exist"
    cmd = make_kubectl(awsrun_output_dir=str(out_dir))
    result = kubectl._Result("out\n", "warn\n", "cluster1", "default")
    cmd.regional_collect_results("100200300400", "us-east-1", lambda: [result])

    assert filenames(out_dir) == [
        "100200300400-us-east-1-cluster1-default.stderr.log",
        "100200300400-us-east-1-cluster1-default.stdout.log",
    ]
    name = "100200300400-us-east-1-cluster1-default.stdout.log"
    assert (out_dir / name).read_text() == "out\n"


def test_kubectl_output_dir_from_the_command_line(tmp_path, capsys):
    out_dir = tmp_path / "out"
    parser = argparse.ArgumentParser()
    argv = ["--region", "us-east-1", "--awsrun-output-dir", str(out_dir), "get", "pods"]
    cmd = kubectl.CLICommand.from_cli(parser, argv, lambda *a, **kw: kw.get("default"))

    result = kubectl._Result("out\n", None, "cluster1", "default")
    cmd.regional_collect_results("100200300400", "us-east-1", lambda: [result])
    assert filenames(out_dir) == ["100200300400-us-east-1-cluster1-default.stdout.log"]


def test_kubectl_without_an_output_dir_writes_nothing(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cmd = make_kubectl()
    result = kubectl._Result("out\n", None, "cluster1", "default")
    cmd.regional_collect_results("100200300400", "us-east-1", lambda: [result])
    assert filenames(tmp_path) == []


# -- kubeconfig ---------------------------------------------------------------

CLUSTER = {
    "cluster": {
        "endpoint": "https://ABC.gr7.us-east-1.eks.amazonaws.com",
        "certificateAuthority": {"data": "Q0VSVA=="},
    }
}


class FakeSession:
    def __init__(self, token="session-token"):
        self._creds = SimpleNamespace(
            access_key="AKIA", secret_key="s3cr3t", token=token
        )

    def get_credentials(self):
        return self._creds

    def client(self, *args, **kwargs):
        return FakeEKS()


class FakeEKS:
    def describe_cluster(self, name):
        return CLUSTER


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(kubectl.Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def exec_env(config):
    env = config["users"][0]["user"]["exec"]["env"]
    return {e["name"]: e["value"] for e in env}


def test_kubeconfig_with_temporary_credentials(home):
    path = kubectl._save_kubecfg(
        "cluster1", "kube-system", "100200300400", "us-east-1", CLUSTER, FakeSession()
    )
    assert path == home / ".kube" / "awsrun-100200300400-us-east-1-cluster1-kube-system"

    config = yaml.safe_load(path.read_text())
    assert config["apiVersion"] == "v1"
    assert config["kind"] == "Config"
    assert config["current-context"] == "aws"
    assert config["preferences"] == {}
    assert config["clusters"] == [
        {
            "cluster": {
                "certificate-authority-data": "Q0VSVA==",
                "server": "https://ABC.gr7.us-east-1.eks.amazonaws.com",
            },
            "name": "cluster1",
        }
    ]
    assert config["contexts"] == [
        {
            "context": {
                "cluster": "cluster1",
                "namespace": "kube-system",
                "user": "aws",
            },
            "name": "aws",
        }
    ]
    user = config["users"][0]
    assert user["name"] == "aws"
    assert user["user"]["exec"]["apiVersion"] == "client.authentication.k8s.io/v1beta1"
    assert user["user"]["exec"]["command"] == "aws"
    assert user["user"]["exec"]["args"] == [
        "--region",
        "us-east-1",
        "eks",
        "get-token",
        "--cluster-name",
        "cluster1",
    ]
    assert exec_env(config) == {
        "AWS_ACCESS_KEY_ID": "AKIA",
        "AWS_SECRET_ACCESS_KEY": "s3cr3t",
        "AWS_SESSION_TOKEN": "session-token",
    }


def test_kubeconfig_with_long_term_credentials_has_no_session_token(home):
    """A missing token must not be written as the string 'None'."""
    path = kubectl._save_kubecfg(
        "c", "default", "100200300400", "us-east-1", CLUSTER, FakeSession(token=None)
    )
    assert "None" not in path.read_text()
    assert exec_env(yaml.safe_load(path.read_text())) == {
        "AWS_ACCESS_KEY_ID": "AKIA",
        "AWS_SECRET_ACCESS_KEY": "s3cr3t",
    }


def test_kubeconfig_values_survive_yaml_special_characters(home):
    """Values such as a token with a colon must round-trip unchanged."""
    session = FakeSession(token="abc: def #not-a-comment\n")
    path = kubectl._save_kubecfg("c", "default", "1", "us-east-1", CLUSTER, session)
    env = exec_env(yaml.safe_load(path.read_text()))
    assert env["AWS_SESSION_TOKEN"] == "abc: def #not-a-comment\n"


def test_kubeconfig_file_name_escapes_slashes(home):
    path = kubectl._save_kubecfg(
        "c", "default", "org/team", "us-east-1", CLUSTER, FakeSession()
    )
    assert path.parent == home / ".kube"
    assert path.name == "awsrun-org_team-us-east-1-c-default"


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_kubeconfig_is_private(home):
    path = kubectl._save_kubecfg(
        "c", "default", "1", "us-east-1", CLUSTER, FakeSession()
    )
    assert path.stat().st_mode & 0o777 == 0o600


# -- kubectl subprocess environment -------------------------------------------


def test_kubectl_passes_kubeconfig_without_touching_os_environ(
    home, mocker, monkeypatch
):
    monkeypatch.delenv("KUBECONFIG", raising=False)
    run = mocker.patch.object(kubectl.subprocess, "run", return_value=completed())

    results = make_kubectl().regional_execute(
        FakeSession(), "100200300400", "us-east-1"
    )

    expected = home / ".kube" / "awsrun-100200300400-us-east-1-cluster1-default"
    env = run.call_args.kwargs["env"]
    assert env["KUBECONFIG"] == str(expected)
    assert env["PATH"] == os.environ["PATH"]
    assert "KUBECONFIG" not in os.environ
    assert run.call_args.args[0] == ["/usr/bin/fake", "get", "pods"]
    assert results[0].stdout == "out\n"


def test_kubectl_keeps_kubeconfig_separate_between_threads(home, mocker, monkeypatch):
    """Each account's kubectl must see its own kubeconfig when run concurrently."""
    monkeypatch.delenv("KUBECONFIG", raising=False)
    accounts = [f"{n:012d}" for n in range(1, 9)]
    barrier = threading.Barrier(len(accounts))
    seen = {}

    def fake_run(cmd, env, **kwargs):
        # Hold every worker here until all have built their environment, then
        # give the others time to interfere before reading the value back.
        kubeconfig = env["KUBECONFIG"]
        barrier.wait(timeout=10)
        time.sleep(0.05)
        return completed(stdout=f"{kubeconfig}|{env['KUBECONFIG']}")

    mocker.patch.object(kubectl.subprocess, "run", side_effect=fake_run)
    cmd = make_kubectl()

    def work(acct):
        seen[acct] = cmd.regional_execute(FakeSession(), acct, "us-east-1")[0].stdout

    threads = [threading.Thread(target=work, args=(a,)) for a in accounts]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert set(seen) == set(accounts)
    for acct in accounts:
        expected = str(home / ".kube" / f"awsrun-{acct}-us-east-1-cluster1-default")
        assert seen[acct] == f"{expected}|{expected}"
    assert "KUBECONFIG" not in os.environ
