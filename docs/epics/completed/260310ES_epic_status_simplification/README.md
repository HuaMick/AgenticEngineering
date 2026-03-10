# Epic: Simplify Epic Status — Remove Action Column

## Objective

Remove the redundant "Action" column from `agentic epic list` and unify epic lifecycle status into a single "Status" column. The executor already sets `in_progress` and `completed` on the epic status field — the derived "Action" column (`needs_planning`, `execute`, `archive`, `blocked`) duplicates this with different terminology.

## Current State

- `agentic epic list` shows both "Status" (stored TinyDB field) and "Action" (derived from ticket counts)
- The Action column was needed when Status wasn't reliably updated, but now the executor properly manages epic status transitions: `active` → `in_progress` → `completed`
- The two columns frequently disagree (e.g., Status=`in_progress`, Action=`archive`)

## Desired State

- Single "Status" column reflecting the epic lifecycle: `active`, `planning`, `in_progress`, `completed`, `deferred`, `blocked`
- The executor, planner loop, and CLI commands all update the Status field directly
- Remove the `action_required` derivation logic from `cmd_list_plans()`
- Update `agentic epic status` to use the same unified status

## Scope

- `modules/AgenticCLI/src/agenticcli/commands/epic.py` — `cmd_list_plans()` and `cmd_plan_status()`
- `modules/AgenticCLI/src/agenticcli/workflows/orchestration.py` — executor status transitions (already partially done)
- `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py` — planner sets `planning` status
- Tests covering the status display and transitions

## Out of Scope

- Changing the TinyDB schema (status field already exists)
- Modifying agent guidance files
- Changing the epic folder structure
