# story: US-SES-001, US-SET-014
"""Session state helpers — reduce duplication across spawn paths.

Provides builder functions for common session state dict patterns:
- Failure state update with structured error info
- SDK metrics reading
- Event ledger cleanup
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def mark_failed(
    data: dict[str, Any],
    *,
    error_code: str = "unknown",
    error_type: str = "unknown",
    detail: str = "",
    retryable: bool = False,
    exit_code: int = 1,
    suggested_action: str = "",
) -> dict[str, Any]:
    """Update session data to failed state with structured error info.

    Args:
        data: Existing session data dict (mutated in place).
        error_code: Machine-readable error code.
        error_type: Error classification.
        detail: Human-readable error detail.
        retryable: Whether the error is retryable.
        exit_code: Process exit code.
        suggested_action: Override the default suggested action.  When omitted,
            defaults to "retry" for retryable errors and "escalate" otherwise.

    Returns:
        The mutated data dict.
    """
    data["status"] = "failed"
    data["ended_at"] = datetime.now().isoformat()
    data["exit_code"] = exit_code
    data["error_code"] = error_code
    data["failure_reason"] = {
        "error_code": error_code,
        "error_type": error_type,
        "suggested_action": suggested_action or ("retry" if retryable else "escalate"),
        "detail": detail[:500],
        "retryable": retryable,
        "matched_pattern": "",
    }
    return data


def read_sdk_metrics(session_id: str) -> dict:
    """Read SDK metrics from session state store.

    Returns dict with keys: cost_usd, duration_ms, num_turns, usage,
    sdk_session_id, transport (all with safe defaults).
    """
    from agenticcli.utils.state_store import StateStore
    store = StateStore("sessions", id_key="session_id")
    state_data = store.load(session_id)

    return {
        "cost_usd": state_data.get("cost_usd", 0.0) if state_data else 0.0,
        "duration_ms": state_data.get("duration_ms", 0) if state_data else 0,
        "num_turns": state_data.get("num_turns", 0) if state_data else 0,
        "usage": state_data.get("usage", {}) if state_data else {},
        "sdk_session_id": state_data.get("sdk_session_id", "") if state_data else "",
        "transport": state_data.get("transport", "unknown") if state_data else "unknown",
    }


# @story US-260401AG-009
def cleanup_event_ledger(session_id: str) -> bool:
    """Remove the event ledger file and session directory for a session.

    Idempotent — returns ``True`` if the ledger existed and was removed,
    ``False`` if it was already missing.  Never raises on missing files.

    Removes the session event directory
    (``/tmp/agentic/sessions/{session_id}/``) only if it becomes empty
    after deleting ``events.jsonl``.

    This is the canonical cleanup function for the event bus side-channel.
    Called by :class:`~agenticcli.utils.session_cleanup.SessionCleanupService`
    during bulk cleanup, and available for direct use by ``cmd_stop`` or
    other lifecycle hooks that need to clean up a single session's ledger.

    Args:
        session_id: UUID string identifying the agent session.

    Returns:
        ``True`` if a ledger file was found and removed, ``False`` otherwise.
    """
    from agenticcli.utils.event_bus import get_event_file_path

    event_file = get_event_file_path(session_id)
    removed = False

    if event_file.exists():
        try:
            event_file.unlink(missing_ok=True)
            removed = True
            logger.debug("Removed event ledger: %s", event_file)
        except OSError as exc:
            logger.warning("Failed to remove event ledger %s: %s", event_file, exc)

    # Remove the session event directory if it's now empty
    event_dir = event_file.parent
    if event_dir.exists():
        try:
            event_dir.rmdir()  # Only succeeds if empty — safe
            logger.debug("Removed empty event dir: %s", event_dir)
        except OSError:
            pass  # Directory not empty or already gone — fine

    return removed
