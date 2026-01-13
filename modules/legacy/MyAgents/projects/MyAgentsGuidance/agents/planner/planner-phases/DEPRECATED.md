# DEPRECATED: planner-phases

## Deprecation Notice
**Status**: DEPRECATED
**Date**: 2026-01-07
**Decision**: DECISION-001 Option B

## Why Deprecated
The functionality of `planner-phases` has been absorbed into the `orchestration-planning` agent's Phase Determination Subgraph. The orchestration-planning agent now handles phase determination as an integrated part of the planning workflow, eliminating the need for a separate phase determination agent.

## What Replaced It
- **Agent**: `orchestration-planning`
- **Location**: `modules/AgenticGuidance/agents/orchestration/orchestration-planning/process.mmd`
- **Specific Coverage**: Phase Determination Subgraph (lines 47-61)

## Coverage Evidence
1. The orchestration-planning subgraph explicitly determines phases: teach, build, test, cleanup
2. The `CreatePlaceholders` step creates phase `.yml` files
3. Phase determination is now embedded in orchestration-planning, not handled by a separate agent

## Migration Path
**No action required.** When using the AgenticGuidance 2.0 architecture:
- Use `_plan_build.yml` or `_plan_teach.yml` entrypoints
- The orchestration-planning agent automatically handles phase determination
- Refer to `modules/AgenticGuidance/agents/orchestration/orchestration-planning/process.mmd` for the current implementation

## Legacy Reference
This folder is retained for historical reference only. Do not use or reference this agent in new implementations.
