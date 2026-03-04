# Plan: Close _plan_teach.yml Test Planning Gap

**Plan ID**: 260131GA_close_plan_teach_test_planning_gap
**Branch**: teach-test-gap
**Worktree**: /home/code/AgenticEngineering-teach-test-gap
**Status**: Planning
**Created**: 2026-01-31

## Problem Statement

The `_plan_teach.yml` entrypoint currently orchestrates guidance changes through:
- **Teach phase**: Guidance updates via teacher-update-assets
- **Validation phase**: Agent self-review
- **Audit phase**: Consistency checks

**MISSING**: Test phase to validate that guidance changes actually work correctly with simulated agent behavior.

Without this test phase, guidance changes may pass validation but fail during actual agent execution. The honeycomb/UAT guidance plan (260130HO) demonstrated this gap - it completed with only self-review and audit validation, without any behavioral testing.

## Root Cause

The orchestration-planning process includes CheckTest routing, but when invoked via `_plan_teach.yml`:
1. The orchestrator may skip test phase for "guidance-only" changes
2. There's no explicit routing to test-guidance-simulator scenarios
3. `test-guidance-simulator` agent exists but isn't invoked from the planning flow

## Proposed Solution

**Hybrid of Option B + Option C** (from friction analysis):

1. Modify `orchestration-planning/process.mmd` to detect teach intent
2. Add `CheckGuidanceTestRequired` decision node after teach phase
3. Route to test phase when guidance files are modified
4. `planner-test` generates `test-guidance-simulator` execution tasks
5. Make test phase conditional on change severity

## Plan Structure

```
260131GA_close_plan_teach_test_planning_gap/
├── README.md                  # This file
├── plan_teach.yml             # Teach/implementation phases (3 phases, 9 tasks)
├── plan_test.yml              # Test strategy and validation (3 phases, 8 tasks)
├── plan_audit_clean.yml       # Audit and cleanup tasks (3 phases, 5 tasks)
├── plan_completed.yml         # Completion tracking (template)
└── analysis/
    └── friction_analysis.yml  # Gap investigation and recommendations
```

## Phases Overview

### Phase 1: Investigation and Design (plan_teach.yml)
- Review test-guidance-simulator capabilities
- Map orchestration-planning test routing
- Design planner-test guidance mode

### Phase 2: Implementation (plan_teach.yml)
- Update orchestration-planning/process.mmd
- Update planner-test for guidance mode
- Update _plan_teach.yml documentation

### Phase 3: Validation (plan_teach.yml)
- Self-review modified guidance files
- Dry-run test flow with sample guidance change

### Test Phases (plan_test.yml)
- Unit validation tests
- Integration tests
- Self-review validation

### Audit/Cleanup (plan_audit_clean.yml)
- Consistency audit
- Stale reference search
- Cleanup and documentation updates

## Open Questions

| ID | Question | Proposed Answer |
|----|----------|-----------------|
| oq_001 | Should ALL guidance changes require test simulation? | Yes, with graduated depth based on severity |
| oq_002 | What's the minimum viable test for guidance changes? | self_review_test, reference_resolution_test, task_completion_test |
| oq_003 | Should test failures block plan completion? | Yes, with severity-based escalation |
| oq_004 | How to detect which agents need testing? | Use file patterns from guidance-process-requirements.yml |

## Files in Scope

- `modules/AgenticGuidance/agents/orchestration/orchestration-planning/process.mmd`
- `modules/AgenticGuidance/agents/planner/planner-test/process.yml`
- `modules/AgenticGuidance/agents/planner/planner-test/inputs.yml`
- `modules/AgenticGuidance/entrypoints/_plan_teach.yml`

## Files Out of Scope

- `modules/AgenticGuidance/agents/test/test-guidance-simulator/` (exists, no changes needed)
- `modules/legacy/` (legacy code)

## Success Criteria

1. `_plan_teach.yml` flow includes test phase for guidance validation
2. `orchestration-planning` routes to test phase after teach completes
3. `planner-test` generates test-guidance-simulator tasks when `guidance_test_mode=true`
4. Test scenarios cover self-review, reference resolution, and task completion
5. Documentation updated to reflect new test phase
6. Self-review passes for all modified guidance files

## Related Artifacts

- `/home/code/AgenticEngineering/modules/AgenticGuidance/entrypoints/_plan_teach.yml`
- `/home/code/AgenticEngineering/modules/AgenticGuidance/agents/orchestration/orchestration-planning/process.mmd`
- `/home/code/AgenticEngineering/modules/AgenticGuidance/agents/test/test-guidance-simulator/process.yml`
- `/home/code/AgenticEngineering/modules/AgenticGuidance/agents/planner/planner-test/process.yml`
- `/home/code/AgenticEngineering/modules/AgenticGuidance/assets/definitions/guidance-process-requirements.yml`

## Execution

To execute this plan:
```bash
cd /home/code/AgenticEngineering-teach-test-gap
agentic entrypoint execute _orchestrate --plan 260131GA_close_plan_teach_test_planning_gap
```
