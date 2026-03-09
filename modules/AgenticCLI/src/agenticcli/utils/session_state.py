"""Session state helpers — reduce duplication across spawn paths.

Provides builder functions for common session state dict patterns:
- Initial session creation
- Running state update
- Completion state update
- Failure state update with structured error info
"""

import json
from datetime import datetime
from typing import Any, Optional


def make_session_data(
    session_id: str,
    *,
    prompt: str = "",
    role: str = "",
    epic_folder: str = "",
    working_dir: str = "",
    transport: str = "",
    background: bool = False,
    max_turns: int | None = None,
    estimated_tokens: int = 0,
    context_usage_percent: float = 0.0,
    compiled_context: str = "",
) -> dict[str, Any]:
    """Create initial session data dict.

    Args:
        session_id: Session UUID.
        prompt: Original prompt text.
        role: Agent role identifier.
        epic_folder: Epic folder name.
        working_dir: Working directory path.
        transport: Spawn transport type (sdk-tmux, tmux, subprocess).
        background: Whether session runs in background.
        max_turns: Max turns limit.
        estimated_tokens: Estimated token count.
        context_usage_percent: Context window usage percentage.
        compiled_context: Path to compiled context file.

    Returns:
        Session data dict ready for StateStore.save().
    """
    data: dict[str, Any] = {
        "session_id": session_id,
        "pid": None,
        "prompt": prompt,
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "ended_at": None,
        "background": background,
        "working_dir": working_dir,
    }
    if role:
        data["role"] = role
    if epic_folder:
        data["epic_folder"] = epic_folder
    if transport:
        data["transport"] = transport
    if max_turns is not None:
        data["max_turns"] = max_turns
    if estimated_tokens:
        data["estimated_tokens"] = estimated_tokens
    if context_usage_percent:
        data["context_usage_percent"] = context_usage_percent
    if compiled_context:
        data["compiled_context"] = compiled_context
    return data


def mark_running(
    data: dict[str, Any],
    *,
    pid: int | None = None,
    transport: str = "",
    tmux_session: str = "",
) -> dict[str, Any]:
    """Update session data to running state.

    Args:
        data: Existing session data dict (mutated in place).
        pid: Process ID of the running session.
        transport: Transport type.
        tmux_session: Tmux session name.

    Returns:
        The mutated data dict.
    """
    data["status"] = "running"
    data["last_activity"] = datetime.now().isoformat()
    if pid is not None:
        data["pid"] = pid
    if transport:
        data["transport"] = transport
    if tmux_session:
        data["tmux_session"] = tmux_session
    return data


def mark_completed(
    data: dict[str, Any],
    *,
    exit_code: int = 0,
    cost_usd: float = 0.0,
    duration_ms: int = 0,
    num_turns: int = 0,
    sdk_session_id: str = "",
) -> dict[str, Any]:
    """Update session data to completed state.

    Args:
        data: Existing session data dict (mutated in place).
        exit_code: Process exit code.
        cost_usd: Total cost in USD.
        duration_ms: Duration in milliseconds.
        num_turns: Number of agent turns.
        sdk_session_id: SDK session identifier.

    Returns:
        The mutated data dict.
    """
    data["status"] = "completed"
    data["ended_at"] = datetime.now().isoformat()
    data["exit_code"] = exit_code
    if cost_usd:
        data["cost_usd"] = cost_usd
    if duration_ms:
        data["duration_ms"] = duration_ms
    if num_turns:
        data["num_turns"] = num_turns
    if sdk_session_id:
        data["sdk_session_id"] = sdk_session_id
    return data


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
