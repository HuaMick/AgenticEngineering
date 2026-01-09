# Plan Metadata: 260104AE_agenticguidance

## Context
- **Plan ID**: 260104AE_agenticguidance
- **Worktree**: `/home/code/AgenticEngineering-agenticguidance`
- **Branch**: `agenticguidance`
- **Objective**: Refactor orchestration to be generic, split planning entrypoints (build/teach), and transition to MMD-driven dynamic workflows.

## Session History
- **2026-01-04**: Initial setup of `agenticguidance` worktree.
- **2026-01-06 (Session 1)**: Remediation of entrypoint refactor complete. CLI capability mapping performed.
- **2026-01-06 (Session 2)**: Agent self-review testing completed (19 agents). Identified 100+ friction points. Friction Remediation phase completed (7 tasks). Fixed critical path semantics, required inputs, loop context, output schemas, fragment references, context loading, and version alignment.
- **2026-01-06 (Session 3)**: Agent Self-Review Testing Phase 2 completed via Ralph loop (8 iterations). 19 agents re-reviewed via test-guidance-simulator. Created plan_live_teach.yml with 8 teaching phases. Added Friction Remediation Phase 2 with 11 tasks.
- **2026-01-08 (Session 4)**: **EXAMPLE-ALIGNMENT-001 COMPLETED**. Executed 7-phase plan to update planner examples:
  - Phase 1: Added root-level inputs pattern to 4 example plan files
  - Phase 2: Created unified main plan example (plan_main.yml) with related_plans
  - Phase 3: Created MMD orchestration example (orchestration.mmd) with metadata
  - Phase 4: Added decision_items pattern to teach plan example
  - Phase 5: Created README.md example with consolidated session tracking
  - Phase 6: Updated guidance alignment (plans.yml, process.yml, inputs.yml)
  - Phase 7: Verification passed - all checklist items verified
- **2026-01-09 (Session 5/6)**: **PLAN STRUCTURE STANDARDIZATION**. Comprehensive planning and audit execution:
  - Created consolidated teach plan (plan_live_teach_consolidated.yml) with T4 specialization
  - Generated 6 detailed audit files for agent guidance review
  - Created 6 review plans from audit findings
  - Built remediation plans for planner-guidance, planner-test, planner-cleaning, planner-build, deploy-worktree, and planner-reviewer
  - Established plan_example.yml as unified structure standard
- **2026-01-09 (Session 7)**: **PLAN CLEANUP AND CONSOLIDATION**. Streamlined plan structure:
  - Moved 2 superseded plans to completed: plan_live_teach.yml, plan_live_orchestration_remodel.yml
  - Consolidated 3 planner remediation plans (cleaning, build, test) into unified remediation approach
  - T4 specialized core layer work unified across all planner agents
  - Reduced live plan count for clearer active work tracking

## Implementation Details

### Session 3 Implementation (Ralph Loop)

**Iteration 1-2: Agent Self-Review Testing**
- Spawned 19 test-guidance-simulator agents in parallel
- Each agent reviewed its own guidance files (process.yml, inputs.yml, manifest.yml)
- Generated structured YAML reports with severity classifications (CRITICAL, HIGH, MEDIUM, LOW)
- Aggregated 180+ friction points into consolidated audit report

**Iteration 2-3: _plan_teach.yml Pattern Execution**
- Created plan_live_teach.yml following the teach plan structure
- Mapped all CRITICAL and HIGH friction points to specific teach phases
- Documented 2 decision items requiring human input before execution
- Added related_plans reference to main plan

**Iteration 4-5: Documentation and Preparation**
- Created NEXT_SESSION_CHECKLIST.md with prioritized execution guide
- Created session summary (audit/260106_session3_summary.yml)
- Verified all deliverables and coverage

**Key Findings Summary**
| Category | Count | Examples |
|----------|-------|----------|
| CRITICAL | 12 | Legacy-only agents, fragment resolution, missing process.yml |
| HIGH | 38 | Version mismatches, empty outputs, undefined REPO_ROOT |
| MEDIUM | 52 | Comment-only guidelines, excessive context loading |
| LOW | 34 | Missing outputs.yml files, version scheme clarity |

