"""Session diagnostics: parse session logs for known error patterns.

Provides structured diagnosis when a session exits unexpectedly, enabling
automatic retry decisions in the orchestration layer (260308FX P3_002).

Also provides ``failure_summary()`` for persisting structured failure data
into session state records (260308FX P6_001/P6_003).
"""

import logging
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ErrorType(str, Enum):
    """Known error patterns that can be detected from session logs."""

    NESTED_SESSION = "nested_session"
    MAX_TURNS_EXCEEDED = "max_turns_exceeded"
    PERMISSION_DENIED = "permission_denied"
    API_KEY_MISSING = "api_key_missing"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"


class SuggestedAction(str, Enum):
    """Suggested remediation actions based on diagnosis."""

    RETRY_TMUX = "retry_tmux"          # Retry with --tmux
    RETRY_CLEAN_ENV = "retry_clean_env"  # Retry after cleaning env
    INCREASE_TURNS = "increase_turns"   # Increase --max-turns
    CHECK_PERMISSIONS = "check_permissions"  # Operator must fix permissions
    CHECK_API_KEY = "check_api_key"     # Operator must set API key
    WAIT_AND_RETRY = "wait_and_retry"   # Rate limited, wait then retry
    ESCALATE = "escalate"               # Unknown issue, needs human


@dataclass
class SessionDiagnosis:
    """Structured diagnosis of a session failure."""

    error_type: ErrorType
    suggested_action: SuggestedAction
    detail: str
    retryable: bool
    matched_pattern: str = ""


# Pattern definitions: (substring_to_match, error_type, suggested_action, retryable)
_ERROR_PATTERNS: list[tuple[str, ErrorType, SuggestedAction, bool]] = [
    (
        "cannot be launched inside another",
        ErrorType.NESTED_SESSION,
        SuggestedAction.RETRY_CLEAN_ENV,
        True,
    ),
    (
        "Claude Code cannot be launched inside",
        ErrorType.NESTED_SESSION,
        SuggestedAction.RETRY_CLEAN_ENV,
        True,
    ),
    (
        "max turns exceeded",
        ErrorType.MAX_TURNS_EXCEEDED,
        SuggestedAction.INCREASE_TURNS,
        False,
    ),
    (
        "Maximum number of turns",
        ErrorType.MAX_TURNS_EXCEEDED,
        SuggestedAction.INCREASE_TURNS,
        False,
    ),
    (
        "permission denied",
        ErrorType.PERMISSION_DENIED,
        SuggestedAction.CHECK_PERMISSIONS,
        False,
    ),
    (
        "EACCES",
        ErrorType.PERMISSION_DENIED,
        SuggestedAction.CHECK_PERMISSIONS,
        False,
    ),
    (
        "API key",
        ErrorType.API_KEY_MISSING,
        SuggestedAction.CHECK_API_KEY,
        False,
    ),
    (
        "ANTHROPIC_API_KEY",
        ErrorType.API_KEY_MISSING,
        SuggestedAction.CHECK_API_KEY,
        False,
    ),
    (
        "rate limit",
        ErrorType.RATE_LIMIT,
        SuggestedAction.WAIT_AND_RETRY,
        True,
    ),
    (
        "429",
        ErrorType.RATE_LIMIT,
        SuggestedAction.WAIT_AND_RETRY,
        True,
    ),
]

# Maximum bytes to read from log files for pattern matching.
# Keeps memory usage bounded even for very large log files.
_MAX_LOG_BYTES = 64 * 1024  # 64 KB


def diagnose_session_log(
    log_path: str | Path,
    stderr_path: Optional[str | Path] = None,
) -> SessionDiagnosis:
    """Parse session log file(s) for known error patterns.

    Reads both stdout and stderr log files (if provided) and checks
    for known error patterns. Returns a structured diagnosis.

    Args:
        log_path: Path to the stdout log file.
        stderr_path: Optional path to the stderr log file.

    Returns:
        SessionDiagnosis with error_type, suggested_action, and details.
    """
    log_content = _read_log_safely(log_path)
    stderr_content = _read_log_safely(stderr_path) if stderr_path else ""

    combined = f"{log_content}\n{stderr_content}"

    if not combined.strip():
        return SessionDiagnosis(
            error_type=ErrorType.UNKNOWN,
            suggested_action=SuggestedAction.ESCALATE,
            detail="Session logs are empty — agent may have failed to start",
            retryable=True,  # Empty logs often mean env issue, worth retrying
        )

    # Check each pattern
    combined_lower = combined.lower()
    for pattern, error_type, action, retryable in _ERROR_PATTERNS:
        if pattern.lower() in combined_lower:
            # Extract context around the match
            idx = combined_lower.index(pattern.lower())
            start = max(0, idx - 100)
            end = min(len(combined), idx + len(pattern) + 200)
            context = combined[start:end].strip()

            logger.info(
                "Session diagnosis: %s (pattern: %r)",
                error_type.value, pattern,
            )

            return SessionDiagnosis(
                error_type=error_type,
                suggested_action=action,
                detail=context,
                retryable=retryable,
                matched_pattern=pattern,
            )

    # No known pattern matched
    # Include the last 500 chars of the log as context
    tail = combined.strip()[-500:] if combined.strip() else ""
    return SessionDiagnosis(
        error_type=ErrorType.UNKNOWN,
        suggested_action=SuggestedAction.ESCALATE,
        detail=f"No known error pattern detected. Log tail: {tail}",
        retryable=False,
    )


