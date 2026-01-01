# Orchestration Guidance Refinement Plan

**Branch**: `guidance-refinement-v1`
**Worktree**: `/home/code/myagents/MyAgentsGuidance-guidance-refinement-v1`
**Created**: 2025-12-21
**Objective**: Consolidate and verify agent guidance orchestration flow

## Purpose

This plan addresses friction in the orchestration workflow that coordinates planner-teach, planner-reviewer, and teacher agents to improve agent guidance. The focus is on making paths clearer, fences stronger, and signposts more discoverable.

## Background

The orchestration agent (defined at `agents/orchestration/process.mm`) manages a recursive planning loop:

```
LoadInputs → VerifyWorktree → PlanningLoop → Execute → Audit → Complete
                                    ↓
                          planner-teach ↔ planner-reviewer
                                    ↓
                          teacher-process, teacher-update-assets
```

Analysis revealed 9 friction points where agents lack clear guidance, causing:
- Ambiguity about loop termination conditions
- Missing context about teaching framework definitions
- Inconsistent planning artifacts
- Weak validation fences
- Path convention mismatches

## Approach

Following the planner-teach process, this refactor applies minimal, verifiable changes to guidance files:

1. **Critical Path Clarification** (Phase 1): Fix high-impact gaps in orchestration loop definition, inputs, and examples
2. **Strengthen Fences** (Phase 2): Add explicit validation criteria and loop contexts
3. **Remove Inconsistencies** (Phase 3): Standardize conventions and correct mismatches
4. **Verification** (Phase 4): Validate all changes and confirm checkpoints met

Each phase builds on the previous to reduce rework risk.

## Key Artifacts

### Analysis
- **`analysis/friction-analysis.md`**: Detailed friction analysis identifying 9 specific gaps, 2 mismatches, and 3 root cause patterns

### Plans
- **`plan_live_teach.yml`**: 4 phases, 13 tasks targeting specific guidance files with verifiable acceptance criteria

### Outputs (to be created during execution)
- Updated process files with loop contexts
- Extended inputs files with teaching framework references
- New teaching plan example
- Formalized approval checklists
- Standardized path conventions
- Updated definitions

## Scope

**In Scope**:
- Process files (process.yml, process.mm)
- Input files (inputs.yml)
- Definition files (agent-categories.yml, guidance-artifacts.yml, etc.)
- Example files (creating teaching-plan-example.yml)
- Loop context declarations

**Out of Scope**:
- Application code changes
- New agent creation
- Workflow logic changes (only documentation/guidance updates)

## Success Criteria

### User Experience
- Orchestrator executes guidance improvement loop without ambiguity
- Planner-teach produces consistent, reviewable planning artifacts
- Planner-reviewer has clear, verifiable approval criteria
- Teacher agents receive well-structured plans with explicit file paths
- All loop participants know their max iterations and escalation triggers

### Technical Validation
- All process files have valid loop_context where applicable
- All inputs.yml references resolve to existing files
- Teaching plan example matches actual plan structure used
- No path convention inconsistencies remain
- Zero broken references across all modified files

## Phase Summary

### Phase 1: Critical Path Clarification
**Target**: Orchestration loop clarity
**Impact**: HIGH
**Tasks**: 3 (loop context, inputs extension, example creation)

### Phase 2: Strengthen Fences
**Target**: Validation and loop definitions
**Impact**: MEDIUM
**Tasks**: 4 (approval checklist, loop contexts for planners, worktree verification)

### Phase 3: Remove Inconsistencies
**Target**: Convention standardization
**Impact**: LOW
**Tasks**: 3 (path conventions, category description, format guidance)

### Phase 4: Verification
**Target**: Quality assurance
**Impact**: CRITICAL
**Tasks**: 2 (reference validation, checkpoint verification)

## Execution Strategy

Per the orchestration process, this plan will be executed via:

1. **Planning Loop**: planner-teach creates/refines this plan → planner-reviewer approves
2. **Execution**: teacher-process and teacher-update-assets implement tasks in phase order
3. **Issues Handling**: Any execution issues trigger return to planning loop for plan updates
4. **Final Audit**: test-final-output validates all success criteria met
5. **Completion**: Move to docs/plans/completed/ upon successful verification

## Files Modified

### Process Files (7)
- `agents/orchestration/process.mm`
- `agents/orchestration/inputs.yml`
- `agents/planner/planner-teach/process.yml`
- `agents/planner/planner-teach/inputs.yml`
- `agents/planner/planner-reviewer/process.yml`

### Definition Files (3)
- `assets/definitions/agent-categories.yml`
- `assets/definitions/guidance-artifacts.yml`
- `assets/definitions/folder-structure.yml` (possibly)

### Example Files (1)
- `assets/examples/planner/teaching-plan-example.yml` (new)

### Input Files (variable)
- Multiple `agents/*/inputs.yml` files for path convention standardization

## Dependencies

- **External**: None
- **Internal**: Sequential phase dependencies (each phase builds on previous)
- **Coordination**: Requires orchestrator to manage teacher agent sequencing

## Risk Mitigation

### Low Risk Changes
All changes are documentation/guidance only. No code execution paths modified.

### Validation Gates
- Each task has explicit acceptance criteria
- Phase 4 validates all references before completion
- Broken reference check prevents deployment of invalid guidance

### Rollback Strategy
Git branch isolation allows easy rollback if issues discovered.

## References

### Process Definitions
- Planner-teach process: `agents/planner/planner-teach/process.yml`
- Orchestration process: `agents/orchestration/process.mm`
- Teacher processes: `agents/teacher/teacher-*/process.yml`

### Core Concepts
- Path: `assets/definitions/path.yml`
- Fence: `assets/definitions/fence.yml`
- Signpost: `assets/definitions/signpost.yml`
- Agent loops: `assets/definitions/agent-loops.yml`

### Guidelines
- Context minimization: `assets/guidelines/context-minimisation.yml`
- Fix the source: `assets/guidelines/fix-the-source.yml`
- Outcome verification: `assets/definitions/outcome-verification.yml`

## Timeline

This is a guidance improvement plan with no external deadlines. Execution proceeds based on agent availability and orchestrator scheduling.

Estimated effort:
- Phase 1: 3 tasks (critical) - Priority execution
- Phase 2: 4 tasks (medium) - Sequential after Phase 1
- Phase 3: 3 tasks (low) - Sequential after Phase 2
- Phase 4: 2 tasks (validation) - Final gate

## Notes

- This plan was created following the planner-teach process defined at `agents/planner/planner-teach/process.yml`
- All recommendations are grounded in observed friction patterns documented in `analysis/friction-analysis.md`
- Each task specifies exact files to modify and verifiable acceptance criteria
- The plan prioritizes high-impact changes first to reduce iteration risk
- Verification phase ensures no broken references before marking complete
