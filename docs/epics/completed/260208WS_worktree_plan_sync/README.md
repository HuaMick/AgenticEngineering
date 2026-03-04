# Worktree-Plan Synchronization Validation

**Plan ID**: 260208WS  
**Status**: Active  
**Created**: 2026-02-08

## Problem Statement

There is no validation to ensure that:
1. **Live plans have corresponding active worktrees** - Plans like `260208CF` and `260208PL` exist without matching worktrees
2. **Worktree registry (`worktrees.yml`) reflects actual worktrees** - Registry has 8 entries but only 2 worktrees exist
3. **Stale worktrees are detected** - Worktrees without live plans accumulate (had 17 before cleanup)

## Gap Analysis

| Component | Current State | Desired State |
|-----------|--------------|---------------|
| `worktree list` | Lists worktrees, shows matching plans | Should WARN about orphaned plans |
| `plan list` | Lists plans | Should WARN about plans without worktrees |
| `worktrees.yml` | Static registry | Should be validated against `git worktree list` |
| `worktree create` | Creates worktree + plan | ✅ Working |
| `worktree remove` | Removes worktree | Should validate no live plans remain |

## Proposed Solution

Add `agentic worktree validate` command that:
1. Cross-references `git worktree list` with `docs/plans/live/` folders
2. Cross-references `worktrees.yml` registry with actual worktrees
3. Outputs validation report with actionable warnings
4. Returns non-zero exit code if validation fails

## Files to Modify

- `modules/AgenticCLI/src/agenticcli/commands/worktree.py` - Add `cmd_validate()`
- `modules/AgenticCLI/tests/test_worktree.py` - Add validation tests
- `modules/AgenticCLI/src/agenticcli/commands/plan.py` - Add warning to `cmd_list()`

## Success Criteria

- [ ] `agentic worktree validate` reports orphaned plans (plans without worktrees)
- [ ] `agentic worktree validate` reports stale worktrees (worktrees without plans)
- [ ] `agentic worktree validate` reports registry drift (entries not matching reality)
- [ ] All existing tests pass
- [ ] JSON output supported for automation
