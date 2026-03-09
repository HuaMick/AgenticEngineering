#!/usr/bin/env python3
"""Lightweight reproducer for SDK sequential spawn failures.

Replicates the planning loop pattern:
  explore → story → planner → reviewer → orchestration
Each agent runs a trivial prompt via the SDK, blocking until complete.

Hypothesis: After N successful spawns, subsequent SDK calls fail with
"Fatal error in message reader: Command failed with exit code 1".

Usage:
    python3 scripts/test_sdk_sequential_spawn.py
    python3 scripts/test_sdk_sequential_spawn.py --delay 5
    python3 scripts/test_sdk_sequential_spawn.py --count 3
"""

import argparse
import asyncio
import contextlib
import os
import time

LOG_FILE = "/tmp/sdk_sequential_test.log"


def log(msg: str):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
        f.flush()


# ---------------------------------------------------------------------------
# Env isolation — same dual-layer as sdk_runner.py
# ---------------------------------------------------------------------------
_CLAUDECODE_ENV_VARS = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")


@contextlib.contextmanager
def _clean_claude_env():
    saved = {}
    for var in _CLAUDECODE_ENV_VARS:
        val = os.environ.pop(var, None)
        if val is not None:
            saved[var] = val
    if saved:
        log(f"  [env] Stripped Claude Code vars: {list(saved.keys())}")
    try:
        yield saved
    finally:
        os.environ.update(saved)


# ---------------------------------------------------------------------------
# SDK import
# ---------------------------------------------------------------------------
try:
    from claude_agent_sdk import ClaudeAgentOptions, query
    SDK_OK = True
except ImportError:
    SDK_OK = False
    log("ERROR: claude_agent_sdk not installed")
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Simulated agent roles — mirrors planning loop sequence
# ---------------------------------------------------------------------------
AGENTS = [
    {"role": "explore",       "tools": ["Read", "Glob", "Grep", "Bash"],          "prompt": "Reply with exactly: EXPLORE_OK"},
    {"role": "story-gen",     "tools": ["Read", "Glob", "Grep", "Write", "Bash"], "prompt": "Reply with exactly: STORY_OK"},
    {"role": "planner-build", "tools": ["Read", "Glob", "Grep", "Write", "Bash"], "prompt": "Reply with exactly: PLANNER_OK"},
    {"role": "reviewer",      "tools": ["Read", "Glob", "Grep"],                  "prompt": "Reply with exactly: REVIEWER_OK"},
    {"role": "orchestration", "tools": None,                                       "prompt": "Reply with exactly: ORCH_OK"},
]


async def spawn_one(role: str, prompt: str, tools: list[str] | None, cwd: str) -> dict:
    """Spawn a single SDK agent and return result metadata."""
    kwargs: dict = {
        "permission_mode": "bypassPermissions",
        "cwd": cwd,
    }
    if tools is not None:
        kwargs["allowed_tools"] = tools

    options = ClaudeAgentOptions(**kwargs)

    # Dual-layer env isolation (layer 2: clean options.env if present)
    if hasattr(options, "env") and options.env:
        for var in _CLAUDECODE_ENV_VARS:
            options.env.pop(var, None)

    start = time.monotonic()
    status = "unknown"
    result_text = ""
    error_msg = ""
    msg_count = 0

    try:
        with _clean_claude_env():
            async for msg in query(prompt=prompt, options=options):
                msg_count += 1
                mtype = type(msg).__name__
                elapsed = round(time.monotonic() - start, 1)
                log(f"    [{elapsed}s] msg #{msg_count}: {mtype}")

                # Capture result message
                if hasattr(msg, "subtype") and getattr(msg, "subtype", "") == "success":
                    status = "completed"
                    result_text = getattr(msg, "result", "") or ""
                    break
                elif hasattr(msg, "subtype") and getattr(msg, "subtype", "") in ("error", "result"):
                    is_err = getattr(msg, "is_error", False)
                    status = "failed" if is_err else "completed"
                    result_text = getattr(msg, "result", "") or ""
                    break

                # Capture assistant text
                if hasattr(msg, "role") and getattr(msg, "role", None) == "assistant":
                    for block in getattr(msg, "content", []):
                        if hasattr(block, "text"):
                            result_text += block.text

                if msg_count > 30:
                    log("    Stopping after 30 messages")
                    status = "completed"
                    break

    except Exception as e:
        status = "exception"
        error_msg = str(e)
        log(f"    EXCEPTION: {type(e).__name__}: {e}")

    elapsed = time.monotonic() - start
    return {
        "role": role,
        "status": status,
        "elapsed_s": round(elapsed, 1),
        "result": result_text[:100],
        "error": error_msg[:200] if error_msg else "",
        "msg_count": msg_count,
    }


async def run_sequence(agents: list[dict], cwd: str, delay: float):
    """Run agents sequentially, mirroring the planning loop."""
    results = []
    for i, agent in enumerate(agents):
        label = f"[{i+1}/{len(agents)}] {agent['role']}"
        log(f"\n{label}: spawning...")

        r = await spawn_one(agent["role"], agent["prompt"], agent["tools"], cwd)
        results.append(r)

        icon = "OK" if r["status"] == "completed" else "FAIL"
        log(f"{label}: {icon} ({r['elapsed_s']}s, {r['msg_count']} msgs) — {r['result'][:60]}")
        if r["error"]:
            log(f"  ERROR: {r['error']}")

        if delay > 0 and i < len(agents) - 1:
            log(f"  [delay] Waiting {delay}s before next spawn...")
            await asyncio.sleep(delay)

    return results


def main():
    parser = argparse.ArgumentParser(description="SDK sequential spawn reproducer")
    parser.add_argument("--delay", type=float, default=0, help="Seconds between spawns")
    parser.add_argument("--count", type=int, default=5, help="Number of agents to spawn")
    parser.add_argument("--cwd", type=str, default=os.getcwd(), help="Working directory")
    args = parser.parse_args()

    # Clear log
    with open(LOG_FILE, "w") as f:
        f.write("")

    agents = AGENTS[:args.count]
    log(f"=== SDK Sequential Spawn Test ===")
    log(f"Agents: {len(agents)}, Delay: {args.delay}s, CWD: {args.cwd}")
    log(f"Nested session: CLAUDECODE={'yes' if os.environ.get('CLAUDECODE') else 'no'}")
    log(f"SDK available: {SDK_OK}")

    results = asyncio.run(run_sequence(agents, args.cwd, args.delay))

    log(f"\n=== Summary ===")
    ok = sum(1 for r in results if r["status"] == "completed")
    fail = len(results) - ok
    log(f"Completed: {ok}/{len(results)}, Failed: {fail}/{len(results)}")
    for r in results:
        detail = r["error"][:60] if r["error"] else r["result"][:60]
        log(f"  {r['role']:20s} {r['status']:12s} {r['elapsed_s']:6.1f}s  {r['msg_count']:2d} msgs  {detail}")

    if fail > 0 and ok > 0:
        log(f"\nHypothesis CONFIRMED: First {ok} succeeded, then failures began.")
    elif fail == 0:
        log(f"\nHypothesis REJECTED: All {ok} agents succeeded.")
    elif ok == 0:
        log(f"\nAll agents failed — may be a config/env issue, not sequential.")


if __name__ == "__main__":
    main()
