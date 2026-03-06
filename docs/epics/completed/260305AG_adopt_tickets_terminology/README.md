# Epic: Adopt Tickets Terminology

## Objective

Migrate the codebase from using the `tasks` key to `tickets` key as the canonical
terminology for work items nested under epic phases. Also simplify the `agentic epic list`
display to show only **pending** and **done** counts (removing the `in_progress` column).

## Background

The system has an inconsistency between YAML schema and code:

- **YAML files** (plan_build.yml) use `tickets` as the key for work items within phases:
  ```yaml
  phases:
    - id: "phase_1"
      tickets:
        - id: "ticket_01"
          status: pending
  ```

- **All code paths** look for the `tasks` key, causing tickets to be invisible:
  - `_get_phases_from_content()` in `epic.py` → `phase.get("tasks", [])`
  - `_get_epic_from_yaml()` in `EpicService` → `phase.get("tasks", [])`
  - `import_from_yaml()` in `EpicRepository` → `phase.get("tasks", [])`
  - `_remove_task_from_source()` → `phase.get("tasks", [])`

This causes epics like `260303AG_reduce_orchestration_context_overflow` (which has 8
pending tickets) to show 0 pending tickets in `agentic epic list`.

## Scope

### 1. Adopt `tickets` as canonical key (code change)

Update all code that reads `phase.get("tasks", [])` to read `phase.get("tickets", [])`
instead. The `tickets` key is the correct domain term and matches the YAML schema used
by planners.

**Files to update:**
- `modules/AgenticCLI/src/agenticcli/commands/epic.py`
  - `_get_phases_from_content()` — look for `tickets` key
  - Any other references to `tasks` key within phase iteration
- `modules/AgenticGuidance/src/agenticguidance/services/epic.py`
  - `_get_epic_from_yaml()` — `phase.get("tickets", [])`
  - `EpicMovementWorkflow` methods that iterate phase tasks
- `modules/AgenticGuidance/src/agenticguidance/services/epic_repository.py`
  - `import_from_yaml()` — `phase.get("tickets", [])`
  - `export_to_yaml()` — write `tickets` key instead of `tasks`
- Tests that reference the `tasks` key for phase-nested items

### 2. Simplify `agentic epic list` display

Remove the `in_progress` column from the list display. Rename remaining columns:
- `Pending` → stays as `Pending`
- `Done` → stays (was `completed`)
- Remove `In Prog` column entirely

Update `cmd_list()` in `epic.py` to:
- Drop `total_in_progress` from the count
- Remove the `In Prog` column from both JSON and table output
- Treat `in_progress` tickets as `pending` for display purposes (they're not done)

## Status

Status: needs_planning
Created: 2026-03-05
