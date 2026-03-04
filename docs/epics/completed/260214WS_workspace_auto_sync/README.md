# Plan 260214WS: Automatic Workspace Sync on Plan Completion

## Overview
Implement automatic workspace file synchronization at key lifecycle points to eliminate manual intervention and prevent workspace drift.

## Problem Statement
The workspace file (`agenticengineering.code-workspace`) drifts out of sync with actual git worktrees on disk:
- Stale entries persist when worktrees deleted outside CLI
- Missing entries when worktrees reused in plan init
- Registry (`docs/worktrees.yml`) can contain entries for deleted worktrees
- Manual `agentic worktree sync` works but requires user to remember

## Key Issues Identified

### Bug 1: Plan Init Workspace Update (line 1154 in plan.py)
```python
# CURRENT (BUGGY):
if workspace_file and not worktree_exists:
    update_workspace_add(...)

# SHOULD BE:
if workspace_file:
    update_workspace_add(...)
```
**Impact**: Reused worktrees don't get workspace entries added.

### Gap 1: No Auto-Sync on Plan Completion
Currently `_try_worktree_cleanup_after_archive()` cleans up worktrees but doesn't sync workspace file comprehensively.

### Gap 2: Registry Cleanup Missing
`docs/worktrees.yml` registry entries persist even after worktrees are deleted, causing confusion in worktree matching logic.

## Solution Approach

### Phase 1: Fix Plan Init Bug
- Remove `and not worktree_exists` condition
- Ensure workspace updates for ALL worktree scenarios

### Phase 2: Auto-Sync on Completion
- Call `cmd_sync()` after successful worktree cleanup
- Triggered by plan auto-archival flow

### Phase 3: Registry Cleanup
- Extend `cmd_sync()` to clean `docs/worktrees.yml`
- Remove entries for deleted worktrees

### Phase 4: FileLock Protection
- Add FileLock to workspace file operations
- Prevent concurrent sync corruption

### Phase 5: Testing
- Unit tests for sync integration
- Manual integration testing

## Open Questions

**Q1**: Sync on every plan completion or only during cleanup?
- **Answer**: Start with cleanup-triggered sync (more targeted)

**Q2**: Should registry auto-cleanup deleted worktrees?
- **Answer**: Yes, add to sync logic

**Q3**: Sync in cmd_init for ALL scenarios?
- **Answer**: Yes, fix the bug on line 1154

**Q4**: Performance impact?
- **Answer**: Minimal - small JSON files, infrequent operations

**Q5**: Sync on manual worktree removal?
- **Answer**: Manual removal requires manual sync (document this)

## Success Criteria
- Workspace file auto-syncs when plans complete and archive
- Workspace file updates correctly when plan init reuses worktrees
- Registry cleanup removes entries for deleted worktrees
- No manual sync commands needed in normal workflow
- `agentic worktree validate` passes after auto-sync operations

## Architecture Alignment
- Uses existing `cmd_sync()` logic (no new sync mechanism)
- Maintains separation: worktree.py owns sync, plan.py calls it
- No cross-module coupling beyond existing imports
- Preserves CLI patterns and JSON output

## Files Involved
- `/home/code/AgenticEngineering/modules/AgenticCLI/src/agenticcli/commands/plan.py` (bug fix, sync trigger)
- `/home/code/AgenticEngineering/modules/AgenticCLI/src/agenticcli/commands/worktree.py` (registry cleanup, FileLock)
- `/home/code/AgenticEngineering/docs/worktrees.yml` (registry cleanup target)

## Estimated Effort
8-12 hours total

## Next Steps
1. Start with Phase 1 (fix plan init bug) - clear bug affecting current usage
2. Phase 2 (auto-sync on completion) - highest value for auto-sync goal
3. Phases 3-5 as time permits