def diagnose_session_state(session_data: dict) -> Optional[SessionDiagnosis]:
    """Diagnose a session from its state data (includes log file paths).

    Convenience wrapper that extracts log paths from session state and
    delegates to diagnose_session_log.

    Args:
        session_data: Session state dict (from StateStore).

    Returns:
        SessionDiagnosis if log files exist, None if no logs available.
    """
    stdout_log = session_data.get("stdout_log")
    stderr_log = session_data.get("stderr_log")

    if not stdout_log and not stderr_log:
        return None

    return diagnose_session_log(
        log_path=stdout_log or "/dev/null",
        stderr_path=stderr_log,
    )


def failure_summary(diagnosis: SessionDiagnosis) -> dict:
    """Convert a SessionDiagnosis to a JSON-serializable dict for session state.

    Returns a dict suitable for storing as ``session_data["failure_reason"]``
    and individual top-level fields (``error_code``, ``error_type``).

    The returned dict has the shape::

        {
            "error_code": "nested_session",   # ErrorType value (P6_003)
            "error_type": "nested_session",   # Same, kept for backward compat
            "suggested_action": "retry_clean_env",
            "detail": "...",
            "retryable": True,
            "matched_pattern": "cannot be launched inside another",
        }

    Args:
        diagnosis: SessionDiagnosis from ``diagnose_session_log`` or
            ``diagnose_session_state``.

    Returns:
        Dict with structured failure information.
    """
    return {
        "error_code": diagnosis.error_type.value,
        "error_type": diagnosis.error_type.value,
        "suggested_action": diagnosis.suggested_action.value,
        "detail": diagnosis.detail[:500],  # Bound detail size
        "retryable": diagnosis.retryable,
        "matched_pattern": diagnosis.matched_pattern,
    }


def diagnose_quick_exit(session_id: str) -> Optional[SessionDiagnosis]:
    """Run session diagnostics on a quick-exit session.

    Diagnoses the session and persists ``failure_reason`` and
    ``error_code`` back into the session state record so
    operators can inspect the structured failure data.

    Args:
        session_id: Session UUID to diagnose.

    Returns:
        SessionDiagnosis or None if diagnostics unavailable.
    """
    if not session_id:
        return None
    try:
        from agenticcli.utils.state_store import StateStore

        store = StateStore("sessions")
        data = store.load(session_id)
        if data:
            diagnosis = diagnose_session_state(data)
            if diagnosis:
                summary = failure_summary(diagnosis)
                data["error_code"] = summary["error_code"]
                data["failure_reason"] = summary
                store.save(data)
                logger.info(
                    "Session %s diagnosed: error_code=%s, retryable=%s",
                    session_id[:8], summary["error_code"], summary["retryable"],
                )
            return diagnosis
    except Exception as e:
        logger.debug("Failed to diagnose session %s: %s", session_id[:8], e)
    return None


def _read_log_safely(path: Optional[str | Path]) -> str:
    """Read a log file safely, returning empty string on any error.

    Args:
        path: Path to the log file.

    Returns:
        Log file content (truncated to _MAX_LOG_BYTES), or empty string.
    """
    if not path:
        return ""
    try:
        p = Path(path)
        if not p.exists():
            return ""
        # Read only the last _MAX_LOG_BYTES to keep memory bounded
        size = p.stat().st_size
        if size <= _MAX_LOG_BYTES:
            return p.read_text(errors="replace")
        else:
            with open(p, "r", errors="replace") as f:
                f.seek(size - _MAX_LOG_BYTES)
                return f.read()
    except (OSError, IOError, UnicodeDecodeError) as e:
        logger.debug("Failed to read log %s: %s", path, e)
        return ""