## Status
- **Phase 0 (Friction Remediation)**: **COMPLETED** (7/7 tasks)
- **Phase 0.5 (Friction Remediation Phase 2)**: **PENDING** (11 tasks - 4 CRITICAL, 7 HIGH)
- **Phase 1 (CLI Offloading)**: Pending (4 tasks)
- **Phase 2 (Entrypoint & Schema)**: Pending (2 tasks)
- **Phase 3 (MMD Implementation)**: Pending (3 tasks)
- **Phase 4 (Asset & Example Alignment)**: **COMPLETED** (plan_live_example_alignment.yml - 7 phases)
- **Phase 5 (Agent Self-Review Testing)**: **COMPLETED** (19 agents tested x2)
- **Phase 6 (CLI Fitness Testing)**: **COMPLETED** (CLI verified working)
- **Phase 7 (Plan Cleanup)**: **COMPLETED** (Session 7 - consolidation and archival)

## Folder Structure

```
260104AE_agenticguidance/
├── README.md                    # This file
├── NEXT_SESSION_CHECKLIST.md    # Prioritized execution guide
├── analysis/                    # Analysis artifacts
├── audit/
│   ├── 260106_agent_self_review_results.yml   # Session 2 findings
│   ├── 260106_audit_findings.yml              # Initial audit
│   ├── 260106_session2_self_review_results.yml # Session 3 consolidated (180+ points)
│   ├── 260106_session3_summary.yml            # Session summary
│   └── agent-reports/                         # Individual agent reports
│       ├── orchestration-planning-report.yml  # 19 issues (2 CRITICAL)
│       ├── orchestration-build-report.yml     # 30 issues (4 CRITICAL)
│       ├── planner-build-report.yml           # 12 issues (3 HIGH)
│       ├── planner-guidance-report.yml        # 16 issues (2 CRITICAL)
│       ├── planner-test-report.yml            # 11 issues (3 HIGH)
│       └── planner-phases-review.yml          # 11 issues (2 CRITICAL, legacy-only)
├── completed/
│   ├── plan_live_build.yml
│   ├── plan_live_remediation.yml
│   ├── plan_next_actions.yml
│   ├── plan_completed_example_alignment.yml   # Example alignment (7 phases) - Session 4
│   ├── plan_live_teach.yml                    # Original teach plan - superseded by consolidated
│   └── plan_live_orchestration_remodel.yml    # Orchestration remodel - superseded
└── live/
    ├── orchestration_agenticguidance.mmd      # Orchestration flow diagram
    ├── plan_agenticguidance.yml               # Main plan (all phases)
    │
    │   # Active Plans
    ├── plan_live_teach_consolidated.yml       # Consolidated teach plan with T4 specialization
    ├── plan_live_build_migration.yml          # Test agent migration plan
    ├── plan_live_cleanup_deprecation.yml      # Legacy agent deprecation plan
    │
    │   # Guidance Remediation (Consolidated)
    ├── plan_planner_guidance_remediation.yml  # Unified planner guidance fixes
    ├── plan_guidance_deploy_worktree_remediation.yml  # Deploy-worktree guidance fixes
    ├── plan_guidance_reviewer_context.yml     # Reviewer context improvements
    │
    │   # Audit Files
    ├── audit_deploy_worktree.yml              # Deploy-worktree agent audit
    ├── audit_planner_build.yml                # Planner-build agent audit
    ├── audit_planner_cleaning.yml             # Planner-cleaning agent audit
    ├── audit_planner_guidance.yml             # Planner-guidance agent audit
    ├── audit_planner_reviewer.yml             # Planner-reviewer agent audit
    ├── audit_planner_test.yml                 # Planner-test agent audit
    │
    │   # Review Plans
    ├── review_deploy_worktree.yml             # Deploy-worktree review plan
    ├── review_planner_build.yml               # Planner-build review plan
    ├── review_planner_cleaning.yml            # Planner-cleaning review plan
    ├── review_planner_guidance.yml            # Planner-guidance review plan
    ├── review_planner_reviewer.yml            # Planner-reviewer review plan
    └── review_planner_test.yml                # Planner-test review plan
```

## Quick Start for Next Session
See `NEXT_SESSION_CHECKLIST.md` for prioritized execution guide.

## Plan Structure Standard

Plans in this project follow the unified structure defined in `plan_example.yml`.

**Reference**: `modules/AgenticGuidance/assets/examples/planner/YYMMDDRepo_Branch/plan_example.yml`

