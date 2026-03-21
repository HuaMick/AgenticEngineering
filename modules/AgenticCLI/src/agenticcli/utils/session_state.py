"""Session state helpers — reduce duplication across spawn paths.

Provides builder functions for common session state dict patterns:
- Failure state update with structured error info
- SDK metrics reading
"""

import json
from datetime import datetime
from typing import Any, Optional


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
