# Plan: 260104AE_agenticguidance

## Status: IN_PROGRESS

**Updated**: 2026-01-12
**Branch**: `agenticguidance`
**Worktree**: `/home/code/AgenticEngineering-agenticguidance`

## Current Work: Post-Definitions Audit Self-Review

**Session 2026-01-12 (Ralph Loop Orchestration)**

### Definitions Audit Remediation - COMPLETE
Executed `completed/plan_teach_definitions_audit_remediation.yml` with 4 phases:

1. **Phase 1: Remove Redundant Files** - COMPLETE (5 files deleted)
   - Deleted test-roles.yml (redundant with test-builder-role.yml + test-runner-role.yml)
   - Deleted testing-documentation.yml (100% project-specific)
   - Deleted acceptable-skips.yml (project-specific test counts)
   - Deleted success-criteria-teacher.yml (merged into success-criteria.yml)
   - Deleted flutter-project-type.yml (22 bytes, obsolete)
   - Updated 11 files with reference changes

2. **Phase 2: Move Strategy Files to Guidelines** - COMPLETE (10 files moved)
   - Moved all strategy-*.yml files from definitions/ to guidelines/
   - Updated 18 files with new path references
   - All strategy files now in prescriptive guidelines/ folder

3. **Phase 3: Reclassify Prescriptive Definitions** - COMPLETE (12 files moved)
   - Moved escalation.yml, exploration-principles.yml, test-structure.yml (renamed to test-organization.yml)
   - Moved test-creation-principles.yml, test-execution-workflow.yml (with TODO for generalization)
   - Moved minimal-sufficient-change.yml, iteration-approach.yml, root-cause-analysis.yml
   - Moved model-first-verification.yml, component-verification.yml, readme-context.yml, preserved-files.yml
   - Updated all references across agent inputs.yml and layer files

4. **Phase 4: Consolidate Related Files** - COMPLETE
   - Merged separation-of-concerns.yml into role-separation.yml (6 files updated)
   - KEEP SEPARATE: fence.yml and signpost.yml (serve distinct conceptual purposes)

### Agent Self-Review Testing (Round 2) - COMPLETE
Spawned 23 agents to self-review their own guidance files:
- **Test agents**: 7 reviewed (avg clarity: 3.1)
- **Planner agents**: 6 reviewed (avg clarity: 3.5)
- **Orchestration agents**: 4 reviewed (avg clarity: 3.0)
- **Teacher/Deploy/Build agents**: 6 reviewed (avg clarity: 3.0)

**Findings**: `audit/260112_self_review_findings.yml`
- 18 critical issues identified
- 32 high-priority issues
- 10 cross-cutting patterns found (XCUT-001 to XCUT-010)
- Key issues: path references to definitions/ (now in guidelines/), empty outputs: [], missing outputs.yml files

### Key Cross-Cutting Issues Discovered
1. **XCUT-001 (CRITICAL)**: Path references still pointing to definitions/ for migrated files
2. **XCUT-002 (CRITICAL)**: Empty outputs: [] in 6 agents despite producing artifacts
3. **XCUT-003 (HIGH)**: Missing outputs.yml files referenced in test-guidance-simulator and planner-guidance-testing
4. **XCUT-004 (HIGH)**: Inconsistent placeholder naming (plan_id vs plan_folder vs plan_folder_name)
5. **XCUT-006 (HIGH)**: References to deleted success-criteria-teacher.yml

### Self-Review Remediation R2 - COMPLETE
Executed `completed/plan_teach_self_review_remediation_r2.yml`:

1. **Phase 1 (Critical)** - COMPLETE
   - crit_001: Fixed path references (definitions/ → guidelines/) in build-flutter and build-python inputs.yml
   - crit_002: Defined output schema for planner-guidance-testing

2. **Phase 2 (High)** - COMPLETE
   - high_001: Removed all outputs.yml references from test-guidance-simulator and planner-guidance-testing
   - high_002: Standardized placeholders to {plan_folder_name} in 6 planner files
   - high_003: Updated success-criteria-teacher.yml references (4 process.yml files)

3. **Phase 3 (Validation)** - COMPLETE
   - val_002: No empty outputs:[] remaining (7 agents fixed)
   - val_003: No outputs.yml references remaining
   - val_004: No {plan_id} or {plan_folder} placeholders remaining
   - val_005: No success-criteria-teacher references remaining
   - val_006: Spot-check passed for planner-guidance-testing, build-flutter, test-runner

**Additional fixes**: Defined output schemas for 7 agents (build-flutter, build-python, teacher-update-assets, test-builder, test-runner, test-service, test-user-simulator)

---

**Session 2026-01-11 (Ralph Loop Orchestration)**

### Documentation Fixes - COMPLETE
Executed `live/plan_documentation_fixes.yml`:
1. **Phase 1: Restructure Components** - COMPLETE
   - Moved 5 phase template files to `assets/examples/orchestration/phase_templates/`
   - Created 3 new reusable components (feedback_loop.mmd, approval_gate.mmd, audit_test_fix_loop.mmd)
   - Created README.md for components folder
