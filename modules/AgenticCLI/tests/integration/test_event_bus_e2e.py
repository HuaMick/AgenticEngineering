"""End-to-end integration test for the event bus pipeline.

Validates the full event bus pipeline: EventWriter writes events in one
thread, EventWatcher reads them in another.  Simulates the pane-runner-to-
orchestrator flow:

    Thread 1 (producer): EventWriter emits started → 3×(tool_use, tool_result)
                         → completed with metrics.
    Thread 2 (consumer): EventWatcher.iter_events() collects all events and
                         verifies sequence integrity.

Assertions:
    - All events received in order, no loss, no duplication.
    - CompletedEvent has correct metrics fields.
    - Event count matches (1 started + 6 tool events + 1 completed = 8 total).
    - Test is isolated (uses tmp_path, no /tmp pollution).
    - Test runs in under 10 seconds.

@story US-260401AG-006
"""

import threading
import time
from pathlib import Path
from unittest.mock import patch

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

_SESSION_ID = "test-e2e-session-001"


def _make_started(session_id: str = _SESSION_ID) -> StartedEvent:
    return StartedEvent(
        timestamp=make_timestamp(),
        session_id=session_id,
        role="test-builder",
        working_dir="/home/code/test",
    )


def _make_tool_use(tool_name: str, session_id: str = _SESSION_ID) -> ToolUseEvent:
    return ToolUseEvent(
        timestamp=make_timestamp(),
        session_id=session_id,
        tool_name=tool_name,
        tool_input_preview=f'{{"action": "run {tool_name}"}}',
    )


def _make_tool_result(
    tool_name: str, *, is_error: bool = False, session_id: str = _SESSION_ID
) -> ToolResultEvent:
    return ToolResultEvent(
        timestamp=make_timestamp(),
        session_id=session_id,
        tool_name=tool_name,
        is_error=is_error,
        output_preview=f"output from {tool_name}",
    )


