"""Tests for main CLI functionality."""

import pytest


class TestCLIHelp:
    """Tests for CLI help output."""

    def test_main_help(self, cli_runner):
        """Test main --help output."""
        stdout, stderr, code = cli_runner(["--help"])
        assert "AgenticCLI" in stdout
        assert "worktree" in stdout
        assert "plan" in stdout
        assert "config" in stdout
        assert code == 0

    def test_no_args_shows_help(self, cli_runner):
        """Test that no args shows help."""
        stdout, stderr, code = cli_runner([])
        assert "usage:" in stdout.lower() or "AgenticCLI" in stdout
        assert code == 0


class TestSubcommandHelp:
    """Tests for subcommand help output."""

    def test_worktree_help(self, cli_runner):
        """Test worktree --help output."""
        stdout, stderr, code = cli_runner(["worktree", "--help"])
        assert "worktree" in stdout.lower()
        assert "create" in stdout
        assert "list" in stdout
        assert "remove" in stdout
        assert code == 0

    def test_plan_help(self, cli_runner):
        """Test plan --help output."""
        stdout, stderr, code = cli_runner(["plan", "--help"])
        assert "plan" in stdout.lower()
        assert "scaffold" in stdout
        assert "status" in stdout
        assert "validate" in stdout
        assert code == 0

    def test_config_help(self, cli_runner):
        """Test config --help output."""
        stdout, stderr, code = cli_runner(["config", "--help"])
        assert "config" in stdout.lower()
        assert "show" in stdout
        assert "get" in stdout
        assert "set" in stdout
        assert "delete" in stdout
        assert code == 0

    def test_template_help(self, cli_runner):
        """Test template --help output."""
        stdout, stderr, code = cli_runner(["template", "--help"])
        assert "template" in stdout.lower()
        assert "generate" in stdout
        assert "list" in stdout
        assert code == 0


class TestCLIVersion:
    """Tests for CLI version output."""

    def test_version(self, cli_runner):
        """Test --version output."""
        stdout, stderr, code = cli_runner(["--version"])
        assert "0.1.0" in stdout
        assert code == 0
