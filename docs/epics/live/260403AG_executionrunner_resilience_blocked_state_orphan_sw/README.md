# ExecutionRunner Resilience: Blocked State, Orphan Sweep, Phase Scoping, Logging, Race Fix

## Objective

Harden the `ExecutionRunner` orchestration loop with five resilience improvements:

1. **Blocked State** -- Add a `blocked` phase/ticket status so phases can be explicitly gated (e.g., by unresolved dependencies or max-iteration exhaustion) without conflating with `failed`.
2. **Orphan Sweep** -- Upgrade `_recover_stale_phases()` from a blind reset to a liveness-checked sweep that verifies PID/tmux existence before resetting, and adds age-based stale detection.
3. **Phase Scoping** -- Ensure spawned agents can only query/modify tickets within their assigned phase, preventing cross-phase state bleed.
4. **Structured Logging** -- Replace ad-hoc `logger.info/error` calls with a `PhaseLoggerAdapter` that injects consistent context fields (epic, phase, session_id, agent) and adds phase-transition audit logging.
5. **Race Fix** -- Guard the gap between marking a phase `in_progress` and spawning the agent with atomic try/finally rollback, and add compare-and-swap semantics for phase status transitions to prevent stale-cache overwrites.

## Affected User Stories

| Story ID    | Title                                    | Relevance                              |
|-------------|------------------------------------------|----------------------------------------|
| US-PLN-051  | Phase Status Tracking                    | Blocked state adds new status value    |
| US-PLN-059  | Execute Approved Epic via TinyDB Phases  | Execution loop resilience              |
| US-PLN-063  | Persistent Execution State               | Resume after crash with blocked/orphan |
| US-PLN-065  | Test-Fix Loop Execution                  | Blocked on max-iteration exhaustion    |
| US-PLN-066  | Feedback Trigger Handling                | Failure routing with blocked state     |
| US-SES-004  | Inspect Session Health and Logs          | Structured logging improvements        |
| US-SES-008  | Cleanup Dead Processes                   | Orphan sweep process cleanup           |

## Phases Overview

| Phase | Name                     | Agent         | Tickets | Description                                                            |
|-------|--------------------------|---------------|---------|------------------------------------------------------------------------|
| P1    | Story Writing            | story-writer  | 1       | Write user stories for all resilience features (completed)             |
| P2    | Codebase Exploration     | trace-explorer| 1       | Explore orchestration.py, sdk_pane_runner.py, session state (completed)|
| P3    | Build Planning           | planner-build | 1       | Generate sequenced implementation plan (completed)                     |
| P4    | Dev Session Race Fix     | build-python  | 3       | Session file write-before-spawn, os.utime, negative duration clamping  |
| P5    | Dev Retry Orphan Logging | build-python  | 6       | Blocked state model, retry→blocked, orphan sweep liveness, tmux pipe-pane, PhaseLoggerAdapter |
| P6    | Dev Phase Scoping        | build-python  | 3       | Phase-scoped ticket queries, spawn context scoping, CLI --blocked-reason |
| P7    | Test Planning            | planner-test  | 1       | Design test plan covering all fixes                                    |
| P8    | Test Build               | test-builder  | 7       | Unit tests for all fixes + blocked state + structured logging          |
| P9    | Test Audit Fix           | test-audit    | 1       | Audit test coverage, identify and fix gaps                             |
| P10   | UAT                      | test-uat      | 1       | Story-anchored acceptance validation (7 stories)                       |

## Dependencies and Prerequisites

- **TinyDB backend**: All state changes go through `EpicRepository` (no YAML fallback).
- **FileLock / fcntl.flock()**: Existing locking infrastructure in `agenticguidance.services.state`.
- **epic_lock.py**: Epic-level orchestration lock (prevents concurrent planning+execution).
- **sdk_pane_runner / tmux**: Process isolation for spawned agents.
- **wait_for_session()**: Polling loop in `planner_loop.py` with PID and tmux liveness checks.

