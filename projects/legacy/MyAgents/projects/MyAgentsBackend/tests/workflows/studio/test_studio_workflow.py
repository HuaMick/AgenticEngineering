"""Unit tests for StudioWorkflow.

Tests the Studio lifecycle management workflow functionality.
Following the Domain → Workflow → Entrypoint pattern.

Note: This file contains both unit tests for the StudioWorkflow class
and e2e tests for the Studio service endpoints.
"""

import os
import pytest
import requests  # type: ignore[import-untyped]
import subprocess
import time
from pathlib import Path
from unittest.mock import patch, MagicMock


from myagents.backend.services.agents.workflows.studio_workflow import (
    StudioWorkflow,
    start_studio,
    stop_studio,
    restart_studio,
    get_studio_status,
    get_studio_recent_errors
)


STUDIO_BASE_URL = "http://127.0.0.1:2024"
STUDIO_STARTUP_WAIT = 12  # Wait 12 seconds for service to fully initialize


def is_studio_running():
    """Check if Studio service is running via health endpoint."""
    try:
        response = requests.get(f"{STUDIO_BASE_URL}/ok", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def wait_for_studio(timeout=30):
    """Wait for Studio service to become available."""
    start = time.time()
    while time.time() - start < timeout:
        if is_studio_running():
            # Additional stability wait
            time.sleep(STUDIO_STARTUP_WAIT)
            return True
        time.sleep(1)
    return False


@pytest.fixture
def temp_home_config_dir(tmp_path):
    """Create a temporary home config directory with langgraph.json."""
    langgraph_json = tmp_path / "langgraph.json"
    langgraph_json.write_text("{}")
    return tmp_path


@pytest.fixture
def workflow(temp_home_config_dir):
    """Create a StudioWorkflow instance for testing."""
    return StudioWorkflow(home_config_dir=temp_home_config_dir)


# ============================================================================
# UNIT TESTS - StudioWorkflow methods
# ============================================================================

@pytest.mark.workflow_studio
class TestStudioWorkflowInitialization:
    """Test StudioWorkflow initialization."""

    def test_workflow_init_with_home_config_dir(self, temp_home_config_dir):
        """Test workflow initialization with home config directory."""
        workflow = StudioWorkflow(home_config_dir=temp_home_config_dir)

        assert workflow.home_config_dir == temp_home_config_dir
        assert workflow.config_path is None

    def test_workflow_init_with_config(self, temp_home_config_dir, tmp_path):
        """Test workflow initialization with config path."""
        config_path = tmp_path / "config.yml"
        workflow = StudioWorkflow(home_config_dir=temp_home_config_dir, config_path=config_path)

        assert workflow.home_config_dir == temp_home_config_dir
        assert workflow.config_path == config_path


@pytest.mark.workflow_studio
class TestStartStudio:
    """Test start_studio() method."""

    @pytest.mark.parametrize("expected_success,return_message,expected_text", [
        (True, "Studio started", "started"),
        (False, "Failed to start", "failed"),
    ])
    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_start_studio(self, mock_manager_class, workflow, expected_success, return_message, expected_text):
        """Test starting Studio with success and failure scenarios."""
        mock_manager = MagicMock()
        mock_manager.start.return_value = (expected_success, return_message)
        mock_manager_class.return_value = mock_manager

        success, message = workflow.start_studio()

        assert success is expected_success
        assert expected_text in message.lower()
        mock_manager.start.assert_called_once_with(background=True, port=None)

    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_start_studio_foreground(self, mock_manager_class, workflow):
        """Test starting Studio in foreground."""
        mock_manager = MagicMock()
        mock_manager.start.return_value = (True, "Studio started")
        mock_manager_class.return_value = mock_manager

        success, message = workflow.start_studio(background=False)

        assert success is True
        mock_manager.start.assert_called_once_with(background=False, port=None)

    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_start_studio_with_port(self, mock_manager_class, workflow):
        """Test starting Studio with custom port."""
        mock_manager = MagicMock()
        mock_manager.start.return_value = (True, "Studio started on port 3000")
        mock_manager_class.return_value = mock_manager

        success, message = workflow.start_studio(port=3000)

        assert success is True
        mock_manager.start.assert_called_once_with(background=True, port=3000)


@pytest.mark.workflow_studio
class TestStopStudio:
    """Test stop_studio() method."""

    @pytest.mark.parametrize("expected_success,return_message", [
        (True, "Studio stopped"),
        (False, "Failed to stop"),
    ])
    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_stop_studio(self, mock_manager_class, workflow, expected_success, return_message):
        """Test stopping Studio with success and failure scenarios."""
        mock_manager = MagicMock()
        mock_manager.stop.return_value = (expected_success, return_message)
        mock_manager_class.return_value = mock_manager

        success, message = workflow.stop_studio()

        assert success is expected_success
        mock_manager.stop.assert_called_once_with(force=False)

    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_stop_studio_force(self, mock_manager_class, workflow):
        """Test stopping Studio with force flag."""
        mock_manager = MagicMock()
        mock_manager.stop.return_value = (True, "Studio stopped (forced)")
        mock_manager_class.return_value = mock_manager

        success, message = workflow.stop_studio(force=True)

        assert success is True
        mock_manager.stop.assert_called_once_with(force=True)


@pytest.mark.workflow_studio
class TestRestartStudio:
    """Test restart_studio() method."""

    @pytest.mark.parametrize("expected_success,return_message", [
        (True, "Studio restarted"),
        (False, "Failed to restart"),
    ])
    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_restart_studio(self, mock_manager_class, workflow, expected_success, return_message):
        """Test restarting Studio with success and failure scenarios."""
        mock_manager = MagicMock()
        mock_manager.restart.return_value = (expected_success, return_message)
        mock_manager_class.return_value = mock_manager

        success, message = workflow.restart_studio()

        assert success is expected_success
        mock_manager.restart.assert_called_once()


@pytest.mark.workflow_studio
class TestGetStudioStatus:
    """Test get_studio_status() method."""

    @pytest.mark.parametrize("is_running,has_pid", [
        (True, True),
        (False, False),
    ])
    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_get_studio_status(self, mock_manager_class, workflow, is_running, has_pid):
        """Test getting status when Studio is running or stopped."""
        mock_manager = MagicMock()
        status_dict = {
            "running": is_running,
            "port": 2024,
            "host": "127.0.0.1",
            "url": "http://127.0.0.1:2024",
            "api_url": "http://127.0.0.1:2024"
        }
        if has_pid:
            status_dict["pid"] = 12345
        mock_manager.get_status.return_value = status_dict
        mock_manager_class.return_value = mock_manager

        status = workflow.get_studio_status()

        assert status["running"] is is_running
        assert status["port"] == 2024
        if has_pid:
            assert "pid" in status
        else:
            assert "port" in status


@pytest.mark.workflow_studio
class TestCheckStudioHealth:
    """Test check_studio_health() method."""

    @pytest.mark.parametrize("is_running,expected_healthy", [
        (True, True),
        (False, False),
    ])
    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_check_studio_health(self, mock_manager_class, workflow, is_running, expected_healthy):
        """Test health check when Studio is healthy or unhealthy."""
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": is_running,
            "port": 2024
        }
        mock_manager_class.return_value = mock_manager

        health = workflow.check_studio_health()

        assert health["healthy"] is expected_healthy
        assert health["running"] is is_running
        if is_running:
            assert health["responding"] is True


