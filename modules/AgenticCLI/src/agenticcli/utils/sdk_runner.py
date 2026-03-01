"""SDK runner: wraps Claude Agent SDK query() with session lifecycle semantics.

Provides sync and async wrappers around the SDK's query() function,
replacing the subprocess.Popen + PID-polling pattern with direct SDK calls.
Falls back gracefully when the SDK is not installed.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

try:
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        ResultMessage,
        query,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

# Re-export for callers that want to check availability
__all__ = ["SDK_AVAILABLE", "SessionResult", "run_agent", "run_agent_sync"]


@dataclass
class SessionResult:
    """Result of an SDK agent run."""

    status: str  # "completed" | "failed"
    result: str  # Agent text output
    cost_usd: float = 0.0
    duration_ms: int = 0
    session_id: str = ""
    num_turns: int = 0
    usage: dict[str, Any] = field(default_factory=dict)
    is_error: bool = False


DEFAULT_TIMEOUT_SECONDS = 1800  # 30 minutes

# Role-based tool allow-lists.
# These restrict what tools each agent role can invoke, reducing blast radius.
# If a role is not listed here, all tools are allowed (backwards-compatible default).
ROLE_TOOL_ALLOWLIST: dict[str, list[str]] = {
    "explore": ["Read", "Glob", "Grep", "Bash"],
    "planner-build": ["Read", "Glob", "Grep", "Write", "Bash"],
    "planner-test": ["Read", "Glob", "Grep", "Write", "Bash"],
    "planner-guidance": ["Read", "Glob", "Grep", "Write", "Bash"],
    "planner-cleaning": ["Read", "Glob", "Grep", "Write", "Bash"],
    "planner-guidance-testing": ["Read", "Glob", "Grep", "Write", "Bash"],
    "planner-sdk": ["Read", "Glob", "Grep", "Write", "Bash"],
    "planner-reviewer": ["Read", "Glob", "Grep"],
    "test-runner": ["Read", "Glob", "Grep", "Bash", "Edit"],
    "build-python": ["Read", "Glob", "Grep", "Edit", "Write", "Bash"],
    "build-flutter": ["Read", "Glob", "Grep", "Edit", "Write", "Bash"],
    "story-generator": ["Read", "Glob", "Grep", "Write", "Bash"],
}


def get_allowed_tools_for_role(role: str) -> list[str] | None:
    """Return the allowed tool list for an agent role, or None if unrestricted.

    Args:
        role: Agent role identifier (e.g., "explore", "planner-build").

    Returns:
        List of allowed tool names, or None if the role has no restriction.
        None means all tools are allowed (backwards-compatible default).
    """
    return ROLE_TOOL_ALLOWLIST.get(role)


async def _stream_query(
    prompt: str,
    options: Optional[Any],
    on_message: Optional[Callable],
    result_text_parts: list,
) -> Optional[Any]:
    """Stream messages from query() and return the final ResultMessage (or None).

    Extracted so asyncio.wait_for() can wrap the entire streaming operation.

    Args:
        prompt: The prompt to send to the agent.
        options: ClaudeAgentOptions instance (or None for defaults).
        on_message: Optional callback invoked with each streamed message.
        result_text_parts: Mutable list that collects assistant text blocks.

    Returns:
        The final ResultMessage if one was received, otherwise None.
    """
    final_result: Optional[Any] = None

    async for message in query(prompt=prompt, options=options):
        if on_message:
            on_message(message)

        # Collect assistant text from AssistantMessage content blocks
        if hasattr(message, "content") and hasattr(message, "role"):
            if getattr(message, "role", None) == "assistant":
                for block in getattr(message, "content", []):
                    if hasattr(block, "text"):
                        result_text_parts.append(block.text)

        # Capture the final ResultMessage for metadata
        if hasattr(message, "subtype") and hasattr(message, "duration_ms"):
            final_result = message

    return final_result


async def run_agent(
    prompt: str,
    options: Optional[Any] = None,
    on_message: Optional[Callable] = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> SessionResult:
    """Run a Claude agent via the SDK and return a SessionResult.

    Streams messages from query(), collecting the final ResultMessage
    for cost/usage data and all assistant text for the result.

    Args:
        prompt: The prompt to send to the agent.
        options: ClaudeAgentOptions instance (or None for defaults).
        on_message: Optional callback invoked with each streamed message.
        timeout_seconds: Maximum time to wait for the SDK query to complete.
            Defaults to 1800 seconds (30 minutes). Set to 0 to disable.

    Returns:
        SessionResult with status, result text, cost, and usage data.
    """
    if not SDK_AVAILABLE:
        return SessionResult(
            status="failed",
            result="claude-agent-sdk is not installed",
            is_error=True,
        )

    start_time = time.monotonic()
    result_text_parts: list[str] = []
    final_result: Optional[Any] = None

    try:
        stream_coro = _stream_query(prompt, options, on_message, result_text_parts)
        if timeout_seconds and timeout_seconds > 0:
            final_result = await asyncio.wait_for(stream_coro, timeout=timeout_seconds)
        else:
            final_result = await stream_coro

    except asyncio.TimeoutError:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.warning(
            "SDK agent query timed out after %ds (elapsed: %dms)",
            timeout_seconds, elapsed_ms,
        )
        return SessionResult(
            status="failed",
            result=f"SDK query timed out after {timeout_seconds}s",
            duration_ms=elapsed_ms,
            is_error=True,
        )

    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error("SDK agent run failed: %s", e)
        return SessionResult(
            status="failed",
            result=str(e),
            duration_ms=elapsed_ms,
            is_error=True,
        )

    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    if final_result is not None:
        return SessionResult(
            status="failed" if final_result.is_error else "completed",
            result=final_result.result or "\n".join(result_text_parts),
            cost_usd=final_result.total_cost_usd or 0.0,
            duration_ms=final_result.duration_ms or elapsed_ms,
            session_id=final_result.session_id or "",
            num_turns=final_result.num_turns or 0,
            usage=final_result.usage or {},
            is_error=final_result.is_error,
        )

    # No ResultMessage received — stream dropped without signaling completion.
    # Detect stall: if result text is also empty AND cost is 0, flag as failure.
    collected_text = "\n".join(result_text_parts)
    if not collected_text.strip():
        logger.warning(
            "SDK agent stream ended with no ResultMessage and empty output — "
            "stream may have dropped (stall detection)"
        )
        return SessionResult(
            status="failed",
            result="No ResultMessage received - stream may have dropped",
            duration_ms=elapsed_ms,
            is_error=True,
        )

    # We got some text but no ResultMessage — treat as completed with collected text.
    return SessionResult(
        status="completed",
        result=collected_text,
        duration_ms=elapsed_ms,
    )


def run_agent_sync(
    prompt: str,
    options: Optional[Any] = None,
    on_message: Optional[Callable] = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> SessionResult:
    """Synchronous wrapper around run_agent().

    Safe to call from non-async code. Creates a new event loop if needed.

    Args:
        prompt: The prompt to send to the agent.
        options: ClaudeAgentOptions instance (or None for defaults).
        on_message: Optional callback invoked with each streamed message.
        timeout_seconds: Maximum time to wait for the SDK query to complete.
            Defaults to 1800 seconds (30 minutes). Set to 0 to disable.

    Returns:
        SessionResult with status, result text, cost, and usage data.
    """
    if not SDK_AVAILABLE:
        return SessionResult(
            status="failed",
            result="claude-agent-sdk is not installed",
            is_error=True,
        )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already inside an async context — run in a new thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                run_agent(prompt, options, on_message, timeout_seconds),
            )
            return future.result()
    else:
        return asyncio.run(run_agent(prompt, options, on_message, timeout_seconds))
