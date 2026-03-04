# 260128AG Mandatory RLM Enforcement in Trace Analysis

**Created**: 2026-01-28
**Branch**: main
**Status**: ACTIVE
**Module**: AgenticGuidance

## Objective

Make RLM (Recursive Language Model) patterns MANDATORY (not optional) for all trace analysis operations in the AgenticGuidance module.

## Problem Statement

Current state:
- RLM patterns are defined but OPTIONAL in trace analysis workflows
- The teacher-trace-diagnostics process.yml mentions RLM with "(when implemented)" qualifier
- Agents can skip RLM patterns even when dealing with large trace contexts
- No validation that RLM is actually being used during trace analysis

Desired state:
- RLM is MANDATORY when trace context exceeds thresholds (500 lines or 100+ traces)
- Validation step verifies RLM patterns are being applied
- Clear error/warning if RLM is bypassed for large contexts
- Orchestration-friction workflow enforces RLM usage

## Approach Decision

**Chosen**: Strengthen guidance enforcement (not implement Python code)

Rationale:
- RLM context accessor spec defines a conceptual API, not a Python implementation
- Implementation notes in spec explicitly state: "Context accessor functions are conceptual - actual implementation depends on the runtime environment"
- Agents implement RLM by generating code using available tools (grep, file read, etc.)
- Enforcement should be through guidance/process files, not runtime code

## Phases and Focus

We are taking a **Friction Analysis First** approach. The primary goal is to ensure the `_analyze_friction` entrypoint (which typically handles large volumes of trace data) correctly implements and enforces RLM patterns before expanding to other modules.

1. **Friction Analysis Milestone**: Mandate RLM for `_analyze_friction` (Plan: `plan_friction_enforcement.yml`).
2. **Global Enforcement**: Expand to all trace diagnostics and large-context operations.

## Success Criteria

1. `teacher-trace-diagnostics/process.yml` has MANDATORY RLM step (not optional)
2. `orchestration-friction/process.mmd` includes RLM validation gate
3. RLM usage can be verified through trace metadata or output format
4. Blind test confirms agent cannot proceed without RLM for large contexts

## Files to Modify

| File | Change |
|------|--------|
| `modules/AgenticGuidance/agents/teacher/teacher-trace-diagnostics/process.yml` | Add mandatory RLM enforcement step |
| `modules/AgenticGuidance/agents/orchestration/orchestration-friction/process.mmd` | Add RLM validation gate |
| `modules/AgenticGuidance/agents/teacher/teacher-trace-diagnostics/inputs.yml` | Add RLM validation criteria |
| `modules/AgenticGuidance/assets/definitions/trace-diagnostics.yml` | Add RLM mandatory flag |

## Related References

- RLM Patterns: `modules/AgenticGuidance/assets/definitions/rlm-patterns.yml`
- RLM Integration: `modules/AgenticGuidance/assets/guidelines/rlm-integration.yml`
- RLM Context Accessor Spec: `modules/AgenticGuidance/assets/specifications/rlm-context-accessor.yml`
- Agent Loops (RLM-enhanced): `modules/AgenticGuidance/assets/definitions/agent-loops.yml`
