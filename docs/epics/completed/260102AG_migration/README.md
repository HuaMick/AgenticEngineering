# 260102AG_migration - AgenticGuidance Migration (Planner Agents Only)

**Created**: 2026-01-02
**Branch**: main
**Status**: COMPLETE
**Last Updated**: 2026-01-02
**Completed**: 2026-01-02

## Purpose

Migrate the **planner agents and their direct dependencies** from legacy MyAgentsGuidance to AgenticGuidance module.

**Source**: `/home/code/AgenticEngineering/modules/legacy/MyAgents/projects/MyAgentsGuidance/entrypoints/_plan.yml`
**Destination**: `/home/code/AgenticEngineering/modules/AgenticGuidance/`

## IMPORTANT: Migration Scope

This migration is **localized to planner agents only** - NOT the entire agent ecosystem.

### What IS in scope:
- `_plan.yml` entrypoint and its direct dependencies
- The 8 planner agents in `agents/planner/`
- Assets (definitions, guidelines, examples) that planner agents directly reference
- Input files that planner agents use

### What is NOT in scope:
- `agents/teacher/` - separate agent category (not migrated)
- `agents/explore/` - separate agent category (not migrated)
- `agents/orchestration/` - separate agent category (not migrated)
- `agents/documentation/` - separate agent category (not migrated)
- `agents/test/` - only migrated where directly needed by planner agents
- `agents/build/` - only migrated where directly needed by planner agents
- `agents/deploy/` - only migrated where directly needed by planner agents
- `agents/cleaner/` - only migrated where directly needed by planner agents

### Intentional Broken References

References to other agent categories (teacher, explore, orchestration, documentation, etc.) within the migrated planner agents are **intentionally left as broken references** pointing to the legacy location. These are separate agents with separate objectives that may be migrated independently in the future.

## Current Phase

**COMPLETE**

All migration phases completed including refactoring to true "planner only" scope.

### Completed Refactoring (2026-01-02)

| Task | Description | Status |
|------|-------------|--------|
| REFACTOR-001 | Create `agents/manifest.yml` listing only planner agents | **COMPLETE** |
| REFACTOR-002 | Create `agents/README.md` with design decisions | **COMPLETE** |
| REFACTOR-003 | Add `assets/definitions/readme-context.yml` | **COMPLETE** |
| REFACTOR-004 | Update planner manifests with placeholder comments | **COMPLETE** |
| REFACTOR-005 | Remove `build/`, `test/`, `cleaner/`, `deploy/` directories | **COMPLETE** |
| REFACTOR-006 | Final validation | **COMPLETE** |

### Resolution Summary

- **6 consecutive review approvals** achieved
- All non-planner agent directories removed from `agents/`
- `agents/` now contains only: `manifest.yml`, `README.md`, `planner/`
- Planner manifests updated with `# NOT_MIGRATED:` placeholder comments for references to non-migrated agents
- README-as-context design pattern documented in `assets/definitions/readme-context.yml`

## Related References

- All progress tracking is maintained in this canonical plan location
- This canonical plan location follows legacy planning standards from `assets/definitions/plans.yml`

## Plan Files

All plans have been completed and archived:

| File | Purpose | Status |
|------|---------|--------|
| `completed/plan_migrate.yml` | Core migration plan (phases 1-3) | **Complete** |
| `completed/plan_validate.yml` | Validation and cleanup (phases 4-5) | **Complete** |
| `completed/plan_refactor.yml` | Refactor to true planner-only scope | **Complete** |
| `completed/plan_completed.yml` | Archive of completed items | **Reference** |

## Folder Structure

```
260102AG_migration/
├── README.md           # This file
└── completed/          # All completed plan files
    ├── plan_completed.yml
    ├── plan_migrate.yml
    ├── plan_validate.yml
    └── plan_refactor.yml
```

## Migration Summary

### Scope: Planner-Focused Migration

This migration targeted **planner agents and their direct dependencies only**. Supporting agent categories (test, build, deploy, cleaner) were migrated only where directly referenced by planner agents, not as complete agent ecosystems.

### Files Migrated (71 total)

**Entrypoint (1):**
- `entrypoints/_plan.yml` - Main planning entrypoint

**Guidelines (11):**
- Core 6: fix-the-source, experiment-first, context-minimisation, worktree-and-branching, response-audit, iteration
- Dependencies 5: testing, safety, reward-hacking-prevention, less-is-more, focus-on-what-didnt-work

**Definitions (30):**
- Core 2: plans.yml, guidance.yml
- Dependencies 28: Including context-minimisation, escalation, exploration-principles, fence, folder-structure, guidance-artifacts, iteration-approach, minimal-sufficient-change, outcome-verification, overengineering, path, reward-hacking, role-separation, root-cause-analysis, separation-of-concerns, skipped-test, steps, success-criteria, testing-types, agent-loops, and 9 strategy-* files

