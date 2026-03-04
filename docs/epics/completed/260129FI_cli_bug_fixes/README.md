# 260129FI CLI Bug Fixes

**Created**: 2026-01-29
**Status**: ACTIVE

## Objective

Fix three critical bugs in the CLI plan movement workflow discovered during 260129CL review.

## Bugs Addressed

### Bug 1: Short-name Resolution Not Working
- **Symptom**: `plan move folder --plan <short_name>` fails with "No such file or directory"
- **Root Cause**: `find_plan_folder()` simply converts path to `Path()` without searching for matching folders
- **Target File**: `modules/AgenticCLI/src/agenticcli/commands/plan.py` (lines 181-209)

### Bug 2: Archive Doesn't Remove Source Folder
- **Symptom**: After `plan move folder`, source folder remains in `docs/plans/live/`
- **Root Cause**: `archive_plan_folder()` uses `shutil.copytree()` without removing source
- **Target File**: `modules/AgenticGuidance/src/agenticguidance/services/plan.py` (line 377)

### Bug 3: Task Move Doesn't Remove from Source YAML
- **Symptom**: After `plan move task`, task still exists in source plan_*.yml file
- **Root Cause**: `move_task_to_completed()` appends to completed file but never modifies source
- **Target File**: `modules/AgenticGuidance/src/agenticguidance/services/plan.py` (lines 153-276)

## Success Criteria

1. `agentic plan move folder --plan 260129FI_cli_bug_fixes` works (short-name)
2. Source folder removed from `live/` after archive
3. Task removed from source YAML after move to completed
4. All existing tests pass
5. New tests cover the fixed behaviors
