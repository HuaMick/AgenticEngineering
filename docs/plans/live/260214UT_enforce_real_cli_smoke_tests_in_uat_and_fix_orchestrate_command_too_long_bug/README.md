# Plan 260214UT: Enforce Real CLI Smoke Tests in UAT

## Problem Statement

Our orchestration loop just executed 3 plans (260214PF, 260214TG, 260214US) and all "passed UAT", but the actual user command `agentic orchestrate --mode planning` is STILL broken with two bugs:

1. **tmux split bug**: Changes were applied in a worktree but never merged to main (executor had no merge step)
2. **command too long**: The entire 447-line process.mmd is passed as `--append-system-prompt` CLI arg, which exceeds tmux's `send-keys` character limit

These bugs were NOT caught by UAT because:
- UAT validates against user story acceptance criteria using **mocked tests**
- No UAT step actually **runs the real installed CLI command** end-to-end
- Each plan tested its component in isolation (tmux splits, orchestrate command, tmux layout) but nobody tested the full pipeline
- The test-user-simulator agent can "pass" stories without ever touching the real system

## Root Cause

**Systemic gap in UAT validation:** Guidance does not enforce real CLI smoke tests. Plans can "pass UAT" by validating against mocked subprocess calls or --help output, never running the actual installed binary.

## Solution

This plan fixes the root cause AND the immediate bugs:

### 1. Teach Phase - Update Guidance (ROOT CAUSE FIX)

Update four guidance files to mandate real CLI smoke tests:

- **planner-test/process.yml**: Add fence requiring UAT tasks for CLI commands to run actual installed binary
- **orchestration-executor/process.yml**: Add integration smoke test gate before shutdown
- **test-user-simulator/process.yml**: Prefer real command execution over mocking
- **planning-standard.yml**: Add CLI smoke test requirement rule

### 2. Build Phase - Fix Orchestrate Command (IMMEDIATE BUG FIX)

Fix the command-too-long bug in orchestrate.py:
- Write system prompt to temp file using `tempfile.NamedTemporaryFile`
- Use `--append-system-prompt-file <path>` instead of `--append-system-prompt <content>`
- Avoids tmux character limit errors

### 3. Test Phase - Integration Tests (VALIDATION)

Create integration tests that demonstrate the RIGHT way to test CLI commands:
- Run actual `agentic orchestrate` commands (not mocked subprocess)
- Use `--no-tmux` flag for CI compatibility
- Verify exit codes and error messages
- NO MOCKING

### 4. UAT Phase - Real CLI Smoke Tests (PROOF)

Smoke test the actual CLI commands:
- Run `agentic orchestrate --mode planning --no-tmux`
- Run `agentic orchestrate --mode executor --no-tmux`
- Verify integration tests pass
- Verify guidance updates are effective

## Success Criteria

1. Guidance enforces real CLI testing in UAT (prevents future bugs)
2. Orchestrate command works without character limit errors
3. Integration tests demonstrate correct approach (real CLI, no mocks)
4. Future plans will catch similar bugs BEFORE shipping

## Impact

**Prevents future failures:** After this plan, any future plan that modifies CLI commands will be required to test the actual installed binary, not mocked versions. This ensures we never ship broken CLI commands again.

**Demonstrates best practices:** The test phase shows the RIGHT way to test CLI commands - integration tests with real execution, not unit tests with mocks.

**Fixes immediate bugs:** The build phase fixes the command-too-long error so `agentic orchestrate` works correctly.

## Files Changed

### Guidance (Teach Phase)
- `modules/AgenticGuidance/agents/planner/planner-test/process.yml`
- `modules/AgenticGuidance/agents/orchestration/orchestration-executor/process.yml`
- `modules/AgenticGuidance/agents/test/test-user-simulator/process.yml`
- `modules/AgenticGuidance/assets/guidelines/planning-standard.yml`

### Code (Build Phase)
- `modules/AgenticCLI/src/agenticcli/commands/orchestrate.py`

### Tests (Test Phase)
- `modules/AgenticCLI/tests/integration/test_orchestrate_integration.py` (new)
- `modules/AgenticCLI/tests/integration/conftest.py` (new)
- `modules/AgenticCLI/pytest.ini` (update)

## Execution Order

1. **Teach Phase** - Update guidance files (no dependencies)
2. **Build Phase** - Fix orchestrate.py (depends on: none)
3. **Test Phase** - Create integration tests (depends on: Build)
4. **UAT Phase** - Smoke test CLI commands (depends on: Test)

## Related Plans

This plan remediates bugs from:
- **260214PF**: Tmux pane split fix (changes in worktree, never merged)
- **260214TG**: Tmux orchestrate command (command-too-long error)
- **260214US**: User story generation (passed UAT with mocks)

All three plans "passed UAT" but shipped broken code because UAT used mocked tests instead of real CLI execution.

## Next Steps

After this plan completes:
1. Run `agentic orchestrate --mode executor` to execute the plan
2. Verify all phases complete successfully
3. Test the fixed `agentic orchestrate --mode planning` command
4. Future plans will automatically enforce real CLI testing in UAT
