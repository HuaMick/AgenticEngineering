# Epic: Add Epic Priority Ordering and Cross-Epic Dependency Gates

## Objective

Add priority-based ordering and cross-epic dependency gating to the planning orchestration system, so that high-priority epics execute first and epics with unsatisfied dependencies are automatically blocked until prerequisites complete.

## Problem Statement

Currently, epics are discovered and processed in reverse creation-date order (YYMMDD prefix in folder name). The `priority` field exists on `EpicData`/`EpicMetadata` but is never used in selection logic. There is no concept of cross-epic dependencies - an epic cannot declare that it depends on another epic completing first.

This means:
- A critical hotfix epic has no way to jump ahead of less important work
- Epics that logically depend on each other can execute in the wrong order
- The orchestration runner has no mechanism to gate execution on prerequisite completion

## Affected User Stories

| Story ID | Title | Impact |
|----------|-------|--------|
| US-PLN-004 | List All Epics | Must display priority and dependency status |
| US-PLN-003 | View Epic Status | Must show dependency info (blocks/blocked-by) |
| US-PLN-059 | Execute Approved Epic via TinyDB Phases | Must gate on dependency fulfillment |
| US-PLN-062 | Validation Gates | Dependency validation before execution |
| US-PLN-082 | Epic CRUD Operations | `depends_on` field in create/update |
| US-PLN-083 | Epic Data Validation | Validate dependency references |
| US-PLN-084 | Epic Movement Workflow | Blocked epics cannot be archived |
| US-PLN-085 | Epic Listing and Discovery | Priority-ordered listing |

## Phases Overview

### Phase 1: Domain Model & Repository (`P1_domain_model`)
Extend the TinyDB schema and repository layer with `depends_on` field, priority sorting, and dependency query methods. This is the foundation all other phases build on.

### Phase 2: Dependency Validation Service (`P2_dependency_service`)
Create a `DependencyService` in AgenticGuidance with cycle detection, blocked-epic queries, and ready-epic filtering. Follows Domain -> Workflow -> Entrypoint pattern.

### Phase 3: CLI Commands (`P3_cli_commands`)
Add `agentic epic link`, `agentic epic unlink`, and `agentic epic set-priority` CLI commands. Update `agentic epic list` and `agentic epic status` to display priority and dependency information.

### Phase 4: Orchestration Integration (`P4_orchestration`)
Wire dependency gating into `discover_plans_needing_execution()` and `discover_plans_needing_orchestration()`. High-priority epics sort first; blocked epics are filtered out with logging.

### Phase 5: Tests (`P5_tests`)
Unit tests for dependency validation, priority sorting, cycle detection. Integration tests for CLI commands and orchestration discovery changes.

### Phase 6: UAT (`P6_uat`)
User acceptance testing against affected user stories. Validate priority ordering, dependency blocking, CLI output, and orchestration behavior.

## Dependencies and Prerequisites

- TinyDB is the sole data store (no YAML/MMD fallback needed)
- `EpicRepository` already stores `priority` field (unused) - we activate it
- `_order` field pattern on phases provides precedent for ordering
- `FileLock` from `state.py` used for atomic TinyDB operations
- `validate_phase_routing()` utility provides pattern for pre-execution validation

## Architecture

Follows **Domain -> Workflow -> Entrypoint** pattern:

- **Domain**: `EpicData.depends_on`, `DependencyService` (validation, cycle detection)
- **Workflow**: `OrchestrationWorkflow.discover_plans_*()` (filtering and sorting)
- **Entrypoint**: CLI commands (`epic link`, `epic unlink`, `epic set-priority`)

## Key Design Decisions

1. **`depends_on` is a list of epic_folder_name strings** - simple, queryable, no separate junction table
2. **Priority values**: `critical`, `high`, `medium` (default), `low` - sort order maps to integer weights
3. **Cycle detection via topological sort** - prevents deadlock scenarios
4. **Blocked epics are filtered, not errored** - orchestration skips them with informational logging
5. **Dependency validation at write-time AND execution-time** - catch invalid refs early, but also guard at runtime

## Impacted Artifacts

| Artifact | Type | Change |
|----------|------|--------|
| `agenticguidance/services/epic.py` | Data Model | Add `depends_on` to EpicData, EpicMetadata |
| `agenticguidance/services/epic_repository.py` | Repository | Add dependency CRUD, priority sorting |
| `agenticguidance/services/dependency.py` | Service (NEW) | DependencyService with cycle detection |
| `agenticcli/workflows/orchestration.py` | Workflow | Filter blocked, sort by priority |
| `agenticcli/workflows/planner_loop.py` | Workflow | Sort discovery by priority |
| `agenticcli/commands/epic.py` | CLI | Add link/unlink/set-priority commands |

## Success Criteria

1. `agentic epic list` displays epics sorted by priority (critical > high > medium > low), then by creation date
2. `agentic epic link --epic A --depends-on B` creates a dependency; `agentic epic unlink` removes it
3. `agentic epic set-priority --epic A --priority high` updates priority
4. `agentic epic status` shows dependency info (depends_on, blocked_by, blocks)
5. `discover_plans_needing_execution()` filters out epics with incomplete dependencies
6. `discover_plans_needing_orchestration()` returns epics sorted by priority
7. Circular dependency detection prevents deadlocks (error on cycle creation)
8. All existing tests continue to pass (no regressions)
9. UAT validates user stories US-PLN-004, US-PLN-059, US-PLN-082, US-PLN-085

## Open Questions

None - the existing `priority` field and TinyDB-first architecture provide a clear path.
