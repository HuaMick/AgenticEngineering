"""Pytest fixtures for AgenticLangSmith tests."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


@pytest.fixture
def mock_langsmith_client():
    """Create a mocked langsmith.Client instance.

    Returns a MagicMock configured to simulate the langsmith Client behavior.
    The mock patches the Client class so LangSmithService can be instantiated
    without making real API calls.
    """
    with patch("agenticlangsmith.service.Client") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_run_data() -> dict[str, Any]:
    """Create sample run response data.

    Returns a dictionary representing a typical LangSmith run response
    with all common fields populated.
    """
    run_id = str(uuid4())
    session_id = str(uuid4())
    start_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2024, 1, 15, 10, 0, 2, tzinfo=timezone.utc)

    return {
        "id": run_id,
        "name": "ChatOpenAI",
        "run_type": "llm",
        "start_time": start_time,
        "end_time": end_time,
        "inputs": {"messages": [{"role": "user", "content": "Hello"}]},
        "outputs": {"generations": [[{"text": "Hi there!"}]]},
        "error": None,
        "parent_run_id": None,
        "session_id": session_id,
        "tags": ["production", "chat"],
        "extra": {"metadata": {"model": "gpt-4"}},
        "total_tokens": 150,
        "prompt_tokens": 50,
        "completion_tokens": 100,
    }


@pytest.fixture
def sample_run_with_error() -> dict[str, Any]:
    """Create sample run data with an error.

    Returns a dictionary representing a failed LangSmith run.
    """
    run_id = str(uuid4())
    session_id = str(uuid4())
    start_time = datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2024, 1, 15, 11, 0, 1, tzinfo=timezone.utc)

    return {
        "id": run_id,
        "name": "FailingChain",
        "run_type": "chain",
        "start_time": start_time,
        "end_time": end_time,
        "inputs": {"query": "test query"},
        "outputs": None,
        "error": "ValueError: Invalid input format",
        "parent_run_id": None,
        "session_id": session_id,
        "tags": ["debug"],
        "extra": {},
        "total_tokens": None,
        "prompt_tokens": None,
        "completion_tokens": None,
    }


@pytest.fixture
def sample_project_data() -> dict[str, Any]:
    """Create sample project response data.

    Returns a dictionary representing a typical LangSmith project response.
    """
    project_id = str(uuid4())
    created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    return {
        "id": project_id,
        "name": "my-project",
        "description": "A sample LangSmith project for testing",
        "created_at": created_at,
        "run_count": 500,
        "extra": {"environment": "development"},
    }


@pytest.fixture
def mock_run_object(sample_run_data):
    """Create a mock Run object from sample_run_data.

    Returns a MagicMock configured to look like a langsmith.schemas.Run instance.
    """
    mock_run = MagicMock()
    mock_run.id = sample_run_data["id"]
    mock_run.name = sample_run_data["name"]
    mock_run.run_type = sample_run_data["run_type"]
    mock_run.start_time = sample_run_data["start_time"]
    mock_run.end_time = sample_run_data["end_time"]
    mock_run.inputs = sample_run_data["inputs"]
    mock_run.outputs = sample_run_data["outputs"]
    mock_run.error = sample_run_data["error"]
    mock_run.parent_run_id = sample_run_data["parent_run_id"]
    mock_run.session_id = sample_run_data["session_id"]
    mock_run.tags = sample_run_data["tags"]
    mock_run.extra = sample_run_data["extra"]
    mock_run.total_tokens = sample_run_data["total_tokens"]
    mock_run.prompt_tokens = sample_run_data["prompt_tokens"]
    mock_run.completion_tokens = sample_run_data["completion_tokens"]
    return mock_run


@pytest.fixture
def mock_run_with_error_object(sample_run_with_error):
    """Create a mock Run object from sample_run_with_error.

    Returns a MagicMock configured to look like a failed langsmith.schemas.Run instance.
    """
    mock_run = MagicMock()
    mock_run.id = sample_run_with_error["id"]
    mock_run.name = sample_run_with_error["name"]
    mock_run.run_type = sample_run_with_error["run_type"]
    mock_run.start_time = sample_run_with_error["start_time"]
    mock_run.end_time = sample_run_with_error["end_time"]
    mock_run.inputs = sample_run_with_error["inputs"]
    mock_run.outputs = sample_run_with_error["outputs"]
    mock_run.error = sample_run_with_error["error"]
    mock_run.parent_run_id = sample_run_with_error["parent_run_id"]
    mock_run.session_id = sample_run_with_error["session_id"]
    mock_run.tags = sample_run_with_error["tags"]
    mock_run.extra = sample_run_with_error["extra"]
    mock_run.total_tokens = sample_run_with_error["total_tokens"]
    mock_run.prompt_tokens = sample_run_with_error["prompt_tokens"]
    mock_run.completion_tokens = sample_run_with_error["completion_tokens"]
    return mock_run


@pytest.fixture
def mock_project_object(sample_project_data):
    """Create a mock TracerSession/Project object from sample_project_data.

    Returns a MagicMock configured to look like a langsmith project instance.
    """
    mock_project = MagicMock()
    mock_project.id = sample_project_data["id"]
    mock_project.name = sample_project_data["name"]
    mock_project.description = sample_project_data["description"]
    mock_project.created_at = sample_project_data["created_at"]
    mock_project.run_count = sample_project_data["run_count"]
    mock_project.extra = sample_project_data["extra"]
    return mock_project
