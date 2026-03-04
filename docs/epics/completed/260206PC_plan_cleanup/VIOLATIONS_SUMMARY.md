# Plan Folder Violations Summary

**Generated**: 2026-02-06
**Total Violations**: 5 plans

## Visual Overview

```
BEFORE CLEANUP:                          AFTER CLEANUP:
==================                        ================

docs/plans/live/                         docs/plans/live/
├── 260205BO_bootstrap_test/             ├── 260203PS_plan_service/
│   ├── plan_completed.yml               ├── 260203QC_question_cli/
│   └── live/  ← WRONG                   ├── 260203QG_question_guidance/
│       ├── plan_build.yml               ├── 260203QT_question_tmux/
│       └── plan_test.yml                ├── 260203TS_task_service/  ✓ FIXED
│                                        │   ├── plan_build.yml
├── 260203AV_agenticvoice_async/         │   └── orchestration_*.mmd
│   ├── README.md                        ├── 260203VP_voice_personaplex/
│   ├── orchestration_*.mmd              ├── 260205IM_cli_hardening/  ✓ FIXED
│   └── live/  ← WRONG                   │   ├── plan_build.yml
│       ├── plan_build.yml               │   ├── plan_test.yml
│       └── orchestration_*.mmd          │   └── analysis/
│                                        ├── 260205LB_cli_loading_bar/  ✓ FIXED
├── 260203TS_task_service/               │   ├── plan_build.yml
│   ├── README.md                        │   └── plan_test.yml
│   ├── orchestration_*.mmd              ├── 260205TY_migrate_cli/
│   └── live/  ← WRONG                   └── 260206PC_plan_cleanup/
│       ├── plan_build.yml
│       └── orchestration_*.mmd          docs/plans/completed/
│                                        └── 260205BO_bootstrap_test/  ✓ ARCHIVED
├── 260205IM_cli_hardening/                  ├── plan_completed.yml
│   ├── orchestration_*.mmd                  └── live/
│   ├── analysis/                                ├── plan_build.yml
│   └── live/  ← WRONG                           └── plan_test.yml
│       ├── plan_build.yml
│       └── plan_test.yml                docs/plans/deferred/
│                                        └── 260203AV_agenticvoice_async/  ✓ ARCHIVED
├── 260205LB_cli_loading_bar/                ├── README.md
│   ├── orchestration_*.mmd                  ├── orchestration_*.mmd
│   └── live/  ← WRONG                       └── live/
│       ├── plan_build.yml                       ├── plan_build.yml
│       └── plan_test.yml                        └── orchestration_*.mmd
```

## Violations Detail

### 🔴 VIOLATION 1: 260205BO_bootstrap_test

**Issue**: Nested `live/` folder + completion signal
**Evidence**:
- `plan_completed.yml` exists at root
- Plan files buried in `live/` subdirectory
- Structure suggests incomplete migration

**Decision**: ARCHIVE to `completed/`
**Reason**: `plan_completed.yml` signals work is done
**Action**:
```bash
git mv docs/plans/live/260205BO_bootstrap_test docs/plans/completed/
```

---

### 🔴 VIOLATION 2: 260203AV_agenticvoice_async

**Issue**: Nested `live/` folder + replaced by newer plan
**Evidence**:
- Plan files in `live/` subdirectory
- 260203VP plan explicitly states: "This plan REPLACES 260203AV"
- README shows status as "Active" but work superseded

**Decision**: ARCHIVE to `deferred/`
**Reason**: Not completed, but replaced by new architecture
**Action**:
```bash
git mv docs/plans/live/260203AV_agenticvoice_async docs/plans/deferred/
```

**Reference**: See `docs/plans/live/260203VP_voice_personaplex/plan_build.yml` line 31

---

### 🟡 VIOLATION 3: 260203TS_task_service

**Issue**: Nested `live/` folder (active plan)
**Evidence**:
- Plan files in `live/` subdirectory
- README shows active planning session
- No completion signal

**Decision**: FLATTEN structure
**Reason**: Active plan, needs structural fix only
**Action**:
```bash
cd docs/plans/live/260203TS_task_service
git mv live/plan_build.yml .
# Check diff for orchestration file before moving
git rm -r live/
```

**Note**: Root has `orchestration_task_service.mmd`, nested has `orchestration_task_service_implementation.mmd` - check for differences

---

### 🟡 VIOLATION 4: 260205IM_cli_hardening

**Issue**: Nested `live/` folder (active plan)
**Evidence**:
- Plan files in `live/` subdirectory
- `analysis/` subfolder at root (legitimate)
- No completion signal

**Decision**: FLATTEN structure
**Reason**: Active plan, keep `analysis/` folder, move plan files
**Action**:
```bash
cd docs/plans/live/260205IM_cli_hardening
git mv live/plan_build.yml .
git mv live/plan_test.yml .
git rm -r live/
```

**Note**: `analysis/` subfolder is valid (supporting docs), should remain

---

### 🟡 VIOLATION 5: 260205LB_cli_loading_bar

**Issue**: Nested `live/` folder (active plan)
**Evidence**:
- Plan files in `live/` subdirectory
- Orchestration at root (correct)
- No completion signal

**Decision**: FLATTEN structure
**Reason**: Active plan, needs structural fix only
**Action**:
```bash
cd docs/plans/live/260205LB_cli_loading_bar
git mv live/plan_build.yml .
git mv live/plan_test.yml .
git rm -r live/
```

## Resolution Summary

| Plan | Type | From | To | Files Affected |
|------|------|------|----|----|
| 260205BO | Archive | live/ | completed/ | 2 plan files |
| 260203AV | Archive | live/ | deferred/ | 2 plan files + docs |
| 260203TS | Flatten | live/live/ | live/ | 2 files moved to root |
| 260205IM | Flatten | live/live/ | live/ | 2 files moved to root |
| 260205LB | Flatten | live/live/ | live/ | 2 files moved to root |

**Total Plans Cleaned**: 5
**Total Files Moved**: ~12 files

## Validation Checklist

After cleanup, verify:

- [ ] No nested `live/` folders exist: `find docs/plans/live -type d -name 'live' | grep -v '^docs/plans/live$'` (should be empty)
- [ ] 260205BO exists at `docs/plans/completed/260205BO_bootstrap_test/`
- [ ] 260203AV exists at `docs/plans/deferred/260203AV_agenticvoice_async/`
- [ ] 260203TS has `plan_build.yml` at root
- [ ] 260205IM has `plan_build.yml` and `plan_test.yml` at root
- [ ] 260205LB has `plan_build.yml` and `plan_test.yml` at root
- [ ] All `git mv` operations preserve history (`git log --follow <file>`)

## Prevention

To prevent future violations:

1. **Reference Example**: Always check `modules/AgenticGuidance/assets/examples/planner/YYMMDDXX_description/` for structure
2. **Flat Structure**: Plan files at root, NO nested `live/` subdirectories
3. **Valid Subdirectories**: Only `reference/`, `analysis/`, `questions/` are acceptable
4. **Tooling**: Consider adding validation to `agentic plan init` command

## Impact

- **Low Risk**: All metadata changes, no code affected
- **High Value**: Cleaner structure, consistent patterns
- **Maintainability**: Future plans follow clear standard
- **Tooling**: CLI commands work predictably

## Authority

This cleanup follows guidance from:
- `modules/AgenticGuidance/assets/examples/planner/YYMMDDXX_description/plan_example.yml`
- `modules/AgenticGuidance/assets/guidelines/context-minimisation.yml`
- Planner-cleaning agent role responsibilities
