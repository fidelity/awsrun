#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests that drive the CLI entry point the way a user would."""

import pytest

from awsrun import cli

TWO_ACCOUNTS = [
    "--account",
    "100200300400",
    "--account",
    "200300400100",
    "list_vpcs",
    "--region",
    "us-east-1",
]


@pytest.fixture(autouse=True)
def empty_user_config(monkeypatch, tmp_path):
    monkeypatch.setenv("AWSRUN_CONFIG", str(tmp_path / "missing.yaml"))
    monkeypatch.delenv("AWSRUN_TRACE", raising=False)


def run_main(monkeypatch, argv):
    """Runs the CLI and returns its exit status (None if it did not exit)."""
    monkeypatch.setattr(cli.sys, "argv", ["awsrun", *argv])
    try:
        cli.main()
    except SystemExit as e:
        return e.code
    return None


def test_no_accounts_selected(monkeypatch, capsys):
    assert run_main(monkeypatch, []) == 1
    assert "No accounts selected" in capsys.readouterr().err


def test_version(monkeypatch, capsys):
    assert run_main(monkeypatch, ["--version"]) == 0
    assert cli.__version__ in capsys.readouterr().out


def test_accounts_are_listed_without_a_command(monkeypatch, mocker):
    # The printing functions are spied upon, rather than capturing the output,
    # as they bind sys.stdout when the module is imported.
    print_accounts = mocker.spy(cli, "_print_accounts")
    print_commands = mocker.spy(cli, "_print_valid_commands")

    argv = ["--account", "100200300400", "--account", "200300400100"]
    assert run_main(monkeypatch, argv) == 1

    assert sorted(print_accounts.call_args.args[0]) == ["100200300400", "200300400100"]
    commands = print_commands.call_args.args[0]
    assert "list_vpcs" in commands
    assert "aws" in commands


def test_unknown_command(monkeypatch, capsys):
    argv = ["--account", "100200300400", "no_such_command"]
    assert run_main(monkeypatch, argv) == 1
    assert "no_such_command" in capsys.readouterr().err


def test_prompt_with_closed_stdin_explains_force(monkeypatch, capsys, mocker):
    mocker.patch("builtins.input", side_effect=EOFError)
    run = mocker.patch.object(cli.AccountRunner, "run")

    assert run_main(monkeypatch, TWO_ACCOUNTS) == 1

    err = capsys.readouterr().err
    assert "Proceed (y/n)?" in err
    assert "--force" in err
    assert "EOF when reading a line" not in err
    run.assert_not_called()


@pytest.mark.parametrize("answer", ["n", "no", "", "maybe"])
def test_prompt_declined(monkeypatch, capsys, mocker, answer):
    mocker.patch("builtins.input", return_value=answer)
    run = mocker.patch.object(cli.AccountRunner, "run")

    assert run_main(monkeypatch, TWO_ACCOUNTS) == 0

    assert "Exiting" in capsys.readouterr().err
    run.assert_not_called()


@pytest.mark.parametrize("answer", ["y", "Y", "yes", "YES"])
def test_prompt_accepted(monkeypatch, capsys, mocker, answer):
    mocker.patch("builtins.input", return_value=answer)
    run = mocker.patch.object(cli.AccountRunner, "run", return_value=1.5)

    assert run_main(monkeypatch, TWO_ACCOUNTS) is None

    run.assert_called_once()
    assert "Processed 2 accounts" in capsys.readouterr().err


def test_force_skips_the_prompt(monkeypatch, capsys, mocker):
    ask = mocker.patch("builtins.input", side_effect=AssertionError("prompted"))
    run = mocker.patch.object(cli.AccountRunner, "run", return_value=0.1)

    assert run_main(monkeypatch, ["--force", *TWO_ACCOUNTS]) is None

    ask.assert_not_called()
    run.assert_called_once()


def test_single_account_is_not_prompted(monkeypatch, capsys, mocker):
    ask = mocker.patch("builtins.input", side_effect=AssertionError("prompted"))
    run = mocker.patch.object(cli.AccountRunner, "run", return_value=0.1)

    argv = ["--account", "100200300400", "list_vpcs", "-r", "us-east-1"]
    assert run_main(monkeypatch, argv) is None

    ask.assert_not_called()
    run.assert_called_once()
    assert "Processed 1 account in" in capsys.readouterr().err


def test_ctrl_c_at_the_prompt_exits_without_a_traceback(monkeypatch, capsys, mocker):
    mocker.patch("builtins.input", side_effect=KeyboardInterrupt)
    run = mocker.patch.object(cli.AccountRunner, "run")

    assert run_main(monkeypatch, TWO_ACCOUNTS) == 130

    err = capsys.readouterr().err
    assert "Interrupted" in err
    assert "Traceback" not in err
    run.assert_not_called()


def test_ctrl_c_during_a_run_exits_without_a_traceback(monkeypatch, capsys, mocker):
    mocker.patch.object(cli.AccountRunner, "run", side_effect=KeyboardInterrupt)

    assert run_main(monkeypatch, ["--force", *TWO_ACCOUNTS]) == 130

    err = capsys.readouterr().err
    assert "Interrupted" in err
    assert "Traceback" not in err


def test_trace_variable_shows_the_traceback_on_ctrl_c(monkeypatch, capsys, mocker):
    monkeypatch.setenv("AWSRUN_TRACE", "1")
    mocker.patch.object(cli.AccountRunner, "run", side_effect=KeyboardInterrupt)

    assert run_main(monkeypatch, ["--force", *TWO_ACCOUNTS]) == 130
    assert "Traceback" in capsys.readouterr().err


def test_errors_still_exit_with_status_one(monkeypatch, capsys, mocker):
    mocker.patch.object(cli.AccountRunner, "run", side_effect=RuntimeError("boom"))

    assert run_main(monkeypatch, ["--force", *TWO_ACCOUNTS]) == 1

    err = capsys.readouterr().err
    assert "boom" in err
    assert "Traceback" not in err
