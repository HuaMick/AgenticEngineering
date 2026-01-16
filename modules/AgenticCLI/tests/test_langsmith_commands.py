"""Tests for LangSmith CLI commands."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestLangsmithCommandRegistration:
    """Test that langsmith command is properly registered."""

    def test_langsmith_command_exists(self, cli_runner):
        """Test that langsmith command is registered."""
        result = cli_runner("langsmith", "--help")
        assert result.returncode == 0
        assert "runs" in result.stdout
        assert "run" in result.stdout
        assert "projects" in result.stdout
        assert "stats" in result.stdout

    def test_langsmith_alias_ls_works(self, cli_runner):
        """Test that 'ls' alias works for langsmith."""
        result = cli_runner("ls", "--help")
        assert result.returncode == 0
        assert "runs" in result.stdout
        assert "projects" in result.stdout


class TestLangsmithRunsCommand:
    """Test langsmith runs subcommand."""

    def test_langsmith_runs_help(self, cli_runner):
        """Test runs subcommand help text."""
        result = cli_runner("langsmith", "runs", "--help")
        assert result.returncode == 0
        assert "--project" in result.stdout
        assert "--limit" in result.stdout
        assert "--type" in result.stdout
        assert "--error" in result.stdout

    def test_langsmith_runs_parsing_limit(self, cli_runner):
        """Test that --limit argument is parsed correctly."""
        # Mock the service to avoid actual API calls
        mock_service = MagicMock()
        mock_service.list_runs.return_value = []

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("langsmith", "runs", "--limit", "50")

        # Check that list_runs was called with limit=50
        mock_service.list_runs.assert_called_once()
        call_kwargs = mock_service.list_runs.call_args[1]
        assert call_kwargs["limit"] == 50

    def test_langsmith_runs_parsing_project(self, cli_runner):
        """Test that --project argument is parsed correctly."""
        mock_service = MagicMock()
        mock_service.list_runs.return_value = []

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("langsmith", "runs", "--project", "my-project")

        mock_service.list_runs.assert_called_once()
        call_kwargs = mock_service.list_runs.call_args[1]
        assert call_kwargs["project_name"] == "my-project"

    def test_langsmith_runs_parsing_type(self, cli_runner):
        """Test that --type argument is parsed correctly."""
        mock_service = MagicMock()
        mock_service.list_runs.return_value = []

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("langsmith", "runs", "--type", "llm")

        mock_service.list_runs.assert_called_once()
        call_kwargs = mock_service.list_runs.call_args[1]
        assert call_kwargs["run_type"] == "llm"

    def test_langsmith_runs_parsing_error_flag(self, cli_runner):
        """Test that --error flag is parsed correctly."""
        mock_service = MagicMock()
        mock_service.list_runs.return_value = []

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("langsmith", "runs", "--error")

        mock_service.list_runs.assert_called_once()
        call_kwargs = mock_service.list_runs.call_args[1]
        assert call_kwargs["error_only"] is True

    def test_langsmith_runs_default_limit(self, cli_runner):
        """Test that default limit is 20."""
        mock_service = MagicMock()
        mock_service.list_runs.return_value = []

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("langsmith", "runs")

        mock_service.list_runs.assert_called_once()
        call_kwargs = mock_service.list_runs.call_args[1]
        assert call_kwargs["limit"] == 20


class TestLangsmithRunCommand:
    """Test langsmith run subcommand."""

    def test_langsmith_run_help(self, cli_runner):
        """Test run subcommand help text."""
        result = cli_runner("langsmith", "run", "--help")
        assert result.returncode == 0
        assert "run_id" in result.stdout
        assert "--url" in result.stdout

    def test_langsmith_run_requires_run_id(self, cli_runner):
        """Test that run_id is required."""
        result = cli_runner("langsmith", "run")
        assert result.returncode != 0

    def test_langsmith_run_parsing(self, cli_runner):
        """Test that run_id is parsed correctly."""
        mock_service = MagicMock()
        mock_service.get_run.return_value = {
            "id": "test-run-id-123",
            "name": "Test Run",
            "run_type": "llm",
        }

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("langsmith", "run", "test-run-id-123")

        mock_service.get_run.assert_called_once_with("test-run-id-123")

    def test_langsmith_run_url_flag(self, cli_runner):
        """Test that --url flag generates URL."""
        mock_service = MagicMock()
        mock_service.get_run_url.return_value = "https://smith.langchain.com/run/test-id"

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("langsmith", "run", "test-id", "--url")

        mock_service.get_run_url.assert_called_once_with("test-id")
        assert "https://smith.langchain.com" in result.stdout


class TestLangsmithProjectsCommand:
    """Test langsmith projects subcommand."""

    def test_langsmith_projects_help(self, cli_runner):
        """Test projects subcommand help text."""
        result = cli_runner("langsmith", "projects", "--help")
        assert result.returncode == 0
        assert "--detail" in result.stdout

    def test_langsmith_projects_lists_projects(self, cli_runner):
        """Test that projects are listed."""
        mock_service = MagicMock()
        mock_service.list_projects.return_value = [
            {"name": "project-1", "id": "id-1", "run_count": 100},
            {"name": "project-2", "id": "id-2", "run_count": 50},
        ]

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("langsmith", "projects")

        assert result.returncode == 0
        mock_service.list_projects.assert_called_once()


class TestLangsmithStatsCommand:
    """Test langsmith stats subcommand."""

    def test_langsmith_stats_help(self, cli_runner):
        """Test stats subcommand help text."""
        result = cli_runner("langsmith", "stats", "--help")
        assert result.returncode == 0
        assert "--project" in result.stdout
        assert "--since" in result.stdout
        assert "--until" in result.stdout

    def test_langsmith_stats_requires_project(self, cli_runner):
        """Test that --project is required for stats."""
        result = cli_runner("langsmith", "stats")
        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_langsmith_stats_with_project(self, cli_runner):
        """Test stats with --project argument."""
        mock_service = MagicMock()
        mock_service.get_project_stats.return_value = {
            "total_runs": 1000,
            "total_tokens": 50000,
            "error_count": 10,
        }

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("langsmith", "stats", "--project", "my-project")

        assert result.returncode == 0
        mock_service.get_project_stats.assert_called_once_with("my-project")


class TestLangsmithJsonOutput:
    """Test JSON output mode for langsmith commands."""

    def test_langsmith_runs_json_output(self, cli_runner):
        """Test that runs outputs valid JSON with --json flag."""
        mock_service = MagicMock()
        mock_service.list_runs.return_value = [
            {"id": "run-1", "name": "Run 1"},
            {"id": "run-2", "name": "Run 2"},
        ]

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("-j", "langsmith", "runs")

        assert result.returncode == 0
        # Parse JSON to verify it's valid
        data = json.loads(result.stdout)
        assert "runs" in data
        assert len(data["runs"]) == 2

    def test_langsmith_projects_json_output(self, cli_runner):
        """Test that projects outputs valid JSON with --json flag."""
        mock_service = MagicMock()
        mock_service.list_projects.return_value = [
            {"name": "project-1", "id": "id-1"},
        ]

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("-j", "langsmith", "projects")

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "projects" in data

    def test_langsmith_run_json_output(self, cli_runner):
        """Test that run detail outputs valid JSON with --json flag."""
        mock_service = MagicMock()
        mock_service.get_run.return_value = {
            "id": "test-id",
            "name": "Test Run",
            "run_type": "llm",
        }

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("-j", "langsmith", "run", "test-id")

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["id"] == "test-id"


class TestLangsmithErrorHandling:
    """Test error handling for langsmith commands."""

    def test_langsmith_api_error_is_handled(self, cli_runner):
        """Test that API errors are handled gracefully."""
        mock_service = MagicMock()
        mock_service.list_runs.side_effect = Exception("API connection failed")

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("langsmith", "runs")

        # Should fail gracefully with error message
        assert result.returncode != 0
        assert "API" in result.stderr or "failed" in result.stderr.lower()

    def test_langsmith_run_not_found(self, cli_runner):
        """Test handling when run is not found."""
        mock_service = MagicMock()
        mock_service.get_run.return_value = None

        with patch("agenticcli.commands.langsmith._get_service", return_value=mock_service):
            result = cli_runner("langsmith", "run", "nonexistent-id")

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()
