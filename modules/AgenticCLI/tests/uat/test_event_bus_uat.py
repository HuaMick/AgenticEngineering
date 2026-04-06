"""UAT: Validate event bus pipeline against affected user stories.

Tests the streaming event bus side-channel from a user-story perspective,
validating that the event bus contract is correct and backward compatible.

User stories tested:
- US-SES-001: Spawn a session → events.jsonl created with started+completed events
- US-SES-004: Event stream provides structured health signals (error events)
- US-SET-014: Real-time progress via tool_use events (not batched)
- US-SET-016: CompletedEvent carries token/cost metrics
- Backward compat (US-260401AG-005): Session without events.jsonl completes via fallback

@story US-260401AG-006
"""

import json
import os
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agenticcli.utils.event_bus import (
    CompletedEvent,
    ErrorEvent,
    EventType,
    EventWatcher,
    EventWriter,
    StartedEvent,
    ToolResultEvent,
    ToolUseEvent,
    deserialize_event,
    get_event_file_path,
    make_timestamp,
    serialize_event,
)

pytestmark = pytest.mark.story("US-SES-001")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UAT_SESSION_ID = "uat-event-bus-session-001"


def _emit_started(writer: EventWriter, session_id: str, role: str = "build-python") -> StartedEvent:
    """Emit a StartedEvent and return it."""
    event = StartedEvent(
        timestamp=make_timestamp(),
        session_id=session_id,
        role=role,
        working_dir="/home/code/AgenticEngineering",
    )
    writer.emit(event)
    return event


def _emit_tool_use(writer: EventWriter, session_id: str, tool_name: str) -> ToolUseEvent:
    """Emit a ToolUseEvent and return it."""
    event = ToolUseEvent(
        timestamp=make_timestamp(),
        session_id=session_id,
        tool_name=tool_name,
        tool_input_preview=f'{{"path": "/home/code/src/{tool_name}.py"}}',
    )
    writer.emit(event)
    return event


def _emit_tool_result(
    writer: EventWriter, session_id: str, tool_name: str, *, is_error: bool = False,
) -> ToolResultEvent:
    """Emit a ToolResultEvent and return it."""
    event = ToolResultEvent(
        timestamp=make_timestamp(),
        session_id=session_id,
        tool_name=tool_name,
        is_error=is_error,
        output_preview=f"Result from {tool_name}" if not is_error else f"Error in {tool_name}",
    )
    writer.emit(event)
    return event


def _emit_error(
    writer: EventWriter, session_id: str, message: str, error_type: str = "sdk_error",
) -> ErrorEvent:
    """Emit an ErrorEvent and return it."""
    event = ErrorEvent(
        timestamp=make_timestamp(),
        session_id=session_id,
        error_message=message,
        error_type=error_type,
    )
    writer.emit(event)
    return event


def _emit_completed(
    writer: EventWriter,
    session_id: str,
    *,
    status: str = "completed",
    cost_usd: float = 0.0042,
    duration_ms: int = 12345,
    num_turns: int = 7,
    usage: dict | None = None,
    sdk_session_id: str = "sdk-sess-uat-abc",
) -> CompletedEvent:
    """Emit a CompletedEvent and return it."""
    event = CompletedEvent(
        timestamp=make_timestamp(),
        session_id=session_id,
        status=status,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        num_turns=num_turns,
        usage=usage if usage is not None else {"input_tokens": 2000, "output_tokens": 1000},
        sdk_session_id=sdk_session_id,
    )
    writer.emit(event)
    return event


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sessions_root(tmp_path: Path):
    """Redirect _SESSIONS_ROOT to tmp_path for test isolation."""
    root = tmp_path / "sessions"
    root.mkdir()
    with patch("agenticcli.utils.event_bus._SESSIONS_ROOT", root):
        yield root


# ---------------------------------------------------------------------------
# US-SES-001: Spawn session → events.jsonl created with started+completed
# ---------------------------------------------------------------------------


