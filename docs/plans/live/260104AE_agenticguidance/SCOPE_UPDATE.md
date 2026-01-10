# Scope Update: Orchestration Decommissioning Added
**Date**: 2026-01-10
**Status**: Planning complete, ready for execution

## Summary

Added **plan_orchestration_decommission.yml** to complete the MMD-driven orchestration vision outlined in the orchestration-executor specification.

## What Was Added

### New Definition: Agent Momentum
**Problem Identified**: Planning agents often fail to generate MMD files during their process because they build momentum doing one task type (creating plan YAML) and forget ancillary requirements.

**Solution**: Create `agent-momentum.yml` definition that:
- Formalizes the cognitive pattern
- Provides detection signals
- Offers mitigation strategies (explicit checklists, output schemas)

### 7 Phases, 27 Tasks

| Phase | Tasks | Purpose |
|-------|-------|---------|
| **1. Teaching: Agent Momentum** | 3 | Define momentum, add validation to orchestration-planning, update planner outputs |
| **2. Build: Planner MMD Completeness** | 4 | Enable planner-test, planner-cleaning, planner-guidance-testing to generate MMD |
| **3. Build: Orchestration-Planning Refactor** | 3 | Transform into MMD generation coordinator/"guardian" |
| **4. Build: Deprecate orchestration-build** | 3 | Mark DEPRECATED, convert to reference MMD, remove from routing |
| **5. Build: Deprecate orchestration-guidance** | 3 | Same as orchestration-build deprecation |
| **6. Build: Entrypoint Migration** | 2 | Update `_orchestrate.yml` to route to orchestration-executor |
| **7. Test: Integration & E2E** | 9 | Complete deferred tests (int_005-010) + E2E validation |

**Total Estimated Effort**: 16-24 hours across multiple sessions

## Why This Matters

### Current Architecture (Hardcoded)
```yaml
_plan_build.yml    → orchestration-planning  # Hardcoded planning flow
_plan_teach.yml    → orchestration-planning  # Hardcoded planning flow
_orchestrate.yml   → orchestration-build     # Hardcoded execution flow
```

### Target Architecture (Generic, MMD-Driven)
```yaml
_plan_build.yml    → orchestration-planning  → planner-build → outputs MMD
_plan_teach.yml    → orchestration-planning  → planner-guidance → outputs MMD
_orchestrate.yml   → orchestration-executor  ← reads MMD dynamically
```

## Key Architectural Changes

### 1. orchestration-planning Role Change
**Before**: Hardcoded coordinator that knows which agents to spawn and when
**After**: Lightweight "MMD guardian" that:
- Spawns appropriate planner agents
- **Explicitly validates MMD generation** (anti-momentum)
- Presents plan YAML + orchestration MMD for approval
- Does NOT execute (delegates to orchestration-executor)

### 2. All Planners Generate MMD
**Currently**: Only planner-build and planner-guidance generate MMD
**Target**: ALL planners (test, cleaning, guidance-testing) generate MMD with:
- Required AGENT_ROUTING metadata
- Phase definitions
- Feedback triggers
- Status tracking

### 3. Hardcoded Flows Deprecated
**orchestration-build** and **orchestration-guidance**:
- Marked DEPRECATED with migration docs
- Converted to reference MMD examples
- Removed from active routing
- Replaced by generic orchestration-executor

### 4. Dynamic Execution
The executor reads MMD at runtime and determines:
- Which agents to spawn (from AGENT_ROUTING)
- How to handle failures (from FEEDBACK_TRIGGERS)
- When to loop vs escalate (from trigger patterns)
- Where to resume (from STATUS metadata)

## Agent Momentum: The Core Insight

### The Problem
Planners get into a flow:
1. Analyze objective ✓
2. Determine phases ✓
3. Create tasks ✓
4. Write plan YAML ✓
5. Generate MMD ✗ ← **FORGOTTEN**

### Why It Happens
- Task completion momentum
- Single-track focus (YAML generation)
- No explicit checkpoint
- Output schema not enforced

### The Solution
**Multi-layered defense**:
1. **Definition**: Formalize the pattern in agent-momentum.yml
2. **Validation**: orchestration-planning checks "Did planner create MMD?"
3. **Output Schema**: Manifest declares MMD as required output
4. **Process Reminder**: Explicit step in planner process.yml

## Deliverables

### New Files
- `assets/definitions/agent-momentum.yml`
- `assets/examples/orchestration/orchestration_build_reference.mmd`
- `assets/examples/orchestration/orchestration_guidance_reference.mmd`
- `agents/orchestration/orchestration-build/DEPRECATED.md`
- `agents/orchestration/orchestration-guidance/DEPRECATED.md`

### Updated Files
- All planner agents (test, cleaning, guidance-testing) - MMD generation
- orchestration-planning - MMD validation checkpoint
- `entrypoints/_orchestrate.yml` - Route to executor
- README files - Reflect new architecture

### Test Results
- Integration tests (int_005-010): 6 tests PASS
- E2E tests (e2e_001-003): 3 workflows validated

## Execution Strategy

**DO NOT attempt all phases in one session**. Break into focused sessions:

### Session 1: Teaching (Phase 1)
- Create agent-momentum.yml
- Update orchestration-planning with validation
- Update planner output schemas

### Session 2: Planner MMD (Phase 2)
- planner-test MMD generation
- planner-cleaning MMD generation
- planner-guidance-testing MMD generation

### Session 3: Planning Refactor (Phase 3)
- Add MMD validation checkpoint to orchestration-planning
- Add MMD aggregation to approval gate
- Update inputs

### Session 4: Deprecation (Phases 4-5)
- Deprecate orchestration-build
- Deprecate orchestration-guidance
- Convert to reference MMDs

### Session 5: Migration (Phase 6)
- Update _orchestrate.yml entrypoint
- Update documentation
- Test backward compatibility

### Session 6: Testing (Phase 7)
- Run integration tests int_005-010
- Run E2E tests e2e_001-003
- Validate complete system

## Success Criteria

✓ agent-momentum.yml created and referenced
✓ All 6 planner agents generate MMD files
✓ orchestration-planning validates MMD before approval
✓ orchestration-build and orchestration-guidance DEPRECATED
✓ _orchestrate.yml routes to orchestration-executor
✓ Integration tests PASS (6/6)
✓ E2E workflows PASS (3/3)
✓ Documentation reflects new architecture

## Related Files

- **Main Plan**: `live/plan_agenticguidance.yml`
- **Decommission Plan**: `live/plan_orchestration_decommission.yml`
- **Integration Tests**: `live/plan_integration_testing.yml`
- **Executor Spec**: `modules/AgenticGuidance/assets/definitions/orchestration-executor-specification.yml`

## Next Steps

1. Review plan_orchestration_decommission.yml for detailed task breakdown
2. Decide execution order (recommend teaching → build → test)
3. Execute phases sequentially with validation between each
4. Document any deviations or new insights as they emerge

---

**This completes the MMD-driven orchestration vision. The system will be fully generic, flexible, and maintainable.**
