# Fix TinyDB File Lock Not Released on Agent Crash

## Objective

Harden the `FileLock` implementation in `state.py` and the epic orchestration lock in `epic_lock.py` so that lock files are automatically released when an agent process crashes (SIGKILL, OOM, uncaught exception). Currently, agent crashes leave orphaned `.lock` files on disk that block subsequent agents from acquiring the TinyDB write lock, requiring manual intervention.

## Problem Analysis

The current `FileLock` uses `os.open()` with `O_CREAT | O_EXCL` to create an exclusive lock file, and stores the owning PID. On contention, it checks whether the lock-holder PID is alive. This approach has several failure modes:

1. **No OS-level auto-release** — The lock file persists after process death; only PID-based stale detection can recover, but that requires another process to contend on the lock.
2. **PID recycling** — If the OS reuses the crashed process's PID, stale detection falsely concludes the lock is still valid, causing indefinite lockout.
3. **No lock age limit** — No maximum lock age means a recycled PID can hold the lock forever.
4. **No proactive cleanup** — No `atexit` handler, no signal handlers (SIGTERM/SIGINT).
5. **Race condition** — Two processes can simultaneously detect a stale lock and both attempt force-release + re-acquire.
6. **Silent recovery** — Stale lock recovery has no logging, making debugging difficult.

The `epic_lock.py` has analogous issues with its JSON-based lock file.

## Solution

### Layer 1: `fcntl.flock()` (Primary)
Replace file-existence locking with POSIX `fcntl.flock()`. The kernel automatically releases flocks when the file descriptor is closed — including on SIGKILL, OOM, or any process termination. This eliminates the root cause.

### Layer 2: Lock age expiration (Secondary)
Add a timestamp to lock files. If a lock file is older than `max_age` (default: 5 minutes), treat it as stale regardless of PID status. This handles NFS/cross-platform edge cases and PID recycling.

### Layer 3: Cleanup infrastructure
- `atexit` handler for orderly shutdown
- Signal handlers (SIGTERM, SIGINT) for graceful cleanup
- Global lock registry tracking all active `FileLock` instances

## Phases

### Phase 1: Harden FileLock (`harden-filelock`)
Rewrite the `FileLock` class in `state.py` to use `fcntl.flock()` as the primary locking mechanism. Add lock-age secondary detection, atexit cleanup, and signal handlers. Maintain backward-compatible API (context manager, `acquire()/release()`).

### Phase 2: Harden Epic Lock (`harden-epic-lock`)
Update `epic_lock.py` to either use the hardened `FileLock` or apply `fcntl.flock()` directly. Ensure orchestration locks also auto-release on crash.

### Phase 3: Test (`test`)
Comprehensive test coverage for crash recovery scenarios: fcntl auto-release on process death, lock age expiration, PID recycling handling, atexit cleanup, signal handler cleanup. Update existing tests for new implementation.

### Phase 4: UAT (`uat`)
Validate against affected user stories using test-uat strategy.

## Affected Stories

- **US-SET-017**: TinyDB Epic Repository - CRUD Operations ("FileLock wraps ALL write operations")
- **US-PLN-063**: Persistent Execution State ("FileLock ensures concurrent agents cannot corrupt state")
- **US-PLN-082**: Epic CRUD Operations (directly uses FileLock)
- **US-SES-008**: Cleanup Dead Processes (detects/removes dead process artifacts)
- **US-PLN-067**: Re-Planning After Failure (recovery from crashed agents)

## Dependencies and Prerequisites

- Python 3.12+ (current project standard)
- `fcntl` module (POSIX only — Linux/macOS; not Windows)
- `psutil` (optional, already used for PID checking)
- No external dependencies added

## Impacted Artifacts

| Artifact | Impact |
|----------|--------|
| `agenticguidance/services/state.py` | **Major** — FileLock class rewritten |
| `agenticcli/utils/epic_lock.py` | **Major** — Lock mechanism replaced |
| `agenticguidance/services/epic_repository.py` | **Minor** — No API change, uses FileLock internally |
| `agenticguidance/services/claude_session.py` | **Minor** — Uses FileLock, benefits from fix |
| `agenticguidance/services/question.py` | **Minor** — Uses FileLock, benefits from fix |
| `tests/test_plan_repository_filelock.py` | **Major** — Tests updated for new behavior |
| `tests/test_epic_lock.py` | **Major** — Tests updated for new behavior |

## Success Criteria

1. When an agent process is killed with SIGKILL while holding a TinyDB lock, subsequent agents can acquire the lock without manual intervention.
2. Lock files older than `max_age` are automatically treated as stale, even if the PID has been recycled.
3. All existing `FileLock` consumers (EpicRepository, StateRegistry, SessionStateService, QuestionQueue) work without API changes.
4. All existing tests pass (with updates for new behavior).
5. New tests cover: crash recovery, PID recycling, lock age expiration, atexit cleanup, signal handlers.
6. UAT validates affected user stories pass.

## Open Questions

None — the solution approach is well-understood and `fcntl.flock()` is a proven POSIX mechanism used extensively in production systems.