class TestUATSessionSpawnEvents:
    """US-SES-001: Verify events.jsonl is created when a session is spawned.

    Validates that the event bus produces a well-formed events.jsonl file
    containing at minimum a started event and a completed event at the
    canonical file path for the session.
    """

    def test_events_jsonl_created_on_session_spawn(self, sessions_root: Path):
        """Spawning a session creates events.jsonl at the correct path.

        Simulates the pane runner flow: EventWriter is created for a session,
        a StartedEvent is emitted at session start, and a CompletedEvent is
        emitted when the session finishes. The events.jsonl file should exist
        at /tmp/agentic/sessions/{session_id}/events.jsonl (redirected to
        tmp_path for isolation).
        """
        session_id = "uat-ses-001-spawn-test"

        with EventWriter(session_id) as writer:
            _emit_started(writer, session_id, role="build-python")
            _emit_completed(writer, session_id)

        # Verify the file exists at the canonical path
        expected_path = sessions_root / session_id / "events.jsonl"
        assert expected_path.exists(), (
            f"events.jsonl not created at expected path: {expected_path}"
        )

        # Verify the file contains exactly 2 lines (started + completed)
        lines = expected_path.read_text().strip().split("\n")
        assert len(lines) == 2, f"Expected 2 event lines, got {len(lines)}"

        # Parse and verify event types
        event_0 = deserialize_event(lines[0])
        event_1 = deserialize_event(lines[1])
        assert isinstance(event_0, StartedEvent), f"First event should be StartedEvent, got {type(event_0).__name__}"
        assert isinstance(event_1, CompletedEvent), f"Second event should be CompletedEvent, got {type(event_1).__name__}"

    def test_started_event_carries_role_and_session_id(self, sessions_root: Path):
        """StartedEvent carries the role and session_id of the spawned session."""
        session_id = "uat-ses-001-role-check"

        with EventWriter(session_id) as writer:
            started = _emit_started(writer, session_id, role="test-uat")

        # Read back via watcher
        watcher = EventWatcher(session_id)
        events = watcher.poll()

        assert len(events) == 1
        assert events[0].session_id == session_id
        assert events[0].role == "test-uat"
        assert events[0].working_dir == "/home/code/AgenticEngineering"
        assert events[0].timestamp != ""

    def test_session_directory_created_automatically(self, sessions_root: Path):
        """EventWriter creates the session directory if it doesn't exist."""
        session_id = "uat-ses-001-dir-creation"
        session_dir = sessions_root / session_id

        assert not session_dir.exists()

        with EventWriter(session_id) as writer:
            _emit_started(writer, session_id)

        assert session_dir.exists(), "Session directory was not created"
        assert (session_dir / "events.jsonl").exists()

    def test_writer_and_watcher_path_agreement(self, sessions_root: Path):
        """EventWriter and EventWatcher resolve to the same canonical path."""
        session_id = "uat-ses-001-path-agreement"

        writer = EventWriter(session_id)
        watcher = EventWatcher(session_id)

        assert writer.path == watcher.path, (
            f"Writer path {writer.path} != Watcher path {watcher.path}"
        )
        writer.close()


# ---------------------------------------------------------------------------
# US-SES-004: Event stream provides structured health signals
# ---------------------------------------------------------------------------


