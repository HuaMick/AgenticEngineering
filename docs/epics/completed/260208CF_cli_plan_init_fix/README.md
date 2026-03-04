# CLI Plan Init Fix

**Plan ID**: 260208CF  
**Status**: Active  
**Created**: 2026-02-08

## Objective

Fix the `agentic plan init` command that generates incorrect folder names due to wrong 2-character code extraction.

## Bug Description

```bash
$ agentic plan init 260208PN -d "phone_notifications_ntfy_wizard"

# EXPECTED: 260208PN_phone_notifications_ntfy_wizard
# ACTUAL:   26020826_phone_notifications_ntfy_wizard
```

The 2-char code `26` is wrong - it should be `PN` (the branch suffix).

## Root Cause

**Two different `generate_plan_folder_name()` functions exist:**

| Location | Uses Registry? | Correct? |
|----------|----------------|----------|
| `worktree.py` L163-193 | ✅ Yes | ✅ |
| `naming.py` L116-145 | ❌ No | ❌ |

`plan.py:cmd_init()` calls `naming.py`'s version, which:
1. Calls `get_worktree_id(worktree_path)` WITHOUT branch name
2. Extracts first 2 chars of path suffix: `260208PN` → `26`
3. Should instead lookup from worktree registry or parse branch suffix

## Fix Approach

Add `branch` parameter to `naming.py` functions:
- `get_worktree_id(worktree_path, branch=None)` - enables registry lookup
- `generate_plan_folder_name(worktree_path, description, date, branch=None)`
- Update `cmd_init()` to pass branch: `generate_plan_folder_name(..., branch=branch)`

## Files to Modify

- `modules/AgenticCLI/src/agenticcli/utils/naming.py`
- `modules/AgenticCLI/src/agenticcli/commands/plan.py`
- `modules/AgenticCLI/tests/test_naming.py`

## Success Criteria

- [ ] `agentic plan init 260208PN -d "..." ` creates folder `260208PN_...`
- [ ] Registered branches use worktrees.yml abbreviation
- [ ] Unregistered branches fall back to path suffix extraction
- [ ] All existing tests pass
- [ ] User stories US-PLAN-INIT-001, 002, 003 pass UAT
