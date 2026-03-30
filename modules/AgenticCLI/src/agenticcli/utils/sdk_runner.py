"""SDK runner: wraps Claude Agent SDK query() with session lifecycle semantics.

Provides sync and async wrappers around the SDK's query() function,
replacing the subprocess.Popen + PID-polling pattern with direct SDK calls.
Falls back gracefully when the SDK is not installed.
"""

import asyncio
import contextlib
import logging
import os
import signal
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
__all__ = [
    "SDK_AVAILABLE",
    "SessionResult",
    "run_agent",
    "run_agent_sync",
    "sdk_env_preflight",
    "_clean_claude_env",
    "DEFAULT_TIMEOUT_SECONDS",
    "ROLE_TIMEOUT_SECONDS",
    "get_timeout_for_role",
]


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
    # ── Planning phase: Read + Bash only (use `agentic` CLI for tickets/phases) ──
    "epic-creator": ["Read", "Glob", "Grep", "Bash"],
    "planner-explore": ["Read", "Glob", "Grep", "Bash"],
    "explore": ["Read", "Glob", "Grep", "Bash"],
    "planner-build": ["Read", "Glob", "Grep", "Bash"],
    "planner-test": ["Read", "Glob", "Grep", "Bash"],
    "planner-orchestration": ["Read", "Glob", "Grep", "Bash"],
    "planner-audit": ["Read", "Glob", "Grep", "Bash"],
    # ── Execution phase: full access ──
    "build-python": ["Read", "Glob", "Grep", "Edit", "Write", "Bash"],
    "build-flutter": ["Read", "Glob", "Grep", "Edit", "Write", "Bash"],
    "build-story-writer": ["Read", "Glob", "Grep", "Bash", "Write"],
    "build-docs-writer": ["Read", "Glob", "Grep", "Edit", "Write", "Bash"],
    "test-builder": ["Read", "Glob", "Grep", "Bash", "Edit", "Write"],
    "test-audit": ["Read", "Glob", "Grep", "Bash", "Edit", "Write"],
    "test-uat": ["Read", "Glob", "Grep", "Bash", "Edit", "Write"],
    "trace-explorer": ["Read", "Glob", "Grep", "Bash", "Edit", "Write"],
}


# Role-based timeout budgets (seconds). Used by planner_loop and sdk_pane_runner.
# If a role is not listed, DEFAULT_TIMEOUT_SECONDS applies.
ROLE_TIMEOUT_SECONDS: dict[str, int] = {
    # ── Planning roles: 30 min or less ──
    "epic-creator": 600,           # 10 min — CLI scaffolding only
    "planner-explore": 900,        # 15 min — codebase exploration + ticket updates
    "explore": 600,                # 10 min — lightweight codebase analysis
    "planner-build": 1800,         # 30 min
    "planner-test": 1800,          # 30 min
    "planner-audit": 1800,         # 30 min
    "planner-orchestration": 900,  # 15 min (observed: 4-5 min)
    # ── Implementation roles: 60 min ──
    "build-python": 3600,
    "build-flutter": 3600,
    "build-story-writer": 600,     # 10 min — story generation (lightweight)
    "build-docs-writer": 3600,
    "test-builder": 3600,
    "test-audit": 3600,
    "test-uat": 3600,
    "trace-explorer": 3600,
    # ── Teacher roles: 60 min ──
    "teacher-update-guidance": 3600,
    "teacher-update-assets": 3600,
}


def get_timeout_for_role(role: str) -> int:
    """Return timeout for a role, or DEFAULT_TIMEOUT_SECONDS if unknown."""
    return ROLE_TIMEOUT_SECONDS.get(role, DEFAULT_TIMEOUT_SECONDS)


def get_allowed_tools_for_role(role: str) -> list[str] | None:
    """Return the allowed tool list for an agent role, or None if unrestricted.

    Args:
        role: Agent role identifier (e.g., "explore", "planner-build").

    Returns:
        List of allowed tool names, or None if the role has no restriction.
        None means all tools are allowed (backwards-compatible default).
    """
    return ROLE_TOOL_ALLOWLIST.get(role)


# Environment variables that must be stripped before spawning Claude
# via the SDK.  The SDK merges os.environ into the subprocess env,
# so these vars would trigger the "nested session" guard.
_CLAUDECODE_ENV_VARS = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")


@contextlib.contextmanager
def _clean_claude_env():
    """Context manager that temporarily strips Claude Code env vars.

    Removes CLAUDECODE and CLAUDE_CODE_ENTRYPOINT from os.environ for the
    duration of the block.  Restores them on exit (even on exception) to
    leave the parent process state unchanged.

    Logs a critical warning when the vars are detected, since their presence
    means we're running inside a Claude Code session and the SDK spawn
    would fail without this workaround.
    """
    saved: dict[str, str] = {}
    for var in _CLAUDECODE_ENV_VARS:
        val = os.environ.pop(var, None)
        if val is not None:
            saved[var] = val
    if saved:
        logger.critical(
            "SDK pre-flight: stripped Claude Code env vars %s — running "
            "inside an existing Claude Code session; env isolation applied",
            list(saved.keys()),
        )
    try:
        yield saved
    finally:
        os.environ.update(saved)


