"""Tests for agenticcli.utils.session_diagnostics."""

import json

import pytest

pytestmark = pytest.mark.story("US-SES-001")

from agenticcli.utils.session_diagnostics import (
    ErrorType,
    SessionDiagnosis,
    SuggestedAction,
    diagnose_session_log,
    diagnose_session_state,
    failure_summary,
)


# ---------------------------------------------------------------------------
# diagnose_session_log — pattern matching
# ---------------------------------------------------------------------------


def test_diagnose_nested_session(tmp_path):
    log = tmp_path / "session.log"
    log.write_text(
        "Error: Claude Code cannot be launched inside another Claude Code session.\n"
    )

    result = diagnose_session_log(log)

    assert result.error_type == ErrorType.NESTED_SESSION
    assert result.suggested_action == SuggestedAction.RETRY_CLEAN_ENV
    assert result.retryable is True
    assert result.matched_pattern != ""


def test_diagnose_nested_session_alternate_phrase(tmp_path):
    log = tmp_path / "session.log"
    log.write_text(
        "Fatal: cannot be launched inside another process.\n"
    )

    result = diagnose_session_log(log)

    assert result.error_type == ErrorType.NESTED_SESSION
    assert result.suggested_action == SuggestedAction.RETRY_CLEAN_ENV
    assert result.retryable is True


def test_diagnose_max_turns_exceeded(tmp_path):
    log = tmp_path / "session.log"
    log.write_text("Session ended: max turns exceeded after 50 iterations.\n")

    result = diagnose_session_log(log)

    assert result.error_type == ErrorType.MAX_TURNS_EXCEEDED
    assert result.suggested_action == SuggestedAction.INCREASE_TURNS
    assert result.retryable is False
    assert result.matched_pattern != ""


def test_diagnose_max_turns_exceeded_alternate_phrase(tmp_path):
    log = tmp_path / "session.log"
    log.write_text("Maximum number of turns reached — stopping.\n")

    result = diagnose_session_log(log)

    assert result.error_type == ErrorType.MAX_TURNS_EXCEEDED
    assert result.suggested_action == SuggestedAction.INCREASE_TURNS
    assert result.retryable is False


def test_diagnose_permission_denied(tmp_path):
    log = tmp_path / "session.log"
    log.write_text("bash: /var/run/agent.sock: permission denied\n")

    result = diagnose_session_log(log)

    assert result.error_type == ErrorType.PERMISSION_DENIED
    assert result.suggested_action == SuggestedAction.CHECK_PERMISSIONS
    assert result.retryable is False
    assert result.matched_pattern != ""


def test_diagnose_permission_denied_eacces(tmp_path):
    log = tmp_path / "session.log"
    log.write_text("EACCES: cannot open /etc/private\n")

    result = diagnose_session_log(log)

    assert result.error_type == ErrorType.PERMISSION_DENIED
    assert result.suggested_action == SuggestedAction.CHECK_PERMISSIONS
    assert result.retryable is False


def test_diagnose_api_key_missing(tmp_path):
    log = tmp_path / "session.log"
    log.write_text("Error: API key not set. Please configure your key.\n")

    result = diagnose_session_log(log)

    assert result.error_type == ErrorType.API_KEY_MISSING
    assert result.suggested_action == SuggestedAction.CHECK_API_KEY
    assert result.retryable is False
    assert result.matched_pattern != ""


def test_diagnose_api_key_missing_env_var(tmp_path):
    log = tmp_path / "session.log"
    log.write_text("ANTHROPIC_API_KEY is not set in the environment.\n")

    result = diagnose_session_log(log)

    assert result.error_type == ErrorType.API_KEY_MISSING
    assert result.suggested_action == SuggestedAction.CHECK_API_KEY
    assert result.retryable is False


def test_diagnose_rate_limit(tmp_path):
    log = tmp_path / "session.log"
    log.write_text("Upstream returned rate limit error, backing off.\n")

    result = diagnose_session_log(log)

    assert result.error_type == ErrorType.RATE_LIMIT
    assert result.suggested_action == SuggestedAction.WAIT_AND_RETRY
    assert result.retryable is True
    assert result.matched_pattern != ""


def test_diagnose_rate_limit_429(tmp_path):
    log = tmp_path / "session.log"
    log.write_text("HTTP 429 Too Many Requests from api.anthropic.com\n")

    result = diagnose_session_log(log)

    assert result.error_type == ErrorType.RATE_LIMIT
    assert result.suggested_action == SuggestedAction.WAIT_AND_RETRY
    assert result.retryable is True


def test_diagnose_unknown_error(tmp_path):
    log = tmp_path / "session.log"
    log.write_text("Something went terribly wrong — segmentation fault\n")

    result = diagnose_session_log(log)

    assert result.error_type == ErrorType.UNKNOWN
    assert result.suggested_action == SuggestedAction.ESCALATE
    assert result.retryable is False
    assert "No known error pattern detected" in result.detail