2. **Phase 2: Fix Plan Examples** - COMPLETE
   - Deleted 4 phase-split example files
   - Moved plan_example.yml to live/ subfolder
   - Updated content to show unified approach
3. **Phase 3: Update Documentation** - COMPLETE
   - Verified agents/README.md and module README.md are current
   - Updated docs/README.md with empty live folder note

### Agent Self-Review Testing - COMPLETE
Spawned 4 audit agents to review all 23 agents in parallel:
- **Test agents**: 7 reviewed (medium-low clarity)
- **Planner agents**: 6 reviewed (medium-low clarity)
- **Orchestration agents**: 4 reviewed (2 deprecated)
- **Teacher/Deploy/Build agents**: 6 reviewed (medium-low clarity)

**Findings**: `audit/260111_self_review_findings.yml`
- 5 critical issues identified
- 14 cross-cutting patterns found
- 0 agents rated "high" clarity, 12 "medium", 11 "low"

### Self-Review Remediation - COMPLETE
Executed `live/plan_teach_self_review_remediation.yml` with 4 phases:

1. **Phase 1: Critical Fixes** - COMPLETE (4 tasks)
   - Fixed broken path in teacher-update-assets/process.yml
   - Added deprecation flags to orchestration-guidance and orchestration-build manifests
   - Clarified orchestration-executor path semantics (plan_folder_path excludes trailing /live/)
   - Updated 11 files with component references to phase_templates/ location

2. **Phase 2: Cross-Cutting Cleanup** - COMPLETE (5 tasks)
   - Removed impossible 'update path' instructions from 4 test agents
   - Added loop_context sections to 5 test agents
   - Defined outputs in process.yml for 7 agents
   - Synchronized version numbers for 3 agents
   - Added required_inputs sections to 3 planners

3. **Phase 3: Standardization** - COMPLETE (3/4 tasks)
   - Standardized loop terminology (audit-test-fix-loop as canonical)
   - Standardized agent_context reference format across 15+ agents
   - Standardized manifest.yml structure for 4 agents (deploy/build)
   - DEFERRED: Extract MMD generation logic (requires significant refactoring)

4. **Phase 4: Documentation Improvements** - COMPLETE (3 tasks)
   - Documented subagent spawning mechanism in test-guidance-simulator
   - Documented placeholder resolution in test-final-output
   - Expanded vague build steps in build-flutter and build-python

### Planner Component Awareness - COMPLETE
Executed `live/plan_teach_planner_component_awareness.yml`:

1. **Teach Phase** - COMPLETE (7 tasks)
   - Created `component-over-workflow.yml` guideline in guidelines/
   - Created `planner-components.yml` definition with component inventory
   - Wired awareness through shared layers (planner-core-guidelines.yml, planner-shared.yml)
   - All planners now inherit component awareness automatically

2. **Cleanup Phase** - COMPLETE (5 tasks)
   - Deleted `strategy-guidance-blind-test.yml` (replaced by component)
   - Updated 16 references across 8 files to point to guidance_blind_test.mmd component
   - Verified legacy copy preserved for historical reference

3. **Test Phase** - DEFERRED
   - Blind tests deferred to dedicated session to avoid bias

### Decommissioning Guideline - COMPLETE
Executed `live/plan_teach_decommissioning_guideline.yml`:
- Created `decommissioning-over-deprecation.yml` guideline
- Wired into planner-cleaning inputs
- Tested: Cleaner agents now autonomously identify deprecated components for full removal

### Definitions Audit - PLANNING COMPLETE
Created `live/plan_teach_definitions_audit_remediation.yml` for next session:
- 88 definition files audited by 6 parallel agents
- ~30 files to reclassify (definitions → guidelines)
- ~12 files to remove (redundant/obsolete)
- ~8 files to generalize (project-specific content)

## Previous Objective

Consolidate remaining tasks for CLI offloading and MMD orchestration refinement. This plan unified work to:
- Offload deterministic logic to the agentic-cli
- Implement dynamic orchestration via Mermaid diagrams
- Remediate friction points discovered through agent self-review testing
- Create teaching artifacts for MMD-driven orchestration

## Final Session Progress (2026-01-11)

### Orchestration Decommissioning - ALL PHASES COMPLETE

**Phases 1-5: BUILD WORK COMPLETE**
- Phase 1: orchestration-planning MMD Generation - COMPLETE
  - Added MMD Generation subgraph to process.mmd (after AllPhasesPlanned, before HumanApproval)
  - inputs.yml already had plan-mmd-schema.yml and component examples
  - manifest.yml already had orchestration_*.mmd output declared

- Phase 2: planner-reviewer MMD Check - COMPLETE
  - MMD PRESENCE CHECKLIST already existed in process.yml
  - FENCE for rejection when MMD missing

- Phases 3-4: Deprecate orchestration-build and orchestration-guidance - COMPLETE
  - DEPRECATED.md files exist for both
  - Reference MMD examples created in assets/examples/orchestration/
  - README files updated with strikethrough and DEPRECATED labels

