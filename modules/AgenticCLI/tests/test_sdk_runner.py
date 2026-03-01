"""Tests for agenticcli.utils.sdk_runner.

Covers:
- Successful agent run -> SessionResult(status="completed")
- Agent error -> SessionResult(status="failed")
- SDK not installed -> fallback behavior
- Streaming messages passed to on_message callback
- Timeout fires and returns failed SessionResult (SDK_008)
- Missing ResultMessage returns failed (not completed) when output is empty (SDK_009)
- Empty result + no ResultMessage triggers stall detection failure (SDK_009)
- Genuine completion with text-only (no ResultMessage) still returns completed (SDK_009)
"""

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ── Fixtures: mock SDK message types ───────────────────────────────────

@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeAssistantMessage:
    role: str = "assistant"
    content: list = None

    def __post_init__(self):
        if self.content is None:
            self.content = [FakeTextBlock("Hello from agent")]


@dataclass
class FakeResultMessage:
    subtype: str = "result"
    duration_ms: int = 1500
    duration_api_ms: int = 1200
    is_error: bool = False
    num_turns: int = 3
    session_id: str = "test-session-123"
    total_cost_usd: float = 0.05
    usage: dict = None
    result: str = "Agent completed successfully"
    structured_output: Any = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = {"input_tokens": 100, "output_tokens": 50}


@dataclass
class FakeErrorResultMessage:
    subtype: str = "result"
    duration_ms: int = 500
    duration_api_ms: int = 400
    is_error: bool = True
    num_turns: int = 1
    session_id: str = "test-session-err"
    total_cost_usd: float = 0.01
    usage: dict = None
    result: str = "Error: something went wrong"
    structured_output: Any = None


# ── Helpers: async generator mocks ─────────────────────────────────────

async def _mock_query_success(**kwargs):
    yield FakeAssistantMessage()
    yield FakeResultMessage()


async def _mock_query_error(**kwargs):
    yield FakeErrorResultMessage()


async def _mock_query_exception(**kwargs):
    raise RuntimeError("Connection failed")
    yield  # noqa: unreachable


async def _mock_query_no_result(**kwargs):
    yield FakeAssistantMessage()


async def _mock_query_completely_empty(**kwargs):
    """Simulate a stream that drops immediately with no messages at all."""
    return
    yield  # noqa: unreachable — makes this an async generator


async def _mock_query_timeout(**kwargs):
    """Simulate a stream that never finishes (for timeout testing)."""
    await asyncio.sleep(9999)
    yield  # noqa: unreachable


def _run(coro):
    """Run an async coroutine synchronously for tests."""
    return asyncio.run(coro)


# ── Tests: run_agent (async, tested via asyncio.run) ───────────────────

class TestRunAgent:
    """Tests for the async run_agent function."""

    def test_successful_run(self):
        """Successful agent run returns completed SessionResult with metadata."""
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_success):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                result = _run(run_agent("test prompt"))

        assert result.status == "completed"
        assert result.result == "Agent completed successfully"
        assert result.cost_usd == 0.05
        assert result.session_id == "test-session-123"
        assert result.num_turns == 3
        assert result.is_error is False

    def test_error_result(self):
        """Agent error returns failed SessionResult."""
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_error):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                result = _run(run_agent("test prompt"))

        assert result.status == "failed"
        assert "Error" in result.result
        assert result.is_error is True

    def test_exception_during_query(self):
        """Exception during query() returns failed SessionResult."""
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_exception):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                result = _run(run_agent("test prompt"))

        assert result.status == "failed"
        assert "Connection failed" in result.result
        assert result.is_error is True
        assert result.duration_ms >= 0

    def test_sdk_not_available(self):
        """When SDK is not installed, returns failed with descriptive message."""
        with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", False):
            from agenticcli.utils.sdk_runner import run_agent
            result = _run(run_agent("test prompt"))

        assert result.status == "failed"
        assert "not installed" in result.result
        assert result.is_error is True

    def test_on_message_callback(self):
        """on_message callback is invoked for each streamed message."""
        messages_received = []

        with patch("agenticcli.utils.sdk_runner.query", _mock_query_success):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                _run(run_agent("test", on_message=messages_received.append))

        assert len(messages_received) == 2  # AssistantMessage + ResultMessage

    def test_no_result_message(self):
        """When no ResultMessage is yielded, still returns completed with collected text."""
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_no_result):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                result = _run(run_agent("test prompt"))

        assert result.status == "completed"
        assert "Hello from agent" in result.result

    def test_options_passed_through(self):
        """ClaudeAgentOptions are passed through to query()."""
        captured_kwargs = {}

        async def mock_query(**kwargs):
            captured_kwargs.update(kwargs)
            yield FakeResultMessage()

        with patch("agenticcli.utils.sdk_runner.query", mock_query):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                fake_options = MagicMock()
                _run(run_agent("my prompt", options=fake_options))

        assert captured_kwargs["prompt"] == "my prompt"
        assert captured_kwargs["options"] is fake_options


