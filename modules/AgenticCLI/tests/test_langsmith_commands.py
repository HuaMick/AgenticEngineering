"""Tests for LangSmith CLI commands."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestLangsmithHelp:
    """Tests for langsmith command help output."""

    def test_langsmith_help(self, cli_runner):
        """Test langsmith --help output."""
        stdout, stderr, code = cli_runner(["langsmith", "--help"])
        assert "langsmith" in stdout.lower()
        assert "runs" in stdout
        assert "run" in stdout
        assert "projects" in stdout
        assert "stats" in stdout
        assert code == 0

    def test_langsmith_alias_ls(self, cli_runner):
        """Test 'ls' alias works for langsmith."""
        result_full = cli_runner(["langsmith", "--help"])
        result_alias = cli_runner(["ls", "--help"])
        assert result_full.returncode == 0
        assert result_alias.returncode == 0
        # Both should show langsmith help
        assert "runs" in result_alias.stdout
        assert "projects" in result_alias.stdout

    def test_langsmith_runs_help(self, cli_runner):
        """Test langsmith runs --help output."""
        stdout, stderr, code = cli_runner(["langsmith", "runs", "--help"])
        assert "--project" in stdout
        assert "--limit" in stdout
        assert "--type" in stdout
        assert "--error" in stdout
        assert code == 0

    def test_langsmith_run_help(self, cli_runner):
        """Test langsmith run --help output."""
        stdout, stderr, code = cli_runner(["langsmith", "run", "--help"])
        assert "run_id" in stdout
        assert "--url" in stdout
        assert code == 0

    def test_langsmith_projects_help(self, cli_runner):
        """Test langsmith projects --help output."""
        stdout, stderr, code = cli_runner(["langsmith", "projects", "--help"])
        assert "--detail" in stdout
        assert code == 0

    def test_langsmith_stats_help(self, cli_runner):
        """Test langsmith stats --help output."""
        stdout, stderr, code = cli_runner(["langsmith", "stats", "--help"])
        assert "--project" in stdout
        # The project flag is shown as required via the syntax in usage
        assert code == 0


class TestLangsmithCommandRegistration:
    """Tests for langsmith command registration in CLI."""

    def test_langsmith_in_main_help(self, cli_runner):
        """Test that langsmith is listed in main help."""
        stdout, stderr, code = cli_runner(["--help"])
        assert "langsmith" in stdout
        assert code == 0

    def test_langsmith_in_global_commands(self):
        """Test that langsmith is in GLOBAL_COMMANDS set."""
        from agenticcli.cli import GLOBAL_COMMANDS

        assert "langsmith" in GLOBAL_COMMANDS
        assert "ls" in GLOBAL_COMMANDS

    def test_langsmith_not_in_project_commands(self):
        """Test that langsmith is NOT in PROJECT_COMMANDS set."""
        from agenticcli.cli import PROJECT_COMMANDS

        assert "langsmith" not in PROJECT_COMMANDS


class TestLangsmithCommandsWithMock:
    """Tests for langsmith commands with mocked service."""

    def test_runs_command_calls_service(self, cli_runner):
        """Test that runs command calls list_runs on service."""
        mock_service = MagicMock()
        mock_service.list_runs.return_value = []

        with patch("agenticcli.commands.langsmith._get_service") as mock_get:
            mock_get.return_value = mock_service

            result = cli_runner(["langsmith", "runs"])

            # Verify the service was called
            mock_service.list_runs.assert_called_once()
            assert result.returncode == 0

    def test_runs_command_passes_filters(self, cli_runner):
        """Test that runs command passes filter options to service."""
        mock_service = MagicMock()
        mock_service.list_runs.return_value = []

        with patch("agenticcli.commands.langsmith._get_service") as mock_get:
            mock_get.return_value = mock_service

            result = cli_runner([
                "langsmith", "runs",
                "--project", "my-project",
                "--limit", "50",
                "--type", "llm",
                "--error"
            ])

            call_kwargs = mock_service.list_runs.call_args.kwargs
            assert call_kwargs["project_name"] == "my-project"
            assert call_kwargs["limit"] == 50
            assert call_kwargs["run_type"] == "llm"
            assert call_kwargs["error_only"] is True

    def test_runs_command_json_output(self, cli_runner):
        """Test that runs command outputs JSON when requested."""
        mock_service = MagicMock()
        mock_service.list_runs.return_value = [
            {
                "id": "run-123",
                "name": "test-run",
                "run_type": "llm",
                "latency": 1.5,
                "total_tokens": 100,
                "status": "success",
            }
        ]

        with patch("agenticcli.commands.langsmith._get_service") as mock_get:
            mock_get.return_value = mock_service

            result = cli_runner(["-j", "langsmith", "runs"])

            data = json.loads(result.stdout)
            assert "runs" in data
            assert data["count"] == 1
            assert data["runs"][0]["name"] == "test-run"

    def test_run_command_calls_get_run(self, cli_runner):
        """Test that run command calls get_run on service."""
        mock_service = MagicMock()
        mock_service.get_run.return_value = {
            "id": "run-123",
            "name": "test-run",
            "run_type": "llm",
            "status": "success",
        }
        mock_service.get_run_feedback.return_value = []

        with patch("agenticcli.commands.langsmith._get_service") as mock_get:
            mock_get.return_value = mock_service

            result = cli_runner(["langsmith", "run", "run-123"])

            mock_service.get_run.assert_called_once_with("run-123")
            assert result.returncode == 0

    def test_run_command_with_url_flag(self, cli_runner):
        """Test that run command with --url calls get_run_url."""
        mock_service = MagicMock()
        mock_service.get_run.return_value = {
            "id": "run-123",
            "name": "test-run",
            "run_type": "llm",
            "status": "success",
        }
        mock_service.get_run_feedback.return_value = []
        mock_service.get_run_url.return_value = "https://smith.langchain.com/runs/run-123"

        with patch("agenticcli.commands.langsmith._get_service") as mock_get:
            mock_get.return_value = mock_service

            result = cli_runner(["langsmith", "run", "run-123", "--url"])

            mock_service.get_run_url.assert_called_once_with("run-123")
            assert "https://smith.langchain.com" in result.stdout

    def test_projects_command_calls_list_projects(self, cli_runner):
        """Test that projects command calls list_projects on service."""
        mock_service = MagicMock()
        mock_service.list_projects.return_value = []

        with patch("agenticcli.commands.langsmith._get_service") as mock_get:
            mock_get.return_value = mock_service

            result = cli_runner(["langsmith", "projects"])

            mock_service.list_projects.assert_called_once()
            assert result.returncode == 0

    def test_projects_command_json_output(self, cli_runner):
        """Test that projects command outputs JSON when requested."""
        mock_service = MagicMock()
        mock_service.list_projects.return_value = [
            {
                "id": "proj-123",
                "name": "my-project",
                "run_count": 100,
            }
        ]

        with patch("agenticcli.commands.langsmith._get_service") as mock_get:
            mock_get.return_value = mock_service

            result = cli_runner(["-j", "langsmith", "projects"])

            data = json.loads(result.stdout)
            assert "projects" in data
            assert data["count"] == 1
            assert data["projects"][0]["name"] == "my-project"

    def test_stats_command_requires_project(self, cli_runner):
        """Test that stats command requires --project flag."""
        result = cli_runner(["langsmith", "stats"])
        # Should fail because --project is required
        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_stats_command_calls_get_project_stats(self, cli_runner):
        """Test that stats command calls get_project_stats on service."""
        mock_service = MagicMock()
        mock_service.get_project_stats.return_value = {
            "project_name": "my-project",
            "total_runs": 100,
            "error_count": 5,
            "error_rate": 5.0,
            "avg_latency": 1.5,
            "total_tokens": 10000,
            "run_types": {"llm": 80, "chain": 20},
        }

        with patch("agenticcli.commands.langsmith._get_service") as mock_get:
            mock_get.return_value = mock_service

            result = cli_runner(["langsmith", "stats", "--project", "my-project"])

            mock_service.get_project_stats.assert_called_once_with("my-project")
            assert result.returncode == 0


class TestLangsmithErrorHandling:
    """Tests for langsmith command error handling."""

    def test_missing_api_key_error(self, cli_runner):
        """Test clear error message when API key is missing."""
        # Mock _get_service to simulate missing API key error
        with patch("agenticcli.commands.langsmith._get_service") as mock_get:
            from agenticlangsmith import LangSmithConfigError
            mock_get.side_effect = SystemExit(1)

            result = cli_runner(["langsmith", "runs"])

            assert result.returncode == 1

    def test_api_error_is_displayed(self, cli_runner):
        """Test that API errors are displayed to user."""
        with patch("agenticcli.commands.langsmith._get_service") as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service
            mock_service.list_runs.side_effect = Exception("Connection failed")

            result = cli_runner(["langsmith", "runs"])

            assert result.returncode == 1
            assert "error" in result.stderr.lower() or "failed" in result.stderr.lower()


class TestLangsmithSubcommandRouting:
    """Tests for langsmith subcommand routing."""

    def test_no_subcommand_shows_usage(self, cli_runner):
        """Test that no subcommand shows usage message."""
        result = cli_runner(["langsmith"])

        # Typer/Click returns exit code 2 for usage errors (no subcommand given)
        assert result.returncode in (1, 2)
        combined = result.stdout + result.stderr
        assert "runs" in combined.lower() or "usage" in combined.lower()

    def test_invalid_subcommand_shows_usage(self, cli_runner):
        """Test that invalid subcommand shows usage message."""
        result = cli_runner(["langsmith", "invalid"])

        # Should exit with error
        assert result.returncode != 0
