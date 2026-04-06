"""Event bus domain model, typed events, and JSONL file I/O.

Defines the structured event vocabulary for the streaming event bus side-channel.
Producers (sdk_pane_runner) emit events to events.jsonl; consumers (orchestrator,
EventWatcher) deserialize them for real-time observation of agent sessions.

All events share three base fields: type (EventType), timestamp (ISO 8601 str),
and session_id (str). Each event type has a corresponding dataclass with
additional type-specific fields.

EventWriter provides atomic JSONL append to
``/tmp/agentic/sessions/{session_id}/events.jsonl``.

Uses stdlib only: json, dataclasses, enum, datetime, os, pathlib.

@story US-260401AG-001
@story US-260401AG-002
"""

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import IO, Generator, Union

__all__ = [
    "EventType",
    "StartedEvent",
    "ToolUseEvent",
    "ToolResultEvent",
    "ErrorEvent",
    "CompletedEvent",
    "Event",
    "serialize_event",
    "deserialize_event",
    "make_timestamp",
    "get_event_file_path",
    "EventWriter",
    "EventWatcher",
    "summarize_session_ledger",
    "filter_session_ledger",
]


class EventType(str, Enum):
    """Event types emitted by the streaming event bus."""

    started = "started"
    tool_use = "tool_use"
    tool_result = "tool_result"
    error = "error"
    completed = "completed"


def make_timestamp() -> str:
    """Return current UTC time as ISO 8601 string.

    Uses timezone-aware UTC datetime for deterministic timestamps across
    all producers.
    """
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Event dataclasses — one per EventType member.
#
# Pattern follows SessionDiagnosis from session_diagnostics.py:
# plain @dataclass, no __post_init__ magic, fields with defaults where
# appropriate.
# ---------------------------------------------------------------------------


@dataclass
class StartedEvent:
    """Emitted when an agent session begins a query() call."""

    type: EventType = field(default=EventType.started, init=False)
    timestamp: str = ""
    session_id: str = ""
    role: str = ""
    working_dir: str = ""


@dataclass
class ToolUseEvent:
    """Emitted when the SDK streaming loop receives a tool_use message."""

    type: EventType = field(default=EventType.tool_use, init=False)
    timestamp: str = ""
    session_id: str = ""
    tool_name: str = ""
    tool_input_preview: str = ""


@dataclass
class ToolResultEvent:
    """Emitted when the SDK streaming loop receives a tool_result message."""

    type: EventType = field(default=EventType.tool_result, init=False)
    timestamp: str = ""
    session_id: str = ""
    tool_name: str = ""
    is_error: bool = False
    output_preview: str = ""


@dataclass
class ErrorEvent:
    """Emitted when an error occurs during an agent session."""

    type: EventType = field(default=EventType.error, init=False)
    timestamp: str = ""
    session_id: str = ""
    error_message: str = ""
    error_type: str = ""


@dataclass
class CompletedEvent:
    """Emitted when an agent session finishes (success or failure)."""

    type: EventType = field(default=EventType.completed, init=False)
    timestamp: str = ""
    session_id: str = ""
    status: str = ""
    cost_usd: float = 0.0
    duration_ms: int = 0
    num_turns: int = 0
    usage: dict = field(default_factory=dict)
    sdk_session_id: str = ""


# Union type for all events — useful for type hints in consumers.
Event = Union[StartedEvent, ToolUseEvent, ToolResultEvent, ErrorEvent, CompletedEvent]


# Dispatch table: EventType -> dataclass constructor.
_EVENT_TYPE_MAP: dict[EventType, type] = {
    EventType.started: StartedEvent,
    EventType.tool_use: ToolUseEvent,
    EventType.tool_result: ToolResultEvent,
    EventType.error: ErrorEvent,
    EventType.completed: CompletedEvent,
}


def serialize_event(event: Event) -> str:
    """Serialize an event dataclass to a single-line JSON string.

    Converts the EventType enum to its string value so the output is
    plain JSON (no Python-specific encoding).

    Args:
        event: Any event dataclass instance.

    Returns:
        Single-line JSON string (no trailing newline).
    """
    data = asdict(event)
    # EventType enum -> plain string for JSON portability
    data["type"] = data["type"].value if isinstance(data["type"], EventType) else data["type"]
    return json.dumps(data, separators=(",", ":"), sort_keys=False)


