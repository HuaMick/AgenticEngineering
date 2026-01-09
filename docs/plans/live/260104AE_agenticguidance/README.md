# Plan: 260104AE_agenticguidance

## Context
- **Plan ID**: 260104AE_agenticguidance
- **Worktree**: `/home/code/AgenticEngineering-agenticguidance`
- **Branch**: `agenticguidance`
- **Objective**: Refactor orchestration to be generic, split planning entrypoints (build/teach), and transition to MMD-driven dynamic workflows.

## Session History
| Session | Date | Summary |
|---------|------|---------|
| 1 | 2026-01-04 | Initial worktree setup |
| 2 | 2026-01-06 | Entrypoint refactor, CLI capability mapping |
| 3 | 2026-01-06 | Agent self-review (19 agents), Friction Remediation (7 tasks) |
| 4 | 2026-01-06 | Ralph loop (8 iterations), created teach plan, 180+ friction points |
| 5 | 2026-01-08 | Example alignment (7 phases completed) |
| 6 | 2026-01-09 | Plan structure standardization, 6 audits, 6 review plans |
| 7 | 2026-01-09 | Plan cleanup: consolidated remediation plans, archived superseded |

## Active Decisions

### DECISION-001: Legacy Agents (planner-phases, planner-teach)
**Status**: IN PROGRESS - Option B selected (Deprecate)

**Decision**: Keep existing AgenticGuidance structure, mark legacy agents as deprecated.

**Verified**:
- Functionality absorbed: planner-phases → orchestration-planning Phase Determination; planner-teach → planner-guidance
- No dangling references in active code

**Pending**:
- [ ] Create `DEPRECATED.md` for planner-phases
- [ ] Create `DEPRECATED.md` for planner-teach
- Plan: `live/plan_live_cleanup_deprecation.yml`

### DECISION-002: Test Agents Migration
**Status**: UNRESOLVED - Option B selected (Migrate with 2.0 compliance)

**Decision**: Migrate test-user-simulator, test-service, test-builder to AgenticGuidance.

**Current State**:
- Agents exist ONLY in legacy location
- planner-test manifest has inconsistent references (NOT_MIGRATED comments but AgenticGuidance paths)
- agent-categories.yml lists them but they don't exist in AgenticGuidance

**Pending**:
- [ ] Execute 6-phase migration plan
- Plan: `live/plan_live_build_migration.yml`

## Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0: Friction Remediation | COMPLETED | 7/7 tasks |
| Phase 0.5: Friction Remediation Phase 2 | PENDING | 11 tasks (4 CRITICAL, 7 HIGH) |
| Phase 1: CLI Offloading | Pending | 4 tasks |
| Phase 2: Entrypoint & Schema | Pending | 2 tasks |
| Phase 3: MMD Implementation | Pending | 3 tasks |
| Phase 4: Asset & Example Alignment | COMPLETED | 7 phases |
| Phase 5: Agent Self-Review Testing | COMPLETED | 19 agents tested x2 |
| Phase 6: CLI Fitness Testing | COMPLETED | CLI verified |
| Phase 7: Plan Cleanup | COMPLETED | Session 7 |

## Folder Structure

```
260104AE_agenticguidance/
├── README.md
├── analysis/
│   ├── friction-consolidation-analysis.yml
│   └── viability-assessment.yml
├── audit/
│   ├── 260106_agent_self_review_results.yml
│   ├── 260106_audit_findings.yml
│   ├── 260106_session2_self_review_results.yml
│   ├── 260106_session3_summary.yml
│   └── agent-reports/                    # 6 individual agent reports
├── completed/                            # 10 archived plans
│   ├── plan_completed_example_alignment.yml
│   ├── plan_live_build.yml
│   ├── plan_live_guidance_cleaning_remediation.yml
│   ├── plan_live_guidance_planner_build.yml
│   ├── plan_live_orchestration_remodel.yml
│   ├── plan_live_planner_test_remediation.yml
│   ├── plan_live_remediation.yml
│   ├── plan_live_teach.yml
│   ├── plan_next_actions.yml
│   └── plan_planner_guidance_remediation.yml
└── live/                                 # 21 active files
    ├── orchestration_agenticguidance.mmd
    ├── plan_agenticguidance.yml          # MASTER PLAN
    │
    │   # Active Consolidated Plans
    ├── plan_live_teach_consolidated.yml
    ├── plan_live_planner_remediation_consolidated.yml
    │
    │   # Action Plans
    ├── plan_live_build_migration.yml     # DECISION-002
    ├── plan_live_cleanup_deprecation.yml # DECISION-001
    ├── plan_guidance_deploy_worktree_remediation.yml
    ├── plan_guidance_reviewer_context.yml
    │
    │   # Audits (6)
    ├── audit_deploy_worktree.yml
    ├── audit_planner_build.yml
    ├── audit_planner_cleaning.yml
    ├── audit_planner_guidance.yml
    ├── audit_planner_reviewer.yml
    ├── audit_planner_test.yml
    │
    │   # Reviews (6)
    ├── review_deploy_worktree.yml
    ├── review_planner_build.yml
    ├── review_planner_cleaning.yml
    ├── review_planner_guidance.yml
    ├── review_planner_reviewer.yml
    ├── review_planner_test.yml
    │
    └── consolidation_recommendations.yml # Meta: further cleanup options
```

## Next Session Priorities

### Priority 1: Execute Deprecation (DECISION-001)
```bash
# Plan: live/plan_live_cleanup_deprecation.yml
# Tasks: Create DEPRECATED.md files for planner-phases, planner-teach
```

### Priority 2: Execute Migration (DECISION-002)
```bash
# Plan: live/plan_live_build_migration.yml
# Tasks: Migrate test-user-simulator, test-service, test-builder
```

### Priority 3: Consolidated Remediation
```bash
# Plan: live/plan_live_planner_remediation_consolidated.yml
# Contains: T4 Specialized Core Layer Audit, context reduction for all planner agents
```

### Priority 4: Teach Plan Execution
```bash
# Plan: live/plan_live_teach_consolidated.yml
# 8 phases: Fragment resolution, Process format, Output schema, Input validation,
#           Version alignment, CLI centralization, Spawns declaration, REPO_ROOT
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `live/plan_agenticguidance.yml` | Master plan with all phases |
| `live/plan_live_teach_consolidated.yml` | Teaching phases (8 phases, T4 specialization) |
| `live/plan_live_planner_remediation_consolidated.yml` | Unified remediation (5 planner agents) |
| `live/plan_live_build_migration.yml` | Test agent migration (DECISION-002) |
| `live/plan_live_cleanup_deprecation.yml` | Legacy deprecation (DECISION-001) |
| `audit/260106_session3_summary.yml` | Session 3 findings summary |

## Plan Structure Standard

Plans follow the unified structure in `modules/AgenticGuidance/assets/examples/planner/YYMMDDRepo_Branch/plan_example.yml`.

**Key Sections**: metadata, context, related_plans, inputs, open_questions, phases, success_criteria

**Plan Types**:
- Main plans (`plan_*.yml`): Primary coordination
- Teach plans (`plan_live_teach*.yml`): Guidance improvement
- Audit plans (`audit_*.yml`): Issue identification
- Review plans (`review_*.yml`): Approval status
- Remediation plans (`plan_*_remediation*.yml`): Fix implementations
