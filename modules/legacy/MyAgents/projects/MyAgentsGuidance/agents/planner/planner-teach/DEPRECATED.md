# DEPRECATED: planner-teach

## Deprecation Notice
**Status**: DEPRECATED
**Date**: 2026-01-07
**Decision**: DECISION-001 Option B

## Why Deprecated
The functionality of `planner-teach` has been moved to the `planner-guidance` agent in the AgenticGuidance 2.0 architecture. The planner-guidance agent provides the same capabilities for creating guidance-focused plans to improve agent paths, fences, and signposts.

## What Replaced It
- **Agent**: `planner-guidance`
- **Location**: `modules/AgenticGuidance/agents/planner/planner-guidance/`
- **Files**:
  - `manifest.yml` - Agent metadata
  - `process.yml` - Agent process definition
  - `inputs.yml` - Context and layer references

## Coverage Evidence
1. Identical goal statement: "Create guidance-focused plan to improve agent paths, fences, and signposts"
2. Same output files: `plan_live_teach.yml`, `plan_live_audit_clean.yml`
3. Same loop participation: planner-loop, max 5 iterations
4. Referenced in orchestration-planning (line 84): `Spawn planner-guidance Agent`

## Migration Path
Update any references to use `planner-guidance`:
1. Replace import/reference paths from this folder to `modules/AgenticGuidance/agents/planner/planner-guidance/`
2. Use the planner-guidance process.yml for guidance planning tasks
3. For orchestrated workflows, use the `_plan_teach.yml` entrypoint which spawns planner-guidance automatically

## Legacy Reference
This folder is retained for historical reference only. Do not use or reference this agent in new implementations.
