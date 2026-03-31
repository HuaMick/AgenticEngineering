"""Tests for StateStore.delete() and list_stale() methods.

Validates:
- delete() removes JSON files and is idempotent on missing records
- list_stale() filters records by a predicate, returns empty when all alive

Story coverage: US-SES-007 (Clear State Registry), US-SES-008 (Cleanup Dead Processes)
"""

import json
from pathlib import Path

import pytest

from agenticcli.utils.state_store import StateStore, is_process_running

pytestmark = pytest.mark.story("US-SES-007", "US-SES-008")


@pytest.fixture
def store(tmp_path):
    """Create a StateStore backed by tmp_path."""
    s = StateStore("sessions", id_key="session_id")
    # Ensure the directory exists under tmp_path
    state_dir = tmp_path / "sessions"
    state_dir.mkdir(parents=True)
    return s, state_dir


def _write_record(state_dir: Path, record: dict, id_key: str = "session_id") -> Path:
    """Helper to write a record JSON file."""
    path = state_dir / f"{record[id_key]}.json"
    path.write_text(json.dumps(record))
    return path


class TestStateStoreDelete:
    """Tests for StateStore.delete() method."""

    def test_delete_existing_record(self, store):
        """delete() removes the JSON file and returns True."""
        s, state_dir = store
        record = {"session_id": "sess-001", "status": "completed"}
        _write_record(state_dir, record)

        assert (state_dir / "sess-001.json").exists()
        result = s.delete("sess-001", state_dir=state_dir)
        assert result is True
        assert not (state_dir / "sess-001.json").exists()

    def test_delete_missing_record_is_idempotent(self, store):
        """delete() returns False for non-existent records without error."""
        s, state_dir = store
        result = s.delete("nonexistent", state_dir=state_dir)
        assert result is False

    def test_delete_idempotent_double_call(self, store):
        """Calling delete() twice on the same record succeeds both times."""
        s, state_dir = store
        record = {"session_id": "sess-002", "status": "failed"}
        _write_record(state_dir, record)

        assert s.delete("sess-002", state_dir=state_dir) is True
        assert s.delete("sess-002", state_dir=state_dir) is False

    def test_delete_does_not_affect_other_records(self, store):
        """Deleting one record leaves other records intact."""
        s, state_dir = store
        rec_a = {"session_id": "sess-a", "status": "completed"}
        rec_b = {"session_id": "sess-b", "status": "running"}
        _write_record(state_dir, rec_a)
        _write_record(state_dir, rec_b)

        s.delete("sess-a", state_dir=state_dir)
        assert not (state_dir / "sess-a.json").exists()
        assert (state_dir / "sess-b.json").exists()

    def test_delete_record_can_be_verified_via_load(self, store):
        """After delete(), load() returns None for the deleted record."""
        s, state_dir = store
        record = {"session_id": "sess-003", "status": "stopped"}
        s.save(record, state_dir=state_dir)

        assert s.load("sess-003", state_dir=state_dir) is not None
        s.delete("sess-003", state_dir=state_dir)
        assert s.load("sess-003", state_dir=state_dir) is None


class TestStateStoreListStale:
    """Tests for StateStore.list_stale() method."""

    def test_list_stale_returns_dead_records(self, store):
        """list_stale() returns records where predicate returns False."""
        s, state_dir = store
        alive = {"session_id": "alive-1", "status": "running", "pid": 1}
        dead = {"session_id": "dead-1", "status": "running", "pid": 99999}
        _write_record(state_dir, alive)
        _write_record(state_dir, dead)

        def is_alive(rec):
            return rec.get("session_id") == "alive-1"

        stale = s.list_stale(is_alive, state_dir=state_dir)
        stale_ids = {r["session_id"] for r in stale}
        assert "dead-1" in stale_ids
        assert "alive-1" not in stale_ids

    def test_list_stale_empty_when_all_alive(self, store):
        """list_stale() returns empty list when all records are alive."""
        s, state_dir = store
        for i in range(3):
            _write_record(state_dir, {"session_id": f"alive-{i}", "status": "running"})

        stale = s.list_stale(lambda rec: True, state_dir=state_dir)
        assert stale == []

    def test_list_stale_all_dead(self, store):
        """list_stale() returns all records when none are alive."""
        s, state_dir = store
        for i in range(3):
            _write_record(state_dir, {"session_id": f"dead-{i}", "status": "completed"})

        stale = s.list_stale(lambda rec: False, state_dir=state_dir)
        assert len(stale) == 3

    def test_list_stale_with_empty_directory(self, store):
        """list_stale() returns empty list for empty state directory."""
        s, state_dir = store
        stale = s.list_stale(lambda rec: False, state_dir=state_dir)
        assert stale == []

    def test_list_stale_skips_malformed_json(self, store):
        """list_stale() skips files with invalid JSON without crashing."""
        s, state_dir = store
        good = {"session_id": "good-1", "status": "completed"}
        _write_record(state_dir, good)
        # Write a malformed JSON file
        (state_dir / "bad-1.json").write_text("{invalid json content")

        stale = s.list_stale(lambda rec: False, state_dir=state_dir)
        # Only the valid record should be returned
        assert len(stale) == 1
        assert stale[0]["session_id"] == "good-1"

    def test_list_stale_predicate_receives_full_record(self, store):
        """The predicate function receives the full record dict."""
        s, state_dir = store
        record = {"session_id": "full-rec", "status": "running", "pid": 123, "extra": "data"}
        _write_record(state_dir, record)

        received = []

        def capture_pred(rec):
            received.append(rec)
            return True

        s.list_stale(capture_pred, state_dir=state_dir)
        assert len(received) == 1
        assert received[0]["session_id"] == "full-rec"
        assert received[0]["pid"] == 123
        assert received[0]["extra"] == "data"


class TestIsProcessRunning:
    """Tests for the is_process_running() helper function."""

    def test_current_process_is_running(self):
        """The current process should be detected as running."""
        import os
        assert is_process_running(os.getpid()) is True

    def test_dead_pid_not_running(self):
        """A very high PID that doesn't exist should be detected as not running."""
        # PID 4000000 is very unlikely to be running
        assert is_process_running(4000000) is False

    def test_negative_pid_not_running(self):
        """Negative PIDs should be reported as not running."""
        assert is_process_running(-1) is False
