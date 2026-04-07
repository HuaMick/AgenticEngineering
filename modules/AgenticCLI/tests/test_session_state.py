"""Tests for session state helpers."""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-SES-006")

from agenticcli.utils.session_state import (
    mark_failed,
)


@pytest.mark.story("US-SES-006")
class TestMarkFailed:
    def test_basic(self):
        data = {"session_id": "abc", "status": "running"}
        mark_failed(data, error_code="timeout", detail="Timed out", retryable=True)
        assert data["status"] == "failed"
        assert data["exit_code"] == 1
        assert data["error_code"] == "timeout"
        assert data["failure_reason"]["retryable"] is True
        assert data["failure_reason"]["suggested_action"] == "retry"

    def test_non_retryable(self):
        data = {"session_id": "abc", "status": "running"}
        mark_failed(data, error_code="crash", retryable=False)
        assert data["failure_reason"]["suggested_action"] == "escalate"


@pytest.mark.story("US-SES-006")
class TestReadSdkMetrics:
    """Direct unit tests for the read_sdk_metrics() function."""

    def test_read_sdk_metrics_function_full_state(self):
        """read_sdk_metrics() returns all fields correctly from a complete state dict."""
        from agenticcli.utils.session_state import read_sdk_metrics

        full_state = {
            "session_id": "test-session-001",
            "cost_usd": 0.123,
            "duration_ms": 8750,
            "num_turns": 12,
            "usage": {"input_tokens": 3000, "output_tokens": 800},
            "sdk_session_id": "sdk-abc-001",
            "transport": "sdk-tmux",
        }

        with patch("agenticcli.utils.state_store.StateStore") as MockStore:
            mock_instance = MagicMock()
            mock_instance.load.return_value = full_state
            MockStore.return_value = mock_instance

            result = read_sdk_metrics("test-session-001")

        # Verify StateStore was constructed with correct args
        MockStore.assert_called_once_with("sessions", id_key="session_id")
        mock_instance.load.assert_called_once_with("test-session-001")

        # Verify all fields are returned correctly
        assert result["cost_usd"] == 0.123
        assert result["duration_ms"] == 8750
        assert result["num_turns"] == 12
        assert result["usage"] == {"input_tokens": 3000, "output_tokens": 800}
        assert result["sdk_session_id"] == "sdk-abc-001"
        assert result["transport"] == "sdk-tmux"

    def test_read_sdk_metrics_function_none_state(self):
        """read_sdk_metrics() returns safe defaults when session is not found."""
        from agenticcli.utils.session_state import read_sdk_metrics

        with patch("agenticcli.utils.state_store.StateStore") as MockStore:
            mock_instance = MagicMock()
            mock_instance.load.return_value = None
            MockStore.return_value = mock_instance

            result = read_sdk_metrics("missing-session")

        assert result["cost_usd"] == 0.0
        assert result["duration_ms"] == 0
        assert result["num_turns"] == 0
        assert result["usage"] == {}
        assert result["sdk_session_id"] == ""
        assert result["transport"] == "unknown"

    def test_read_sdk_metrics_function_zero_cost_is_preserved(self):
        """read_sdk_metrics() returns 0.0 cost from state (not confused with missing)."""
        from agenticcli.utils.session_state import read_sdk_metrics

        state_with_zero_cost = {
            "session_id": "zero-cost-session",
            "cost_usd": 0.0,
            "duration_ms": 500,
            "num_turns": 2,
            "usage": {},
            "sdk_session_id": "",
            "transport": "subprocess",
        }

        with patch("agenticcli.utils.state_store.StateStore") as MockStore:
            mock_instance = MagicMock()
            mock_instance.load.return_value = state_with_zero_cost
            MockStore.return_value = mock_instance

            result = read_sdk_metrics("zero-cost-session")

        # Explicit zero should be returned, not treated as missing
        assert result["cost_usd"] == 0.0
        assert result["duration_ms"] == 500
        assert result["num_turns"] == 2
        assert result["transport"] == "subprocess"