def sdk_env_preflight() -> dict[str, str]:
    """Check for problematic env vars before SDK spawn.

    Returns:
        Dict of detected Claude Code env vars and their values.
        Empty dict means the env is clean.
    """
    found: dict[str, str] = {}
    for var in _CLAUDECODE_ENV_VARS:
        val = os.environ.get(var)
        if val is not None:
            found[var] = val
    if found:
        logger.warning(
            "SDK pre-flight check: detected Claude Code env vars %s — "
            "these will be stripped before SDK query to prevent nested-session errors",
            list(found.keys()),
        )
    return found


def _kill_child_claude_processes(parent_pid: int) -> list[int]:
    """Find and kill child 'claude' subprocesses of the given parent PID.

    Uses /proc to avoid adding a psutil dependency. Falls back silently
    on non-Linux or if /proc is unavailable.

    Returns:
        List of PIDs that were sent SIGKILL.
    """
    killed: list[int] = []
    try:
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            pid = int(entry)
            try:
                with open(f"/proc/{pid}/stat", "r") as f:
                    stat = f.read()
                # stat format: pid (comm) state ppid ...
                # Extract ppid (4th field) and comm (in parens)
                comm_start = stat.index("(")
                comm_end = stat.rindex(")")
                comm = stat[comm_start + 1 : comm_end]
                rest = stat[comm_end + 2 :].split()
                ppid = int(rest[1])  # state is rest[0], ppid is rest[1]

                if ppid == parent_pid and "claude" in comm:
                    logger.info("Killing hung claude subprocess PID %d", pid)
                    os.kill(pid, signal.SIGKILL)
                    killed.append(pid)
            except (FileNotFoundError, ValueError, IndexError, ProcessLookupError,
                    PermissionError):
                continue
    except FileNotFoundError:
        logger.debug("/proc not available — cannot scan for child processes")
    return killed


def _ensure_clean_sdk_env(options: Optional[Any]) -> Optional[Any]:
    """Ensure SDK options.env excludes Claude Code internal vars.

    Dual-layer env isolation: even if _clean_claude_env() strips os.environ,
    the SDK options may carry a snapshot of the env taken earlier (before
    stripping).  This function ensures that snapshot is also clean.

    This is the pragmatic alternative to the "nuclear option" of running
    the SDK call in a completely separate subprocess. Performance evaluation
    showed that subprocess isolation adds ~2-3 seconds of startup overhead
    per spawn, while this approach adds negligible overhead.

    Args:
        options: ClaudeAgentOptions instance (may be None).

    Returns:
        The same options object with env cleaned (mutated in place), or None.
    """
    if options is not None and hasattr(options, "env") and options.env:
        for var in _CLAUDECODE_ENV_VARS:
            options.env.pop(var, None)
    return options


async def _stream_query(
    prompt: str,
    options: Optional[Any],
    on_message: Optional[Callable],
    result_text_parts: list,
) -> Optional[Any]:
    """Stream messages from query() and return the final ResultMessage (or None).

    Extracted so asyncio.wait_for() can wrap the entire streaming operation.

    Env isolation is dual-layered:
      1. _clean_claude_env() strips vars from os.environ (context manager)
      2. _ensure_clean_sdk_env() strips vars from options.env (snapshot clean)

    Args:
        prompt: The prompt to send to the agent.
        options: ClaudeAgentOptions instance (or None for defaults).
        on_message: Optional callback invoked with each streamed message.
        result_text_parts: Mutable list that collects assistant text blocks.

    Returns:
        The final ResultMessage if one was received, otherwise None.
    """
    final_result: Optional[Any] = None

    # Layer 2: Clean the options.env snapshot (see _ensure_clean_sdk_env docstring)
    _ensure_clean_sdk_env(options)

    # Layer 1: Strip CLAUDECODE vars from os.environ for the duration of
    # the SDK call.  The SDK also merges os.environ into the subprocess env.
    with _clean_claude_env():
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

    # Pre-flight: detect problematic env vars early so the log shows the
    # warning before the potentially long-running SDK call begins.
    sdk_env_preflight()

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
        # Kill any hung claude subprocess that the SDK spawned via Popen.
        # asyncio.wait_for cancels the coroutine but does NOT terminate the
        # underlying OS process, leaving it hung and blocking pipes.
        killed = _kill_child_claude_processes(os.getpid())
        if killed:
            logger.warning("Killed hung claude subprocess(es): %s", killed)
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