- Phase 5: Migrate _orchestrate.yml to orchestration-executor - COMPLETE
  - _orchestrate.yml now routes to orchestration-executor/process.yml
  - Executor discovers orchestration_*.mmd in <plan_folder>/live/
  - Documentation updated

**Phase 6: Integration Testing - COMPLETE**
- Structural validation audit: ALL 5 CHECKS PASS
- Runtime tests (int_005-010): Deferred to future enhancement session

**Phase 7: E2E Workflow Validation - COMPLETE**
- e2e_002: _plan_teach.yml flow validated (documentation already complete)
- e2e_003: Backward compatibility validated (6/6 checks PASS)
- e2e_001: Full _plan_build.yml flow deferred to dedicated session

### E2E Validation Results
| Check | Result |
|-------|--------|
| _orchestrate.yml routes to orchestration-executor | PASS |
| Input is plan_folder_path | PASS |
| Plan folder contains orchestration_*.mmd | PASS |
| Executor has startup_load_mmd step | PASS |
| Executor documents discovery process | PASS |
| Manifest contains spawns fence (12 agents) | PASS |

---

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
| Agent Self-Review Testing | 23 agents | Completed |
| Entrypoint & Schema | 2 | Completed |
| Orchestration Remodel | 6/7 | Completed |
| Asset & Example Alignment | 4 | Completed |
| CLI Fitness Testing | 7/8 | Completed |
| MMD Teaching Prerequisites | 7 | Completed |
| MMD Implementation | 3 (partial) | Completed |
| Test Infrastructure Optimization | 2 | Completed |
| Documentation Fixes | 3 phases | Completed |
| Self-Review Remediation | 15/16 tasks | Completed |
| Planner Component Awareness | 12/14 tasks | Completed |
| Decommissioning Guideline | 7/7 tasks | Completed |

## Deferred Items

| Item | Reason |
|------|--------|
| Integration test execution (mmd_005_002-005) | Requires focused testing session with actual executor invocation |
| remod_plan_001 (orchestration-planning MMD refactoring) | Lower priority |
| Integration test (CLI Fitness) | Out of scope |
| std_004: Extract MMD generation logic | Requires significant refactoring; lower priority |
| Planner component blind tests | Requires dedicated session to avoid bias |
| Definitions audit implementation | Pending next session (~40 files to reclassify/remove) |

## Folder Structure

```
260104AE_agenticguidance/
├── README.md                 # This file
├── analysis/                 # Viability assessments, friction analysis
├── audit/                    # Self-review results, findings
│   ├── 260111_self_review_findings.yml   # Consolidated findings
│   └── agent-reports/        # Individual agent reports
├── completed/                # 35 archived plan files
│   ├── plan_friction_remediation_phase1.yml
│   ├── plan_friction_remediation_phase2.yml
│   ├── plan_cli_offloading.yml
│   ├── plan_documentation_fixes.yml
│   ├── plan_teach_self_review_remediation.yml
│   └── ... (30 more)
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
| Documentation Fixes | `completed/plan_documentation_fixes.yml` | Completed |
| Self-Review Remediation | `completed/plan_teach_self_review_remediation.yml` | Completed |
| Planner Component Awareness | `completed/plan_teach_planner_component_awareness.yml` | Completed |
| Decommissioning Guideline | `completed/plan_teach_decommissioning_guideline.yml` | Completed |
| Definitions Audit Remediation | `live/plan_teach_definitions_audit_remediation.yml` | Pending |

## Success Criteria Met

- [x] Friction Remediation Phase 2: All 11 tasks completed (4 CRITICAL, 7 HIGH)
- [x] CLI Offloading: Worktree, plan folder, task status, and completed task movement handled by agentic-cli
- [x] Entrypoint & Schema: Orchestration pattern evaluated, Plan-MMD schema defined
- [x] MMD Implementation: Planners generate MMD, generic executor created (test execution deferred)
- [x] Asset Alignment: Examples use unified plan + orchestration.mmd pattern
- [x] DECISION-001 resolved: Legacy agents deprecated with DEPRECATED.md files
- [x] DECISION-002 resolved: Test agents migrated to modules/AgenticGuidance/agents/test/
- [x] Self-Review Remediation: 15/16 tasks completed (4 critical, 5 cross-cutting, 3 standardization, 3 documentation)
- [x] All critical issues (CRIT-001 to CRIT-004) resolved
- [x] No broken path references in any process.yml
- [x] Deprecated agents clearly marked in manifest.yml files
- [x] Component references updated to phase_templates/ location
- [x] All agents have defined outputs in process.yml
- [x] Loop terminology consistent (audit-test-fix-loop canonical)
- [x] Planner component awareness: All planners now prefer components over hardcoding
- [x] Decommissioning guideline: Cleaners autonomously identify deprecated components for removal
- [x] Definitions audit planned: 88 files audited, remediation plan created for next session
