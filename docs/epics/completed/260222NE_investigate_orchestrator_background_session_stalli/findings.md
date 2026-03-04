# Investigation: Orchestrator Background Session Stalling

**Date**: 2026-02-22
**Plan**: 260222NE_investigate_orchestrator_background_session_stalli
**Status**: Complete
**Investigators**: Session e04f7844 (false STALE analysis), Session 5794b627 (quantitative root cause)

## Symptom

Background sessions spawned with `-b` flag stall instantly with no logs. Two
distinct manifestations:

1. **Orchestration planning loops** (`agentic session orchestrate planning -b`):
   Background process stalls with empty log directories.
2. **Session spawns** (`agentic session spawn --role <role> -b`): `claude`
   process exits immediately with nested-session error or hangs with no output.

---

## Quantitative Evidence

### Session Log File Analysis (ALL historical sessions)

| Metric | Count | Percentage |
|--------|-------|------------|
| Total log file pairs on disk | 1,340 | 100% |
| Empty stdout logs (0 bytes) | 1,161 | 86.6% |
| Non-empty stdout logs | 179 | 13.4% |
| Empty stderr logs (0 bytes) | 1,327 | 99.0% |
| Non-empty stderr logs | 13 | 1.0% |

### Tracked Background Session Analysis

| Metric | Count | Percentage |
|--------|-------|------------|
| Total tracked background sessions | 214 | 100% |
| Empty stdout (0 bytes) | 34 | 15.9% |
| Non-empty stdout | 180 | 84.1% |
| Nested-session error in stderr | 13 | 6.1% |
| Zero bytes in BOTH stdout and stderr | 18 | 8.4% |

All 13 sessions with the nested-session error occurred on 2026-02-21 before a
local fix was applied. The remaining 5 zero-output sessions are either currently
running (2) or were manually stopped after appearing to stall (3).

### Orchestration Loop State Analysis

| Metric | Count |
|--------|-------|
| JSON state files (foreground runs) | 277 |
| Directories (background log dirs) | 89 |
| **Overlap between JSON and directories** | **0** |

Zero overlap confirms the background orchestration path has never successfully
completed initialization — directories are created but state is never saved,
meaning the subprocess fails before `_store.save()` is reached.

### Orphaned Resources

~977 log file pairs have no corresponding session state file (1,340 total minus
363 tracked sessions). These are artifacts from historical spawn attempts that
failed before state persistence.

---

## Root Causes

### RC-1: Missing `env=get_clean_env()` in session.py (COMMITTED CODE) — PRIMARY

**File**: `modules/AgenticCLI/src/agenticcli/commands/session.py`

The **committed** version of `session.py` has NO `env=` parameter in any
`subprocess.Popen()` call. When `cmd_spawn()` spawns `claude` from inside a
Claude Code session, the child inherits `CLAUDECODE=1` and
`CLAUDE_CODE_ENTRYPOINT=sdk-cli`, causing immediate rejection:

```
Error: Claude Code cannot be launched inside another Claude Code session.
```

A **local fix exists** (uncommitted):
- `subprocess_utils.py` (new file) provides `get_clean_env()`
- `session.py` imports and uses it in all 3 Popen calls (lines 364, 948, 1032)

**These changes must be committed to resolve the primary issue.**

### RC-2: Missing `env=get_clean_env()` in orchestrate.py

**File**: `modules/AgenticCLI/src/agenticcli/commands/orchestrate.py:96`

Same issue as RC-1 but for the orchestration background path. The spawned
Python subprocess inherits `CLAUDECODE=1`. While this doesn't directly affect
the Python process, it propagates to all downstream `agentic` CLI calls.

### RC-3: `--print` mode stdout buffering (FALSE STALE cause)

Background sessions use `claude --print --output-format json` which:
- Buffers ALL output until process exit (stdout is a file, not TTY)
- During the entire run, stdout.log remains 0 bytes
- Health check uses log file size as a health signal
- Any `--print` session running >10 minutes triggers false STALE report

**Evidence**: Sessions bf5f6623 and f19762bb were falsely reported STALE while
actively running (consuming CPU, spawning child processes).

### RC-4: No immediate spawn failure detection in orchestrate.py

After `subprocess.Popen()`, `orchestrate.py` reports "running" without checking
if the process actually started. `session.py` has a 1-second check but
`orchestrate.py` lacks it entirely.

### RC-5: `wait_for_session()` has no dead-process detection

**File**: `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py:278-298`

The polling loop continues sleeping even when `_get_session_status()` returns
`None` (CLI call failed). A dead session can block the orchestrator for up to
10 minutes (600s timeout with 10s polls).

### RC-6: `planner_loop.py` subprocess calls don't clean environment

All 14 `subprocess.run()` calls inherit dirty env. While `session.py` (with
the local fix) strips env vars at the final `claude` Popen, intermediate
`agentic` CLI processes all run with `CLAUDECODE=1`.

### RC-7: Health check false positives for `--print` mode

- `has_output` signal: Always FAIL for running `--print` sessions (session.py:387)
- `tmux_session` signal: Always FAIL for non-tmux sessions (session.py:425)
- `recent_activity` signal: Stale after 10 minutes for any session (threshold too low)
- Auto-diagnostic spawning wastes resources on false positives

---

## Call Chain Analysis

### Session spawn with `-b` flag