No external dependency changes. All modifications are internal to AgenticCLI and AgenticGuidance modules.

## Ticket Summary

### P4: Dev Session Race Fix (3 tickets)
- **DEV_001**: Write session file with status=starting BEFORE spawn (completed)
- **DEV_002**: Add os.utime after os.replace in _write_state (completed)
- **DEV_003**: Clamp negative durations to 0 wherever ended_at is computed (completed)

### P5: Dev Retry Orphan Logging (6 tickets)
- **DEV_004**: After retry exhaustion in _run_phase(), set phase to blocked (completed)
- **DEV_005**: In _recover_stale_phases(), add tmux session liveness check before resetting (completed)
- **DEV_006**: After tmux session spawn, run tmux pipe-pane for session logging (in_progress)
- **DEV_009**: Add `blocked` status to PhaseData status values and `blocked_reason` field (proposed)
- **DEV_010**: Update ExecutionRunner to skip blocked phases, exclude from recovery sweep (proposed)
- **DEV_012**: Create PhaseLoggerAdapter with structured context fields (proposed)

### P6: Dev Phase Scoping (3 tickets)
- **DEV_007**: Add phase_name param to EpicRepository.get_current_ticket (proposed)
- **DEV_008**: In _compile_spawn_context(), accept phase_id for scoped ticket queries (proposed)
- **DEV_011**: Add --blocked-reason flag to agentic epic phase update CLI (proposed)

### P8: Test Build (7 tickets)
- **TB_001**: Tests for session file write-before-spawn race fix
- **TB_002**: Tests for retry exhaustion blocked state
- **TB_003**: Tests for orphan sweep tmux liveness checks
- **TB_004**: Tests for tmux pipe-pane logging
- **TB_005**: Tests for phase-filtered ticket queries
- **TB_006**: Tests for blocked state PhaseData model and ExecutionRunner skip logic
- **TB_007**: Tests for PhaseLoggerAdapter structured context and audit logging

### P9: Test Audit Fix (1 ticket)
- **TA_001**: Audit test coverage for all fixes, identify and fix gaps

### P10: UAT (1 ticket)
- **UAT_001**: Validate all user stories against implementation (US-PLN-051/059/063/065/066, US-SES-004/008)

## Impacted Artifacts

| Artifact                          | Type       | Impact                                         |
|-----------------------------------|------------|-------------------------------------------------|
| `orchestration.py`                | Workflow   | ExecutionRunner: blocked skip, orphan sweep, race guard, logging |
| `epic.py` (PhaseData)             | Domain     | New `blocked` status value, `blocked_reason` field |
| `epic_repository.py`              | Repository | Phase-scoped queries, compare-and-swap update   |
| `epic.py` CLI commands            | CLI        | `--status blocked --blocked-reason` support     |
| `sdk_pane_runner.py`              | Utility    | Session file write-before-spawn, tmux pipe-pane |

## Success Criteria

1. Phases can transition to `blocked` status with a reason; ExecutionRunner skips blocked phases and logs the reason.
2. `_recover_stale_phases()` checks PID/tmux liveness before resetting; phases with live processes are not reset.
3. Age-based stale detection marks phases stuck `in_progress` beyond a configurable threshold as `blocked` (not `pending`).
4. Phase-scoped ticket queries prevent cross-phase ticket modification by spawned agents.
5. Phase status transitions use compare-and-swap to prevent stale-cache overwrites.
6. The gap between `update_phase("in_progress")` and spawn is guarded by try/finally rollback.
7. All log messages from ExecutionRunner include epic, phase, session_id, and agent context.
8. All new behaviors have unit test coverage.
9. UAT validates against affected user stories (US-PLN-051, US-PLN-059, US-PLN-063, US-PLN-065, US-PLN-066, US-SES-004, US-SES-008).

## Open Questions

None -- all implementation patterns are well-established in the existing codebase (FileLock, TinyDB, tmux liveness probes).