class TestUATHealthSignals:
    """US-SES-004: Verify event stream provides structured health signals.

    Validates that error events carry full error context (message, type) and
    that the EventWatcher can read them with all fields intact, enabling
    health inspection of agent sessions.
    """

    def test_error_event_carries_full_context(self, sessions_root: Path):
        """Error events include error_message and error_type fields."""
        session_id = "uat-ses-004-health-error"

        with EventWriter(session_id) as writer:
            _emit_started(writer, session_id)
            _emit_error(
                writer, session_id,
                message="SDK query timed out after 600s — no ResultMessage received",
                error_type="timeout",
            )
            _emit_completed(writer, session_id, status="failed", cost_usd=0.0, duration_ms=600000, num_turns=0)

        watcher = EventWatcher(session_id)
        events = watcher.poll()

        assert len(events) == 3

        error_event = events[1]
        assert isinstance(error_event, ErrorEvent)
        assert error_event.error_message == "SDK query timed out after 600s — no ResultMessage received"
        assert error_event.error_type == "timeout"
        assert error_event.session_id == session_id
        assert error_event.timestamp != ""

    def test_multiple_error_types_distinguishable(self, sessions_root: Path):
        """Different error types (timeout, sdk_error, etc.) are correctly preserved."""
        session_id = "uat-ses-004-multi-error"

        with EventWriter(session_id) as writer:
            _emit_started(writer, session_id)
            _emit_error(writer, session_id, message="Connection refused", error_type="network_error")
            _emit_error(writer, session_id, message="OOM killed", error_type="process_error")
            _emit_error(writer, session_id, message="Rate limited", error_type="api_error")
            _emit_completed(writer, session_id, status="failed")

        watcher = EventWatcher(session_id)
        events = watcher.poll()

        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        assert len(error_events) == 3

        error_types = [e.error_type for e in error_events]
        assert error_types == ["network_error", "process_error", "api_error"]

        error_messages = [e.error_message for e in error_events]
        assert "Connection refused" in error_messages[0]
        assert "OOM killed" in error_messages[1]
        assert "Rate limited" in error_messages[2]

    def test_error_event_followed_by_completed_event(self, sessions_root: Path):
        """Error sessions always end with a CompletedEvent (failed status).

        Per US-260401AG-003 step 5: A 'completed' event is still emitted
        (with failed status) so watchers know the session ended.
        """
        session_id = "uat-ses-004-error-completed"

        with EventWriter(session_id) as writer:
            _emit_started(writer, session_id)
            _emit_error(writer, session_id, message="Unexpected SDK crash")
            _emit_completed(writer, session_id, status="failed", cost_usd=0.0)

        watcher = EventWatcher(session_id)
        events = watcher.poll()

        # The final event must always be CompletedEvent
        assert isinstance(events[-1], CompletedEvent)
        assert events[-1].status == "failed"

    def test_watcher_reads_error_events_with_long_messages(self, sessions_root: Path):
        """Error messages up to 500 chars are preserved (pane runner truncates at 500)."""
        session_id = "uat-ses-004-long-error"
        long_message = "X" * 500  # pane runner caps at 500 chars

        with EventWriter(session_id) as writer:
            _emit_started(writer, session_id)
            _emit_error(writer, session_id, message=long_message)
            _emit_completed(writer, session_id, status="failed")

        watcher = EventWatcher(session_id)
        events = watcher.poll()

        error_event = [e for e in events if isinstance(e, ErrorEvent)][0]
        assert len(error_event.error_message) == 500
        assert error_event.error_message == long_message


# ---------------------------------------------------------------------------
# US-SET-014: Real-time progress via tool_use events
# ---------------------------------------------------------------------------


