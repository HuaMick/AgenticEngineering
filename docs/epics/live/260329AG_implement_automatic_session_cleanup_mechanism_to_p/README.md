# Epic: Implement Automatic Session Cleanup Mechanism

## Objective

Implement an automatic session cleanup mechanism to prevent stale session artifact
accumulation in `~/.agentic/sessions/`. Currently, session JSON files, stdout/stderr
logs, and context files accumulate indefinitely with no cleanup. On a typical
development machine this has grown to **7,600+ log files**, **114 session JSONs**,
and **53 context files** consuming significant disk space.

The existing cleanup infrastructure only handles:
- **Process registry** (`state.json`): marks dead PIDs as STALE via manual `agentic orchestrate debug state cleanup`
- **Orchestration tmux sessions**: kills `agentic-orch-*` sessions before new layout creation
- **Foreground tmux sessions**: atexit handler for current-process sessions only

What is completely missing:
- No cleanup of session JSON files for completed/dead sessions
- No cleanup of log files (stdout/stderr) for dead sessions
- No cleanup of context files (compiled agent context) for dead sessions
- No age-based purging (e.g., remove sessions older than N days)
- No automatic cleanup triggered by normal CLI usage
- No unified CLI command that cleans all session artifacts at once
- No orphaned tmux session garbage collection beyond `agentic-orch-*`

## Affected User Stories

- **US-SES-003**: Stop Running Session (cleanup after stop)
- **US-SES-007**: Clear State Registry (extends to full artifact cleanup)
- **US-SES-008**: Cleanup Dead Processes (extends from registry to disk artifacts)
- **US-SES-009**: Manage Process State (unified state management including cleanup)

## Phases Overview

### Phase 1: Build - Session Cleanup Service (4 tickets)

Implements the core cleanup service and CLI command following Domain -> Workflow -> Entrypoint pattern:

| Ticket | Description |
|--------|-------------|
| T01_state_store_delete | Add `delete()` and `list_stale()` methods to `StateStore` class |
| T02_session_cleanup_service | Create `SessionCleanupService` domain service with full artifact cleanup |
| T03_cli_cleanup_command | Create `agentic session cleanup` CLI command |
| T04_auto_cleanup_hooks | Add automatic lightweight cleanup hooks to session spawn/list |

### Phase 2: Test - Session Cleanup Tests (2 tickets)

| Ticket | Description |
|--------|-------------|
| T05_unit_tests | Unit tests for StateStore extensions and SessionCleanupService |
| T06_integration_tests | Integration tests for CLI command and auto-cleanup hooks |

### Phase 3: UAT - User Acceptance Testing (1 ticket)

| Ticket | Description |
|--------|-------------|
| T07_uat | UAT validation against US-SES-007, US-SES-008, US-SES-009 |

## Dependencies and Prerequisites

- **StateStore** (`agenticcli/utils/state_store.py`): Core JSON-on-disk store, needs `delete()` method
- **StateRegistry** (`agenticguidance/services/state.py`): Process registry with `cleanup_dead_processes()`
- **Session commands** (`agenticcli/commands/session.py`): Session spawn/list/stop/health infrastructure
- **Tmux utilities** (`agenticcli/utils/tmux.py`, `tmux_layout.py`): Session existence checks and cleanup
- **Session state** (`agenticcli/utils/session_state.py`): Session state marking utilities

## Success Criteria

1. `agentic session cleanup` removes all stale session artifacts (JSON, logs, context files)
2. `agentic session cleanup --dry-run` previews cleanup without modifying anything
3. `agentic session cleanup --max-age 7` purges sessions older than 7 days
4. Automatic cleanup runs on `session list` (stale detection) and `session spawn` (age-based purge)
5. Orphaned tmux sessions (`agentic-*` prefix) are detected and killed
6. Cleanup report shows: sessions cleaned, files removed, disk space freed
7. No data loss: running sessions are never cleaned up
8. All existing tests continue to pass

## Architecture Notes

The cleanup service follows the Domain -> Workflow -> Entrypoint pattern:
- **Domain**: `SessionCleanupService` in `agenticcli/utils/session_cleanup.py`
- **Workflow**: Integrates with existing `session.py` command handlers
- **Entrypoint**: `agentic session cleanup` CLI command and auto-hooks

## Open Questions

None - the scope is well-defined by the existing infrastructure gaps.
