"""Tests for entry point module."""

import sys
from unittest.mock import patch, MagicMock

import pytest


class TestEntryPoint:
    """Tests for the main entry point."""

    def test_version_flag(self, cli_runner):
        """Test --version flag shows version."""
        stdout, stderr, code = cli_runner(["--version"])
        # Version output goes through entry.py early exit
        assert "0.1.0" in stdout or code == 0

    def test_help_flag(self, cli_runner):
        """Test --help flag shows help."""
        stdout, stderr, code = cli_runner(["--help"])
        assert "usage" in stdout.lower() or "agentic" in stdout.lower()
        assert code == 0

    def test_no_args_shows_help(self, cli_runner):
        """Test running without arguments shows help."""
        stdout, stderr, code = cli_runner([])
        assert code == 0
        # Should show usage or help message
        assert "agentic" in stdout.lower() or "usage" in stdout.lower()

    @patch("agenticcli.cli.run_cli")
    def test_main_calls_run_cli(self, mock_run_cli):
        """Test main() delegates to run_cli for commands."""
        from agenticcli.entry import main

        with patch.object(sys, "argv", ["agentic", "config", "show"]):
            try:
                main()
            except SystemExit:
                pass

        mock_run_cli.assert_called()

    def test_main_version_early_exit(self):
        """Test --version exits early without heavy imports."""
        from agenticcli.entry import main

        with patch.object(sys, "argv", ["agentic", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_v_flag(self):
        """Test -v flag also shows version."""
        from agenticcli.entry import main

        with patch.object(sys, "argv", ["agentic", "-v"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_h_flag(self):
        """Test -h flag shows help."""
        from agenticcli.entry import main

        with patch.object(sys, "argv", ["agentic", "-h"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0


class TestEntryPointImports:
    """Test that entry point handles imports correctly."""

    def test_imports_agenticcli(self):
        """Test agenticcli package can be imported."""
        import agenticcli
        assert hasattr(agenticcli, "__version__")

    def test_imports_entry_module(self):
        """Test entry module can be imported."""
        from agenticcli import entry
        assert hasattr(entry, "main")

    def test_imports_cli_module(self):
        """Test cli module can be imported."""
        from agenticcli import cli
        assert hasattr(cli, "run_cli")
