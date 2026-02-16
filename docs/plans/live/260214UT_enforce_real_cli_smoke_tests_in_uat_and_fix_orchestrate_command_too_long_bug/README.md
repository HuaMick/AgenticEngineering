# Plan 260214UT: Enforce Real Tmux Integration Testing

## Problem Statement

The tmux orchestration GUI keeps breaking with obvious bugs that are never caught
before they reach the user. Root cause: **every test either mocks tmux or uses 
`--no-tmux` to bypass it entirely**.

Recent bugs that shipped despite "passing UAT":
1. **`-p` percentage flag bug**: Detached tmux sessions don't support `-p` for splits
2. **`$(cat file)` expansion bug**: `shlex.quote` wrapped the substitution in single
   quotes, blocking shell expansion — Claude never received the system prompt
3. **Missing Enter key**: `send-keys` sent the command but never pressed Enter
4. **Orphaned sessions**: Each run created a new `agentic-orch-*` session without
   cleaning up the old ones — resulted in 7+ zombie sessions

**All of these would have been caught by a test that creates a real tmux session
and checks that 3 panes exist.**

The command-too-long bug (orchestrate.py passing 447-line prompt as CLI arg) is
already fixed — orchestrate.py now uses `tempfile` + `$(cat file)` approach.

## Root Cause

**No real tmux integration tests exist.** Test coverage breakdown:
- `test_tmux_layout.py`: 36 tests, ALL mocked (`mock_subprocess_success`)
- `test_orchestrate_command.py`: mocked subprocess
- Integration tests: used `--no-tmux` flag, bypassing the broken path

## Solution

### 1. Build Phase - Make Tmux Testable

- **Add `--dry-run` flag** to `agentic orchestrate` that creates the tmux layout,
  verifies pane structure, prints layout JSON, then cleans up. This enables
  automated testing of the tmux GUI path without needing Claude to run.
- **Fix `_create_inplace_layout`** which still uses `-p` percentage flags instead
  of the `-l` absolute values that were already applied to `_create_new_session_layout`.

### 2. Teach Phase - Update Guidance

Update guidance files to mandate real CLI smoke tests in UAT phases.
(Unchanged from original plan — the guidance updates are still needed.)

### 3. Test Phase - Real Tmux Integration Tests

Create integration tests that use the ACTUAL tmux binary:
- Create real tmux sessions and verify 3 panes exist
- Verify pane dimensions follow 70/30 and 60/40 splits
- Verify `send-keys` actually delivers commands to panes
- Verify `$(cat file)` shell expansion works inside tmux
- Verify session cleanup kills orphaned sessions
- Use `--dry-run` for smoke tests of the full command

**13 real tmux integration tests across 2 files**, zero mocking.

### 4. UAT Phase - Real Tmux GUI Validation

Validate the actual tmux GUI end-to-end:
- Verify 3-pane layout via `--dry-run`
- Verify pane titles (orchestrator, sessions, questions)
- Verify `$(cat file)` expansion in tmux send-keys
- **Launch full `agentic orchestrate` and verify Claude + dashboards start**
- Verify all integration tests pass
- Verify zombie session cleanup

## Success Criteria

1. `agentic orchestrate --mode planning --dry-run` creates 3-pane layout and exits cleanly
2. Real tmux integration tests verify pane count, dimensions, titles, and send-keys
3. `$(cat file)` expansion is verified working inside tmux
4. Full live launch works (Claude starts, dashboards run, no errors)
5. No orphaned tmux sessions after any test or dry-run
6. Guidance updated to prevent future mock-only UAT

## Files Changed

### Build Phase
- `modules/AgenticCLI/src/agenticcli/commands/orchestrate.py` — add --dry-run
- `modules/AgenticCLI/src/agenticcli/utils/tmux_layout.py` — add skip_commands, fix -p flags
- `modules/AgenticCLI/src/agenticcli/commands/cli.py` — register --dry-run arg

### Teach Phase
- `modules/AgenticGuidance/agents/planner/planner-test/process.yml`
- `modules/AgenticGuidance/agents/orchestration/orchestration-executor/process.yml`
- `modules/AgenticGuidance/agents/test/test-user-simulator/process.yml`
- `modules/AgenticGuidance/assets/guidelines/planning-standard.yml`

### Test Phase
- `modules/AgenticCLI/tests/integration/test_tmux_layout_real.py` (new)
- `modules/AgenticCLI/tests/integration/test_orchestrate_smoke.py` (new)
- `modules/AgenticCLI/tests/integration/conftest.py` (modify)

## Execution Order

1. **Build Phase** — Add --dry-run flag, fix inplace layout (no dependencies)
2. **Teach Phase** — Update guidance files (parallel with Build)
3. **Test Phase** — Create and run real tmux integration tests (depends on: Build)
4. **UAT Phase** — Validate full tmux GUI (depends on: Test)

## Key Difference from Previous Plans

Previous tmux plans shipped broken code because:
- Tests mocked subprocess → never called real tmux
- UAT used --no-tmux → bypassed the broken code path
- No test ever created a real tmux session and counted the panes

This plan ensures every test touches real tmux. The `--dry-run` flag makes
even the full command pipeline testable without human interaction.
