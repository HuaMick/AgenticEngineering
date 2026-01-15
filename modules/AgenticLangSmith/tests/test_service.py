"""Unit tests for LangSmithService."""

import os
from unittest.mock import MagicMock, patch

import pytest

from agenticlangsmith.service import (
    LangSmithService,
    LangSmithConfigError,
    LangSmithAPIError,
)


class TestServiceInit:
    """Tests for LangSmithService initialization."""

    def test_service_init_with_api_key(self, mock_langsmith_client):
        """Test that explicit api_key parameter works."""
        service = LangSmithService(api_key="test-api-key-123")

        assert service.api_key == "test-api-key-123"
        assert service._client is not None

    def test_service_init_from_env(self, mock_langsmith_client):
        """Test that service reads from LANGSMITH_API_KEY env var."""
        with patch.dict(os.environ, {"LANGSMITH_API_KEY": "env-api-key-456"}):
            service = LangSmithService()

            assert service.api_key == "env-api-key-456"
            assert service._client is not None

    def test_service_raises_without_key(self):
        """Test that LangSmithConfigError is raised when no API key available."""
        # Ensure no env var is set
        with patch.dict(os.environ, {"LANGSMITH_API_KEY": ""}, clear=False):
            # Also clear the key if it exists
            env_copy = os.environ.copy()
            if "LANGSMITH_API_KEY" in env_copy:
                del env_copy["LANGSMITH_API_KEY"]

            with patch.dict(os.environ, env_copy, clear=True):
                with pytest.raises(LangSmithConfigError) as exc_info:
                    LangSmithService()

                assert "LANGSMITH_API_KEY" in str(exc_info.value)

    def test_service_prefers_explicit_key_over_env(self, mock_langsmith_client):
        """Test that explicit api_key takes precedence over env var."""
        with patch.dict(os.environ, {"LANGSMITH_API_KEY": "env-key"}):
            service = LangSmithService(api_key="explicit-key")

            assert service.api_key == "explicit-key"


class TestListRuns:
    """Tests for LangSmithService.list_runs()."""

    def test_list_runs_returns_list(self, mock_langsmith_client, mock_run_object):
        """Test that list_runs returns a list with mocked client."""
        mock_langsmith_client.list_runs.return_value = [mock_run_object]

        service = LangSmithService(api_key="test-key")
        result = service.list_runs()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == mock_run_object.name
        assert result[0]["run_type"] == mock_run_object.run_type

    def test_list_runs_with_filters(self, mock_langsmith_client, mock_run_object):
        """Test that filters are passed correctly to SDK."""
        mock_langsmith_client.list_runs.return_value = [mock_run_object]

        service = LangSmithService(api_key="test-key")
        service.list_runs(
            project_name="my-project",
            limit=50,
            run_type="llm",
            error_only=True,
            filter_expr="eq(status, 'error')"
        )

        # Verify the client was called with correct kwargs
        mock_langsmith_client.list_runs.assert_called_once()
        call_kwargs = mock_langsmith_client.list_runs.call_args.kwargs

        assert call_kwargs["project_name"] == "my-project"
        assert call_kwargs["limit"] == 50
        assert call_kwargs["run_type"] == "llm"
        assert call_kwargs["error"] is True
        assert call_kwargs["filter"] == "eq(status, 'error')"

    def test_list_runs_empty_result(self, mock_langsmith_client):
        """Test that list_runs handles empty results gracefully."""
        mock_langsmith_client.list_runs.return_value = []

        service = LangSmithService(api_key="test-key")
        result = service.list_runs()

        assert isinstance(result, list)
        assert len(result) == 0

    def test_list_runs_calculates_latency(self, mock_langsmith_client, mock_run_object):
        """Test that latency is calculated correctly from start/end times."""
        mock_langsmith_client.list_runs.return_value = [mock_run_object]

        service = LangSmithService(api_key="test-key")
        result = service.list_runs()

        # The sample run has 2 seconds between start and end time
        assert result[0]["latency"] == 2.0

    def test_list_runs_api_error(self, mock_langsmith_client):
        """Test that API errors are wrapped in LangSmithAPIError."""
        mock_langsmith_client.list_runs.side_effect = Exception("API connection failed")

        service = LangSmithService(api_key="test-key")

        with pytest.raises(LangSmithAPIError) as exc_info:
            service.list_runs()

        assert "Failed to list runs" in str(exc_info.value)


class TestGetRun:
    """Tests for LangSmithService.get_run()."""

    def test_get_run_returns_details(self, mock_langsmith_client, mock_run_object):
        """Test that get_run returns full run details."""
        mock_langsmith_client.read_run.return_value = mock_run_object

        service = LangSmithService(api_key="test-key")
        result = service.get_run("run-id-123")

        assert result["id"] == str(mock_run_object.id)
        assert result["name"] == mock_run_object.name
        assert result["inputs"] == mock_run_object.inputs
        assert result["outputs"] == mock_run_object.outputs
        assert result["tags"] == mock_run_object.tags

    def test_get_run_not_found(self, mock_langsmith_client):
        """Test that 404/not found is handled gracefully."""
        mock_langsmith_client.read_run.side_effect = Exception("Run not found")

        service = LangSmithService(api_key="test-key")

        with pytest.raises(LangSmithAPIError) as exc_info:
            service.get_run("nonexistent-run-id")

        assert "Failed to get run" in str(exc_info.value)
        assert "nonexistent-run-id" in str(exc_info.value)

    def test_get_run_with_error_status(
        self, mock_langsmith_client, mock_run_with_error_object
    ):
        """Test that runs with errors have correct status."""
        mock_langsmith_client.read_run.return_value = mock_run_with_error_object

        service = LangSmithService(api_key="test-key")
        result = service.get_run("error-run-id")

        assert result["status"] == "error"
        assert result["error"] is not None


