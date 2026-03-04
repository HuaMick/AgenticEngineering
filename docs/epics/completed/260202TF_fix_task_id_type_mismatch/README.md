# Plan: Fix Task ID Type Mismatch Bug

## Overview
Fix CLI bug where `agentic plan task start` and other task commands cannot find tasks due to type mismatch between YAML parsing and CLI argument handling.

## Problem Statement
When task IDs use decimal notation (e.g., `01.1`, `01.2`), Python's YAML parser interprets them as floats (`1.1`, `1.2`). The CLI passes task IDs as strings, causing comparison failures:
- `task.get("id")` returns `1.1` (float)
- `target_task` is `"01.1"` or `"1.1"` (string)
- `1.1 == "01.1"` evaluates to `False`
- Result: "Task not found" error

## Root Cause
Type inconsistency in comparison logic at multiple locations in `plan.py`:
- Line 1120: `task.get("id") == target_task` (nested tasks)
- Line 1128: `item.get("id") == target_task` (legacy structure)
- Line 2031: `tid == target_task` (main task update logic)
- Line 1259: Task list output doesn't normalize IDs

## Solution
Implement type-safe task ID normalization:
1. Create `_normalize_task_id()` helper function
2. Update all comparison points to use normalized comparison
3. Ensure task list output shows normalized IDs
4. Add comprehensive tests

## Worktree
- Branch: `260202TF`
- Path: `/home/code/AgenticEngineering-260202TF`

## Plan Files
- `plan_build.yml`: Implementation phases and tasks
- `plan_test.yml`: Testing validation phases
- `plan_audit_clean.yml`: Audit and cleanup tasks
- `plan_completed.yml`: Completion tracking
- `orchestration_fix_task_id_type_mismatch.mmd`: Execution flow

## Phases
1. **P1 - Root Cause Analysis**: Audit all comparison locations, verify YAML behavior
2. **P2 - Implementation**: Create normalization helper, update comparisons
3. **P3 - Testing**: Unit tests, integration tests, regression tests
4. **P4 - Documentation**: Update guidance on task ID formatting
5. **A1 - Plan Folder Audit**: Validate structure and consistency
6. **A2 - Code Quality Audit**: Linting, type checking, security review
7. **A3 - Cleanup**: Remove temporary files, prepare for merge

## Success Criteria
- Task commands work with decimal IDs (01.1, 1.1, etc.)
- Both string and numeric task IDs handled consistently
- No regression in existing functionality
- Comprehensive test coverage
- Code quality standards met

## Entry Points
Execute the plan using:
```bash
agentic orchestrate --plan docs/plans/live/260202TF_fix_task_id_type_mismatch
```

Or manually with specific orchestrators:
```bash
# Build phase
cd /home/code/AgenticEngineering-260202TF
agentic spawn build-python --context plan_build.yml

# Test phase
agentic spawn test-runner --context plan_test.yml

# Audit phase
agentic spawn test-final-output --context plan_audit_clean.yml
```

## Affected Files
- `/home/code/AgenticEngineering/modules/AgenticCLI/src/agenticcli/commands/plan.py`
- `/home/code/AgenticEngineering/modules/AgenticCLI/tests/test_task_id_handling.py` (new)
- `/home/code/AgenticEngineering/modules/AgenticCLI/tests/integration/test_task_commands.py` (new)

## Dependencies
- Python PyYAML library (already in use)
- pytest for testing
- Existing AgenticCLI test infrastructure

## Related Issues
- Bug report: CLI task ID parsing issue
- Impact: All users of `agentic plan task` commands with decimal task IDs

## Status
- Created: 2026-02-02
- Status: pending
- Worktree: Ready
- Plan files: Complete
- Ready for execution
