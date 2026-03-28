# Epic: Extract validate_phase_routing Utility from Duplicated Orchestration Logic

## Objective

Extract duplicated phase routing validation logic into a shared utility module
(`agenticcli/utils/phase_routing.py`) to eliminate code duplication, improve
testability, and establish a single source of truth for phase routing checks.

## Problem Statement

Two distinct patterns of phase routing logic are duplicated across the codebase:

1. **Phase agent routing check** — `phases and all(p.agent for p in phases)` is
   duplicated in `planner_loop.py` at lines 229 and 1095, used to determine
   whether an epic's phases are fully routed to agents.

2. **Feedback triggers string parsing** — comma-separated `KEY=VALUE` string
   parsing logic is duplicated in `epic.py` (commands) at lines 2358-2364
   (`cmd_phase_add`) and lines 2540-2547 (`cmd_phase_update`).

## Affected User Stories

This is an internal refactoring with no user-facing behavior change.

- **no_stories_rationale**: Internal code deduplication refactoring. No
  user-facing behavior changes — the extracted utility functions produce
  identical results to the inlined code they replace. CLI commands, orchestration
  workflows, and phase routing behavior remain unchanged from the user's
  perspective.

## Phases Overview

### P2: Build (agent: build-python, sequential)
Extract utility functions into a new module and replace inline duplications.

| Ticket | Description |
|--------|-------------|
| T01 | Create `phase_routing.py` utility module with `phases_fully_routed()` and `parse_feedback_triggers()` functions |
| T02 | Replace inline duplication in `planner_loop.py` with `phases_fully_routed()` calls |
| T03 | Replace inline duplication in `epic.py` commands with `parse_feedback_triggers()` calls |

### P3: Test (agent: test-builder, sequential, feedback: TEST_FAILURE→Build)
Write unit tests for the new utility and verify no regressions.

| Ticket | Description |
|--------|-------------|
| T04 | Write unit tests for `phase_routing.py` (both functions, edge cases) |
| T05 | Run full AgenticCLI test suite — verify zero regressions |

### P4: UAT (agent: test-uat, sequential)
Verify behavior preservation end-to-end.

| Ticket | Description |
|--------|-------------|
| T06 | UAT: Verify `agentic epic phase add/update --feedback-triggers` behavior unchanged |
| T07 | UAT: Verify planner loop discovery detects unrouted phases correctly |

## Dependencies and Prerequisites

- No external dependencies — pure internal refactoring
- Existing tests must continue to pass after extraction
- `PhaseData` dataclass imported from `agenticguidance.services.epic`

## Impacted Artifacts

| Artifact | Impact |
|----------|--------|
| `modules/AgenticCLI/src/agenticcli/utils/phase_routing.py` | **NEW** — utility module |
| `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py` | MODIFIED — replace inline checks with utility |
| `modules/AgenticCLI/src/agenticcli/commands/epic.py` | MODIFIED — replace inline parsing with utility |
| `modules/AgenticCLI/tests/utils/test_phase_routing.py` | **NEW** — unit tests |

## Success Criteria

1. Zero duplicated phase routing logic remains in `planner_loop.py` and `epic.py`
2. New `phase_routing.py` utility module exists with two exported functions
3. All existing AgenticCLI tests pass without modification
4. New unit tests cover both functions with edge cases (empty phases, None triggers, malformed input)
5. `agentic epic phase add --feedback-triggers "K=V"` produces identical TinyDB state
6. Planner loop discovery correctly identifies unrouted epics using the utility