def deserialize_event(line: str) -> Event:
    """Deserialize a single JSON line back into the correct event dataclass.

    Dispatches on the ``type`` field to reconstruct the right dataclass.

    Args:
        line: A single JSON line (as produced by ``serialize_event``).

    Returns:
        The reconstructed event dataclass instance.

    Raises:
        ValueError: If the ``type`` field is missing or unrecognized.
        json.JSONDecodeError: If the line is not valid JSON.
    """
    data = json.loads(line)

    raw_type = data.get("type")
    if raw_type is None:
        raise ValueError("Event JSON missing required 'type' field")

    try:
        event_type = EventType(raw_type)
    except ValueError:
        raise ValueError(f"Unknown event type: {raw_type!r}")

    cls = _EVENT_TYPE_MAP[event_type]

    # Build kwargs from data, skipping 'type' (set by field default)
    kwargs = {k: v for k, v in data.items() if k != "type"}
    return cls(**kwargs)


# ---------------------------------------------------------------------------
# Event file I/O — atomic JSONL writer for the streaming side-channel.
#
# The event file lives at /tmp/agentic/sessions/{session_id}/events.jsonl.
# EventWriter keeps the file handle open for its lifetime and guarantees:
#   - Exactly one JSON line per emit() call
#   - Immediate flush + fsync after each write (no partial lines)
#   - Context manager protocol (__enter__/__exit__)
#
# @story US-260401AG-002
# ---------------------------------------------------------------------------

#: Root directory for all session event files.
_SESSIONS_ROOT = Path("/tmp/agentic/sessions")


def get_event_file_path(session_id: str) -> Path:
    """Return the canonical path for a session's event JSONL file.

    The path is deterministic and shared by EventWriter and EventWatcher
    so that producers and consumers agree on the file location.

    Args:
        session_id: UUID string identifying the agent session.

    Returns:
        ``/tmp/agentic/sessions/{session_id}/events.jsonl``
    """
    return _SESSIONS_ROOT / session_id / "events.jsonl"