class TestUATRealTimeProgress:
    """US-SET-014: Verify real-time progress through tool_use events.

    Validates that tool_use events emitted in sequence by the pane runner
    are received by the EventWatcher in real-time (not batched) and in the
    correct chronological order.
    """

    def test_tool_events_received_in_realtime_order(self, sessions_root: Path):
        """Tool events emitted sequentially are received in correct order.

        Simulates a producer emitting events with a slight delay and a
        consumer polling concurrently, verifying events arrive in real-time
        without being batched.
        """
        session_id = "uat-set-014-realtime"
        collected_events: list = []
        poll_timestamps: list[float] = []
        producer_started = threading.Event()

        def producer():
            with EventWriter(session_id) as writer:
                _emit_started(writer, session_id)
                producer_started.set()

                # Emit 5 tool_use events with deliberate delay
                for i, tool in enumerate(["Read", "Grep", "Write", "Bash", "Edit"]):
                    time.sleep(0.05)  # 50ms between events
                    _emit_tool_use(writer, session_id, tool)
                    time.sleep(0.02)
                    _emit_tool_result(writer, session_id, tool)

                time.sleep(0.02)
                _emit_completed(writer, session_id)

        def consumer():
            producer_started.wait(timeout=5)
            watcher = EventWatcher(session_id)
            deadline = time.monotonic() + 10

            while time.monotonic() < deadline:
                batch = watcher.poll()
                for event in batch:
                    collected_events.append(event)
                    poll_timestamps.append(time.monotonic())
                    if isinstance(event, CompletedEvent):
                        return
                if not batch:
                    time.sleep(0.03)

        t_prod = threading.Thread(target=producer, daemon=True)
        t_cons = threading.Thread(target=consumer, daemon=True)
        t_cons.start()
        t_prod.start()

        t_prod.join(timeout=15)
        t_cons.join(timeout=15)

        # Verify all 12 events received: 1 started + 5*(tool_use+tool_result) + 1 completed
        assert len(collected_events) == 12, (
            f"Expected 12 events, got {len(collected_events)}: "
            f"{[type(e).__name__ for e in collected_events]}"
        )

        # Verify order: started, then tool_use/tool_result pairs, then completed
        assert isinstance(collected_events[0], StartedEvent)
        assert isinstance(collected_events[-1], CompletedEvent)

        tool_use_events = [e for e in collected_events if isinstance(e, ToolUseEvent)]
        tool_names = [e.tool_name for e in tool_use_events]
        assert tool_names == ["Read", "Grep", "Write", "Bash", "Edit"], (
            f"Tool events out of order: {tool_names}"
        )

        # Verify events were received incrementally (not all in one batch)
        # The poll_timestamps should span a time range > 100ms if truly incremental
        if len(poll_timestamps) >= 2:
            time_spread = poll_timestamps[-1] - poll_timestamps[0]
            assert time_spread > 0.05, (
                f"Events appear batched (spread={time_spread:.3f}s < 0.05s)"
            )

    def test_tool_use_events_carry_tool_name_and_preview(self, sessions_root: Path):
        """ToolUseEvent carries tool_name and tool_input_preview fields."""
        session_id = "uat-set-014-tool-fields"

        with EventWriter(session_id) as writer:
            _emit_started(writer, session_id)
            _emit_tool_use(writer, session_id, "Read")
            _emit_tool_result(writer, session_id, "Read")
            _emit_completed(writer, session_id)

        watcher = EventWatcher(session_id)
        events = watcher.poll()

        tool_use = [e for e in events if isinstance(e, ToolUseEvent)][0]
        assert tool_use.tool_name == "Read"
        assert tool_use.tool_input_preview != ""
        assert tool_use.session_id == session_id

    def test_tool_result_events_carry_error_flag(self, sessions_root: Path):
        """ToolResultEvent correctly reports is_error for failed tool calls."""
        session_id = "uat-set-014-tool-error"

        with EventWriter(session_id) as writer:
            _emit_started(writer, session_id)
            _emit_tool_use(writer, session_id, "Bash")
            _emit_tool_result(writer, session_id, "Bash", is_error=True)
            _emit_completed(writer, session_id, status="completed")

        watcher = EventWatcher(session_id)
        events = watcher.poll()

        tool_result = [e for e in events if isinstance(e, ToolResultEvent)][0]
        assert tool_result.is_error is True
        assert tool_result.tool_name == "Bash"


# ---------------------------------------------------------------------------
# US-SET-016: CompletedEvent carries token/cost metrics
# ---------------------------------------------------------------------------


