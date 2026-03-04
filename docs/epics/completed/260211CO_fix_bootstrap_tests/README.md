# Fix Bootstrap Test Failures (260211CO)

## Objective

Fix 10 failing tests in `test_plan_bootstrap.py` by updating test expectations to match the current `cmd_bootstrap` → `cmd_init` delegation behavior.

## Root Cause Analysis

`cmd_bootstrap` was refactored to delegate to `cmd_init`, which introduced these behavioral changes:

1. **Git detection**: `cmd_init` uses `subprocess.run(["git", "rev-parse", "--show-toplevel"])` instead of the mocked `git.get_project_root()`. Tests mock `get_project_root` but the subprocess call bypasses the mock.
2. **Folder structure**: `cmd_init` uses `create_planning_folder()` (flat structure - `plan_build.yml` directly in plan folder) instead of the old `live/` subfolder pattern. Tests assert `plan_folder / "live" / "plan_build.yml"` which no longer exists.
3. **JSON output keys**: `cmd_init` outputs `{ plan_folder, plan_folder_name, worktree, branch, ... }` but tests expect `{ plan_id, plan_path, success, objective }`.
4. **Error codes**: `test_bootstrap_fails_outside_git_repo` expects exit code 1 but gets exit code 2 because the subprocess git call succeeds in the real repo.
5. **Worktree operations**: `cmd_init` runs real git subprocess calls (worktree list, worktree add) that aren't mocked in tests.

## Phases Overview

1. **Phase 1: Fix Test Mocking** - Patch subprocess calls so `cmd_init` uses temp git repo instead of real one
2. **Phase 2: Fix Test Assertions** - Update folder structure expectations, JSON output keys, error codes
3. **Phase 3: UAT** - Verify all 11 tests pass

## Dependencies

- Test file: `modules/AgenticCLI/tests/test_plan_bootstrap.py`
- Source: `modules/AgenticCLI/src/agenticcli/commands/plan.py` (cmd_bootstrap, cmd_init)
- Source: `modules/AgenticCLI/src/agenticcli/commands/worktree.py` (create_planning_folder)
- Source: `modules/AgenticCLI/src/agenticcli/utils/naming.py` (generate_plan_folder_name)

## Success Criteria

- All 11 tests in `test_plan_bootstrap.py` pass
- No other tests in the AgenticCLI test suite regress
- Tests properly validate the current `cmd_init` behavior (not the old behavior)