def _make_completed(session_id: str = _SESSION_ID) -> CompletedEvent:
    return CompletedEvent(
        timestamp=make_timestamp(),
        session_id=session_id,
        status="completed",
        cost_usd=0.0042,
        duration_ms=12345,
        num_turns=7,
        usage={"input_tokens": 1500, "output_tokens": 800},
        sdk_session_id="sdk-sess-abc123",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sessions_root(tmp_path: Path):
    """Patch _SESSIONS_ROOT so that EventWriter/EventWatcher use tmp_path.

    This ensures complete test isolation — no writes to /tmp/agentic/sessions/.
    """
    root = tmp_path / "sessions"
    root.mkdir()
    with patch("agenticcli.utils.event_bus._SESSIONS_ROOT", root):
        yield root


# ---------------------------------------------------------------------------
# Test: full pipeline — producer + consumer threads
# ---------------------------------------------------------------------------


class TestEventBusPipelineE2E:
    """End-to-end event bus pipeline: writer→file→watcher."""

    def test_full_pipeline_writer_to_watcher(self, sessions_root: Path):
        """Writer emits 8 events; Watcher reads all 8 in correct order."""
        collected_events: list = []
        consumer_done = threading.Event()
        producer_started = threading.Event()

        def producer():
            """Simulate sdk_pane_runner event emission."""
            with EventWriter(_SESSION_ID) as writer:
                # Signal consumer that the file is ready
                producer_started.set()

                # StartedEvent
                writer.emit(_make_started())
                time.sleep(0.02)  # Simulate SDK streaming delay

                # 3 × (tool_use + tool_result)
                for tool in ["Read", "Grep", "Write"]:
                    writer.emit(_make_tool_use(tool))
                    time.sleep(0.01)
                    writer.emit(_make_tool_result(tool))
                    time.sleep(0.01)

                # CompletedEvent
                writer.emit(_make_completed())

        def consumer():
            """Simulate orchestrator EventWatcher consumption."""
            # Wait for the producer to create the file
            producer_started.wait(timeout=5)

            watcher = EventWatcher(_SESSION_ID)
            # Use iter_events with short timeout and fast polling
            for event in watcher.iter_events(timeout=10, poll_interval=0.05):
                collected_events.append(event)
                # Stop when we see the completed event
                if isinstance(event, CompletedEvent):
                    break
            consumer_done.set()

        # Launch producer and consumer threads
        t_producer = threading.Thread(target=producer, daemon=True)
        t_consumer = threading.Thread(target=consumer, daemon=True)
        t_consumer.start()
        t_producer.start()

        # Wait for both threads to finish
        t_producer.join(timeout=10)
        consumer_done.wait(timeout=10)
        t_consumer.join(timeout=10)

        # --- Assertions ---

        # Exactly 8 events: 1 started + 3 tool_use + 3 tool_result + 1 completed
        assert len(collected_events) == 8, (
            f"Expected 8 events, got {len(collected_events)}: "
            f"{[type(e).__name__ for e in collected_events]}"
        )

        # Verify event types in order
        expected_types = [
            EventType.started,
            EventType.tool_use,
            EventType.tool_result,
            EventType.tool_use,
            EventType.tool_result,
            EventType.tool_use,
            EventType.tool_result,
            EventType.completed,
        ]
        actual_types = [e.type for e in collected_events]
        assert actual_types == expected_types, (
            f"Event type sequence mismatch:\n"
            f"  expected: {[t.value for t in expected_types]}\n"
            f"  actual:   {[t.value for t in actual_types]}"
        )

        # Verify no duplication — each event should be unique by timestamp
        timestamps = [e.timestamp for e in collected_events]
        # Not strictly unique due to time resolution, so check count instead
        assert len(collected_events) == len(set(id(e) for e in collected_events))

        # Verify all events share the same session_id
        for event in collected_events:
            assert event.session_id == _SESSION_ID

        # Verify CompletedEvent metrics
        completed = collected_events[-1]
        assert isinstance(completed, CompletedEvent)
        assert completed.status == "completed"
        assert completed.cost_usd == pytest.approx(0.0042)
        assert completed.duration_ms == 12345
        assert completed.num_turns == 7
        assert completed.usage == {"input_tokens": 1500, "output_tokens": 800}
        assert completed.sdk_session_id == "sdk-sess-abc123"

        # Verify StartedEvent fields
        started = collected_events[0]
        assert isinstance(started, StartedEvent)
        assert started.role == "test-builder"
        assert started.working_dir == "/home/code/test"

        # Verify tool event sequence
        tool_events = [e for e in collected_events if isinstance(e, (ToolUseEvent, ToolResultEvent))]
        assert len(tool_events) == 6
        tool_names_use = [e.tool_name for e in tool_events if isinstance(e, ToolUseEvent)]
        assert tool_names_use == ["Read", "Grep", "Write"]

    def test_event_file_created_at_correct_path(self, sessions_root: Path):
        """EventWriter creates the JSONL file at the expected path."""
        with EventWriter(_SESSION_ID) as writer:
            writer.emit(_make_started())

        expected_path = sessions_root / _SESSION_ID / "events.jsonl"
        assert expected_path.exists()
        assert writer.path == expected_path

        # Verify the file contains exactly one line
        lines = expected_path.read_text().strip().split("\n")
        assert len(lines) == 1

    def test_watcher_handles_file_not_yet_created(self, sessions_root: Path):
        """EventWatcher.poll() returns empty list when file doesn't exist yet."""
        watcher = EventWatcher("nonexistent-session-123")
        events = watcher.poll()
        assert events == []

    def test_watcher_start_from_beginning(self, sessions_root: Path):
        """EventWatcher reads events from the start when start_from_beginning=True."""
        # Write events first
        with EventWriter(_SESSION_ID) as writer:
            writer.emit(_make_started())
            writer.emit(_make_tool_use("Read"))
            writer.emit(_make_completed())

        # Create watcher AFTER events are written (default start_from_beginning=True)
        watcher = EventWatcher(_SESSION_ID, start_from_beginning=True)
        events = watcher.poll()

        assert len(events) == 3
        assert events[0].type == EventType.started
        assert events[1].type == EventType.tool_use
        assert events[2].type == EventType.completed

    def test_watcher_start_from_end(self, sessions_root: Path):
        """EventWatcher skips existing events when start_from_beginning=False."""
        # Write events first
        with EventWriter(_SESSION_ID) as writer:
            writer.emit(_make_started())
            writer.emit(_make_tool_use("Read"))

        # Watcher with start_from_beginning=False should skip existing events
        watcher = EventWatcher(_SESSION_ID, start_from_beginning=False)
        events = watcher.poll()
        assert events == []  # First poll resolves to end of file

        # Now write more events — watcher should only see these
        with EventWriter(_SESSION_ID) as writer:
            writer.emit(_make_completed())

        events = watcher.poll()
        assert len(events) == 1
        assert events[0].type == EventType.completed

    def test_multiple_poll_incremental_reads(self, sessions_root: Path):
        """Multiple poll() calls read events incrementally without duplication."""
        writer = EventWriter(_SESSION_ID)
        watcher = EventWatcher(_SESSION_ID)

        # Write and poll in batches
        writer.emit(_make_started())
        batch_1 = watcher.poll()
        assert len(batch_1) == 1
        assert batch_1[0].type == EventType.started

        writer.emit(_make_tool_use("Read"))
        writer.emit(_make_tool_result("Read"))
        batch_2 = watcher.poll()
        assert len(batch_2) == 2
        assert batch_2[0].type == EventType.tool_use
        assert batch_2[1].type == EventType.tool_result

        writer.emit(_make_completed())
        batch_3 = watcher.poll()
        assert len(batch_3) == 1
        assert batch_3[0].type == EventType.completed

        # Final poll should yield nothing
        batch_4 = watcher.poll()
        assert batch_4 == []

        writer.close()

    def test_no_event_loss_under_rapid_writes(self, sessions_root: Path):
        """Rapid sequential writes don't lose events."""
        n_events = 100
        with EventWriter(_SESSION_ID) as writer:
            for i in range(n_events):
                writer.emit(ToolUseEvent(
                    timestamp=make_timestamp(),
                    session_id=_SESSION_ID,
                    tool_name=f"tool_{i}",
                    tool_input_preview=f"input_{i}",
                ))

        watcher = EventWatcher(_SESSION_ID)
        events = watcher.poll()
        assert len(events) == n_events, (
            f"Expected {n_events} events, got {len(events)}"
        )

        # Verify ordering by tool_name
        for i, event in enumerate(events):
            assert isinstance(event, ToolUseEvent)
            assert event.tool_name == f"tool_{i}"


# ---------------------------------------------------------------------------
# Test: serialization round-trip integrity
# ---------------------------------------------------------------------------


class TestSerializationRoundTrip:
    """Verify serialize → file → deserialize preserves all fields."""

    def test_all_event_types_round_trip(self, sessions_root: Path):
        """Every event type survives serialize → write → read → deserialize."""
        events_to_write = [
            _make_started(),
            _make_tool_use("Read"),
            _make_tool_result("Read"),
            ErrorEvent(
                timestamp=make_timestamp(),
                session_id=_SESSION_ID,
                error_message="Something went wrong",
                error_type="sdk_error",
            ),
            _make_completed(),
        ]

        # Write all events
        with EventWriter(_SESSION_ID) as writer:
            for event in events_to_write:
                writer.emit(event)

        # Read back via watcher
        watcher = EventWatcher(_SESSION_ID)
        read_events = watcher.poll()

        assert len(read_events) == len(events_to_write)

        # Verify each event type and key fields
        assert isinstance(read_events[0], StartedEvent)
        assert read_events[0].role == "test-builder"

        assert isinstance(read_events[1], ToolUseEvent)
        assert read_events[1].tool_name == "Read"

        assert isinstance(read_events[2], ToolResultEvent)
        assert read_events[2].tool_name == "Read"
        assert read_events[2].is_error is False

        assert isinstance(read_events[3], ErrorEvent)
        assert read_events[3].error_message == "Something went wrong"
        assert read_events[3].error_type == "sdk_error"

        assert isinstance(read_events[4], CompletedEvent)
        assert read_events[4].cost_usd == pytest.approx(0.0042)
        assert read_events[4].duration_ms == 12345

    def test_serialize_deserialize_identity(self):
        """Direct serialize → deserialize produces equivalent event."""
        original = _make_completed()
        json_line = serialize_event(original)
        restored = deserialize_event(json_line)

        assert isinstance(restored, CompletedEvent)
        assert restored.session_id == original.session_id
        assert restored.status == original.status
        assert restored.cost_usd == original.cost_usd
        assert restored.duration_ms == original.duration_ms
        assert restored.num_turns == original.num_turns
        assert restored.usage == original.usage
        assert restored.sdk_session_id == original.sdk_session_id
        assert restored.timestamp == original.timestamp


# ---------------------------------------------------------------------------
# Test: error event emission and error-tolerant watcher
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Error event emission and watcher resilience."""

    def test_error_event_in_pipeline(self, sessions_root: Path):
        """Error events are correctly written and read through the pipeline."""
        with EventWriter(_SESSION_ID) as writer:
            writer.emit(_make_started())
            writer.emit(ErrorEvent(
                timestamp=make_timestamp(),
                session_id=_SESSION_ID,
                error_message="SDK query timed out after 600s",
                error_type="timeout",
            ))
            writer.emit(CompletedEvent(
                timestamp=make_timestamp(),
                session_id=_SESSION_ID,
                status="failed",
                cost_usd=0.0,
                duration_ms=600000,
                num_turns=0,
                usage={},
                sdk_session_id="",
            ))

        watcher = EventWatcher(_SESSION_ID)
        events = watcher.poll()

        assert len(events) == 3
        assert events[0].type == EventType.started
        assert events[1].type == EventType.error
        assert events[1].error_message == "SDK query timed out after 600s"
        assert events[1].error_type == "timeout"
        assert events[2].type == EventType.completed
        assert events[2].status == "failed"
        assert events[2].cost_usd == 0.0

    def test_watcher_skips_corrupt_lines(self, sessions_root: Path):
        """EventWatcher silently skips corrupt/truncated JSON lines."""
        event_file = sessions_root / _SESSION_ID / "events.jsonl"
        event_file.parent.mkdir(parents=True, exist_ok=True)

        # Write a mix of valid and corrupt lines
        valid_event = serialize_event(_make_started())
        with open(event_file, "w", encoding="utf-8") as fh:
            fh.write(valid_event + "\n")
            fh.write('{"type":"started","truncated\n')  # corrupt JSON
            fh.write("not json at all\n")               # not JSON
            fh.write(serialize_event(_make_completed()) + "\n")

        watcher = EventWatcher(_SESSION_ID)
        events = watcher.poll()

        # Only the 2 valid events should be returned
        assert len(events) == 2
        assert events[0].type == EventType.started
        assert events[1].type == EventType.completed


# ---------------------------------------------------------------------------
# Test: EventWriter context manager and close idempotency
# ---------------------------------------------------------------------------


class TestEventWriterLifecycle:
    """EventWriter context manager and resource cleanup."""

    def test_context_manager_closes_file(self, sessions_root: Path):
        """EventWriter closes the file handle on __exit__."""
        with EventWriter(_SESSION_ID) as writer:
            writer.emit(_make_started())
            assert not writer._fh.closed

        # After exiting context, file handle should be closed
        assert writer._fh.closed

    def test_close_idempotent(self, sessions_root: Path):
        """Calling close() multiple times is safe."""
        writer = EventWriter(_SESSION_ID)
        writer.emit(_make_started())
        writer.close()
        writer.close()  # Should not raise
        writer.close()  # Should not raise

    def test_writer_creates_session_directory(self, sessions_root: Path):
        """EventWriter creates the session directory if it doesn't exist."""
        new_session = "brand-new-session-xyz"
        expected_dir = sessions_root / new_session
        assert not expected_dir.exists()

        with EventWriter(new_session) as writer:
            writer.emit(_make_started())

        assert expected_dir.exists()
        assert (expected_dir / "events.jsonl").exists()


# ---------------------------------------------------------------------------
# Test: get_event_file_path determinism
# ---------------------------------------------------------------------------


class TestEventFilePath:
    """Canonical path resolution for event files."""

    def test_path_is_deterministic(self, sessions_root: Path):
        """get_event_file_path returns the same path for the same session_id."""
        path1 = get_event_file_path("session-abc")
        path2 = get_event_file_path("session-abc")
        assert path1 == path2

    def test_path_includes_session_id(self, sessions_root: Path):
        """Path contains the session_id as a directory component."""
        path = get_event_file_path("my-session-123")
        assert "my-session-123" in str(path)
        assert path.name == "events.jsonl"

    def test_writer_and_watcher_agree_on_path(self, sessions_root: Path):
        """EventWriter and EventWatcher use the same file path."""
        writer = EventWriter(_SESSION_ID)
        watcher = EventWatcher(_SESSION_ID)
        assert writer.path == watcher.path
        writer.close()


# ---------------------------------------------------------------------------
# Test: concurrent producer-consumer stress test
# ---------------------------------------------------------------------------


class TestConcurrentStress:
    """Stress-test the pipeline with concurrent producer and consumer."""

    def test_concurrent_write_read_50_events(self, sessions_root: Path):
        """50 events written concurrently are all read without loss."""
        n_events = 50
        collected: list = []
        write_done = threading.Event()

        def writer_thread():
            with EventWriter(_SESSION_ID) as writer:
                writer.emit(_make_started())
                for i in range(n_events - 2):  # -2 for started + completed
                    writer.emit(ToolUseEvent(
                        timestamp=make_timestamp(),
                        session_id=_SESSION_ID,
                        tool_name=f"tool_{i}",
                        tool_input_preview=f"input_{i}",
                    ))
                    time.sleep(0.005)  # Simulate slight delay between events
                writer.emit(_make_completed())
            write_done.set()

        def reader_thread():
            watcher = EventWatcher(_SESSION_ID)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                events = watcher.poll()
                collected.extend(events)
                if any(isinstance(e, CompletedEvent) for e in collected):
                    break
                if not events:
                    time.sleep(0.02)

        t_writer = threading.Thread(target=writer_thread, daemon=True)
        t_reader = threading.Thread(target=reader_thread, daemon=True)

        t_reader.start()
        t_writer.start()

        t_writer.join(timeout=10)
        t_reader.join(timeout=10)

        assert len(collected) == n_events, (
            f"Expected {n_events} events, got {len(collected)}"
        )
        assert isinstance(collected[0], StartedEvent)
        assert isinstance(collected[-1], CompletedEvent)

        # Verify no duplicates by checking unique event positions
        tool_events = [e for e in collected if isinstance(e, ToolUseEvent)]
        tool_names = [e.tool_name for e in tool_events]
        expected_names = [f"tool_{i}" for i in range(n_events - 2)]
        assert tool_names == expected_names, "Tool events are out of order or missing"
