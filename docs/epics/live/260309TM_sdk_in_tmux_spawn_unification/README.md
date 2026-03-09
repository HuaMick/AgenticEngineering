# Epic: SDK-in-Tmux Spawn Unification

## Problem Statement

The Claude Agent SDK's `query()` function **cannot be called more than once per Python process**. After the first call completes, the spawned `claude` child process becomes a zombie (never reaped), internal SDK state corrupts, and the second call silently kills the parent process (no exception, no signal).

This breaks the planning loop (`planner_loop.py`), which calls `query()` sequentially for 5+ agents (explore -> story -> planner -> reviewer -> orchestration). Only the first agent succeeds; subsequent agents crash the process.

## Root Cause (Confirmed via Testing)

1. SDK's `query()` spawns `claude --output-format stream-json` via `anyio.open_process()`
2. After `query()` returns, the child process becomes zombie state `Z <defunct>`
3. SDK never calls `waitpid()` to reap it
4. Internal transport state (pipes, streams) is not cleaned up
5. Second `query()` call causes silent process death

**Evidence**: `scripts/test_sdk_sequential_spawn.py` — single spawn works, second spawn kills process. Subprocess isolation (1 process per query) works 5/5.

**Known upstream issues**: SDK #434 (OOM on sequential calls), #515 (exit code 1), #573 (CLAUDECODE env inheritance), #1089 (orphaned subprocesses never terminate).

## Solution: SDK Inside Tmux Panes

Instead of calling `query()` multiple times in one process, spawn each agent in its own **tmux pane** running the SDK. This gives:

- **Tmux** handles process isolation (each agent = separate OS process, no zombie issue)
- **SDK** provides structured data (cost, turns, usage) — one `query()` call per process
- **Visual monitoring** — `tmux attach` to watch agents work live
- **Natural cleanup** — tmux manages process lifecycle

### Architecture

```
Orchestrator (planner_loop.py or orchestration.py)
  |
  ├─ tmux new-session -d -s agent-explore
  │     └─ python3 sdk_pane_runner.py --role explore --epic <folder>
  │           └─ SDK query() → streams to terminal + writes SessionResult to state store
  │
  ├─ wait_for_session(session_id)  # polls state store
  │
  ├─ tmux new-session -d -s agent-story
  │     └─ python3 sdk_pane_runner.py --role story-generator --epic <folder>
  │           └─ SDK query() → streams to terminal + writes SessionResult to state store
  │
  └─ ... (sequential, one at a time)
```

The `sdk_pane_runner.py` script:
1. Imports SDK, constructs `ClaudeAgentOptions` with role-specific tools/timeouts
2. Calls `query()` exactly once (safe — fresh process)
3. Streams messages to stdout (visible in tmux pane)
4. Writes structured `SessionResult` (cost, turns, usage) to session state store
5. Exits — tmux pane closes, process fully cleaned up

## Scope

### In Scope
- Unified tmux+SDK spawn path for all agent spawns
- Structured data capture (cost, turns, usage) from tmux-spawned agents
- Planning loop migration from SDK-first to tmux-first
- Session state enrichment with SDK metrics
- Existing test updates

### Out of Scope
- SDK upstream bug fix (reported, not our responsibility)
- New tmux layout/dashboard features
- Ralph loop changes (uses separate spawn mechanism)
- Agent guidance content changes

## Key Files

### Must Change
- `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py` — migrate _run_role_agent to tmux
- `modules/AgenticCLI/src/agenticcli/commands/session.py` — unified spawn path, wrapper updates
- `modules/AgenticCLI/src/agenticcli/utils/sdk_runner.py` — SDK pane runner entry point

### May Change
- `modules/AgenticCLI/src/agenticcli/workflows/orchestration.py` — enrich with SDK metrics
- `modules/AgenticCLI/src/agenticcli/utils/tmux_layout.py` — pane helpers
- `modules/AgenticCLI/src/agenticcli/utils/session_diagnostics.py` — new error patterns

### Tests
- `tests/test_planner_loop.py` — update mocks for tmux path
- `tests/test_orchestration_workflow.py` — verify SDK metrics flow
- `tests/test_spawn_subprocess_agentic.py` — new integration tests
- `tests/integration/test_tmux_spawn.py` — real tmux spawn tests

## Implementation Results

### Phases Completed
- **P1-P4**: Core SDK pane runner, tmux spawn integration, planning loop migration, execution runner enrichment
- **P5**: Cleanup — deprecated SDK-direct path removed, `--no-sdk` flag removed, transport column added to session list
- **P8**: Code consolidation — 7 new utility modules extracted:
  - `utils/sdk_pane_runner.py` — tmux pane entry point (one `query()` per process)
  - `utils/context_file.py` — centralized context file writing
  - `utils/retry.py` — unified retry/backoff utilities
  - `utils/session_id.py` — session ID generation and tmux naming
  - `utils/spawn_command.py` — centralized spawn command builder
  - `utils/transport.py` — transport selection logic (sdk-tmux > tmux > subprocess)
  - `utils/session_state.py` — state lifecycle helpers + `read_sdk_metrics()`, `mark_failed()` adopted across 4 files
- **P9**: Test coverage gaps filled — session_diagnostics.py (26 tests), SDK metrics (8 tests), transport (6 tests), transport column (4 tests)
- **P10**: Stale reference cleanup — `--no-sdk` removed, comments fixed, transport metadata corrected
- **P11**: Deprecation cleanup — `--plan` → `--epic` migration in spawn_command.py, epic.py, session.py; AGENTIC_FORCE_SDK_DIRECT test coverage (4 new tests)
- **P12**: Documentation — standalone architecture doc (`docs/SDK_TMUX_ARCHITECTURE.md`), README update
- **P13**: UAT — end-to-end verification of sdk-tmux spawn, session list transport display, cost aggregation, zombie-free planning loops, atomic state writes

### Key Metrics
- New utility modules: 7 created (sdk_pane_runner, context_file, retry, session_id, spawn_command, transport, session_state)
- Manual boilerplate eliminated: ~60 lines of failure_reason dict construction
- Duplicate patterns consolidated: spawn commands (4→1), retry logic (3→1), metrics reading (2→1)
- Test coverage added: ~48 new tests across 5 test files
- Session diagnostics: 0 → 26 tests (268 lines now fully covered)
- AGENTIC_FORCE_SDK_DIRECT: 0 → 4 dedicated tests

### Architecture After Migration
- Default spawn transport: `sdk-tmux` (SDK inside tmux pane)
- Fallback chain: sdk-tmux → tmux → subprocess
- Debug override: `AGENTIC_FORCE_SDK_DIRECT=1` for SDK-direct path (warning logged)
- Session state written atomically by sdk_pane_runner.py (temp file + `os.replace()`)
- Metrics (cost, turns, duration, usage) available for all sdk-tmux sessions
- Architecture reference: [`docs/SDK_TMUX_ARCHITECTURE.md`](../../SDK_TMUX_ARCHITECTURE.md)

### Remaining Known Issues
- Ralph loop not integrated with sdk-tmux path (uses separate spawn mechanism)
- `session spawn --plan` flag still accepted as deprecated alias (not removed, for backward compat)
- `agentic ralph next` command not yet registered in CLI