@pytest.mark.workflow_studio
class TestRecoverStudioState:
    """Test recover_studio_state() method."""

    @pytest.mark.parametrize("is_running,expected_text", [
        (True, "recovered"),
        (False, "not running"),
    ])
    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_recover_studio_state(self, mock_manager_class, workflow, is_running, expected_text):
        """Test state recovery when Studio is running or stopped."""
        mock_manager = MagicMock()
        mock_manager.is_running.return_value = is_running
        if is_running:
            mock_manager.get_status.return_value = {
                "port": 2024,
                "pid": 12345
            }
        mock_manager_class.return_value = mock_manager

        success, message = workflow.recover_studio_state()

        assert success is True
        assert expected_text in message.lower()


@pytest.mark.workflow_studio
class TestGetRecentErrors:
    """Test get_recent_errors() method."""

    @pytest.mark.parametrize("has_errors,return_value", [
        (True, "ERROR: Test error\nERROR: Another error"),
        (False, None),
    ])
    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_get_recent_errors(self, mock_manager_class, workflow, has_errors, return_value):
        """Test getting recent errors when errors exist or log doesn't exist."""
        mock_manager = MagicMock()
        mock_manager.get_recent_errors.return_value = return_value
        mock_manager_class.return_value = mock_manager

        errors = workflow.get_recent_errors(num_lines=20) if has_errors else workflow.get_recent_errors()

        if has_errors:
            assert errors is not None
            assert "ERROR" in errors
        else:
            assert errors is None