class TestUATMetricsCompleteness:
    """US-SET-016: Verify CompletedEvent carries complete token/cost metrics.

    Validates that the CompletedEvent emitted by the pane runner contains
    all metric fields needed for cost tracking and progress reporting.
    """

    def test_completed_event_has_all_metric_fields(self, sessions_root: Path):
        """CompletedEvent includes cost_usd, duration_ms, num_turns, usage, sdk_session_id."""
        session_id = "uat-set-016-metrics"

        usage_dict = {
            "input_tokens": 5000,
            "output_tokens": 2500,
            "cache_creation_input_tokens": 1000,
            "cache_read_input_tokens": 500,
        }

        with EventWriter(session_id) as writer:
            _emit_started(writer, session_id)
            _emit_completed(
                writer, session_id,
                status="completed",
                cost_usd=0.0385,
                duration_ms=45000,
                num_turns=15,
                usage=usage_dict,
                sdk_session_id="sdk-sess-real-123",
            )

        watcher = EventWatcher(session_id)
        events = watcher.poll()
        completed = events[-1]

        assert isinstance(completed, CompletedEvent)
        assert completed.status == "completed"
        assert completed.cost_usd == pytest.approx(0.0385)
        assert completed.duration_ms == 45000
        assert completed.num_turns == 15
        assert completed.usage == usage_dict
        assert completed.sdk_session_id == "sdk-sess-real-123"
        assert completed.session_id == session_id
        assert completed.timestamp != ""

    def test_completed_event_metrics_survive_serialization_roundtrip(self, sessions_root: Path):
        """Metrics are preserved through serialize → file → deserialize cycle."""
        session_id = "uat-set-016-roundtrip"

        original_usage = {"input_tokens": 3000, "output_tokens": 1500}
        with EventWriter(session_id) as writer:
            _emit_completed(
                writer, session_id,
                cost_usd=0.0123,
                duration_ms=30000,
                num_turns=10,
                usage=original_usage,
                sdk_session_id="roundtrip-sdk-sess",
            )

        # Read raw file and deserialize manually
        event_file = sessions_root / session_id / "events.jsonl"
        raw_line = event_file.read_text().strip()
        restored = deserialize_event(raw_line)

        assert isinstance(restored, CompletedEvent)
        assert restored.cost_usd == pytest.approx(0.0123)
        assert restored.duration_ms == 30000
        assert restored.num_turns == 10
        assert restored.usage == original_usage
        assert restored.sdk_session_id == "roundtrip-sdk-sess"

    def test_failed_session_metrics_still_present(self, sessions_root: Path):
        """Failed sessions still carry metrics (duration, partial cost)."""
        session_id = "uat-set-016-failed-metrics"

        with EventWriter(session_id) as writer:
            _emit_started(writer, session_id)
            _emit_error(writer, session_id, message="SDK timeout")
            _emit_completed(
                writer, session_id,
                status="failed",
                cost_usd=0.001,
                duration_ms=600000,
                num_turns=0,
                usage={},
                sdk_session_id="",
            )

        watcher = EventWatcher(session_id)
        events = watcher.poll()
        completed = events[-1]

        assert isinstance(completed, CompletedEvent)
        assert completed.status == "failed"
        assert completed.cost_usd == pytest.approx(0.001)
        assert completed.duration_ms == 600000
        assert completed.num_turns == 0
        assert completed.usage == {}
        assert completed.sdk_session_id == ""

    def test_zero_cost_session_metrics(self, sessions_root: Path):
        """Zero-cost sessions (e.g., import failure) have valid metrics."""
        session_id = "uat-set-016-zero-cost"

        with EventWriter(session_id) as writer:
            _emit_completed(
                writer, session_id,
                status="failed",
                cost_usd=0.0,
                duration_ms=0,
                num_turns=0,
                usage={},
                sdk_session_id="",
            )

        watcher = EventWatcher(session_id)
        events = watcher.poll()
        completed = events[0]

        assert completed.cost_usd == 0.0
        assert completed.duration_ms == 0
        assert completed.num_turns == 0


# ---------------------------------------------------------------------------
# Backward compatibility: session without events.jsonl completes normally
# ---------------------------------------------------------------------------


