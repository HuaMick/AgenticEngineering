# Scope Update: Orchestration Decommissioning Added
**Date**: 2026-01-10
**Status**: Planning complete, ready for execution
**Approach**: SIMPLIFIED - orchestration-planning as dedicated MMD generator

## Summary

Added **plan_orchestration_decommission.yml** to complete the MMD-driven orchestration vision outlined in the orchestration-executor specification.

## Simplified Approach (Based on User Feedback)

**Key Insight**: Don't try to remind agents with guidance - they forget to add tasks to their internal lists anyway.

**Solution**:
- **Only orchestration-planning generates MMD** (centralized, not per-planner)
- planner-reviewer does simple .mmd presence check
- No guidance-based reminders/checklists/output schemas
- CLI task list approach moved to **backlog** for experimentation

## What Was Added

### 7 Phases, 20 Tasks

| Phase | Tasks | Purpose |
|-------|-------|---------|
| **1. Build: orchestration-planning MMD Generation** | 3 | Make orchestration-planning the dedicated MMD generator |
| **2. Build: planner-reviewer MMD Check** | 1 | Simple .mmd presence validation |
| **3. Build: Deprecate orchestration-build** | 3 | Mark DEPRECATED, convert to reference MMD, remove from routing |
| **4. Build: Deprecate orchestration-guidance** | 3 | Same as orchestration-build deprecation |
| **5. Build: Entrypoint Migration** | 3 | Update `_orchestrate.yml` to route to orchestration-executor + update executor to discover .mmd |
| **6. Test: Integration Testing** | 6 | Complete deferred tests (int_005-010) |
| **7. Test: E2E Validation** | 3 | Full workflow validation (e2e_001-003) |
| **8. Build: Loop Strategy Integration** | 4 | Orchestrator owns loop selection; Planners only request; Simplify MMD structure |

**Total Estimated Effort**: 16-20 hours across 6-7 focused sessions

## Why This Matters

### Current Architecture (Hardcoded)
```yaml
_plan_build.yml    → orchestration-planning  # Hardcoded planning flow
_plan_teach.yml    → orchestration-planning  # Hardcoded planning flow
_orchestrate.yml   → orchestration-build     # Hardcoded execution flow
```

### Target Architecture (Generic, MMD-Driven)
```yaml
_plan_build.yml    → orchestration-planning  → planner-build → outputs plan_*.yml
                                              → generates orchestration_*.mmd
                                              → outputs to <plan_folder>/live/

_orchestrate.yml   → orchestration-executor  ← receives plan_folder
                                              → discovers orchestration_*.mmd inside
                                              → reads MMD dynamically
                                              → executes based on AGENT_ROUTING
```

**Key Design Decision**: `_orchestrate.yml` receives only `plan_folder_path`. The orchestration-executor discovers the `.mmd` file inside `<plan_folder>/live/` automatically. This keeps the interface clean and ensures both plan YAML and orchestration MMD live in the same location.

## Key Architectural Changes

### 1. orchestration-planning Role Change
**Before**: Hardcoded coordinator that spawns planners
**After**: Dedicated MMD generator that:
- Spawns appropriate planner agents
- **Generates orchestration MMD after planners complete** (centralized)
- Reads all plan_*.yml files from plan folder
- Determines AGENT_ROUTING based on phase types
- Presents plan YAML + orchestration MMD for approval
- Does NOT execute (delegates to orchestration-executor)

### 2. Centralized MMD Generation (Simplified!)
**Previously Planned**: Each planner generates its own MMD (risk of forgetting)
**New Approach**: Only orchestration-planning generates MMD
- Centralizes generation in one place
- orchestration-planning has full context of all phases
- May naturally solve "forgetfulness" problem
- Simpler than per-planner generation

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

## Why Not Guidance-Based Reminders?

### The Problem
Adding reminders to guidance files doesn't work because:
- Agents build their own internal task lists
- If they forget to add "generate MMD" to their list, they won't see the reminder
- Guidance says "remember X" but agent's internal plan doesn't include X

