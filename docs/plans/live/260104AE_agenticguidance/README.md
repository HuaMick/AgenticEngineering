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
| 8 | 2026-01-09 | Ralph loop: DECISION-001 completed (deprecation), DECISION-002 completed (migration) |

## Active Decisions

### DECISION-001: Legacy Agents (planner-phases, planner-teach)
**Status**: COMPLETED (Session 8)

**Decision**: Keep existing AgenticGuidance structure, mark legacy agents as deprecated.

**Completed**:
- [x] Functionality absorbed: planner-phases → orchestration-planning Phase Determination; planner-teach → planner-guidance
- [x] No dangling references in active code
- [x] Created `DEPRECATED.md` for planner-phases
- [x] Created `DEPRECATED.md` for planner-teach
- Plan: `completed/plan_live_cleanup_deprecation.yml`

### DECISION-002: Test Agents Migration
**Status**: COMPLETED (Session 8)

**Decision**: Migrate test-user-simulator, test-service, test-builder to AgenticGuidance.

**Completed**:
- [x] All 3 agents migrated to modules/AgenticGuidance/agents/test/
- [x] Each agent has manifest.yml (version 2.0), process.yml (PATH RESOLUTION SEMANTICS), inputs.yml (layer references)
- [x] planner-test manifest updated with MIGRATED status
- [x] test category manifest updated with migrated agents
- Plan: `completed/plan_live_build_migration.yml`

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
├── completed/                            # 19 archived plans
│   ├── plan_completed_example_alignment.yml
│   ├── plan_live_build.yml
│   ├── plan_live_build_migration.yml     # DECISION-002 COMPLETED
│   ├── plan_live_cleanup_deprecation.yml # DECISION-001 COMPLETED
│   ├── plan_live_guidance_cleaning_remediation.yml
│   ├── plan_live_guidance_planner_build.yml
│   ├── plan_live_orchestration_remodel.yml
│   ├── plan_live_planner_test_remediation.yml
│   ├── plan_live_remediation.yml
│   ├── plan_live_teach.yml
│   ├── plan_next_actions.yml
│   ├── plan_planner_guidance_remediation.yml
│   ├── plan_guidance_artifact_lifecycle.yml
│   ├── plan_guidance_planner_build.yml
│   ├── plan_guidance_planner_cleaning.yml
│   ├── plan_guidance_planner_guidance.yml
│   ├── plan_guidance_planner_reviewer.yml
│   └── plan_guidance_planner_test.yml
└── live/                                 # 8 active files
    ├── orchestration_agenticguidance.mmd
    ├── plan_agenticguidance.yml          # MASTER PLAN
    │
    │   # Active Consolidated Plans
    ├── plan_live_teach_consolidated.yml
    ├── plan_live_planner_remediation_consolidated.yml  # COMPLETED, next: self-review loop
    │
    │   # Remaining Action Plans
    ├── plan_guidance_deploy_worktree_remediation.yml
    ├── plan_guidance_reviewer_context.yml
    └── plan_guidance_artifact_lifecycle.yml
```

## Next Session Priorities

### Priority 1: Agent Self-Review Loop
```bash
# Plan: completed/plan_live_planner_remediation_consolidated.yml (phase-6)
# Task: Validate remediation by spawning planner agents with real tasks
# Status: Ready for execution
```

### Priority 2: Teach Plan Execution
```bash
# Plan: live/plan_live_teach_consolidated.yml
# 8 phases: Fragment resolution, Process format, Output schema, Input validation,
#           Version alignment, CLI centralization, Spawns declaration, REPO_ROOT
```

### Priority 3: Deploy Worktree Remediation
```bash
# Plan: live/plan_guidance_deploy_worktree_remediation.yml
# Task: Fix deploy-worktree guidance based on audit findings
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `live/plan_agenticguidance.yml` | Master plan with all phases |
| `live/plan_live_teach_consolidated.yml` | Teaching phases (8 phases, T4 specialization) |
| `live/plan_live_planner_remediation_consolidated.yml` | Unified remediation (5 planner agents) |
| `completed/plan_live_build_migration.yml` | Test agent migration (DECISION-002) - COMPLETED |
| `completed/plan_live_cleanup_deprecation.yml` | Legacy deprecation (DECISION-001) - COMPLETED |
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
