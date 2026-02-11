# Session Management Robustness

**Plan ID**: 260208SM
**Status**: Active
**Created**: 2026-02-08

## Problem

A spawned session (3f12baeb) ran for 57 minutes but got stuck:
- tmux session disconnected/missing
- stdout/stderr logs are empty (0 bytes)
- Last JSONL write was 40 minutes ago
- Process still shows as 'running' but is actually stuck
- Session status JSON never updated to reflect the actual state

## Root Causes

1. **No heartbeat/watchdog** - No mechanism to detect sessions that stop producing output
2. **Log capture failure** - stdout/stderr logs were empty despite session activity (file descriptor leak)
3. **tmux session loss** - Process continued running after tmux disconnected
4. **Stale status detection** - CLI shows 'running' for sessions that are actually stuck

## Scope

1. Add session heartbeat mechanism (last_activity tracking in session JSON)
2. Implement log capture verification (fail-fast if logs not writing)
3. Add `agentic session health` command to check session vitality
4. Add `agentic session logs <id>` command to view session logs
5. Add stale session detection and warnings to `agentic session list`
6. Add tmux session existence check to status command
7. Fix file descriptor management for background session log files
8. **Auto-spawn diagnostic planner**: When a stuck/unhealthy session is detected:
   - Automatically spawn a DIAGNOSTIC PLANNER session to investigate and create a remediation plan if needed
   - Track `diagnostic_spawned: true` in session JSON to prevent spawning more than one diagnostic session per stuck session
   - This prevents infinite spawn loops while ensuring issues get investigated

## Key Files

- `modules/AgenticCLI/src/agenticcli/commands/session.py` (CLI commands)
- `modules/AgenticCLI/src/agenticcli/cli.py` (Typer command registration)
- `modules/AgenticGuidance/src/agenticguidance/services/claude_session.py` (SessionStateService)
- `modules/AgenticGuidance/src/agenticguidance/services/session.py` (tmux SessionService)
- `modules/AgenticCLI/tests/test_session_commands.py` (tests)
- `modules/AgenticGuidance/tests/test_services_claude_session.py` (service tests)
- `~/.agentic/sessions/*.json` (session state files - add diagnostic_spawned, last_activity fields)