### Alternative Approach: CLI Task Lists (Backlog)
A more promising approach that's been moved to **backlog for experimentation**:

**Concept**: Preset task lists in CLI that agents prefill at workflow start
- Agent invokes: `agentic plan task prefill --preset planner-build`
- CLI loads template with tasks including "Generate MMD"
- Agent sees prefilled tasks in their context
- Agent can check/update via CLI as they work

**Why This Might Work**: External memory that persists and is visible
**Why It's Backlog**: Needs testing, CLI integration, blind loop validation
**See**: `backlog_cli_task_lists.yml`

## Deliverables

### New Files
- `assets/examples/orchestration/orchestration_build_reference.mmd`
- `assets/examples/orchestration/orchestration_guidance_reference.mmd`
- `agents/orchestration/orchestration-build/DEPRECATED.md`
- `agents/orchestration/orchestration-guidance/DEPRECATED.md`
- `live/backlog_cli_task_lists.yml` (backlog experiment)

### Updated Files
- orchestration-planning - MMD generation after planner aggregation
- planner-reviewer - Simple .mmd presence check
- `entrypoints/_orchestrate.yml` - Route to executor
- README files - Reflect new architecture

### Test Results
- Integration tests (int_005-010): 6 tests PASS
- E2E tests (e2e_001-003): 3 workflows validated

## Execution Strategy

**DO NOT attempt all phases in one session**. Break into focused sessions:

### Session 1: orchestration-planning MMD Generation (Phase 1)
- Add MMD generation to orchestration-planning process
- Update inputs with schema and component examples
- Update manifest outputs

### Session 2: Reviewer Validation (Phase 2)
- Add simple .mmd presence check to planner-reviewer
- Test validation works

### Session 3: Deprecation (Phases 3-4)
- Deprecate orchestration-build (DEPRECATED.md, reference MMD)
- Deprecate orchestration-guidance (DEPRECATED.md, reference MMD)
- Update documentation

### Session 4: Migration (Phase 5)
- Update _orchestrate.yml entrypoint
- Update documentation
- Test backward compatibility

### Session 5: Testing (Phase 6)
- Run integration tests int_005-010
- Run E2E tests e2e_001-003
- Validate complete system

## Success Criteria

✓ orchestration-planning generates MMD after planner aggregation (centralized)
✓ planner-reviewer validates .mmd presence (simple check)
✓ orchestration-build and orchestration-guidance DEPRECATED
✓ _orchestrate.yml routes to orchestration-executor
✓ Integration tests PASS (6/6)
✓ E2E workflows PASS (3/3)
✓ Documentation reflects new architecture
✓ CLI task list backlog item documented for future experimentation

## Related Files

- **Main Plan**: `live/plan_agenticguidance.yml`
- **Decommission Plan**: `live/plan_orchestration_decommission.yml`
- **Integration Tests**: `live/plan_integration_testing.yml`
- **CLI Task List Backlog**: `live/backlog_cli_task_lists.yml`
- **Executor Spec**: `modules/AgenticGuidance/assets/definitions/orchestration-executor-specification.yml`

## Next Steps

1. Review plan_orchestration_decommission.yml for detailed task breakdown
2. Execute phases sequentially (5 focused sessions recommended)
3. Validate at each phase before proceeding
4. After completion, consider experimenting with CLI task lists (backlog)

## Backlog: CLI Task List Experiment

After decommissioning is complete, there's a promising experiment to try:

**Hypothesis**: Preset task lists in CLI might help agents remember ancillary tasks better than guidance reminders

**Approach**:
- Implement CLI commands: `agentic plan task prefill --preset <name>`
- Create preset templates for each agent category
- Run blind planning loop tests to see if agents naturally complete prefilled tasks
- Compare success rate with/without CLI task lists

**Why This Could Work**: External memory that's visible to agents vs. internal reminders they might not add to their lists

**See**: `backlog_cli_task_lists.yml` for full experiment design

---

**This completes the MMD-driven orchestration vision with a simplified, centralized approach. The system will be fully generic, flexible, and maintainable.**