class EventWriter:
    """Atomic JSONL append writer for the streaming event bus.

    Opens ``/tmp/agentic/sessions/{session_id}/events.jsonl`` in append mode
    and keeps the file handle open for the writer's lifetime.  Each
    :meth:`emit` call serializes an event to a single JSON line, writes it,
    and immediately flushes + fsyncs to guarantee no partial lines on disk.

    Supports the context manager protocol::

        with EventWriter(session_id) as writer:
            writer.emit(StartedEvent(...))

    @story US-260401AG-002
    """

    def __init__(self, session_id: str) -> None:
        self._session_id = session_id
        self._path = get_event_file_path(session_id)
        # Create the session directory if it doesn't exist.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Open for append; keep the handle for the writer's lifetime.
        self._fh: IO[str] = open(self._path, mode="a", encoding="utf-8")

    # -- public API ----------------------------------------------------------

    def emit(self, event: Event) -> None:
        """Serialize *event* and append exactly one JSON line to the file.

        The line is flushed to the OS buffer and then fsynced to disk so
        that even a process crash cannot leave a partial line.

        Args:
            event: Any event dataclass instance.
        """
        line = serialize_event(event)
        self._fh.write(line + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def close(self) -> None:
        """Close the underlying file handle.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._fh is not None and not self._fh.closed:
            self._fh.close()

    # -- properties ----------------------------------------------------------

    @property
    def path(self) -> Path:
        """Return the path of the events JSONL file."""
        return self._path

    @property
    def session_id(self) -> str:
        """Return the session ID this writer is bound to."""
        return self._session_id

    # -- context manager -----------------------------------------------------

    def __enter__(self) -> "EventWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()
        return None


class EventWatcher:
    """Seek-based tail-follow reader for the streaming event bus.

    Reads new lines from ``/tmp/agentic/sessions/{session_id}/events.jsonl``
    by tracking a file-seek offset between :meth:`poll` calls.  Handles the
    common race condition where the watcher starts *before* the writer has
    created the file — :meth:`poll` simply returns an empty list until the
    file appears.

    Usage — one-shot poll::

        watcher = EventWatcher(session_id)
        events = watcher.poll()

    Usage — blocking generator::

        watcher = EventWatcher(session_id)
        for event in watcher.iter_events(timeout=120):
            print(event)

    @story US-260401AG-002
    """

    def __init__(self, session_id: str, *, start_from_beginning: bool = True) -> None:
        self._session_id = session_id
        self._path = get_event_file_path(session_id)
        self._pos: int = 0 if start_from_beginning else -1
        # -1 signals "seek to end on first open" (not yet resolved)

    # -- public API ----------------------------------------------------------

    def poll(self) -> list[Event]:
        """Read new events since the last poll.

        Opens the file, seeks to the stored offset, reads remaining
        complete lines, and updates the offset.  Incomplete trailing
        lines (no trailing newline) are left for the next poll.

        Returns:
            List of deserialized events (may be empty).
        """
        if not self._path.exists():
            return []

        events: list[Event] = []
        with open(self._path, mode="r", encoding="utf-8") as fh:
            # Resolve "seek to end" on first open when start_from_beginning=False
            if self._pos == -1:
                fh.seek(0, os.SEEK_END)
                self._pos = fh.tell()
                return []

            fh.seek(self._pos)
            data = fh.read()
            if not data:
                return []

            # Split on newlines — the last element may be an incomplete line.
            parts = data.split("\n")

            # If data ends with newline, the last element is an empty string
            # and all preceding parts are complete lines.
            # If data does NOT end with newline, the last element is an
            # incomplete line — leave it for the next poll.
            if data.endswith("\n"):
                complete_lines = parts[:-1]  # drop trailing empty string
                self._pos += len(data)
            else:
                complete_lines = parts[:-1]
                consumed = sum(len(line) + 1 for line in complete_lines)
                self._pos += consumed

            for line in complete_lines:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    events.append(deserialize_event(stripped))
                except (json.JSONDecodeError, ValueError):
                    # Skip corrupt/truncated lines — they should not happen
                    # under normal operation but we must not crash the watcher.
                    continue

        return events

    def iter_events(
        self,
        timeout: float = 600.0,
        poll_interval: float = 0.5,
    ) -> Generator[Event, None, None]:
        """Yield events as they appear, polling at *poll_interval* seconds.

        Stops after *timeout* seconds of wall-clock time.  Uses
        :func:`time.monotonic` for deadline tracking (immune to wall-clock
        adjustments).

        Args:
            timeout: Maximum seconds to keep polling.
            poll_interval: Seconds to sleep between polls.

        Yields:
            Deserialized event objects in chronological order.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            events = self.poll()
            for event in events:
                yield event
            if not events:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(poll_interval, remaining))

    # -- properties ----------------------------------------------------------

    @property
    def path(self) -> Path:
        """Return the path of the events JSONL file being watched."""
        return self._path

    @property
    def session_id(self) -> str:
        """Return the session ID this watcher is bound to."""
        return self._session_id

    @property
    def position(self) -> int:
        """Return the current file-seek position."""
        return self._pos


# ---------------------------------------------------------------------------
# Session ledger summary — fixed-size digest of a session's events.jsonl.
#
# Produces a bounded-size summary (≤1KB) for orchestrator agents to assess
# session outcomes without reading raw JSONL into their context window.
#
# @story US-260401AG-007
# ---------------------------------------------------------------------------

#: Maximum length for truncated error messages in the summary.
_ERROR_PREVIEW_MAX_CHARS = 200

#: Maximum number of error previews included in the summary.
#: Kept low (3) to ensure the full JSON summary stays ≤1KB even when
#: each preview is at the 200-char truncation limit.
_MAX_ERROR_PREVIEWS = 3


