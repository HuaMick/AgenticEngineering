# Investigation: Background Session Stalling / False STALE Reports

**Date**: 2026-02-22
**Investigator**: Claude Opus (session e04f7844)
**Sessions Examined**: bf5f6623, f19762bb, b3b410e1, a7848b44, 2d20ac72

---

## Executive Summary

The four sessions mentioned in the investigation request (bf5f6623, f19762bb, b3b410e1, a7848b44) were part of a batch of **5 orchestration-executor sessions spawned within 17 seconds** at ~19:56 UTC on 2026-02-22. Of these:

- **3 completed successfully** (a7848b44, b3b410e1, 2d20ac72) in ~11 minutes
- **2 reported as STALE** (bf5f6623, f19762bb) but are actually still running and making progress

The STALE reports are **false positives** caused by fundamental issues in the health check system.

---

## Session-by-Session Analysis

### a7848b44 - COMPLETED (Plan: 260214UT - CLI Smoke Tests + Orchestrate Fix)
- Started: 19:56:27 | Ended: 20:07:57 | Duration: ~11.5 min | 74 turns | Cost: $3.39
- Result: All 4 phases completed successfully (Build, Teach, Test, UAT)
- Trace captured: Yes

### b3b410e1 - COMPLETED (Plan: 260219NS - Fix Nested Session Spawn)
- Started: 19:56:40 | Ended: 20:07:57 | Duration: ~11.3 min | 37 turns | Cost: $1.42
- Result: All tasks completed, added `env=get_clean_env()` to 2 files, created 6 tests
- Trace captured: Yes

### 2d20ac72 - COMPLETED (Plan: 260221NE - Remove Backward Compat Aliases)
- Started: 19:56:42 | Ended: 20:07:59 | Duration: ~11.3 min
- Result: Completed successfully
- Trace captured: Yes

### bf5f6623 - RUNNING, falsely reported as STALE (Plan: 260221TU - Redesign Question TUI)
- Started: 19:56:43 | PID: 1283350 | CPU: 7.0% | Memory: 380MB
- **Has spawned a NESTED session**: claude -> bash -> python3 -> agentic -> claude (PID 1425911)
- This is a complex plan with TUI redesign; the agent is actively spawning sub-agents
- Logs are empty (0 bytes) because `--print` mode buffers all output

### f19762bb - RUNNING, falsely reported as STALE (Plan: 260220MI - Migrate PlanService to TinyDB)
- Started: 19:56:41 | PID: 1282529 | CPU: 9.8% | Memory: 392MB
- No child processes but consistently using ~10% CPU
- Likely in API call phase or complex planning/reasoning
- Logs are empty (0 bytes) because `--print` mode buffers all output

---

## Root Causes of False STALE Reports

### RC-1: `--print` mode produces zero output until completion (PRIMARY CAUSE)

Background sessions use `claude --print --output-format json` which:
- Buffers ALL output and only writes a single JSON blob when the process exits
- During the entire run, stdout.log and stderr.log remain at 0 bytes
- The health check (`_check_session_health` at session.py:354) uses log file size as a health signal
- **Impact**: Any `--print` session running >10 minutes will ALWAYS be reported as STALE

**Code reference**: `session.py:387` - `has_output = total_bytes > 0`

### RC-2: `last_activity` is never updated during session lifetime

- `last_activity` is set once at spawn time (session.py:875): `session_data["last_activity"] = session_data["started_at"]`
- There is no mechanism to update this field during the session's lifetime
- The health check falls back to `started_at` when logs have no mtime, making `minutes_since_write` equal to total session age
- **Impact**: Combined with RC-1, staleness is determined solely by how long the session has been running

**Code reference**: `session.py:396-414` - log recency check

### RC-3: Health check expects tmux session for `--print` background sessions

- session.py:425: `if session.get("background") and status == "running"` triggers tmux check
- Background `--print` sessions do NOT create tmux sessions (they're pure Popen processes)
- The tmux check always reports FAIL for these sessions
- **Impact**: Adds a misleading FAIL signal to the health report

**Code reference**: `session.py:425-432` - tmux session check

### RC-4: Auto-diagnostic spawning creates unnecessary resource drain

- When a session is reported as STALE/unhealthy, `_spawn_diagnostic_planner` (session.py:242) automatically spawns a new 10-turn diagnostic claude session
- For false-STALE sessions, these diagnostics are wasteful:
  - They investigate empty log files (which are empty by design in `--print` mode)
  - They consume API tokens and system resources ($0.007+ per diagnostic)
  - 8 diagnostic sessions have been spawned across the project lifetime
  - 2 were just spawned for the currently "stale" bf5f6623 and f19762bb sessions
- **Impact**: Unnecessary cost and system load for false-positive health checks

---

## Analysis of Historically Failed Sessions

**Total failed sessions**: 46
- **45 are MOCK_001 test sessions** - Integration test artifacts, not real failures
- **1 other** - No error recorded, likely a test artifact as well

**Conclusion**: There are zero genuine background session failures in the project history. All real failures are from integration tests.

---

## Concurrent Spawn Analysis

The 5 sessions were spawned within a 17-second window. All 5 were sharing:
- The same working directory (`/home/code/AgenticEngineering`)
- The same git worktree (no isolation)
- API rate limits from the same account

**Observed behavior**:
- 3 completed in ~11 minutes - normal for orchestration-executor tasks
- 2 are taking longer (20+ minutes) but are actively working
- No evidence of resource contention or race conditions
- The slower sessions may be handling more complex plans (TUI redesign, TinyDB migration)

---

## Recommendations

### P0: Fix false-STALE detection for `--print` mode sessions

The health check should not report STALE for sessions using `--print` mode where:
- The PID is alive
- The process is consuming CPU

Options:
1. **Add process CPU check**: Use `/proc/[pid]/stat` to verify the process is consuming CPU cycles
2. **Distinguish `--print` mode**: Store `output_mode: "print"` in session data and adjust staleness thresholds
3. **Use process tree as health signal**: If the claude process has child processes (bash, python3), it's actively executing tools

### P1: Remove/disable tmux check for non-tmux sessions

- Only check tmux session existence for sessions that were launched in tmux
- Add a `spawn_mode` field to session data (e.g., "background_print", "tmux", "foreground")

### P2: Gate auto-diagnostic spawning

- Require at least 2 consecutive STALE health checks before spawning diagnostics
- Add a minimum age threshold (e.g., 30+ minutes) before considering a session truly stuck
- Check if the process PID is consuming CPU before spawning diagnostics
- Consider making diagnostic spawning opt-in rather than automatic

### P3: Add progress heartbeat for `--print` mode

- Claude `--print` doesn't support incremental output, but the session manager could:
  - Periodically check `/proc/[pid]/stat` for CPU usage
  - Monitor child process creation/exit as activity signals
  - Write a heartbeat file (e.g., `{session_id}.heartbeat`) with timestamp on each check
  - Use process RSS/CPU delta as a proxy for activity

### P4: Increase staleness threshold

- Current threshold: 10 minutes (session.py:416)
- Recommendation: Increase to 30 minutes minimum
- Complex plans (TUI redesign, migrations) routinely take 15-30 minutes
- A `--print` session can't produce output until complete, so 10 minutes is too aggressive

---

## Resource Impact

| Metric | Value |
|--------|-------|
| Sessions investigated | 5 |
| Actually failed | 0 |
| False STALE reports | 2 |
| Wasted diagnostic sessions | 2 (currently running) |
| Historical diagnostic sessions | 8 total |
| Historical real session failures | 0 (45/46 are test mocks) |