**Examples (3):**
- `assets/examples/planner/YYMMDDRepo_Branch/live/plan_live_teach.yml`
- `assets/examples/planner/YYMMDDRepo_Branch/live/plan_live_test.yml`
- `assets/examples/planner/YYMMDDRepo_Branch/live/plan_live_audit_clean.yml`

**Planner Agents (25) - PRIMARY MIGRATION TARGET:**
- `agents/planner/manifest.yml` - Parent manifest with 8 sub_agents
- `agents/planner/planner-phases/` - Initial objective decomposition (3 files)
- `agents/planner/planner-build/` - Implementation planning (3 files)
- `agents/planner/planner-test/` - Test planning with loops (3 files)
- `agents/planner/planner-cleaning/` - Cleanup and audit planning (3 files)
- `agents/planner/planner-teach/` - Guidance improvement planning (3 files)
- `agents/planner/planner-agent-exam/` - Agent validation exams (3 files)
- `agents/planner/planner-reviewer/` - Plan review and approval (3 files)
- `agents/planner/planner-test-guidance/` - Guidance completeness testing (3 files)

**Removed (not applicable to planning agents):**
- `assets/examples/teacher/concise.yml` - Teacher-specific example, removed from AgenticGuidance module

**Other (1):**
- README.md

### Planner Agent Dependencies (MIGRATED)

All planner agent dependencies have been migrated:

**Input Layers (6) - COMPLETE:**
- assets/inputs/core-system.yml
- assets/inputs/core-guidelines.yml
- assets/inputs/planner-shared.yml
- assets/inputs/test-shared.yml
- assets/inputs/cleaner-shared.yml
- assets/inputs/deploy-shared.yml

**Missing Definitions (14) - COMPLETE:**
- agent-categories.yml, signpost.yml, success-criteria-teacher.yml, definition.yml
- guideline.yml, generalized-vs-specific.yml, agent-context-files.yml
- knowledge-encapsulation.yml, user-stories.yml, testing-documentation.yml
- test-execution-workflow.yml, friction.yml, strategy-guidance-blind-test.yml
- guidance-test-scenarios.yml

**Missing Examples (4) - COMPLETE:**
- assets/examples/teacher/concise.yml
- assets/examples/planner/teaching-plan-example.yml
- assets/examples/test/guidance-test-plan.yml
- assets/examples/planner/YYMMDDRepo_Branch/completed/plan_completed.yml

### Supporting Agent Categories (PARTIAL - Planner Dependencies Only)

The following agent categories were migrated **only because planner agents reference them directly**. They are NOT complete migrations of these agent ecosystems. These are minimal subsets required for planner agent functionality.

**Test Agents (10 sub-agents) - Partial migration for planner use:**
- agents/test/manifest.yml
- agents/test/test-runner/
- agents/test/test-user-simulator/
- agents/test/test-audit/
- agents/test/test-guidance-simulator/
- agents/test/test-builder/
- agents/test/test-final-output/
- agents/test/test-flutter-builder/
- agents/test/test-flutter-runner/
- agents/test/test-service/

**Deploy Agents (partial) - Partial migration for planner use:**
- agents/deploy/manifest.yml
- agents/deploy/deploy-cicd/

**Build Agents - Partial migration for planner use:**
- agents/build/manifest.yml
- agents/build/build-flutter/
- agents/build/build-python/

**Cleaner Agents - Partial migration for planner use:**
- agents/cleaner/manifest.yml
- agents/cleaner/cleaner-core/
- agents/cleaner/cleaner-execute/
- agents/cleaner/cleaner-identify/

### Agent Categories NOT Migrated (Out of Scope)

The following agent categories are **intentionally NOT migrated** as they are separate agents with separate objectives:

- `agents/teacher/` - Teaching and guidance creation agents
- `agents/explore/` - Exploration and discovery agents
- `agents/orchestration/` - Orchestration and coordination agents
- `agents/documentation/` - Documentation generation agents

Any references to these categories within migrated planner agents are **intentionally left pointing to the legacy location**. They may be migrated independently in the future.

**Transitive Dependencies (22 additional definition files) - COMPLETE:**
- acceptable-skips.yml, test-builder-role.yml, test-creation-principles.yml
- test-structure.yml, test-runner-role.yml, plan-inputs.yml
- domains.yml, workflows.yml, entrypoints.yml
- cleaner-shared-guidelines.yml, voting-system.yml, preserved-files.yml
- signal-and-noise.yml, workflow-test-readme.yml, studio-integration-tests.yml
- test-roles.yml, flutter-project-type.yml, flutter-test-structure.yml
- flutter-test-roles.yml, flutter-environments.yml, flutter-skipped-tests.yml
- flutter-test-execution.yml, builder-role.yml, component-verification.yml

**Additional Examples - COMPLETE:**
- assets/examples/cleaner/dir-allowed.yml
- assets/examples/cleaner/dir-not-allowed.yml
- assets/examples/cleaner/preserved-files.yml
- assets/examples/test/critical_questions.yml
- assets/examples/test/final_outcome_report.yml
