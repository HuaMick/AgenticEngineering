"""SDK Pane Runner: runs exactly one SDK query() per process inside a tmux pane.

This script is the fix for the SDK zombie subprocess bug (SDK #434, #515, #573, #1089).
The Claude Agent SDK's query() cannot be called more than once per Python process —
after the first call, the spawned claude child process becomes a zombie and the second
call silently kills the parent.

Solution: each agent runs in its own tmux pane (separate OS process), calling query()
exactly once. The pane runner:
  1. Parses args (--role, --epic, --session-id, --timeout, --working-dir, --context-file)
  2. Strips CLAUDECODE env vars to avoid nested-session guard
  3. Builds ClaudeAgentOptions with role-specific tools/timeouts
  4. Reads prompt from --context-file
  5. Calls SDK query() exactly once (with timeout)
  6. Streams messages to stdout (visible in tmux pane)
  7. Writes structured SessionResult to session state store
  8. Exits cleanly

Usage:
    python3 -m agenticcli.utils.sdk_pane_runner \\
        --role explore --epic 260309TM_test --session-id <uuid> \\
        --context-file /path/to/context.md --working-dir /home/code/project
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Import role configs and session state helpers
from agenticcli.utils.session_state import mark_failed
from agenticcli.utils.sdk_runner import (
    ROLE_TOOL_ALLOWLIST,
    ROLE_TIMEOUT_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    _CLAUDECODE_ENV_VARS,
    _clean_claude_env,
    _ensure_clean_sdk_env,
    _kill_child_claude_processes,
    get_timeout_for_role,
)


def _write_state_atomic(state_file: Path, data: dict) -> None:
    """Write session state atomically (write to temp file, rename).

    Prevents partial reads by the polling loop in wait_for_session().
    """
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(state_file.parent),
        prefix=".state_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, str(state_file))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _get_state_file(session_id: str) -> Path:
    """Get the state file path for a session."""
    state_dir = Path.home() / ".agentic" / "sessions"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / f"{session_id}.json"


def _load_existing_state(state_file: Path) -> dict:
    """Load existing state from file, or return empty dict."""
    try:
        with open(state_file) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


async def _run_sdk_query(
    prompt: str,
    role: str,
    working_dir: str,
    timeout: int,
) -> dict:
    """Run a single SDK query() and return structured result data.

    Returns dict with: status, cost_usd, duration_ms, num_turns, usage,
    sdk_session_id, result_text, error.
    """
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query
    except ImportError:
        return {
            "status": "failed",
            "error": "claude-agent-sdk not installed",
            "cost_usd": 0.0,
            "duration_ms": 0,
            "num_turns": 0,
            "usage": {},
            "sdk_session_id": "",
            "result_text": "",
        }

    # Build options with role-specific tool restrictions
    allowed_tools = ROLE_TOOL_ALLOWLIST.get(role)
    kwargs: dict = {
        "permission_mode": "bypassPermissions",
        "cwd": working_dir,
    }
    if allowed_tools is not None:
        kwargs["allowed_tools"] = allowed_tools

    options = ClaudeAgentOptions(**kwargs)

    # Dual-layer env isolation
    _ensure_clean_sdk_env(options)

    start_time = time.monotonic()
    result_text_parts: list[str] = []
    final_result = None
    msg_count = 0

    try:
        async def _stream():
            nonlocal final_result, msg_count
            with _clean_claude_env():
                async for message in query(prompt=prompt, options=options):
                    msg_count += 1
                    # Stream to stdout for tmux visibility
                    mtype = type(message).__name__
                    elapsed = time.monotonic() - start_time
                    print(f"[{elapsed:.1f}s] {mtype}", flush=True)

                    # Collect assistant text
                    if hasattr(message, "content") and hasattr(message, "role"):
                        if getattr(message, "role", None) == "assistant":
                            for block in getattr(message, "content", []):
                                if hasattr(block, "text"):
                                    result_text_parts.append(block.text)
                                    # Print agent text to tmux pane
                                    print(block.text, end="", flush=True)

                    # Capture final ResultMessage
                    if hasattr(message, "subtype") and hasattr(message, "duration_ms"):
                        final_result = message

        if timeout > 0:
            await asyncio.wait_for(_stream(), timeout=timeout)
        else:
            await _stream()

    except asyncio.TimeoutError:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        killed = _kill_child_claude_processes(os.getpid())
        if killed:
            print(f"\n[timeout] Killed hung claude subprocesses: {killed}", flush=True)
        return {
            "status": "failed",
            "error": f"SDK query timed out after {timeout}s",
            "cost_usd": 0.0,
            "duration_ms": elapsed_ms,
            "num_turns": 0,
            "usage": {},
            "sdk_session_id": "",
            "result_text": "\n".join(result_text_parts),
        }

    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        return {
            "status": "failed",
            "error": str(e),
            "cost_usd": 0.0,
            "duration_ms": elapsed_ms,
            "num_turns": 0,
            "usage": {},
            "sdk_session_id": "",
            "result_text": "\n".join(result_text_parts),
        }

    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    if final_result is not None:
        is_error = getattr(final_result, "is_error", False)
        return {
            "status": "failed" if is_error else "completed",
            "cost_usd": getattr(final_result, "total_cost_usd", 0.0) or 0.0,
            "duration_ms": getattr(final_result, "duration_ms", elapsed_ms) or elapsed_ms,
            "num_turns": getattr(final_result, "num_turns", 0) or 0,
            "usage": getattr(final_result, "usage", {}) or {},
            "sdk_session_id": getattr(final_result, "session_id", "") or "",
            "result_text": getattr(final_result, "result", "") or "\n".join(result_text_parts),
            "error": "",
        }

    # No ResultMessage — check if we got any output
    collected = "\n".join(result_text_parts)
    if not collected.strip():
        return {
            "status": "failed",
            "error": "No ResultMessage received - stream may have dropped",
            "cost_usd": 0.0,
            "duration_ms": elapsed_ms,
            "num_turns": 0,
            "usage": {},
            "sdk_session_id": "",
            "result_text": "",
        }

    return {
        "status": "completed",
        "cost_usd": 0.0,
        "duration_ms": elapsed_ms,
        "num_turns": msg_count,
        "usage": {},
        "sdk_session_id": "",
        "result_text": collected,
        "error": "",
    }


def run_pane(
    role: str,
    session_id: str,
    context_file: str,
    working_dir: str,
    timeout: int | None = None,
) -> int:
    """Main entry point for the pane runner.

    Args:
        role: Agent role identifier.
        session_id: Pre-generated session UUID.
        context_file: Path to the compiled context file (prompt).
        working_dir: Working directory for the agent.
        timeout: Timeout in seconds (None = use role default).

    Returns:
        Exit code (0=success, 1=failure).
    """
    effective_timeout = timeout or get_timeout_for_role(role)
    state_file = _get_state_file(session_id)

    # Read prompt from context file
    try:
        prompt = Path(context_file).read_text()
    except FileNotFoundError:
        print(f"ERROR: Context file not found: {context_file}", file=sys.stderr)
        # Write failure state
        state = _load_existing_state(state_file)
        state.setdefault("session_id", session_id)
        state.setdefault("transport", "sdk-tmux")
        state["error"] = f"Context file not found: {context_file}"
        mark_failed(
            state,
            error_code="context_file_missing",
            error_type="missing_input",
            detail=f"Context file not found: {context_file}",
            retryable=False,
        )
        _write_state_atomic(state_file, state)
        return 1

    print(f"=== SDK Pane Runner ===", flush=True)
    print(f"Role: {role}", flush=True)
    print(f"Session: {session_id[:8]}", flush=True)
    print(f"Timeout: {effective_timeout}s", flush=True)
    print(f"Working dir: {working_dir}", flush=True)
    print(f"Context: {len(prompt)} chars", flush=True)
    print(f"========================", flush=True)

    # Run the SDK query
    result = asyncio.run(_run_sdk_query(prompt, role, working_dir, effective_timeout))

    # Write result to session state
    state = _load_existing_state(state_file)
    state.update({
        "session_id": session_id,
        "status": result["status"],
        "ended_at": datetime.now().isoformat(),
        "exit_code": 0 if result["status"] == "completed" else 1,
        "cost_usd": result["cost_usd"],
        "duration_ms": result["duration_ms"],
        "num_turns": result["num_turns"],
        "usage": result["usage"],
        "sdk_session_id": result["sdk_session_id"],
        "transport": "sdk-tmux",
    })

    if result["error"]:
        state["error"] = result["error"]
        mark_failed(
            state,
            error_code="sdk_pane_failure",
            error_type="sdk_error",
            detail=result["error"],
            retryable=True,
        )

    _write_state_atomic(state_file, state)

    exit_code = 0 if result["status"] == "completed" else 1
    print(f"\n=== Pane Runner Complete ===", flush=True)
    print(f"Status: {result['status']}", flush=True)
    print(f"Cost: ${result['cost_usd']:.4f}", flush=True)
    print(f"Duration: {result['duration_ms']}ms", flush=True)
    print(f"Turns: {result['num_turns']}", flush=True)
    print(f"Exit code: {exit_code}", flush=True)

    return exit_code


def main():
    """CLI entry point for python3 -m agenticcli.utils.sdk_pane_runner."""
    parser = argparse.ArgumentParser(description="SDK Pane Runner — one query() per process")
    parser.add_argument("--role", required=True, help="Agent role identifier")
    parser.add_argument("--epic", help="Epic folder name (for context)")
    parser.add_argument("--session-id", required=True, help="Pre-generated session UUID")
    parser.add_argument("--context-file", required=True, help="Path to compiled context file")
    parser.add_argument("--timeout", type=int, help="Timeout in seconds (overrides role default)")
    parser.add_argument("--working-dir", default=os.getcwd(), help="Working directory for agent")

    args = parser.parse_args()

    # Configure logging for tmux visibility
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stdout,
    )

    exit_code = run_pane(
        role=args.role,
        session_id=args.session_id,
        context_file=args.context_file,
        working_dir=args.working_dir,
        timeout=args.timeout,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