# ---------------------------------------------------------------------------
# diagnose_session_log — edge cases
# ---------------------------------------------------------------------------


def test_diagnose_empty_log(tmp_path):
    log = tmp_path / "empty.log"
    log.write_text("")

    result = diagnose_session_log(log)

    assert result.error_type == ErrorType.UNKNOWN
    assert result.suggested_action == SuggestedAction.ESCALATE
    assert "empty" in result.detail.lower() or "failed to start" in result.detail.lower()
    # Empty logs are treated as retryable (env issue)
    assert result.retryable is True


def test_diagnose_missing_log_file(tmp_path):
    missing = tmp_path / "does_not_exist.log"

    result = diagnose_session_log(missing)

    assert result.error_type == ErrorType.UNKNOWN
    assert result.retryable is True


def test_diagnose_stderr_path_used(tmp_path):
    stdout_log = tmp_path / "stdout.log"
    stdout_log.write_text("Everything looks fine here.\n")
    stderr_log = tmp_path / "stderr.log"
    stderr_log.write_text("Error: API key not found.\n")

    result = diagnose_session_log(stdout_log, stderr_path=stderr_log)

    assert result.error_type == ErrorType.API_KEY_MISSING


def test_diagnose_detail_contains_context(tmp_path):
    log = tmp_path / "session.log"
    log.write_text("prefix text " + "rate limit" + " suffix text\n")

    result = diagnose_session_log(log)

    assert result.error_type == ErrorType.RATE_LIMIT
    # detail should include surrounding context
    assert "rate limit" in result.detail.lower()


# ---------------------------------------------------------------------------
# diagnose_session_state
# ---------------------------------------------------------------------------


def test_diagnose_session_state_failed(tmp_path):
    log = tmp_path / "stdout.log"
    log.write_text("Session ended: max turns exceeded\n")

    state = {
        "status": "failed",
        "stdout_log": str(log),
        "stderr_log": None,
    }

    result = diagnose_session_state(state)

    assert result is not None
    assert result.error_type == ErrorType.MAX_TURNS_EXCEEDED


def test_diagnose_session_state_completed(tmp_path):
    log = tmp_path / "stdout.log"
    log.write_text("Session completed successfully.\n")

    state = {
        "status": "completed",
        "stdout_log": str(log),
    }

    result = diagnose_session_state(state)

    # A completed session with no error pattern still produces a diagnosis
    assert result is not None
    assert result.error_type == ErrorType.UNKNOWN


def test_diagnose_session_state_no_logs():
    state = {"status": "failed"}

    result = diagnose_session_state(state)

    assert result is None


def test_diagnose_session_state_stderr_only(tmp_path):
    stderr_log = tmp_path / "stderr.log"
    stderr_log.write_text("permission denied: /run/agent\n")

    state = {
        "status": "failed",
        "stdout_log": None,
        "stderr_log": str(stderr_log),
    }

    result = diagnose_session_state(state)

    assert result is not None
    assert result.error_type == ErrorType.PERMISSION_DENIED


# ---------------------------------------------------------------------------
# failure_summary
# ---------------------------------------------------------------------------


def test_failure_summary_output():
    diagnosis = SessionDiagnosis(
        error_type=ErrorType.NESTED_SESSION,
        suggested_action=SuggestedAction.RETRY_CLEAN_ENV,
        detail="Claude Code cannot be launched inside another Claude Code session.",
        retryable=True,
        matched_pattern="cannot be launched inside another",
    )

    summary = failure_summary(diagnosis)

    # Must be JSON-serializable
    serialized = json.dumps(summary)
    reloaded = json.loads(serialized)

    assert reloaded["error_code"] == "nested_session"
    assert reloaded["error_type"] == "nested_session"
    assert reloaded["suggested_action"] == "retry_clean_env"
    assert reloaded["retryable"] is True
    assert "matched_pattern" in reloaded
    assert "detail" in reloaded


def test_failure_summary_detail_bounded():
    long_detail = "x" * 1000
    diagnosis = SessionDiagnosis(
        error_type=ErrorType.UNKNOWN,
        suggested_action=SuggestedAction.ESCALATE,
        detail=long_detail,
        retryable=False,
    )

    summary = failure_summary(diagnosis)

    assert len(summary["detail"]) <= 500


def test_failure_summary_all_error_types():
    for error_type in ErrorType:
        diagnosis = SessionDiagnosis(
            error_type=error_type,
            suggested_action=SuggestedAction.ESCALATE,
            detail="test",
            retryable=False,
        )
        summary = failure_summary(diagnosis)
        assert summary["error_code"] == error_type.value
        # Always JSON-serializable
        json.dumps(summary)


# ---------------------------------------------------------------------------
# Large log file (64 KB tail reading)
# ---------------------------------------------------------------------------