def summarize_session_ledger(session_id: str) -> dict:
    """Produce a fixed-size digest of a session's event ledger.

    Reads all events from ``events.jsonl`` for *session_id* and returns an
    aggregate summary containing:

    - ``session_id``: The session identifier.
    - ``event_counts``: Dict of EventType name → count.
    - ``errors``: List of truncated error message previews (≤200 chars each,
      at most 5 entries).
    - ``total_events``: Total number of events in the ledger.
    - ``duration_ms``: Wall-clock duration from first to last event (ms),
      or ``None`` if fewer than 2 events.
    - ``final_status``: ``"completed"``, ``"failed"``, ``"in_progress"``, or
      ``"unknown"`` depending on the last CompletedEvent seen.

    The output dict serializes to ≤1KB JSON regardless of how many events
    the session produced.

    Args:
        session_id: UUID string identifying the agent session.

    Returns:
        Summary dict suitable for JSON serialization.

    Raises:
        FileNotFoundError: If the events.jsonl file does not exist for the
            given *session_id*.
    """
    event_file = get_event_file_path(session_id)
    if not event_file.exists():
        raise FileNotFoundError(
            f"No ledger found for session {session_id} "
            f"(expected {event_file})"
        )

    # Counters and accumulators
    counts: dict[str, int] = {et.value: 0 for et in EventType}
    errors: list[str] = []
    first_ts: str | None = None
    last_ts: str | None = None
    final_status: str = "unknown"
    total_events = 0

    with open(event_file, mode="r", encoding="utf-8") as fh:
        for raw_line in fh:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                event = deserialize_event(stripped)
            except (json.JSONDecodeError, ValueError):
                continue

            total_events += 1
            counts[event.type.value] = counts.get(event.type.value, 0) + 1

            # Track timestamps for duration
            ts = getattr(event, "timestamp", "")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

            # Collect error previews (bounded)
            if isinstance(event, ErrorEvent) and len(errors) < _MAX_ERROR_PREVIEWS:
                msg = event.error_message or ""
                if len(msg) > _ERROR_PREVIEW_MAX_CHARS:
                    msg = msg[:_ERROR_PREVIEW_MAX_CHARS] + "…"
                errors.append(msg)

            # Track final status from the last CompletedEvent
            if isinstance(event, CompletedEvent):
                status_val = event.status or ""
                if "fail" in status_val.lower() or "error" in status_val.lower():
                    final_status = "failed"
                else:
                    final_status = "completed"

    # If no CompletedEvent was seen, the session may still be running
    if final_status == "unknown" and total_events > 0:
        final_status = "in_progress"

    # Compute duration from first to last event timestamp
    duration_ms: int | None = None
    if first_ts and last_ts and first_ts != last_ts:
        try:
            t0 = datetime.fromisoformat(first_ts)
            t1 = datetime.fromisoformat(last_ts)
            duration_ms = int((t1 - t0).total_seconds() * 1000)
        except (ValueError, TypeError):
            duration_ms = None

    return {
        "session_id": session_id,
        "total_events": total_events,
        "event_counts": counts,
        "errors": errors,
        "duration_ms": duration_ms,
        "final_status": final_status,
    }


# ---------------------------------------------------------------------------
# Session ledger filtered query — scoped slices of a session's events.jsonl.
#
# Returns events matching optional type and last-N filters, enabling
# orchestrator agents to investigate failures surgically without the full
# event stream entering their context window.
#
# @story US-260401AG-008
# ---------------------------------------------------------------------------


def filter_session_ledger(
    session_id: str,
    *,
    event_type: str | None = None,
    last: int | None = None,
) -> list[dict]:
    """Return filtered events from a session's event ledger.

    Reads all events from ``events.jsonl`` for *session_id* and applies
    filters in order:

    1. **Type filter** (``event_type``): keep only events matching the
       given :class:`EventType` value string (e.g. ``"error"``).
    2. **Last-N filter** (``last``): keep only the last *N* events from
       the (possibly type-filtered) set.

    Each returned event is a plain dict (the serialized form) so that
    callers can emit JSON directly.

    Args:
        session_id: UUID string identifying the agent session.
        event_type: Optional EventType value string to filter by
            (e.g. ``"error"``, ``"tool_use"``).  ``None`` means no type
            filter.
        last: Optional positive int — keep only the last *N* events
            after type filtering.  ``None`` means no limit.

    Returns:
        List of event dicts in chronological order.

    Raises:
        FileNotFoundError: If the events.jsonl file does not exist.
        ValueError: If *event_type* is not a valid EventType value.
    """
    event_file = get_event_file_path(session_id)
    if not event_file.exists():
        raise FileNotFoundError(
            f"No ledger found for session {session_id} "
            f"(expected {event_file})"
        )

    # Validate event_type early if provided
    if event_type is not None:
        try:
            EventType(event_type)
        except ValueError:
            valid = ", ".join(et.value for et in EventType)
            raise ValueError(
                f"Unknown event type: {event_type!r}. "
                f"Valid types: {valid}"
            )

    events: list[dict] = []
    with open(event_file, mode="r", encoding="utf-8") as fh:
        for raw_line in fh:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                continue

            # Apply type filter
            if event_type is not None and data.get("type") != event_type:
                continue

            events.append(data)

    # Apply last-N filter
    if last is not None:
        if last <= 0:
            events = []
        else:
            events = events[-last:]

    return events