**Key Sections**:
- `metadata`: Plan identification (plan_id, title, version, status, created, updated)
- `context`: Worktree path, branch, objective, and current phase
- `related_plans`: Links to associated plans (main, teach, audit, review)
- `inputs`: Required inputs with sources and validation status
- `open_questions`: Pending decisions with options and recommendations
- `phases`: Structured phases with tasks, dependencies, and deliverables
- `success_criteria`: Measurable outcomes for plan completion

**Plan Types**:
- Main plans (`plan_*.yml`): Primary coordination plans
- Teach plans (`plan_live_teach*.yml`): Teaching and guidance improvement
- Audit plans (`audit_*.yml`): Agent guidance audits
- Review plans (`review_*.yml`): Audit review and action items
- Remediation plans (`plan_*_remediation.yml`): Fix implementations

## Live Plans

### Core Plans
- `live/plan_agenticguidance.yml` - Main plan with all phases and remediation tasks
- `live/orchestration_agenticguidance.mmd` - Orchestration flow diagram

### Teach Plans
- `live/plan_live_teach_consolidated.yml` - Consolidated teach plan with T4 specialization

### Migration & Deprecation
- `live/plan_live_build_migration.yml` - Test agent migration (test-user-simulator, test-service, test-builder)
- `live/plan_live_cleanup_deprecation.yml` - Legacy agent deprecation (planner-phases, planner-teach)

### Guidance Remediation Plans (Consolidated)
- `live/plan_planner_guidance_remediation.yml` - Unified planner guidance fixes (covers planner-guidance, planner-build, planner-test, planner-cleaning)
- `live/plan_guidance_deploy_worktree_remediation.yml` - Deploy-worktree guidance updates
- `live/plan_guidance_reviewer_context.yml` - Reviewer context improvements

### Audit Files
- `live/audit_planner_guidance.yml` - Planner-guidance agent audit findings
- `live/audit_planner_build.yml` - Planner-build agent audit findings
- `live/audit_planner_test.yml` - Planner-test agent audit findings
- `live/audit_planner_cleaning.yml` - Planner-cleaning agent audit findings
- `live/audit_planner_reviewer.yml` - Planner-reviewer agent audit findings
- `live/audit_deploy_worktree.yml` - Deploy-worktree agent audit findings

### Review Plans
- `live/review_planner_guidance.yml` - Review actions for planner-guidance
- `live/review_planner_build.yml` - Review actions for planner-build
- `live/review_planner_test.yml` - Review actions for planner-test
- `live/review_planner_cleaning.yml` - Review actions for planner-cleaning
- `live/review_planner_reviewer.yml` - Review actions for planner-reviewer
- `live/review_deploy_worktree.yml` - Review actions for deploy-worktree

## Completed Plans
- `completed/plan_completed_example_alignment.yml` - Example alignment (7 phases) - Session 4
- `completed/plan_live_build.yml` - Initial build plan
- `completed/plan_live_remediation.yml` - Initial remediation
- `completed/plan_next_actions.yml` - Action items tracking
- `completed/plan_live_teach.yml` - Original teach plan (superseded by consolidated) - Session 7
- `completed/plan_live_orchestration_remodel.yml` - Orchestration remodel (superseded) - Session 7

## Next Steps
Complete Friction Remediation Phase 2 (11 tasks) and Teach Plan (8 phases) before resuming CLI Offloading.

### Critical Decisions Required
1. **DECISION-001**: Resolve legacy-only agents (planner-phases, planner-teach)
   - Options: Migrate, Deprecate, or Merge into orchestration-planning
   - Recommendation: Evaluate if orchestration-planning already handles phase decomposition

2. **DECISION-002**: NOT_MIGRATED test agents (test-user-simulator, test-service, test-builder)
   - Options: Add fallback paths, Migrate agents, or Remove strategies
   - Recommendation: Start with fallback paths, migrate incrementally

### Teach Phases Ready for Execution
1. Fragment Reference Resolution (CRITICAL) - `teach_frag_001`
2. Process File Format Standardization (CRITICAL) - `teach_proc_001`
3. Output Schema Documentation (HIGH) - `teach_out_001`
4. Required Input Validation (HIGH) - `teach_inp_001`
5. Version Alignment (HIGH) - `teach_ver_001`
6. CLI Command Centralization (HIGH) - `teach_cli_001`
7. Spawns Declaration (HIGH) - `teach_spn_001`
8. REPO_ROOT Variable Definition (HIGH) - `teach_repo_001`
