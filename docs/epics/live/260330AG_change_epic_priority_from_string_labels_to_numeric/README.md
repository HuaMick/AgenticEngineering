# Epic: Change Epic Priority from String Labels to Numeric Values

## Objective

Replace the string-based priority system (`"critical"`, `"high"`, `"medium"`, `"low"`) with
numeric integer values (`1`, `2`, `3`, `4`) across the entire epic data pipeline: domain models,
TinyDB storage, repository sorting, workflows, CLI commands, and specifications.

This eliminates the indirection of `PRIORITY_WEIGHTS` lookup tables for sorting and simplifies
priority comparisons to direct integer operations.

## Affected User Stories

- **US-PLN-004**: List All Epics (displays priority)
- **US-PLN-082**: Epic CRUD Operations (stores priority)
- **US-PLN-083**: Epic Data Validation (validates priority enum)
- **US-PLN-085**: Epic Listing and Discovery (displays priority in sorted order)
- **US-SET-017**: TinyDB Epic Repository - CRUD Operations (stores priority)
- **US-SET-020**: CLI Epic Commands Use EpicRepository (CLI reads/writes priority)
- **US-SET-028**: Service Data Models (priority field type on dataclasses)

## Priority Mapping

| Label      | Numeric Value | Semantics         |
|------------|---------------|-------------------|
| critical   | 1             | Highest priority  |
| high       | 2             | High priority     |
| medium     | 3             | Default priority  |
| low        | 4             | Lowest priority   |

## Phases Overview

### Phase 1: Build — Domain Layer
Update the core data models, repository, and dependency service to use `int` priority internally.
Add backward-compatible string-to-int coercion so callers passing old string values don't break.
Migrate existing TinyDB records from string to int. Update plan-schema.yml.

### Phase 2: Build — Workflow and CLI Layer
Update workflow sorting (orchestration, planner loop) and all CLI commands (set-priority, epic
status, epic list, ticket add) to produce, consume, and display numeric priorities. Maintain
label aliases at the CLI edge for user convenience.

### Phase 3: Test — Update Tests
Update all test files across AgenticGuidance and AgenticCLI that assert string priority values
to use numeric values. Ensure full test suite passes.

### Phase 4: UAT — User Acceptance Testing
Validate the complete user experience against affected stories. Run CLI smoke tests to confirm
priority display, setting, sorting, and backward compatibility.

## Dependencies and Prerequisites

- No external dependencies.
- Depends on the existing `PRIORITY_WEIGHTS` dict in `epic_repository.py` (will be refactored).
- TinyDB migration must handle epics with missing priority (defaulting to `3`).
- Closely related to epic `260329AG_add_epic_priority_ordering_and_cross_epic_dependen` (which
  introduced the current string-based priority system). That epic should be complete first.

## Impacted Artifacts

### Domain Layer
| File | Change |
|------|--------|
| `agenticguidance/services/epic.py` | `EpicData.priority` and `EpicMetadata.priority`: `Optional[str]` -> `Optional[int]` |
| `agenticguidance/services/epic_repository.py` | `PRIORITY_WEIGHTS` refactored to label-to-int converter; sorting uses int directly; default `"medium"` -> `3`; add migration |
| `agenticguidance/services/dependency.py` | `get_execution_order()` sorting uses int priority |

### Workflow Layer
| File | Change |
|------|--------|
| `agenticcli/workflows/orchestration.py` | `discover_plans_needing_execution()` sorts by int priority |
| `agenticcli/workflows/planner_loop.py` | `discover_plans_needing_orchestration()` sorts by int priority |

### CLI Layer
| File | Change |
|------|--------|
| `agenticcli/cli.py` | `_validate_priority()` accepts both labels and ints |
| `agenticcli/commands/epic.py` | `cmd_set_priority`, `cmd_epic_status`, `cmd_epic_list`: display logic uses int keys; color mapping keyed by int |

### Specifications
| File | Change |
|------|--------|
| `assets/specifications/plan-schema.yml` | priority type `str enum` -> `int enum [1,2,3,4]` |

### Tests (9+ files)
| File | Change |
|------|--------|
| `tests/uat/test_epic_priority_deps_uat.py` | String priority assertions -> int |
| `tests/commands/test_epic_deps.py` | String priority assertions -> int |
| `tests/unit/workflows/test_orchestration_deps.py` | String -> int |
| `tests/uat/test_orchestration_deps_uat.py` | String -> int |
| `tests/unit/services/test_epic_repository_deps.py` | String -> int; PRIORITY_WEIGHTS test updated |
| `tests/unit/services/test_dependency.py` | String -> int |
| `tests/test_ticket_story_ids_cli.py` | Priority validation tests updated |
| `tests/test_preset_templates.py` | Priority value assertions updated |
| `tests/test_uat_tinydb_crud.py` | String -> int in test data |
| `tests/test_uat_tinydb_yaml_compat.py` | String -> int in seed data |

## Success Criteria

1. `EpicData.priority` and `EpicMetadata.priority` are `Optional[int]` with default `3`.
2. TinyDB stores priority as integer (1-4), not string.
3. Existing TinyDB records with string priorities are auto-migrated to int on repository open.
4. `PRIORITY_WEIGHTS` dict replaced with `PRIORITY_LABELS` (int->str) and `LABEL_TO_PRIORITY` (str->int) utilities.
5. CLI `agentic epic set-priority --priority <value>` accepts both labels (`high`) and numbers (`2`).
6. `agentic epic list` displays priority as number and sorts correctly (1 first).
7. `agentic epic status` displays priority as number with appropriate color coding.
8. Workflow sorting (orchestration, planner loop, dependency) uses direct int comparison.
9. `plan-schema.yml` documents priority as `int` with enum `[1, 2, 3, 4]`.
10. All existing tests pass with updated assertions (AgenticGuidance + AgenticCLI).
11. No existing CLI behavior regresses — labels still accepted as input aliases.

## Open Questions

- **Q1**: Should the CLI display show the numeric value only (e.g., `Priority: 2`) or include
  the label (e.g., `Priority: 2 (high)`)? *Recommendation: show both for UX clarity.*
- **Q2**: Should story priority (`story.py`) also be changed to numeric in this epic, or
  deferred to a separate epic? *Recommendation: defer — story priority is a separate domain.*
