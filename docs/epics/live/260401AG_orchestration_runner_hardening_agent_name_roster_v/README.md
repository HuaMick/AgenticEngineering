# Orchestration Runner Hardening: Agent Name Roster Validation and Stale In-Progress Phase Recovery

## Objective

Harden the orchestration runner with two safety improvements:

1. **Agent name roster validation**: Validate that the `agent` field on TinyDB phase records references a real agent from the filesystem roster before attempting to spawn. Currently, invalid agent names pass `validate_phase_routing()` (which only checks for field *existence*) and only fail at spawn time with an opaque SDK/tmux error.

2. **Stale in_progress phase recovery**: Detect phases stuck in `in_progress` state from crashed or killed executor processes and recover them to `pending` on executor startup. Currently, stale `in_progress` phases are re-executed by accident (the runner treats `pending` and `in_progress` identically) but without any logging, timestamp tracking, or intentional recovery mechanism.

## Affected User Stories

- **US-PLN-050**: Agent Routing from Metadata — step 4 requires "unsupported agent roles cause graceful failure with clear error"
- **US-PLN-051**: Phase Status Tracking — in_progress/completed transitions and resumability
- **US-PLN-059**: Execute Approved Epic via TinyDB Phases — phase status transitions
- **US-PLN-060**: Dynamic Agent Routing — routing correctness validation
- **US-PLN-063**: Persistent Execution State — in-progress phases re-attempted on resume
- **US-PLN-093**: Unified Phase-Routing Validation Utility — validate_phase_routing() needs roster membership check
- **US-GDN-001**: Discover Available Agents — agent roster discovery
- **US-GDN-002**: Validate Agent Manifest — manifest validation

## Phases Overview

### Phase 1: Build — Agent Roster Validation
Add `validate_agent_name()` utility, integrate roster validation into `validate_phase_routing()`, CLI phase commands (`cmd_phase_add`, `cmd_phase_update`), and the ExecutionRunner spawn guard.

### Phase 2: Build — Stale In-Progress Phase Recovery
Add `last_spawned_at` timestamp to PhaseData records, implement `_recover_stale_phases()` in ExecutionRunner, and wire recovery into executor startup with structured logging.

### Phase 3: Test — Unit and Integration Tests
Unit tests for roster validation and stale recovery. Integration tests for end-to-end flows including invalid agent rejection and crash recovery scenarios.

### Phase 4: UAT — User Acceptance Testing
Validate against affected user stories using test-uat strategy. CLI smoke tests for `agentic epic phase add --agent <invalid>` and orchestration execution with invalid/stale phases.

## Dependencies and Prerequisites

- `get_valid_agent_types()` in `agenticcli.commands.epic` already discovers agent roster from filesystem
- `_FALLBACK_AGENT_TYPES` provides a hardcoded fallback when filesystem is unavailable
- `validate_phase_routing()` in `agenticcli.utils.phase_validation` is the single validation gate for execution readiness
- `EpicRepository.update_phase()` supports arbitrary field updates (can store `last_spawned_at` without schema change)
- `PhaseData` dataclass in `agenticguidance.services.epic` needs new field for `last_spawned_at`
- Existing `test_uat_agent_roster_consistency.py` tests verify roster consistency across registries

## Impacted Artifacts

| Artifact | Type | Impact |
|---|---|---|
| `agenticcli.utils.phase_validation` | Service | Add `validate_agent_name()`, extend `validate_phase_routing()` |
| `agenticcli.commands.epic` | CLI | Add roster validation to `cmd_phase_add`, `cmd_phase_update` |
| `agenticcli.workflows.orchestration` | Workflow | Add roster guard in `_execute_plan()`, add `_recover_stale_phases()` |
| `agenticguidance.services.epic` | Domain | Add `last_spawned_at` field to `PhaseData` |
| `agenticguidance.services.epic_repository` | Repository | Read/write `last_spawned_at` in phase records |

## Success Criteria

1. **Agent roster validation**:
   - `validate_phase_routing()` returns `(False, reason)` when any phase has an agent name not in the roster
   - `agentic epic phase add --agent nonexistent-agent` fails with a clear error listing valid agents
   - `agentic epic phase update --agent nonexistent-agent` fails with a clear error listing valid agents
   - ExecutionRunner logs an error and marks phase as `failed` when agent name is not in roster (before attempting spawn)

2. **Stale in_progress recovery**:
   - ExecutionRunner logs a warning and resets phases from `in_progress` to `pending` on startup when `last_spawned_at` exceeds timeout threshold
   - `last_spawned_at` ISO timestamp is recorded in TinyDB phase record when phase spawn begins
   - Recovery is logged with phase name, epic, and stale duration

3. **No regressions**: All existing AgenticCLI and AgenticGuidance tests continue to pass

## Open Questions

None — both features have clear scope and well-defined integration points.