@pytest.mark.workflow_studio
class TestBackwardCompatibleFunctions:
    """Test backward-compatible function-based API."""

    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_function_start_studio(self, mock_manager_class, temp_home_config_dir):
        """Test backward-compatible start_studio function."""
        mock_manager = MagicMock()
        mock_manager.start.return_value = (True, "Started")
        mock_manager_class.return_value = mock_manager

        success, message = start_studio(home_config_dir=temp_home_config_dir)

        assert success is True

    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_function_stop_studio(self, mock_manager_class, temp_home_config_dir):
        """Test backward-compatible stop_studio function."""
        mock_manager = MagicMock()
        mock_manager.stop.return_value = (True, "Stopped")
        mock_manager_class.return_value = mock_manager

        success, message = stop_studio(home_config_dir=temp_home_config_dir)

        assert success is True

    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_function_restart_studio(self, mock_manager_class, temp_home_config_dir):
        """Test backward-compatible restart_studio function."""
        mock_manager = MagicMock()
        mock_manager.restart.return_value = (True, "Restarted")
        mock_manager_class.return_value = mock_manager

        success, message = restart_studio(home_config_dir=temp_home_config_dir)

        assert success is True

    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_function_get_studio_status(self, mock_manager_class, temp_home_config_dir):
        """Test backward-compatible get_studio_status function."""
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {"running": True, "port": 2024}
        mock_manager_class.return_value = mock_manager

        status = get_studio_status(home_config_dir=temp_home_config_dir)

        assert status["running"] is True

    @patch('myagents.backend.services.studio.domains.studio_manager.manager.StudioManager')
    def test_function_get_studio_recent_errors(self, mock_manager_class, temp_home_config_dir):
        """Test backward-compatible get_studio_recent_errors function."""
        mock_manager = MagicMock()
        mock_manager.get_recent_errors.return_value = "ERROR: test"
        mock_manager_class.return_value = mock_manager

        errors = get_studio_recent_errors(home_config_dir=temp_home_config_dir, num_lines=20)

        assert "ERROR" in errors


# ============================================================================
# E2E TESTS - Studio Service Endpoints
# ============================================================================

@pytest.fixture(scope="module")
def studio_service():
    """Start Studio service for all tests and ensure it's running."""

    # Use the actual project home config directory
    # Go up 3 levels from tests/workflows/infrastructure/test_studio_workflow.py
    home_config_dir = Path(__file__).parents[3]

    # Start Studio if not already running
    if not is_studio_running():
        workflow = StudioWorkflow(home_config_dir=home_config_dir)
        success, message = workflow.start_studio(background=True)
        assert success, f"Failed to start Studio service: {message}"

    # Wait for stable startup - fail test if it doesn't stabilize
    stabilized = wait_for_studio()
    assert stabilized, "Studio service failed to stabilize within timeout"

    yield
    # No teardown - leave service running


@pytest.mark.workflow_studio
@pytest.mark.e2e
def test_studio_health_endpoint(studio_service):
    """Test that /ok endpoint returns 200 with correct JSON after langgraph upgrade."""
    response = requests.get(f"{STUDIO_BASE_URL}/ok", timeout=5)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "ok" in data, "Response should contain 'ok' key"
    assert data["ok"] is True, "Health check should return ok: true"


