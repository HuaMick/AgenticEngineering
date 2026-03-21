# Research Findings: Orchestration Spawn Timeout / Premature Agent Exit

**Epic:** 260308FX_fix_orchestration_spawn_timeout_agents_exit_premat
**Date:** 2026-03-08
**Researcher:** story-generator agent (IM_001)

---

## Executive Summary

Spawned agents exit prematurely (~9 seconds) due to **two independent root causes**:
1. **Environment variable leak** — `CLAUDECODE=1` inherited by child processes triggers Claude Code's nested-session guard, causing immediate exit.
2. **`--print` mode in subprocess fallback** — Forces single-turn, non-agentic execution (no tool use, no multi-turn).

A partial mitigation exists: `--tmux --no-sdk` forces the tmux spawn path which handles env isolation and uses agentic mode (`-p`). However, the subprocess and SDK paths remain broken, and several reliability improvements are needed.

---

## Architecture Overview

### Three Spawn Paths

| Path | Trigger | Command Mode | Env Isolation | Agentic? | Status |
|------|---------|-------------|---------------|----------|--------|
| **SDK** | Background + SDK available + not `--no-sdk` | In-process via `claude_agent_sdk` | `get_clean_env()` (unreliable) | Yes | ❌ Broken |
| **Tmux** | `--tmux` flag | `claude -p` (pipe mode) | `unset CLAUDECODE` in bash wrapper | Yes | ✅ Working |
| **Subprocess** | Fallback (no SDK, no tmux) | `claude --print` (single-turn) | `get_clean_env()` at Popen | No | ❌ Non-agentic |

### Execution Flow

```
Claude Code (CLAUDECODE=1)
  → ExecutionRunner._run_phase()
    → subprocess.run(["agentic", "session", "spawn", "--tmux", "--no-sdk", "-b", ...])
      → cmd_spawn() in session.py
        → tmux new-session → "unset CLAUDECODE; claude -p ..."
          → Agent runs agentically ✅
```

---

## Root Cause Analysis

### RC1: CLAUDECODE Environment Variable Leak

**Mechanism:** Claude Code sets `CLAUDECODE=1` and `CLAUDE_CODE_ENTRYPOINT=claude-code` in the shell environment. When a child `claude` process inherits these variables, it immediately exits with "Claude Code cannot be launched inside another Claude Code session."

**Where it manifests:**
- **SDK path:** `sdk_runner.py` passes `get_clean_env()` to `ClaudeAgentOptions`, but the SDK's internal `subprocess_cli.py` sets `CLAUDE_CODE_ENTRYPOINT="sdk-py"` in `os.environ` before spawning, which can leak.
- **Subprocess path:** Uses `get_clean_env()` which strips the vars, but if SDK has already modified `os.environ`, the cleaning may be stale.

**Existing mitigation:** The tmux path explicitly runs `unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT` inside the tmux bash wrapper before launching `claude`.

**Files:**
- `session.py:759` — tmux wrapper unset
- `subprocess_utils.py:18` — `get_clean_env()` implementation
- `sdk_runner.py:142-145` — SDK env pop/restore (racy)

### RC2: `--print` Mode Is Non-Agentic

**Mechanism:** The subprocess fallback path builds the command with `--print` (line 859), which forces `claude` into single-turn mode: read prompt → generate one response → exit. No tool use, no file reading, no multi-turn conversation.

**Impact:** The agent receives a prompt saying "Read the file at {path} FIRST" but **cannot actually read files** in `--print` mode. It generates a text response and exits.

**Where it manifests:** `session.py:859` — `cmd = list(cmd_base) + ["--print"]`

**Why it exists:** The subprocess fallback has no TTY. The `-p` flag (pipe mode) requires a pseudo-TTY or specific stdin handling. `--print` was chosen as the safe non-TTY option.

### RC3: Missing `--max-turns` (Previously Fixed)

**Mechanism:** Without `--max-turns`, Claude Code uses a small default turn budget. An agent that exhausts its budget in one LLM inference cycle exits in ~9 seconds.

**Status:** ✅ Fixed — `DEFAULT_PHASE_MAX_TURNS = 200` in `orchestration.py:179` and `DEFAULT_BACKGROUND_MAX_TURNS = 200` in `session.py:827`.

---

## Current State of Fixes

