# Plan Folder Cleanup Plan

**Plan ID**: 260206PC
**Status**: Active
**Created**: 2026-02-06
**Agent**: planner-cleaning
**Worktree**: `/home/code/AgenticEngineering` (main branch)

## Objective

Restore correct plan folder structure for all live plans by removing nested `live/` subdirectories and archiving completed/replaced plans.

## Problem Statement

During planner-cleaning review on 2026-02-06, multiple plan folders were found with structural violations:

### Violations Identified

1. **260205BO_bootstrap_test**
   - Has nested `live/` folder with plan files
   - Has `plan_completed.yml` at root (signals completion)
   - **Action**: Archive to `completed/`

2. **260203AV_agenticvoice_async**
   - Has nested `live/` folder with plan files
   - Explicitly REPLACED by 260203VP_voice_personaplex
   - **Action**: Archive to `deferred/`

3. **260203TS_task_service**
   - Has nested `live/` folder with plan files
   - Active plan
   - **Action**: Flatten structure (move files to root)

4. **260205IM_cli_hardening**
   - Has nested `live/` folder with plan files
   - Active plan
   - **Action**: Flatten structure

5. **260205LB_cli_loading_bar**
   - Has nested `live/` folder with plan files
   - Active plan
   - **Action**: Flatten structure

## Correct Structure

Per `plan_example.yml`, plan folders should have a **FLAT** structure:

```
docs/plans/live/YYMMDDXX_description/
├── README.md
├── plan_build.yml          # NOT in nested live/
├── plan_test.yml
├── orchestration_*.mmd
├── reference/              # Optional subdirectories
└── analysis/
```

**NO nested `live/` subdirectories.**

## Plan Components

### Phase 1: Dependency Analysis (Cleaner-Dependency-Loop)

Use cleaner-dependency-loop pattern to safely identify cleanup actions:

1. **Cleaner**: Identify all nested `live/` folders
2. **Explorer**: Check dependencies, plan status, and determine archive vs flatten
3. **Decision**: Create validated action plan with specific git operations

**Output**: `cleanup_actions.yml` with explicit git commands

### Phase 2: Archive Operations

Move completed/replaced plans to appropriate archives:

- **260205BO_bootstrap_test** → `docs/plans/completed/`
- **260203AV_agenticvoice_async** → `docs/plans/deferred/`

### Phase 3: Flatten Operations

Fix active plans with nested structure:

- **260203TS_task_service**: Move plan files to root, remove nested `live/`
- **260205IM_cli_hardening**: Move plan files to root, remove nested `live/`
- **260205LB_cli_loading_bar**: Move plan files to root, remove nested `live/`

### Phase 4: Validation

Verify all cleanup successful:

- No nested `live/` folders remain
- Archived plans in correct locations
- Flattened plans have files at root
- No broken cross-plan references

## Success Criteria

- No nested `live/` folders in `docs/plans/live/`
- 260205BO_bootstrap_test in `docs/plans/completed/`
- 260203AV_agenticvoice_async in `docs/plans/deferred/`
- All active plans have flat structure
- Git history preserved (all operations use `git mv`)

## Key Files

| File | Purpose |
|------|---------|
| `plan_cleanup.yml` | Full cleanup plan with phases and tasks |
| `cleanup_actions.yml` | Executable action plan with git commands |
| `STRUCTURE_REFERENCE.md` | Documentation of correct plan folder structure |
| `README.md` | This file - overview and context |

## Quick Start

### For Agents

```bash
# Bootstrap context
agentic context bootstrap --role planner-cleaning

# Get current task
agentic plan task current

# Execute cleanup (Phase 2-3)
# Follow cleanup_actions.yml for specific commands
```

### For Humans

Review the violation summary and approve cleanup:

```bash
# Preview what will change
cat docs/plans/live/260206PC_plan_cleanup/cleanup_actions.yml

# Execute cleanup (all commands are git mv - safe)
# See cleanup_actions.yml for specific commands
```

## Design Decisions

### Why Archive vs Flatten?

**Archive to completed/:**
- Plan has `plan_completed.yml` (completion signal)
- All tasks marked completed
- No further work planned

**Archive to deferred/:**
- Plan explicitly replaced by newer approach
- Work postponed indefinitely
- Approach deprecated before completion

**Flatten:**
- Plan is active with ongoing work
- Only structural issue (nested `live/`)
- Keep in `live/` but fix structure

### Why Flat Structure?

1. **Simplicity**: Easier to navigate and understand
2. **Tooling**: CLI commands assume flat structure
3. **Consistency**: Matches example in `plan_example.yml`
4. **No Ambiguity**: Clear location for all plan files

## Notes

### Decommissioning Over Deprecation

- No `DEPRECATED.md` files created
- Plans are either active (`live/`) or archived (`completed/`/`deferred/`)
- Clean cuts, no lingering deprecated structures

### Git Operations

All operations use `git mv` to preserve file history:

```bash
# Correct
git mv docs/plans/live/PLANID/live/* docs/plans/live/PLANID/

# Wrong (loses history)
cp docs/plans/live/PLANID/live/* docs/plans/live/PLANID/
rm -r docs/plans/live/PLANID/live/
```

### Reference

See authoritative structure example:
- `modules/AgenticGuidance/assets/examples/planner/YYMMDDXX_description/`

## Session History

### Session 1: 2026-02-06 (Planning)

**Agent**: planner-cleaning
**Status**: Planning complete

**Actions**:
- Identified 5 plans with nested `live/` violations
- Analyzed dependencies and plan status
- Created comprehensive cleanup plan with 4 phases
- Documented correct structure in STRUCTURE_REFERENCE.md
- Generated executable action plan in cleanup_actions.yml

**Decisions**:
- 260205BO → completed/ (has plan_completed.yml)
- 260203AV → deferred/ (replaced by 260203VP)
- Three active plans → flatten structure only

**Next Steps**:
- Execute Phase 2: Archive operations
- Execute Phase 3: Flatten operations
- Validate with Phase 4 checks

## Related Plans

- **260203VP_voice_personaplex**: References 260203AV as replaced plan
- **All active plans**: Benefit from clear structural standards

## Execution Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Dependency Analysis | Complete | cleanup_actions.yml generated |
| Phase 2: Archive Operations | Pending | Ready to execute |
| Phase 3: Flatten Operations | Pending | Ready to execute |
| Phase 4: Validation | Pending | Awaiting Phase 2-3 completion |
