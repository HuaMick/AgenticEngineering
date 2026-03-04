# Plan Folder Structure Reference

**Created**: 2026-02-06
**Purpose**: Define correct plan folder structure to prevent future violations

## Correct Structure

Plan folders should have a **FLAT** structure with all plan files at the root:

```
docs/plans/live/YYMMDDXX_description/
├── README.md                       # Plan overview and status
├── plan_build.yml                  # Build phase tasks
├── plan_test.yml                   # Test phase tasks (if separate)
├── plan_audit_clean.yml            # Audit/cleanup phase tasks (if separate)
├── plan_teach.yml                  # Documentation phase tasks (if separate)
├── plan_completed.yml              # Completed items tracker
├── orchestration_*.mmd             # Mermaid flow diagrams
├── reference/                      # Optional: supporting documents
│   └── examples/
├── analysis/                       # Optional: analysis artifacts
│   └── review_*.yml
└── questions/                      # Optional: HITL question queue
    ├── pending/
    └── answered/
```

## What NOT to Do

**WRONG**: Nested `live/` subdirectory
```
docs/plans/live/YYMMDDXX_description/
├── README.md                       # ✓ Correct
├── orchestration_*.mmd             # ✓ Correct
└── live/                           # ✗ WRONG - no nested live/
    ├── plan_build.yml              # ✗ Should be at root
    └── plan_test.yml               # ✗ Should be at root
```

## Rationale

1. **Simplicity**: Flat structure is easier to navigate and understand
2. **Tooling**: CLI commands assume flat structure (e.g., `agentic plan task list`)
3. **Consistency**: All plans follow same pattern (see plan_example.yml)
4. **No Ambiguity**: Clear location for all plan files

## Plan Lifecycle

Plans progress through three folders:

```
docs/plans/
├── live/               # Active plans
├── completed/          # Successfully finished plans
└── deferred/           # Plans replaced or postponed
```

### When to Archive

**Move to `completed/`:**
- All tasks completed
- Success criteria met
- Implementation merged
- No further work planned

**Move to `deferred/`:**
- Plan replaced by newer approach (e.g., 260203AV replaced by 260203VP)
- Work postponed indefinitely
- Approach deprecated before completion

## Violations Found (2026-02-06)

The following plans had incorrect nested `live/` structure:

| Plan | Issue | Resolution |
|------|-------|------------|
| 260205BO_bootstrap_test | Nested live/ + plan_completed.yml | Archive to completed/ |
| 260203AV_agenticvoice_async | Nested live/ + replaced by 260203VP | Archive to deferred/ |
| 260203TS_task_service | Nested live/ | Flatten structure |
| 260205IM_cli_hardening | Nested live/ | Flatten structure |
| 260205LB_cli_loading_bar | Nested live/ | Flatten structure |

## Reference

See authoritative example:
- `modules/AgenticGuidance/assets/examples/planner/YYMMDDXX_description/plan_example.yml`
- `modules/AgenticGuidance/assets/examples/planner/YYMMDDXX_description/` (directory structure)

## Cleanup Operations

All cleanup uses `git mv` to preserve file history:

```bash
# Flatten nested live/ folder
git mv docs/plans/live/PLANID/live/* docs/plans/live/PLANID/
git rm -r docs/plans/live/PLANID/live/

# Archive to completed
git mv docs/plans/live/PLANID docs/plans/completed/

# Archive to deferred
git mv docs/plans/live/PLANID docs/plans/deferred/
```

Never use `cp` + `rm` - always use `git mv` to maintain history.