```
Claude Code session (CLAUDECODE=1 in env)
  └── agentic session spawn --role <role> --plan <folder> -b
        └── cmd_spawn() in session.py
              ├── Builds: claude --print --dangerously-skip-permissions
              │           --output-format json <prompt>
              ├── Opens: ~/.agentic/sessions/logs/<sid>.stdout.log
              ├── COMMITTED CODE: subprocess.Popen(cmd, ...)
              │     └── NO env= → claude gets CLAUDECODE=1 → REJECTED
              ├── LOCAL FIX: subprocess.Popen(cmd, ..., env=get_clean_env())
              │     └── CLAUDECODE stripped → claude starts OK
              │     └── Output buffered until exit → 0 bytes during run
              ├── time.sleep(1) → checks if PID alive
              └── Returns session_id
```

### Orchestration planning loop with `-b` flag

```
Claude Code session (CLAUDECODE=1 in env)
  └── agentic session orchestrate planning -b
        └── _run_planning_loop(background=True)
              ├── Creates: ~/.agentic/orchestration_loops/orch-xxx/
              ├── Opens: stdout.log, stderr.log in that directory
              ├── subprocess.Popen([python3, -m, agenticcli.entry, ...])
              │     └── NO env= → child inherits CLAUDECODE=1
              ├── Reports "started in background"
              └── Returns (NO spawn failure check)

              In child process:
              └── _run_planning_loop(background=False)
                    └── PlanningRunner.run()
                          ├── spawn_explore_agent() → agentic session spawn -b
                          │     └── cmd_spawn() → claude --print ...
                          │           └── [COMMITTED] NO env= → FAILS
                          │           └── [LOCAL FIX] env stripped → OK
                          ├── wait_for_session() → polls up to 600s
                          │     └── If session failed, blocks here
                          └── [Remaining steps never reached]
```

---

## Recommended Fixes

### Priority 0: Commit existing local fixes (CRITICAL)

1. Commit `modules/AgenticCLI/src/agenticcli/utils/subprocess_utils.py`
2. Commit `modules/AgenticCLI/src/agenticcli/commands/session.py` changes

These uncommitted files contain the fix for RC-1 (the primary cause). Without
committing, other worktrees and fresh clones will still have the bug.

### Priority 1: Fix orchestrate.py env and failure detection

```python
# orchestrate.py, background Popen (line 96)
from agenticcli.utils.subprocess_utils import get_clean_env

process = subprocess.Popen(
    cmd, cwd=working_dir,
    stdin=subprocess.DEVNULL,
    stdout=stdout_log, stderr=stderr_log,
    start_new_session=True,
    env=get_clean_env(),  # ADD THIS
)

# Add after Popen, before returning:
time.sleep(1)
if not is_process_running(process.pid):
    state["status"] = "failed"
    state["error"] = "Process died immediately"
    _store.save(state)
    print_error(f"Loop {loop_id} failed immediately (PID: {process.pid})")
    return
```

### Priority 2: Fix wait_for_session dead-process detection

```python
def wait_for_session(self, session_id, timeout=600, poll_interval=10):
    deadline = time.time() + timeout
    consecutive_failures = 0
    while time.time() < deadline:
        status = self._get_session_status(session_id)
        if status is None:
            consecutive_failures += 1
            if consecutive_failures >= 3:
                return "failed"
        else:
            consecutive_failures = 0
            if status in ("completed", "failed", "stopped"):
                return status
        time.sleep(poll_interval)
    return None
```

### Priority 3: Fix false STALE health checks

- Add PID CPU check via `/proc/[pid]/stat` before reporting STALE
- Skip tmux check for non-tmux `--print` sessions
- Increase stale threshold from 10 minutes to 30 minutes
- Gate auto-diagnostic spawning (require 2+ consecutive STALE checks)

### Priority 4: Clean env for planner_loop.py

Add `env=get_clean_env()` to all `subprocess.run()` calls for defense in depth.

---

## Files Involved

| File | Status | Role |
|------|--------|------|
| `modules/AgenticCLI/src/agenticcli/commands/session.py` | Modified (uncommitted) | Primary spawn logic — has local fix |
| `modules/AgenticCLI/src/agenticcli/utils/subprocess_utils.py` | New (uncommitted) | `get_clean_env()` utility |
| `modules/AgenticCLI/src/agenticcli/commands/orchestrate.py` | Committed | Background orchestration spawn — needs fix |
| `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py` | Committed | Workflow that spawns sessions — needs env fix |
| `modules/AgenticCLI/src/agenticcli/utils/state_store.py` | Committed | Session state persistence |

---

## Summary Table

| # | Component | Issue | Severity | Status |
|---|-----------|-------|----------|--------|
| RC-1 | session.py Popen | Missing env=get_clean_env() | Critical | **Local fix exists (uncommitted)** |
| RC-2 | orchestrate.py Popen | Missing env=get_clean_env() | Critical | Not fixed |
| RC-3 | --print mode buffering | 0-byte stdout during run | High | Design limitation |
| RC-4 | orchestrate.py | No spawn failure detection | High | Not fixed |
| RC-5 | wait_for_session() | No dead-process detection | High | Not fixed |
| RC-6 | planner_loop.py | subprocess.run no env cleanup | Medium | Not fixed |
| RC-7 | Health check system | False STALE for --print mode | Medium | Not fixed |
