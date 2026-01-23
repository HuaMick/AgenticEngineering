"""Tests for entry point module."""

import sys
from unittest.mock import patch

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


class TestAgentNamePositionalRouting:
    """Tests for CCI positional agent name routing in entry point."""

    def test_agent_name_early_detection(self):
        """Test positional agent names are detected early for fast response."""
        from agenticcli.entry import main
        import io
        from contextlib import redirect_stdout

        with patch.object(sys, "argv", ["agentic", "planner-guidance"]):
            captured = io.StringIO()
            with redirect_stdout(captured):
                with pytest.raises(SystemExit) as exc_info:
                    main()
            assert exc_info.value.code == 0
            # Should have agent output
            assert "planner-guidance" in captured.getvalue().lower()

    def test_agent_name_with_bootstrap_flag(self):
        """Test positional agent name with --bootstrap flag."""
        from agenticcli.entry import main
        import io
        from contextlib import redirect_stdout

        with patch.object(sys, "argv", ["agentic", "test-runner", "--bootstrap"]):
            captured = io.StringIO()
            with redirect_stdout(captured):
                with pytest.raises(SystemExit) as exc_info:
                    main()
            assert exc_info.value.code == 0
            output = captured.getvalue()
            # Bootstrap should have more content
            assert "test-runner" in output.lower()

    def test_agent_name_with_json_flag(self):
        """Test positional agent name with -j flag."""
        from agenticcli.entry import main
        import io
        import json
        from contextlib import redirect_stdout

        with patch.object(sys, "argv", ["agentic", "build-python", "-j"]):
            captured = io.StringIO()
            with redirect_stdout(captured):
                with pytest.raises(SystemExit) as exc_info:
                    main()
            assert exc_info.value.code == 0
            # Output should be valid JSON
            output = captured.getvalue()
            data = json.loads(output)
            assert data["agent"] == "build-python"

    def test_unknown_positional_not_routed_as_agent(self):
        """Test non-agent positional args go to normal CLI routing."""
        from agenticcli.entry import main

        with patch("agenticcli.cli.run_cli") as mock_run:
            with patch.object(sys, "argv", ["agentic", "unknown-command"]):
                try:
                    main()
                except SystemExit:
                    pass
            # Should delegate to run_cli, not handle as agent
            mock_run.assert_called()

    def test_flag_args_not_treated_as_agent(self):
        """Test arguments starting with - are not treated as agent names."""
        from agenticcli.entry import main

        with patch("agenticcli.cli.run_cli") as mock_run:
            with patch.object(sys, "argv", ["agentic", "-j"]):
                try:
                    main()
                except SystemExit:
                    pass
            # Should delegate to run_cli, not handle as agent
            mock_run.assert_called()


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