@pytest.mark.workflow_studio
@pytest.mark.e2e
def test_studio_assistants_search(studio_service):
    """Test that /assistants/search endpoint returns valid JSON array after upgrade."""
    response = requests.post(
        f"{STUDIO_BASE_URL}/assistants/search",
        json={},
        timeout=5
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert isinstance(data, list), "Response should be JSON array"
    assert len(data) > 0, "Should have at least one assistant"

    # Validate first assistant has expected structure
    first_assistant = data[0]
    assert "assistant_id" in first_assistant or "id" in first_assistant, \
        "Assistant should have id field"


@pytest.mark.workflow_studio
@pytest.mark.e2e
def test_studio_assistants_get(studio_service):
    """Test that /assistants/{uuid} endpoint returns specific assistant details."""
    # First get list of assistants to get a valid ID
    search_response = requests.post(
        f"{STUDIO_BASE_URL}/assistants/search",
        json={},
        timeout=5
    )
    assert search_response.status_code == 200
    assistants = search_response.json()
    assert len(assistants) > 0, "Need at least one assistant for test"

    # Extract assistant ID (handle different possible field names)
    assistant_id = assistants[0].get("assistant_id") or assistants[0].get("id")
    assert assistant_id, "Assistant must have an ID"

    # Get specific assistant
    response = requests.get(
        f"{STUDIO_BASE_URL}/assistants/{assistant_id}",
        timeout=5
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data is not None, "Should return assistant data"


@pytest.mark.workflow_studio
@pytest.mark.e2e
def test_studio_threads_create(studio_service):
    """Test that POST /threads endpoint creates thread and returns thread_id."""
    response = requests.post(
        f"{STUDIO_BASE_URL}/threads",
        json={},
        timeout=5
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "thread_id" in data, "Response should contain thread_id"
    assert data["thread_id"], "thread_id should not be empty"


@pytest.mark.workflow_studio
@pytest.mark.e2e
def test_studio_threads_get(studio_service):
    """Test that GET /threads/{thread_id} endpoint returns thread details."""
    # First create a thread
    create_response = requests.post(
        f"{STUDIO_BASE_URL}/threads",
        json={},
        timeout=5
    )
    assert create_response.status_code == 200
    thread_id = create_response.json()["thread_id"]

    # Get thread details
    response = requests.get(
        f"{STUDIO_BASE_URL}/threads/{thread_id}",
        timeout=5
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data is not None, "Should return thread data"


@pytest.mark.workflow_studio
@pytest.mark.e2e
def test_studio_delayed_validation(studio_service):
    """Validate service stability after 10+ second delay and verify endpoints still respond."""
    # Service already waited during fixture, but add additional delay
    time.sleep(10)

    # Verify service still running via health check
    health_response = requests.get(f"{STUDIO_BASE_URL}/ok", timeout=5)
    assert health_response.status_code == 200, "Service should still respond after delay"

    # Verify functional endpoint still works
    search_response = requests.post(
        f"{STUDIO_BASE_URL}/assistants/search",
        json={},
        timeout=5
    )
    assert search_response.status_code == 200, \
        "Assistants search should still work after delayed validation"


@pytest.mark.workflow_studio
@pytest.mark.e2e
def test_studio_stability_under_load(studio_service):
    """Test service stability with 10 rapid sequential requests."""
    results = []

    for i in range(10):
        try:
            response = requests.post(
                f"{STUDIO_BASE_URL}/assistants/search",
                json={},
                timeout=5
            )
            results.append({
                "request": i + 1,
                "status": response.status_code,
                "success": response.status_code == 200
            })
        except requests.RequestException as e:
            results.append({
                "request": i + 1,
                "status": None,
                "success": False,
                "error": str(e)
            })

    # Verify all requests succeeded
    successful = [r for r in results if r["success"]]
    assert len(successful) == 10, \
        f"Only {len(successful)}/10 requests succeeded. Results: {results}"


@pytest.mark.workflow_studio
@pytest.mark.e2e
def test_studio_invalid_assistant_id(studio_service):
    """Test that invalid assistant ID returns 404, not crash."""
    response = requests.get(
        f"{STUDIO_BASE_URL}/assistants/invalid-uuid-12345",
        timeout=5
    )

    # Should return 404 or 422, not 500 (server error)
    assert response.status_code in [404, 422], \
        f"Expected 404 or 422 for invalid ID, got {response.status_code}"