class TestListProjects:
    """Tests for LangSmithService.list_projects()."""

    def test_list_projects(self, mock_langsmith_client, mock_project_object):
        """Test that list_projects returns project list."""
        mock_langsmith_client.list_projects.return_value = [mock_project_object]

        service = LangSmithService(api_key="test-key")
        result = service.list_projects()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == mock_project_object.name
        assert result[0]["description"] == mock_project_object.description
        assert result[0]["run_count"] == mock_project_object.run_count

    def test_list_projects_empty(self, mock_langsmith_client):
        """Test that empty project list is handled."""
        mock_langsmith_client.list_projects.return_value = []

        service = LangSmithService(api_key="test-key")
        result = service.list_projects()

        assert isinstance(result, list)
        assert len(result) == 0

    def test_list_projects_api_error(self, mock_langsmith_client):
        """Test that API errors are wrapped in LangSmithAPIError."""
        mock_langsmith_client.list_projects.side_effect = Exception("API error")

        service = LangSmithService(api_key="test-key")

        with pytest.raises(LangSmithAPIError) as exc_info:
            service.list_projects()

        assert "Failed to list projects" in str(exc_info.value)


class TestGetProjectStats:
    """Tests for LangSmithService.get_project_stats()."""

    def test_get_project_stats(self, mock_langsmith_client, mock_run_object):
        """Test that get_project_stats aggregates stats correctly."""
        # Create multiple mock runs for statistical aggregation
        mock_run_1 = MagicMock()
        mock_run_1.id = "run-1"
        mock_run_1.name = "run1"
        mock_run_1.run_type = "llm"
        mock_run_1.start_time = mock_run_object.start_time
        mock_run_1.end_time = mock_run_object.end_time
        mock_run_1.error = None
        mock_run_1.parent_run_id = None
        mock_run_1.session_id = None
        mock_run_1.tags = []
        mock_run_1.extra = {}
        mock_run_1.total_tokens = 100
        mock_run_1.prompt_tokens = 40
        mock_run_1.completion_tokens = 60
        mock_run_1.inputs = {}
        mock_run_1.outputs = {}

        mock_run_2 = MagicMock()
        mock_run_2.id = "run-2"
        mock_run_2.name = "run2"
        mock_run_2.run_type = "chain"
        mock_run_2.start_time = mock_run_object.start_time
        mock_run_2.end_time = mock_run_object.end_time
        mock_run_2.error = "Some error"
        mock_run_2.parent_run_id = None
        mock_run_2.session_id = None
        mock_run_2.tags = []
        mock_run_2.extra = {}
        mock_run_2.total_tokens = 50
        mock_run_2.prompt_tokens = 20
        mock_run_2.completion_tokens = 30
        mock_run_2.inputs = {}
        mock_run_2.outputs = {}

        mock_langsmith_client.list_runs.return_value = [mock_run_1, mock_run_2]

        service = LangSmithService(api_key="test-key")
        result = service.get_project_stats("my-project")

        assert result["project_name"] == "my-project"
        assert result["total_runs"] == 2
        assert result["error_count"] == 1
        assert result["error_rate"] == 50.0
        assert result["avg_latency"] == 2.0  # Both runs have 2 second latency
        assert result["total_tokens"] == 150
        assert result["run_types"]["llm"] == 1
        assert result["run_types"]["chain"] == 1

    def test_get_project_stats_no_runs(self, mock_langsmith_client):
        """Test stats calculation with no runs."""
        mock_langsmith_client.list_runs.return_value = []

        service = LangSmithService(api_key="test-key")
        result = service.get_project_stats("empty-project")

        assert result["total_runs"] == 0
        assert result["error_count"] == 0
        assert result["error_rate"] == 0
        assert result["avg_latency"] is None
        assert result["total_tokens"] == 0

    def test_get_project_stats_api_error(self, mock_langsmith_client):
        """Test that API errors are propagated."""
        mock_langsmith_client.list_runs.side_effect = Exception("API error")

        service = LangSmithService(api_key="test-key")

        with pytest.raises(LangSmithAPIError):
            service.get_project_stats("my-project")


class TestRunToDict:
    """Tests for the _run_to_dict conversion method."""

    def test_run_to_dict_success_status(self, mock_langsmith_client, mock_run_object):
        """Test that successful runs have status 'success'."""
        mock_langsmith_client.read_run.return_value = mock_run_object

        service = LangSmithService(api_key="test-key")
        result = service.get_run("run-id")

        assert result["status"] == "success"

    def test_run_to_dict_running_status(self, mock_langsmith_client, mock_run_object):
        """Test that runs without end_time have status 'running'."""
        mock_run_object.end_time = None
        mock_run_object.error = None
        mock_langsmith_client.read_run.return_value = mock_run_object

        service = LangSmithService(api_key="test-key")
        result = service.get_run("run-id")

        assert result["status"] == "running"
        assert result["latency"] is None

    def test_run_to_dict_error_status(
        self, mock_langsmith_client, mock_run_with_error_object
    ):
        """Test that runs with errors have status 'error'."""
        mock_langsmith_client.read_run.return_value = mock_run_with_error_object

        service = LangSmithService(api_key="test-key")
        result = service.get_run("run-id")

        assert result["status"] == "error"
        assert "ValueError" in result["error"]

    def test_run_to_dict_formats_times_as_iso(
        self, mock_langsmith_client, mock_run_object
    ):
        """Test that timestamps are formatted as ISO strings."""
        mock_langsmith_client.read_run.return_value = mock_run_object

        service = LangSmithService(api_key="test-key")
        result = service.get_run("run-id")

        assert "2024-01-15" in result["start_time"]
        assert "T" in result["start_time"]
