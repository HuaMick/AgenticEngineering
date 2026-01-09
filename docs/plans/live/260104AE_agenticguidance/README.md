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

## Folder Structure

```
260104AE_agenticguidance/
├── README.md                    # This file
├── NEXT_SESSION_CHECKLIST.md    # Prioritized execution guide
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
│   └── plan_completed_example_alignment.yml   # Example alignment (7 phases) - Session 4
└── live/
    ├── orchestration_agenticguidance.mmd      # Orchestration flow diagram
    ├── plan_agenticguidance.yml               # Main plan (all phases)
    └── plan_live_teach.yml                    # Teach plan (8 phases)
```

## Quick Start for Next Session
See `NEXT_SESSION_CHECKLIST.md` for prioritized execution guide.

## Live Plans
- `live/plan_agenticguidance.yml` - Main plan with all phases and remediation tasks
- `live/plan_live_teach.yml` - Teach-focused guidance improvements (8 teaching phases)
- `live/orchestration_agenticguidance.mmd` - Orchestration flow diagram

## Completed Plans (Session 4)
- `completed/plan_completed_example_alignment.yml` - Example alignment (7 phases completed)

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
