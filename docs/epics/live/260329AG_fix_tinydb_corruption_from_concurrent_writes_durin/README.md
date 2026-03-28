# Epic: Fix TinyDB Corruption from Concurrent Writes During Lock Failure

## Objective

Eliminate TinyDB database corruption caused by concurrent write access to
`~/.agentic/epics.db` when multiple processes (CLI commands, SDK agents in
tmux panes, orchestration runners) attempt simultaneous mutations. The root
causes are: (1) TinyDB's JSONStorage performs non-atomic file writes, (2) the
`EpicRepository.__init__` opens TinyDB without holding the FileLock, (3)
`TimeoutError` from lock acquisition is unhandled in all repository write
methods, and (4) there is no corruption recovery when the JSON file is
truncated or malformed from a mid-write crash.

## Affected User Stories

- **US-SET-017**: TinyDB Epic Repository - CRUD Operations
- **US-SET-018**: TinyDB Ticket Storage and Queries
- **US-SET-020**: CLI Epic Commands Use EpicRepository
- **US-SET-022**: TinyDB Database Location and Lifecycle

## Root Cause Analysis

1. **Non-atomic writes**: TinyDB's default `JSONStorage` calls `json.dump()`
   directly to the file handle. If the process crashes mid-write or another
   process reads during the write, the file contains truncated/invalid JSON.

2. **Unlocked initialization**: `EpicRepository.__init__()` calls
   `TinyDB(str(self.db_path))` without acquiring `self._lock`. If another
   process is mid-write, TinyDB reads a partially-written file into its
   cache, leading to data loss or JSONDecodeError.

3. **Unhandled TimeoutError**: `FileLock.__enter__` raises `TimeoutError`
   after 10s. No EpicRepository method catches this — the exception
   propagates uncaught, potentially interrupting a partially-started write.

4. **No corruption recovery**: Unlike `StateRegistry._load()` which returns
   empty data on `JSONDecodeError`, the `EpicRepository` has no fallback.
   A corrupted `epics.db` crashes every subsequent operation.

5. **Never-closed repositories**: `PlannerLoopWorkflow` (line 168) and
   `ExecutionRunner` keep `EpicRepository` instances open indefinitely
   with no `close()` call, leading to stale file handles and cache.

## Phases Overview

### Phase 1: Atomic Storage Backend (`P1_atomic_storage`)
Replace TinyDB's `JSONStorage` with a custom `AtomicJSONStorage` that writes
to a temporary file and renames atomically. Add corruption detection and
automatic backup/recovery.

### Phase 2: Lock Hardening (`P2_lock_hardening`)
Wrap `EpicRepository.__init__` TinyDB open in lock acquisition. Add graceful
`TimeoutError` handling with retry-with-backoff in write methods. Increase
lock timeout for known slow paths (SDK agent cold-start).

### Phase 3: Repository Lifecycle (`P3_lifecycle`)
Add `__enter__`/`__exit__` context manager protocol to `EpicRepository`.
Ensure `close()` is called in `PlannerLoopWorkflow`, `ExecutionRunner`, and
all CLI command paths. Add `refresh()` calls before reads after external
writes.

### Phase 4: Testing (`P4_testing`)
Multi-process concurrent write tests (not just threading). Corruption
recovery tests. Lock timeout handling tests. Atomic write crash simulation
tests.

### Phase 5: UAT (`P5_uat`)
Validate all affected user stories pass with the new protections. Simulate
real-world concurrent agent access patterns.

## Dependencies and Prerequisites

- Python `os.rename()` atomicity on the target filesystem (Linux ext4/tmpfs: yes)
- TinyDB's `Storage` API for custom backend implementation
- No new external dependencies required — uses stdlib only

## Success Criteria

1. `epics.db` never contains truncated or invalid JSON after any crash scenario
2. Concurrent EpicRepository writes from separate processes are safely serialized
3. A corrupted `epics.db` is automatically recovered from backup with logged warning
4. `TimeoutError` from lock acquisition is caught and retried (or fails gracefully with clear error message)
5. All EpicRepository instances are properly closed via context managers or explicit `close()`
6. All existing tests continue to pass (AgenticGuidance + AgenticCLI test suites)
7. All affected user stories (US-SET-017, US-SET-018, US-SET-020, US-SET-022) pass UAT

## Impacted Artifacts

| Artifact | Type | Impact |
|---|---|---|
| `agenticguidance/services/state.py` | Service | FileLock enhancements (retry, backoff) |
| `agenticguidance/services/epic_repository.py` | Service | AtomicJSONStorage, locked init, context manager, error handling |
| `agenticcli/workflows/planner_loop.py` | Workflow | Repository lifecycle (close on exit) |
| `agenticcli/workflows/orchestration.py` | Workflow | Repository lifecycle (close on exit) |
| `agenticcli/commands/epic.py` | CLI | Context manager usage |
| `tests/test_plan_repository_filelock.py` | Test | Extended concurrent/corruption tests |

## Open Questions

None — the fix is fully scoped within existing architecture.
