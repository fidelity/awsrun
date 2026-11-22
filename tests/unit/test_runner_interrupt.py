#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for how the runner behaves when it is interrupted or a command fails."""

import time

import pytest

from awsrun.runner import AccountRunner, Command
from awsrun.session import SessionProvider


@pytest.fixture
def session_provider(mocker):
    return mocker.MagicMock(spec=SessionProvider)


def test_interrupt_does_not_process_waiting_accounts(session_provider):
    """Ctrl-C must not run the command on every account still in the queue."""
    runner = AccountRunner(session_provider, max_workers=1)
    executed = []

    class Interrupted(Command):
        def execute(self, session, acct):
            # Each account takes a little time, as it would in real use, so
            # the single worker cannot finish the whole queue before the main
            # thread has had the chance to react to the interrupt.
            executed.append(acct)
            time.sleep(0.01)

        def collect_results(self, acct, get_result):
            raise KeyboardInterrupt

    accounts = [str(n) for n in range(300)]
    with pytest.raises(KeyboardInterrupt):
        runner.run(Interrupted(), accounts)

    assert 1 <= len(executed) < len(accounts)


def test_error_in_collect_results_is_still_raised(session_provider):
    runner = AccountRunner(session_provider, max_workers=2)

    class Broken(Command):
        def execute(self, session, acct):
            return acct

        def collect_results(self, acct, get_result):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        runner.run(Broken(), ["a", "b", "c"])


def test_all_accounts_are_processed_and_collected(session_provider):
    runner = AccountRunner(session_provider, max_workers=4)
    collected = {}

    class Echo(Command):
        def execute(self, session, acct):
            if acct == "13":
                raise ValueError("unlucky")
            return acct * 2

        def collect_results(self, acct, get_result):
            try:
                collected[acct] = get_result()
            except ValueError as e:
                collected[acct] = str(e)

    accounts = [str(n) for n in range(50)]
    elapsed = runner.run(Echo(), accounts)

    assert elapsed >= 0
    assert set(collected) == set(accounts)
    assert collected["7"] == "77"
    assert collected["13"] == "unlucky"


def test_session_failure_is_reported_per_account(session_provider):
    """A failure to get credentials for one account must not stop the others."""

    def session(acct_id):
        if acct_id == "bad":
            raise PermissionError("access denied")
        return object()

    session_provider.session.side_effect = session
    collected = {}

    class Echo(Command):
        def execute(self, session, acct):
            return "ok"

        def collect_results(self, acct, get_result):
            try:
                collected[acct] = get_result()
            except PermissionError as e:
                collected[acct] = str(e)

    AccountRunner(session_provider, max_workers=3).run(Echo(), ["a", "bad", "c"])
    assert collected == {"a": "ok", "bad": "access denied", "c": "ok"}
