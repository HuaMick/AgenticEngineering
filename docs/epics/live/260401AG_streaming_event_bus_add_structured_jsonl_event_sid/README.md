# Epic: Streaming Event Bus — Structured JSONL Event Side-Channel

**Epic ID**: `260401AG_streaming_event_bus_add_structured_jsonl_event_sid`
**Created**: 2026-04-01
**Type**: build

## Objective

Add a structured JSONL event side-channel so the orchestrator can observe agent
progress mid-execution. Agents write typed events (`started`, `tool_use`,
`tool_result`, `error`, `completed`) to
`/tmp/agentic/sessions/{session_id}/events.jsonl` via `sdk_pane_runner.py`.
`ExecutionRunner` watches the events file instead of blocking on process exit.

This enables:
- **Mid-run kill/redirect/feedback** — orchestrator reacts to events as they stream
- **Real-time progress visibility** — replaces post-hoc `read_sdk_metrics()`
- **Structured observability** — typed events with timestamps, not just stdout

Builds on existing tmux transport (no replacement). The session state JSON file
(`~/.agentic/sessions/{session_id}.json`) remains the source of truth for final
status; the event bus provides the real-time side-channel.

## Affected User Stories

| Story ID    | Title                                 | Relevance                                     |
|-------------|---------------------------------------|-----------------------------------------------|
| US-SES-001  | Spawn Claude Code Session             | Event bus emits events from spawned sessions   |
| US-SES-002  | List and Monitor Sessions             | Event stream enables richer monitoring         |
| US-SES-003  | Stop Running Session                  | Mid-run kill enabled by event observation      |
| US-SES-004  | Inspect Session Health and Logs       | Events provide structured health signals       |
| US-SET-014  | Real-time Progress Visibility         | Events replace polling for progress info       |
| US-SET-016  | Progress Indicators and Token Estimation | Tool events carry token/cost deltas         |

## Phases Overview

### P1: Event Domain Model
Define typed event dataclasses, the `EventType` enum, and JSONL
serialization/deserialization. This is the shared vocabulary all other phases
depend on.

### P2: Event File I/O
Implement `EventWriter` (atomic JSONL append) and `EventWatcher` (tail-follow
reader). These are the two ends of the side-channel pipe — writer in the agent
process, watcher in the orchestrator process.

### P3: Pane Runner Integration
Wire `EventWriter` into `sdk_pane_runner.py`'s `_run_sdk_query()` streaming loop.
Emit events for each SDK message type. Backward compatible — session state JSON
continues to be written as before.

### P4: Orchestrator Integration
Replace `wait_for_session()` polling with event-watcher-based waiting in
`ExecutionRunner`. Extract real-time metrics from `completed` events instead of
post-hoc `read_sdk_metrics()`. Add fallback to old polling when `events.jsonl` is
absent (backward compat with non-event-bus sessions).

### P5: Tests
Unit tests for event model, writer, watcher. Integration tests for end-to-end
pane-runner → event-file → orchestrator flow.

### P6: UAT
User acceptance testing anchored to affected stories. Strategy: `test-uat` —
validate that spawned sessions emit events, orchestrator observes them in real
time, and session lifecycle (spawn/monitor/stop) works end-to-end.

## Dependencies and Prerequisites

- **Existing**: `sdk_pane_runner.py`, `session_state.py`, `orchestration.py`,
  `planner_loop.py`, `state_store.py`
- **No new dependencies**: Uses stdlib only (`json`, `os`, `time`, `pathlib`,
  `dataclasses`, `enum`)
- **Temp directory**: `/tmp/agentic/sessions/{session_id}/` — created on write,
  cleaned up on session completion or expiry

## Impacted Artifacts

| Artifact                           | Impact                                           |
|------------------------------------|--------------------------------------------------|
| `agenticcli/utils/event_bus.py`    | **NEW** — event types, writer, watcher           |
| `agenticcli/utils/sdk_pane_runner.py` | MODIFIED — emit events in streaming loop       |
| `agenticcli/utils/session_state.py`| MODIFIED — add event dir path helper             |
| `agenticcli/workflows/orchestration.py` | MODIFIED — event-based wait, real-time metrics |
| `agenticcli/workflows/planner_loop.py` | MODIFIED — event-aware wait_for_session        |

## Success Criteria

1. `sdk_pane_runner.py` writes JSONL events to `/tmp/agentic/sessions/{session_id}/events.jsonl`
2. Events are typed: `started`, `tool_use`, `tool_result`, `error`, `completed`
3. Each event line is valid JSON with `type`, `timestamp`, and type-specific fields
4. `ExecutionRunner` watches event file instead of only polling session state JSON
5. Orchestrator logs real-time progress as events stream in
6. `completed` event carries SDK metrics (cost, duration, turns) — replaces `read_sdk_metrics()`
7. Backward compatible: sessions without `events.jsonl` fall back to existing polling
8. Event file is append-only, flush-on-write, no partial lines
9. All existing tests continue to pass (no regressions)
10. UAT passes for affected user stories

## Open Questions

_None — architecture is fully constrained by existing tmux transport and session state patterns._