# ── Tests: run_agent_sync ──────────────────────────────────────────────

class TestRunAgentSync:
    """Tests for the synchronous run_agent_sync wrapper."""

    def test_sync_wrapper_success(self):
        """Sync wrapper delegates to async run_agent and returns result."""
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_success):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent_sync
                result = run_agent_sync("test prompt")

        assert result.status == "completed"
        assert result.session_id == "test-session-123"

    def test_sync_wrapper_sdk_unavailable(self):
        """Sync wrapper returns failed when SDK not available."""
        with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", False):
            from agenticcli.utils.sdk_runner import run_agent_sync
            result = run_agent_sync("test prompt")

        assert result.status == "failed"
        assert "not installed" in result.result


# ── Tests: SessionResult ───────────────────────────────────────────────

class TestSessionResult:
    """Tests for SessionResult dataclass."""

    def test_default_values(self):
        from agenticcli.utils.sdk_runner import SessionResult
        r = SessionResult(status="completed", result="done")
        assert r.cost_usd == 0.0
        assert r.duration_ms == 0
        assert r.session_id == ""
        assert r.num_turns == 0
        assert r.usage == {}
        assert r.is_error is False

    def test_all_fields(self):
        from agenticcli.utils.sdk_runner import SessionResult
        r = SessionResult(
            status="failed",
            result="error",
            cost_usd=1.5,
            duration_ms=5000,
            session_id="abc",
            num_turns=10,
            usage={"input_tokens": 500},
            is_error=True,
        )
        assert r.status == "failed"
        assert r.cost_usd == 1.5
        assert r.num_turns == 10


# ── Tests: SDK_008 — Timeout ───────────────────────────────────────────

class TestRunAgentTimeout:
    """Tests for timeout enforcement in run_agent() (SDK_008)."""

    def test_timeout_returns_failed_session_result(self):
        """asyncio.TimeoutError is caught and returns a failed SessionResult."""
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_timeout):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                result = _run(run_agent("test prompt", timeout_seconds=1))

        assert result.status == "failed"
        assert "timed out" in result.result.lower()
        assert result.is_error is True
        assert result.duration_ms >= 0

    def test_timeout_message_includes_duration(self):
        """Timeout message includes the configured timeout value."""
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_timeout):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                result = _run(run_agent("test prompt", timeout_seconds=42))

        assert "42s" in result.result

    def test_default_timeout_is_1800_seconds(self):
        """DEFAULT_TIMEOUT_SECONDS is 1800 (30 minutes)."""
        from agenticcli.utils.sdk_runner import DEFAULT_TIMEOUT_SECONDS
        assert DEFAULT_TIMEOUT_SECONDS == 1800

    def test_timeout_logged_at_warning_level(self, caplog):
        """Timeout event is logged at WARNING level."""
        import logging
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_timeout):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                with caplog.at_level(logging.WARNING, logger="agenticcli.utils.sdk_runner"):
                    _run(run_agent("test prompt", timeout_seconds=1))

        assert any("timed out" in r.message.lower() for r in caplog.records)
        assert any(r.levelname == "WARNING" for r in caplog.records)

    def test_timeout_disabled_when_zero(self):
        """timeout_seconds=0 disables the timeout (stream runs to completion)."""
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_success):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                result = _run(run_agent("test prompt", timeout_seconds=0))

        assert result.status == "completed"

    def test_sync_wrapper_passes_timeout(self):
        """run_agent_sync() forwards timeout_seconds to run_agent()."""
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_timeout):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent_sync
                result = run_agent_sync("test prompt", timeout_seconds=1)

        assert result.status == "failed"
        assert "timed out" in result.result.lower()


# ── Tests: SDK_009 — Stall Detection ──────────────────────────────────