def test_large_log_file(tmp_path):
    log = tmp_path / "large.log"
    # Write 128 KB: first half is noise, second half has the error pattern
    noise = "a" * (64 * 1024)
    tail_content = "\nrate limit exceeded — please slow down\n"
    log.write_bytes((noise + tail_content).encode("utf-8"))

    result = diagnose_session_log(log)

    # The error pattern is in the tail, should be detected via seek
    assert result.error_type == ErrorType.RATE_LIMIT


def test_large_log_file_error_in_head_only(tmp_path):
    log = tmp_path / "large_head_error.log"
    # Error pattern only in the first 64 KB, buried under padding
    head_content = "max turns exceeded\n"
    padding = "b" * (128 * 1024)
    log.write_bytes((head_content + padding).encode("utf-8"))

    result = diagnose_session_log(log)

    # Tail reading means the head-only error is NOT seen — UNKNOWN is expected
    assert result.error_type == ErrorType.UNKNOWN


# ---------------------------------------------------------------------------
# Unicode / invalid bytes
# ---------------------------------------------------------------------------


def test_unicode_error_handling(tmp_path):
    log = tmp_path / "unicode.log"
    # Write valid UTF-8 followed by invalid bytes then the error pattern
    content = b"Some output\xff\xfe invalid bytes\nrate limit hit\n"
    log.write_bytes(content)

    result = diagnose_session_log(log)

    # Should not raise; errors="replace" handles bad bytes
    assert result.error_type == ErrorType.RATE_LIMIT


def test_unicode_error_all_invalid_bytes(tmp_path):
    log = tmp_path / "garbage.log"
    log.write_bytes(b"\xff\xfe\x00\x01" * 100)

    result = diagnose_session_log(log)

    # Should not raise regardless of content
    assert isinstance(result, SessionDiagnosis)


# ---------------------------------------------------------------------------
# FIX-001: pane log fallback for sdk-tmux sessions
# ---------------------------------------------------------------------------


def test_diagnose_session_state_pane_log_fallback_via_pane_log_path(tmp_path, monkeypatch):
    """diagnose_session_state uses pane_log_path when stdout_log/stderr_log absent."""
    pane_log = tmp_path / "fake-session-id.pane.log"
    pane_log.write_text("ResultMessage(is_error=True, duration_ms=123)\n")

    state = {
        "session_id": "fake-session-id",
        "status": "failed",
        "transport": "sdk-tmux",
        "pane_log_path": str(pane_log),
        # intentionally no stdout_log / stderr_log
    }

    result = diagnose_session_state(state)

    assert result is not None
    assert result.retryable is False
    assert result.error_type == ErrorType.SDK_ERROR


def test_diagnose_session_state_pane_log_fallback_via_session_id(tmp_path, monkeypatch):
    """diagnose_session_state derives pane log path from session_id when pane_log_path absent."""
    session_id = "test-sess-001"
    logs_dir = tmp_path / ".agentic" / "sessions" / "logs"
    logs_dir.mkdir(parents=True)
    pane_log = logs_dir / f"{session_id}.pane.log"
    pane_log.write_text("sdk_error: exit code 1\n")

    monkeypatch.setattr(
        "agenticcli.utils.sdk_pane_runner.pane_log_path_for",
        lambda sid: logs_dir / f"{sid}.pane.log",
    )

    state = {
        "session_id": session_id,
        "status": "failed",
        "transport": "sdk-tmux",
        # no pane_log_path, no stdout_log, no stderr_log
    }

    result = diagnose_session_state(state)

    assert result is not None
    assert result.retryable is False
    assert result.error_type == ErrorType.SDK_ERROR


def test_diagnose_session_state_no_logs_no_pane_log():
    """diagnose_session_state returns None when no log paths available at all."""
    state = {"session_id": "nonexistent-session", "status": "failed", "transport": "sdk-tmux"}

    result = diagnose_session_state(state)

    # pane log file does not exist, so result should be None
    assert result is None


def test_diagnose_quick_exit_uses_pane_log(tmp_path, monkeypatch):
    """diagnose_quick_exit returns non-retryable Diagnosis from pane log content."""
    import json as _json
    session_id = "qe-test-sess-002"
    state_dir = tmp_path / ".agentic" / "sessions"
    state_dir.mkdir(parents=True)
    logs_dir = state_dir / "logs"
    logs_dir.mkdir(parents=True)

    pane_log = logs_dir / f"{session_id}.pane.log"
    pane_log.write_text("Command failed with exit code 1\nsdk_error: something went wrong\n")

    state_data = {
        "session_id": session_id,
        "status": "failed",
        "transport": "sdk-tmux",
        "pane_log_path": str(pane_log),
    }

    class _FakeStore:
        def load(self, sid):
            if sid == session_id:
                return state_data
            return None
        def save(self, data):
            pass

    monkeypatch.setattr("agenticcli.utils.state_store.StateStore", lambda *a, **kw: _FakeStore())

    from agenticcli.utils.session_diagnostics import diagnose_quick_exit
    result = diagnose_quick_exit(session_id)

    assert result is not None
    assert result.retryable is False
    assert result.error_type == ErrorType.SDK_ERROR
