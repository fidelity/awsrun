#
# Copyright 2025 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

# pylint: disable=redefined-outer-name,missing-docstring

import pytest
from awsrun.runner import AccountRunner, Command
from awsrun.session import SessionProvider


@pytest.fixture
def runner(mocker):
    session_provider = mocker.MagicMock(spec=SessionProvider)
    return AccountRunner(session_provider)


def test_lifecycle_methods(mocker, runner):
    command = mocker.MagicMock(spec=Command)
    runner.run(command, ["a", "b"])
    command.pre_hook_with_context.assert_called()
    assert command.execute.call_count == 2
    command.collect_results.assert_called()
    command.post_hook.assert_called()


def test_lifecycle_methods_with_no_accts_to_process(mocker, runner):
    command = mocker.MagicMock(spec=Command)
    runner.run(command, [])
    command.pre_hook_with_context.assert_called()
    command.execute.assert_not_called()
    command.collect_results.assert_not_called()
    command.post_hook.assert_called()


def test_pre_hook_with_context(mocker, runner):
    command = Command()
    command.pre_hook_with_context = mocker.MagicMock()
    runner.run(command, [], context="Hello")
    command.pre_hook_with_context.assert_called_with("Hello")


# If no pre_hook_with_context is explicitly defined in a Command, then the
# default implementation should invoke the older pre_hook method for
# backwards compatibility.
def test_backwards_compat_lifecycle_pre_hook(mocker, runner):
    command = Command()
    command.pre_hook = mocker.MagicMock()
    runner.run(command, [])
    command.pre_hook.assert_called()