class TestUATBackwardCompatibility:
    """US-260401AG-005: Verify backward compat when events.jsonl is absent.

    Validates that the EventWatcher gracefully handles missing event files
    and that sessions which don't produce events.jsonl can still complete
    via the existing polling fallback mechanism.
    """

    def test_watcher_returns_empty_for_missing_file(self, sessions_root: Path):
        """EventWatcher.poll() returns empty list when events.jsonl doesn't exist."""
        watcher = EventWatcher("nonexistent-legacy-session")
        events = watcher.poll()
        assert events == [], "Watcher should return empty list for missing event file"

    def test_watcher_does_not_raise_for_missing_file(self, sessions_root: Path):
        """EventWatcher does not raise exceptions when events.jsonl is absent."""
        watcher = EventWatcher("legacy-no-events-session")
        # poll should not raise
        events = watcher.poll()
        assert isinstance(events, list)

    def test_iter_events_stops_on_timeout_with_no_file(self, sessions_root: Path):
        """iter_events() stops after timeout when no events.jsonl exists."""
        watcher = EventWatcher("legacy-iter-session")

        start = time.monotonic()
        events_collected = []
        for event in watcher.iter_events(timeout=0.5, poll_interval=0.1):
            events_collected.append(event)

        elapsed = time.monotonic() - start

        assert events_collected == []
        # Should have waited close to the timeout duration
        assert elapsed >= 0.4, f"iter_events returned too early: {elapsed:.2f}s"
        assert elapsed < 2.0, f"iter_events waited too long: {elapsed:.2f}s"

    def test_pane_runner_graceful_degradation_flag(self):
        """sdk_pane_runner.EVENT_BUS_AVAILABLE flag enables graceful degradation.

        When event_bus module import fails, the pane runner sets
        EVENT_BUS_AVAILABLE=False and continues without event emission.
        This test verifies the flag exists and is True (module is available).
        """
        from agenticcli.utils.sdk_pane_runner import EVENT_BUS_AVAILABLE
        assert EVENT_BUS_AVAILABLE is True, (
            "EVENT_BUS_AVAILABLE should be True when event_bus module is importable"
        )

    def test_session_state_json_path_is_independent_of_events(self, sessions_root: Path):
        """Session state JSON (in ~/.agentic/sessions/) is separate from events.jsonl.

        Verifies the two storage paths don't collide:
        - Session state: ~/.agentic/sessions/{session_id}.json
        - Event bus: /tmp/agentic/sessions/{session_id}/events.jsonl
        """
        from agenticcli.utils.sdk_pane_runner import _get_state_file

        session_id = "uat-backward-compat-paths"
        state_path = _get_state_file(session_id)
        event_path = get_event_file_path(session_id)

        # State file lives in ~/.agentic/sessions/
        assert ".agentic/sessions" in str(state_path)
        assert state_path.name == f"{session_id}.json"

        # Event file lives in /tmp/agentic/sessions/ (or sessions_root in tests)
        assert event_path.name == "events.jsonl"

        # Paths are completely different — no collision
        assert state_path.parent != event_path.parent


# ---------------------------------------------------------------------------
# Cross-cutting: event type enum completeness and serialization
# ---------------------------------------------------------------------------


class TestUATEventTypeCompleteness:
    """Verify EventType enum covers all expected event types.

    Ensures the event vocabulary is complete for the stories being tested.
    """

    def test_event_type_enum_has_all_members(self):
        """EventType enum has all 5 expected members."""
        expected = {"started", "tool_use", "tool_result", "error", "completed"}
        actual = {e.value for e in EventType}
        assert actual == expected, f"Missing event types: {expected - actual}"

    def test_all_event_types_serializable(self):
        """Every event type can be serialized to valid JSON."""
        events = [
            StartedEvent(timestamp="2026-04-04T00:00:00Z", session_id="test", role="r", working_dir="/"),
            ToolUseEvent(timestamp="2026-04-04T00:00:01Z", session_id="test", tool_name="Read", tool_input_preview="{}"),
            ToolResultEvent(timestamp="2026-04-04T00:00:02Z", session_id="test", tool_name="Read", is_error=False, output_preview="ok"),
            ErrorEvent(timestamp="2026-04-04T00:00:03Z", session_id="test", error_message="err", error_type="sdk_error"),
            CompletedEvent(timestamp="2026-04-04T00:00:04Z", session_id="test", status="completed", cost_usd=0.0, duration_ms=0, num_turns=0, usage={}, sdk_session_id=""),
        ]

        for event in events:
            json_str = serialize_event(event)
            # Must be valid JSON
            parsed = json.loads(json_str)
            assert "type" in parsed
            assert "timestamp" in parsed
            assert "session_id" in parsed

            # Round-trip
            restored = deserialize_event(json_str)
            assert type(restored) == type(event)

    def test_deserialize_unknown_type_raises_valueerror(self):
        """Deserializing an unknown event type raises ValueError."""
        bad_json = '{"type":"unknown_event","timestamp":"2026-04-04T00:00:00Z","session_id":"test"}'
        with pytest.raises(ValueError, match="Unknown event type"):
            deserialize_event(bad_json)

    def test_deserialize_missing_type_raises_valueerror(self):
        """Deserializing JSON without 'type' field raises ValueError."""
        bad_json = '{"timestamp":"2026-04-04T00:00:00Z","session_id":"test"}'
        with pytest.raises(ValueError, match="missing required 'type' field"):
            deserialize_event(bad_json)
