"""Tests for state service."""

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.story("US-SES-006")

from agenticguidance.services.state import (
    FileLock,
    ProcessEntry,
    ProcessState,
    StateRegistry,
)


class TestProcessState:
    """Tests for ProcessState enum."""

    def test_state_values(self):
        """Test state enum values."""
        assert ProcessState.RUNNING.value == "running"
        assert ProcessState.COMPLETED.value == "completed"
        assert ProcessState.FAILED.value == "failed"
        assert ProcessState.STALE.value == "stale"


class TestProcessEntry:
    """Tests for ProcessEntry dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        entry = ProcessEntry(
            pid=12345,
            name="test-process",
            command="python test.py",
            started_at=1704067200.0,
            state=ProcessState.RUNNING,
            metadata={"key": "value"},
        )

        result = entry.to_dict()

        assert result["pid"] == 12345
        assert result["name"] == "test-process"
        assert result["command"] == "python test.py"
        assert result["started_at"] == 1704067200.0
        assert result["state"] == "running"
        assert result["metadata"] == {"key": "value"}
        assert result["ended_at"] is None

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "pid": 12345,
            "name": "test-process",
            "command": "python test.py",
            "started_at": 1704067200.0,
            "state": "completed",
            "metadata": {"key": "value"},
            "ended_at": 1704067300.0,
        }

        entry = ProcessEntry.from_dict(data)

        assert entry.pid == 12345
        assert entry.name == "test-process"
        assert entry.state == ProcessState.COMPLETED
        assert entry.ended_at == 1704067300.0

    def test_default_state_is_running(self):
        """Test default state is RUNNING."""
        entry = ProcessEntry(
            pid=1,
            name="test",
            command="test",
            started_at=time.time(),
        )

        assert entry.state == ProcessState.RUNNING


class TestFileLock:
    """Tests for FileLock class."""

    def test_acquire_creates_lock_file(self, tmp_path):
        """Test acquiring lock creates .lock file."""
        target_file = tmp_path / "data.json"
        target_file.write_text("{}")

        lock = FileLock(target_file)
        acquired = lock.acquire()

        assert acquired is True
        assert lock.lock_path.exists()
        lock.release()

    def test_release_unlocks_flock(self, tmp_path):
        """Test releasing lock allows re-acquisition (flock released, file persists)."""
        target_file = tmp_path / "data.json"
        target_file.write_text("{}")

        lock = FileLock(target_file)
        lock.acquire()
        lock.release()

        # With fcntl.flock, the lock file persists but the flock is released.
        # Verify another lock can acquire immediately (no timeout).
        lock2 = FileLock(target_file, timeout=1.0)
        assert lock2.acquire() is True
        lock2.release()

    def test_context_manager_acquires_and_releases(self, tmp_path):
        """Test context manager properly handles lock lifecycle."""
        target_file = tmp_path / "data.json"
        target_file.write_text("{}")

        with FileLock(target_file) as lock:
            assert lock.lock_path.exists()
            assert lock._acquired is True

        # After exit, flock is released (file persists but is unlocked)
        assert lock._acquired is False
        lock2 = FileLock(target_file, timeout=1.0)
        assert lock2.acquire() is True
        lock2.release()

    def test_double_acquire_waits(self, tmp_path):
        """Test second acquire waits for first release."""
        target_file = tmp_path / "data.json"
        target_file.write_text("{}")

        lock1 = FileLock(target_file, timeout=0.5)
        lock2 = FileLock(target_file, timeout=0.1)

        lock1.acquire()
        acquired = lock2.acquire()  # Should timeout

        assert acquired is False
        lock1.release()

    def test_stale_lock_detection(self, tmp_path):
        """Test stale lock is detected and cleaned up."""
        target_file = tmp_path / "data.json"
        target_file.write_text("{}")

        # Create stale lock with non-existent PID
        lock_path = target_file.with_suffix(".json.lock")
        lock_path.write_text("99999999")  # Unlikely to be a real PID

        lock = FileLock(target_file, timeout=1.0)
        acquired = lock.acquire()

        assert acquired is True
        lock.release()


class TestStateRegistry:
    """Tests for StateRegistry class."""

    def test_init_creates_parent_dir(self, tmp_path):
        """Test registry creates parent directory if needed."""
        state_file = tmp_path / "subdir" / "state.json"

        registry = StateRegistry(state_file)

        assert state_file.parent.exists()

    def test_register_creates_entry(self, tmp_path):
        """Test registering a process creates entry."""
        state_file = tmp_path / "state.json"
        registry = StateRegistry(state_file)

        entry = registry.register(name="test", command="python test.py")

        assert entry.pid == os.getpid()
        assert entry.name == "test"
        assert entry.command == "python test.py"
        assert entry.state == ProcessState.RUNNING

    def test_register_persists_to_file(self, tmp_path):
        """Test registration is persisted to state file."""
        state_file = tmp_path / "state.json"
        registry = StateRegistry(state_file)

        registry.register(name="test", command="python test.py")

        data = json.loads(state_file.read_text())
        assert str(os.getpid()) in data["processes"]

    def test_unregister_removes_entry(self, tmp_path):
        """Test unregistering removes process entry."""
        state_file = tmp_path / "state.json"
        registry = StateRegistry(state_file)

        registry.register(name="test", command="test")
        removed = registry.unregister()

        assert removed is True
        data = json.loads(state_file.read_text())
        assert str(os.getpid()) not in data["processes"]

    def test_unregister_returns_false_for_missing(self, tmp_path):
        """Test unregister returns False for non-existent PID."""
        state_file = tmp_path / "state.json"
        registry = StateRegistry(state_file)

        removed = registry.unregister(pid=99999999)

        assert removed is False

    def test_update_state_changes_state(self, tmp_path):
        """Test updating process state."""
        state_file = tmp_path / "state.json"
        registry = StateRegistry(state_file)

        registry.register(name="test", command="test")
        updated = registry.update_state(state=ProcessState.COMPLETED)

        assert updated is True
        entry = registry.get(os.getpid())
        assert entry.state == ProcessState.COMPLETED
        assert entry.ended_at is not None

    def test_get_returns_entry(self, tmp_path):
        """Test getting process by PID."""
        state_file = tmp_path / "state.json"
        registry = StateRegistry(state_file)

        registry.register(name="test", command="test", metadata={"key": "value"})
        entry = registry.get(os.getpid())

        assert entry is not None
        assert entry.name == "test"
        assert entry.metadata == {"key": "value"}

    def test_get_returns_none_for_missing(self, tmp_path):
        """Test get returns None for non-existent PID."""
        state_file = tmp_path / "state.json"
        registry = StateRegistry(state_file)

        entry = registry.get(99999999)

        assert entry is None

    def test_list_all_returns_all_entries(self, tmp_path):
        """Test list_all returns all registered processes."""
        state_file = tmp_path / "state.json"
        registry = StateRegistry(state_file)

        registry.register(name="test1", command="cmd1")
        # Simulate another process entry
        data = json.loads(state_file.read_text())
        data["processes"]["99999"] = {
            "pid": 99999,
            "name": "test2",
            "command": "cmd2",
            "started_at": time.time(),
            "state": "running",
            "metadata": {},
            "ended_at": None,
        }
        state_file.write_text(json.dumps(data))

        entries = registry.list_all()

        assert len(entries) == 2

    def test_list_active_filters_running(self, tmp_path):
        """Test list_active only returns running processes."""
        state_file = tmp_path / "state.json"
        registry = StateRegistry(state_file)

        registry.register(name="test", command="test")
        registry.update_state(state=ProcessState.COMPLETED)

        active = registry.list_active()

        assert len(active) == 0

    def test_clear_completed_removes_non_running(self, tmp_path):
        """Test clear_completed removes completed/failed/stale entries."""
        state_file = tmp_path / "state.json"
        registry = StateRegistry(state_file)

        registry.register(name="test", command="test")
        registry.update_state(state=ProcessState.COMPLETED)

        removed = registry.clear_completed()

        assert removed == 1
        assert len(registry.list_all()) == 0

    def test_clear_all_removes_everything(self, tmp_path):
        """Test clear_all removes all entries."""
        state_file = tmp_path / "state.json"
        registry = StateRegistry(state_file)

        registry.register(name="test", command="test")

        removed = registry.clear_all()

        assert removed == 1
        assert len(registry.list_all()) == 0
