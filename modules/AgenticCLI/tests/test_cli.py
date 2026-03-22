"""Tests for main CLI functionality."""

import pytest

pytestmark = pytest.mark.story("US-SET-001")


@pytest.mark.story("US-SET-001", "US-SET-012", "US-SET-013")
class TestCLIHelp:
    """Tests for CLI help output.

    Also covers US-SET-012 (Install Shell Auto-Completion) and
    US-SET-013 (Show Completion Script) — no dedicated completion tests
    exist; CLI help is the closest related coverage.
    """

    def test_main_help(self, cli_runner):
        """Test main --help output."""
        stdout, stderr, code = cli_runner(["--help"])
        assert "AgenticCLI" in stdout
        assert "setup" in stdout
        assert "orchestrate" in stdout
        assert code == 0

    def test_no_args_shows_help(self, cli_runner):
        """Test that no args shows help."""
        stdout, stderr, code = cli_runner([])
        assert "usage:" in stdout.lower() or "AgenticCLI" in stdout
        assert code == 0


@pytest.mark.story("US-SET-001")
class TestSubcommandHelp:
    """Tests for subcommand help output."""

    def test_config_help(self, cli_runner):
        """Test configure config --help output."""
        stdout, stderr, code = cli_runner(["configure", "config", "--help"])
        assert "config" in stdout.lower()
        assert "show" in stdout
        assert "get" in stdout
        assert "set" in stdout
        assert "delete" in stdout
        assert code == 0



@pytest.mark.story("US-SET-001")
class TestCLIVersion:
    """Tests for CLI version output."""

    def test_version(self, cli_runner):
        """Test --version output."""
        stdout, stderr, code = cli_runner(["--version"])
        assert "0.1.0" in stdout
        assert code == 0


@pytest.mark.story("US-SET-001")
class TestCommandAliases:
    """Tests for command aliases."""

    def test_configure_alias_cfg(self, cli_runner):
        """Test 'cfg' alias works for configure (now deprecated, shows config/env/state subcommands)."""
        result_full = cli_runner(["configure", "--help"])
        result_alias = cli_runner(["cfg", "--help"])
        assert result_full.returncode == 0
        assert result_alias.returncode == 0
        # Both should show the deprecated configure subcommands
        assert "config" in result_alias.stdout
        assert "env" in result_alias.stdout
        assert "state" in result_alias.stdout



@pytest.mark.story("US-SET-007")
class TestFlagShortcuts:
    """Tests for flag shortcuts."""

    def test_json_flag_shortcut_j(self, cli_runner):
        """Test '-j' shortcut works for --json."""
        result = cli_runner(["-j", "setup", "health"])
        assert result.returncode == 0
        # Should be valid JSON output
        import json

        data = json.loads(result.stdout)
        assert "status" in data

    def test_help_shows_aliases(self, cli_runner):
        """Test main help shows user-facing command names, not hidden ones."""
        result = cli_runner(["--help"])
        assert result.returncode == 0
        # Check user-facing top-level groups are visible
        assert "setup" in result.stdout
        assert "orchestrate" in result.stdout
        assert "epic" in result.stdout
        # Check -j flag is documented
        assert "-j" in result.stdout or "--json" in result.stdout
