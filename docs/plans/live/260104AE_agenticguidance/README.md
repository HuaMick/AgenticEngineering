# Plan: 260104AE_agenticguidance

## Status: COMPLETE (Essentially)

**Completed**: 2026-01-10
**Branch**: `agenticguidance`
**Worktree**: `/home/code/AgenticEngineering-agenticguidance`

## Objective

Consolidate remaining tasks for CLI offloading and MMD orchestration refinement. This plan unified work to:
- Offload deterministic logic to the agentic-cli
- Implement dynamic orchestration via Mermaid diagrams
- Remediate friction points discovered through agent self-review testing
- Create teaching artifacts for MMD-driven orchestration

## Key Achievements

### Teaching Work (76+ tasks)
- 12 teaching phases completed
- 31 plan files archived
- 6 MMD teaching artifacts created (3,200+ lines total)
- 18 friction points remediated across 2 phases

### Build Work
- **orchestration-executor agent**: Created (491 lines across manifest, inputs, process files)
- **Planner MMD outputs**: Updated planner-build and planner-guidance with MMD declarations
- **Test fixtures**: 4 MMD files created for orchestration testing

### Friction Remediation
- **Phase 1** (7 tasks): Path semantics, required inputs, loop context, output schemas, fragment references, context loading, version alignment
- **Phase 2** (11 tasks): Legacy agents deprecated, fragment references fixed, process format standardized, test agents migrated, output schemas populated, CLI docs centralized

### CLI Offloading
All deterministic operations offloaded to agentic-cli:
- Worktree setup (`agentic worktree create/status`)
- Plan folder validation (`agentic plan validate`)
- Task status updates (`agentic plan task start/complete`)
- Completed task movement (`agentic plan move task/tasks/folder`)

## Major Deliverables

### Agents Created
| Agent | Location | Lines |
|-------|----------|-------|
| orchestration-executor | `modules/AgenticGuidance/agents/orchestration/orchestration-executor/` | 491 |
| test-user-simulator | `modules/AgenticGuidance/agents/test/test-user-simulator/` | Migrated |
| test-service | `modules/AgenticGuidance/agents/test/test-service/` | Migrated |
| test-builder | `modules/AgenticGuidance/agents/test/test-builder/` | Migrated |

### Specifications Created
| Specification | Location | Lines |
|---------------|----------|-------|
| orchestration-executor-specification.yml | `assets/definitions/` | 400+ |
| orchestration-test-scenarios.yml | `assets/definitions/` | 918 |
| plan-mmd-schema.yml | `assets/definitions/` | 292 |
| strategy-validation.yml | `assets/definitions/` | - |
| planning-standard.yml | `assets/definitions/` | - |

### Examples & Templates
| Asset | Location | Description |
|-------|----------|-------------|
| orchestration_example.mmd | `assets/examples/planner/` | Modern MMD syntax (173 lines) |
| structural-patterns.yml | `assets/examples/planner/` | Plan structural patterns (150 lines) |
| plan-structure-requirements.yml | `assets/definitions/` | Plan requirements (48 lines) |
| reviewer-agent-loops.yml | `assets/definitions/` | Reviewer-specific loop slice (54 lines) |

## Human Decisions Resolved

### DECISION-001: Legacy Agents
**Decision**: Deprecate legacy-only agents (planner-phases, planner-teach)
- Created DEPRECATED.md files in legacy folders
- Functionality absorbed by orchestration-planning and planner-guidance

### DECISION-002: Test Agents
**Decision**: Migrate test agents to AgenticGuidance
- test-user-simulator, test-service, test-builder migrated to `modules/AgenticGuidance/agents/test/`
- Full 2.0 architecture compliance

## Phases Completed

| Phase | Tasks | Status |
|-------|-------|--------|
| Friction Remediation | 7 | Completed |
| Friction Remediation Phase 2 | 11 | Completed |
| CLI Offloading | 4 | Completed |
| Agent Self-Review Testing | 19 agents | Completed |
| Entrypoint & Schema | 2 | Completed |
| Orchestration Remodel | 6/7 | Completed |
| Asset & Example Alignment | 4 | Completed |
| CLI Fitness Testing | 7/8 | Completed |
| MMD Teaching Prerequisites | 7 | Completed |
| MMD Implementation | 3 (partial) | Completed |

## Deferred Items

| Item | Reason |
|------|--------|
| Integration test execution (mmd_005_002-005) | Requires focused testing session with actual executor invocation |
| remod_plan_001 (orchestration-planning MMD refactoring) | Lower priority |
| Integration test (CLI Fitness) | Out of scope |

## Folder Structure

```
260104AE_agenticguidance/
├── README.md                 # This file
├── analysis/                 # Viability assessments, friction analysis
├── audit/                    # Self-review results, findings
│   └── agent-reports/        # Individual agent reports
├── completed/                # 33 archived plan files
│   ├── plan_friction_remediation_phase1.yml
│   ├── plan_friction_remediation_phase2.yml
│   ├── plan_cli_offloading.yml
│   ├── plan_mmd_implementation.yml
│   ├── plan_mmd_teaching_prerequisites.yml
│   └── ... (28 more)
└── live/                     # Active files
    ├── orchestration_agenticguidance.mmd
    ├── plan_agenticguidance.yml          # Master plan
    └── plan_integration_testing.yml       # Deferred testing
```

## Related Plans

| Plan | Location | Status |
|------|----------|--------|
| MMD Teaching | `completed/plan_mmd_teaching_prerequisites.yml` | Completed |
| Teach Consolidated | `completed/plan_live_teach_consolidated.yml` | Completed |
| Build Migration | `completed/plan_live_build_migration.yml` | Completed |
| Cleanup Deprecation | `completed/plan_live_cleanup_deprecation.yml` | Completed |
| Orchestration Remodel | `completed/plan_orchestration_remodel.yml` | Completed |

## Success Criteria Met

- [x] Friction Remediation Phase 2: All 11 tasks completed (4 CRITICAL, 7 HIGH)
- [x] CLI Offloading: Worktree, plan folder, task status, and completed task movement handled by agentic-cli
- [x] Entrypoint & Schema: Orchestration pattern evaluated, Plan-MMD schema defined
- [x] MMD Implementation: Planners generate MMD, generic executor created (test execution deferred)
- [x] Asset Alignment: Examples use unified plan + orchestration.mmd pattern
- [x] DECISION-001 resolved: Legacy agents deprecated with DEPRECATED.md files
- [x] DECISION-002 resolved: Test agents migrated to modules/AgenticGuidance/agents/test/