class TestRunAgentStallDetection:
    """Tests for stall/empty-result detection in run_agent() (SDK_009)."""

    def test_missing_result_message_empty_output_returns_failed(self):
        """No ResultMessage AND no text output -> status='failed' (stall detected)."""
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_completely_empty):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                result = _run(run_agent("test prompt"))

        assert result.status == "failed"
        assert "No ResultMessage" in result.result or "stream may have dropped" in result.result
        assert result.is_error is True

    def test_missing_result_message_with_text_returns_completed(self):
        """No ResultMessage but some text was collected -> status='completed'.

        This is the graceful degradation case: partial output is accepted.
        """
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_no_result):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                result = _run(run_agent("test prompt"))

        assert result.status == "completed"
        assert "Hello from agent" in result.result

    def test_stall_detection_logged_at_warning(self, caplog):
        """Warning is logged when stall (empty output, no ResultMessage) detected."""
        import logging
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_completely_empty):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                with caplog.at_level(logging.WARNING, logger="agenticcli.utils.sdk_runner"):
                    _run(run_agent("test prompt"))

        assert any(
            "stall" in r.message.lower() or "no resultmessage" in r.message.lower()
            for r in caplog.records
        )

    def test_genuine_completion_still_returns_completed(self):
        """A real successful run with ResultMessage still returns status='completed'."""
        with patch("agenticcli.utils.sdk_runner.query", _mock_query_success):
            with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", True):
                from agenticcli.utils.sdk_runner import run_agent
                result = _run(run_agent("test prompt"))

        assert result.status == "completed"
        assert result.result == "Agent completed successfully"


# ── Tests: SDK_016 — Tool Allow-Lists ─────────────────────────────────

class TestRoleToolAllowlist:
    """Tests for role-based tool allow-lists (SDK_016)."""

    def test_known_role_returns_tool_list(self):
        """Known roles return non-empty tool lists."""
        from agenticcli.utils.sdk_runner import get_allowed_tools_for_role

        explore_tools = get_allowed_tools_for_role("explore")
        assert explore_tools is not None
        assert isinstance(explore_tools, list)
        assert len(explore_tools) > 0

    def test_explore_role_has_correct_tools(self):
        """explore role gets read-only tools plus Bash."""
        from agenticcli.utils.sdk_runner import get_allowed_tools_for_role

        tools = get_allowed_tools_for_role("explore")
        assert "Read" in tools
        assert "Glob" in tools
        assert "Grep" in tools
        assert "Bash" in tools
        # Should NOT have write tools
        assert "Edit" not in tools
        assert "Write" not in tools

    def test_build_python_role_has_write_tools(self):
        """build-python role gets full write access."""
        from agenticcli.utils.sdk_runner import get_allowed_tools_for_role

        tools = get_allowed_tools_for_role("build-python")
        assert "Edit" in tools
        assert "Write" in tools
        assert "Bash" in tools

    def test_reviewer_role_has_read_only_tools(self):
        """planner-reviewer gets read-only tools (no Write or Edit)."""
        from agenticcli.utils.sdk_runner import get_allowed_tools_for_role

        tools = get_allowed_tools_for_role("planner-reviewer")
        assert "Read" in tools
        assert "Edit" not in tools
        assert "Write" not in tools

    def test_unknown_role_returns_none(self):
        """Unknown role returns None (all tools allowed by default)."""
        from agenticcli.utils.sdk_runner import get_allowed_tools_for_role

        result = get_allowed_tools_for_role("some-unknown-role-xyz")
        assert result is None

    def test_none_role_returns_none(self):
        """None role (no role specified) returns None."""
        from agenticcli.utils.sdk_runner import get_allowed_tools_for_role

        result = get_allowed_tools_for_role(None)
        assert result is None

    def test_role_tool_allowlist_dict_exists(self):
        """ROLE_TOOL_ALLOWLIST constant is exported and non-empty."""
        from agenticcli.utils.sdk_runner import ROLE_TOOL_ALLOWLIST

        assert isinstance(ROLE_TOOL_ALLOWLIST, dict)
        assert len(ROLE_TOOL_ALLOWLIST) > 0

    def test_all_roles_have_list_values(self):
        """Every entry in ROLE_TOOL_ALLOWLIST is a list of strings."""
        from agenticcli.utils.sdk_runner import ROLE_TOOL_ALLOWLIST

        for role, tools in ROLE_TOOL_ALLOWLIST.items():
            assert isinstance(tools, list), f"Role {role!r} tools should be a list"
            for tool in tools:
                assert isinstance(tool, str), f"Tool {tool!r} for role {role!r} should be str"
