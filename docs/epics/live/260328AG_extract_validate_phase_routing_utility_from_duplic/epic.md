# Extract validate_phase_routing utility from duplicated orchestration logic

## Objective

Extract `validate_phase_routing(repo, epic_folder) -> tuple[bool, str | None]` from duplicated phase-routing validation logic in `discover_plans_needing_orchestration()` and `discover_plans_needing_execution()` into a shared utility function.

## Context

Both `PlannerLoopWorkflow.discover_plans_needing_orchestration()` and `OrchestrationWorkflow.discover_plans_needing_execution()` contain similar logic to check whether an epic's phases have valid agent routing. This duplication increases the risk of drift when validation rules change.

## Scope

- **Source file**: `modules/AgenticCLI/src/agenticcli/workflows/orchestration.py`
- **Also touches**: `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py`
- **New utility**: `modules/AgenticCLI/src/agenticcli/utils/phase_validation.py`

### Deliverables

1. New function `validate_phase_routing(repo, epic_folder)` that returns `(is_valid: bool, reason: str | None)`
2. Both discovery methods refactored to call the shared utility
3. Tests for the new utility function
4. Existing tests still pass

## Constraints

- No behavioral change — pure refactor
- Keep backward compatibility
- Small, focused change