### Already Implemented
1. ✅ `DEFAULT_PHASE_MAX_TURNS = 200` — prevents turn-budget exhaustion
2. ✅ `DEFAULT_BACKGROUND_MAX_TURNS = 200` — same for background sessions
3. ✅ `--tmux --no-sdk` in ExecutionRunner — forces the working tmux path
4. ✅ `QUICK_EXIT_THRESHOLD = 30s` — logs warnings for suspiciously fast exits
5. ✅ `unset CLAUDECODE` in tmux bash wrapper — env isolation for tmux path
6. ✅ `get_clean_env()` — strips env vars at Popen level (partial fix)
7. ✅ Dual PID+tmux liveness check in `wait_for_session()` — robust completion detection

### Still Broken / Missing
1. ❌ **SDK env isolation is unreliable** — SDK internally re-sets env vars
2. ❌ **Subprocess fallback is non-agentic** — `--print` mode cannot do real work
3. ❌ **No per-phase retry** — failure aborts entire plan (feedback triggers are jump-backs, not retries)
4. ❌ **No configurable per-phase timeout** — hardcoded 1800s in wait_for_session call
5. ❌ **Quick-exit detection is warn-only** — no automatic retry on suspicious fast exit
6. ❌ **Ralph loop has no StateStore tracking** — tmux path skips completion tracking
7. ❌ **No health check for nested-env detection** — should detect CLAUDECODE before spawning

---

## Proposed Solution Architecture

### Phase 1: Fix Subprocess Fallback (Make it Agentic)
- Replace `--print` with `-p` in subprocess fallback path
- Handle stdin/stdout properly for non-TTY `-p` mode
- Add the context as piped stdin instead of CLI argument
- **Risk:** Medium — `-p` mode may behave differently without TTY

### Phase 2: Harden SDK Env Isolation
- Use `subprocess.Popen` with explicit `env` dict that excludes all CLAUDE* vars
- Add pre-flight env check: if `CLAUDECODE` in os.environ after SDK import, log critical warning
- Consider process-level isolation (spawn SDK in a clean subprocess)
- **Risk:** Low — defensive programming

### Phase 3: Add Auto-Retry on Quick Exit
- When `elapsed < QUICK_EXIT_THRESHOLD` and status == "completed" → treat as suspicious
- Check session log for "cannot be launched inside another" error message
- Auto-retry with explicit env cleaning (force tmux path on retry)
- Max 2 retries with exponential backoff
- **Risk:** Low — retry logic is well-understood

### Phase 4: Configurable Per-Phase Timeouts
- Add `timeout` field to PhaseData in TinyDB
- CLI: `agentic epic phase add --timeout 3600`
- Pass timeout to `wait_for_session()` from phase config
- Default remains 1800s (30 min)
- **Risk:** Very low — additive change

### Phase 5: Pre-Flight Health Check
- Before spawn: check if `CLAUDECODE` is in current env and warn/fix
- Add `agentic session spawn --dry-run` to validate env without actually spawning
- Report which spawn path would be used and whether env is clean
- **Risk:** Very low — diagnostic only

### Phase 6: Better Diagnostics and State Tracking
- Parse session stdout log for known error patterns on completion
- Add `failure_reason` field to session state (env issue, timeout, turn exhaustion, etc.)
- Ralph loop: add StateStore tracking for tmux-spawned sessions
- Add structured error codes to session state
- **Risk:** Low — observability improvement

---

## Key Files

| File | Purpose |
|------|---------|
| `modules/AgenticCLI/src/agenticcli/commands/session.py` | `cmd_spawn()` — all three spawn paths |
| `modules/AgenticCLI/src/agenticcli/workflows/orchestration.py` | `ExecutionRunner._run_phase()` — phase execution |
| `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py` | `wait_for_session()` — completion polling |
| `modules/AgenticCLI/src/agenticcli/utils/subprocess_utils.py` | `get_clean_env()` — env isolation |
| `modules/AgenticCLI/src/agenticcli/utils/sdk_runner.py` | SDK wrapper with env handling |
| `modules/AgenticCLI/src/agenticcli/utils/state_store.py` | Session state JSON persistence |
| `modules/AgenticCLI/src/agenticcli/commands/ralph.py` | Ralph loop spawning |
| `modules/AgenticGuidance/src/agenticguidance/services/epic_repository.py` | TinyDB phase/ticket CRUD |
