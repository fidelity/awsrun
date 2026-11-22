#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for finding and loading commands."""

import sys
import textwrap

import pytest

from awsrun.cmdmgr import CommandManager, CommandNotFoundError
from awsrun.runner import Command

GOOD = '''
    """Help text for the command."""
    from awsrun.runner import Command


    class CLICommand(Command):
        """A command that works"""

        @classmethod
        def from_cli(cls, parser, argv, cfg):
            parser.add_argument("--flag", default=cfg("flag", default="unset"))
            return cls(**vars(parser.parse_args(argv)))

        def __init__(self, flag):
            self.flag = flag
'''

# This is what the bundled optional commands do when their extra is missing.
NEEDS_EXTRA = '''
    import sys

    try:
        import a_package_that_is_not_installed
    except ImportError:
        sys.exit("install awsrun[{extra}] to use this command")


    class CLICommand:
        """A command with a missing dependency"""
'''

BROKEN = """
    raise RuntimeError("broken at import")


    class CLICommand:
        pass
"""

NOT_A_COMMAND = """
    print("this script must never be executed")
    raise SystemExit("executed a script that is not a command")
"""


@pytest.fixture
def cmd_dir(tmp_path, monkeypatch):
    """A command directory whose modules are forgotten after the test."""
    before = set(sys.modules)
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield tmp_path
    for name in set(sys.modules) - before:
        del sys.modules[name]


def write(directory, name, source, **fmt):
    path = directory / f"{name}.py"
    path.write_text(textwrap.dedent(source).format(**fmt), encoding="utf-8")
    return path


def manager(directory):
    # A trailing separator is how a directory is told apart from a package.
    return CommandManager.from_paths(str(directory) + "/")


def test_lists_commands_in_a_directory(cmd_dir):
    write(cmd_dir, "cmdmgr_good_one", GOOD)
    write(cmd_dir, "cmdmgr_good_two", GOOD)
    commands = manager(cmd_dir).commands()
    assert sorted(commands) == ["cmdmgr_good_one", "cmdmgr_good_two"]
    assert commands["cmdmgr_good_one"].__doc__ == "A command that works"


def test_command_with_missing_extra_does_not_hide_the_others(cmd_dir):
    """Listing commands must survive a command that exits while being imported."""
    write(cmd_dir, "cmdmgr_aaa_needs_extra", NEEDS_EXTRA, extra="extra")
    write(cmd_dir, "cmdmgr_good", GOOD)
    write(cmd_dir, "cmdmgr_zzz_needs_extra", NEEDS_EXTRA, extra="other")

    assert sorted(manager(cmd_dir).commands()) == ["cmdmgr_good"]


def test_broken_command_does_not_hide_the_others(cmd_dir):
    write(cmd_dir, "cmdmgr_broken", BROKEN)
    write(cmd_dir, "cmdmgr_good", GOOD)
    assert sorted(manager(cmd_dir).commands()) == ["cmdmgr_good"]


def test_scripts_without_a_command_are_not_executed(cmd_dir, capsys):
    write(cmd_dir, "cmdmgr_plain_script", NOT_A_COMMAND)
    write(cmd_dir, "cmdmgr_good", GOOD)
    assert sorted(manager(cmd_dir).commands()) == ["cmdmgr_good"]
    assert capsys.readouterr().out == ""


def test_running_a_command_with_missing_extra_still_shows_the_hint(cmd_dir):
    """Naming the command must keep telling the user what to install."""
    write(cmd_dir, "cmdmgr_needs_extra", NEEDS_EXTRA, extra="extra")
    with pytest.raises(SystemExit) as exit_info:
        manager(cmd_dir).instantiate_command("cmdmgr_needs_extra", [], None)
    assert "install awsrun[extra]" in str(exit_info.value)


def test_unknown_command(cmd_dir):
    write(cmd_dir, "cmdmgr_good", GOOD)
    with pytest.raises(CommandNotFoundError) as exc_info:
        manager(cmd_dir).instantiate_command("cmdmgr_missing", [], None)
    assert exc_info.value.command_name == "cmdmgr_missing"


def test_instantiate_command_parses_flags_and_config(cmd_dir):
    write(cmd_dir, "cmdmgr_good", GOOD)
    mgr = manager(cmd_dir)

    def cfg(key, default=None):
        return {"flag": "from-config"}.get(key, default)

    assert mgr.instantiate_command("cmdmgr_good", [], cfg).flag == "from-config"
    cmd = mgr.instantiate_command("cmdmgr_good", ["--flag", "from-cli"], cfg)
    assert cmd.flag == "from-cli"
    assert isinstance(cmd, Command)


def test_first_path_wins(cmd_dir):
    first = cmd_dir / "first"
    second = cmd_dir / "second"
    first.mkdir()
    second.mkdir()
    write(first, "cmdmgr_only_in_first", GOOD)
    write(second, "cmdmgr_only_in_second", GOOD)

    mgr = CommandManager.from_paths(str(first) + "/", str(second) + "/")
    assert sorted(mgr.commands()) == ["cmdmgr_only_in_first", "cmdmgr_only_in_second"]


def test_bundled_commands_are_listed_without_optional_extras():
    """The command list must work whichever optional extras are installed."""
    commands = CommandManager.from_paths("awsrun.commands.aws").commands()
    for name in ("aws", "access_report", "console", "kubectl", "list_vpcs"):
        assert name in commands
        assert issubclass(commands[name], Command)
