"""Tests for agenticcli.utils.epic_lock module.

Updated for fcntl.flock-based locking (FileLock from agenticguidance.services.state).
No more is_process_running mocks — uses real flock contention.

@story US-PLN-082
"""

import json
import os
import threading
from pathlib import Path

import pytest

pytestmark = pytest.mark.story("US-SES-020")

from agenticcli.utils.epic_lock import (
    _held_locks,
    acquire_epic_lock,
    release_epic_lock,
)


@pytest.fixture(autouse=True)
def lock_dir(tmp_path, monkeypatch):
    """Redirect lock directory to tmp_path and clean up _held_locks after each test."""
    lock_dir = tmp_path / ".agentic" / "locks"
    lock_dir.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yield lock_dir
    # Clean up any held locks between tests to avoid state leakage
    for epic, lock in list(_held_locks.items()):
        try:
            lock.release()
        except Exception:
            pass
    _held_locks.clear()


@pytest.mark.story("US-SES-020")
class TestAcquireEpicLock:
    def test_acquires_fresh_lock(self, lock_dir):
        """Acquire succeeds and lock file contains valid JSON with pid+timestamp."""
        assert acquire_epic_lock("test_epic") is True
        lock_file = lock_dir / "orchestrate_test_epic.lock"
        assert lock_file.exists()
        data = json.loads(lock_file.read_text())
        assert data["pid"] == os.getpid()
        assert "timestamp" in data

    def test_blocks_when_held_by_running_process(self, lock_dir):
        """Lock held via real flock blocks a second acquisition."""
        # Acquire in a background thread and hold it
        acquired_event = threading.Event()
        release_event = threading.Event()
        errors = []

        def hold_lock():
            try:
                result = acquire_epic_lock("test_epic")
                if not result:
                    errors.append("Background thread failed to acquire lock")
                    return
                acquired_event.set()
                release_event.wait(timeout=10)
                release_epic_lock("test_epic")
            except Exception as exc:
                errors.append(str(exc))

        holder = threading.Thread(target=hold_lock)
        holder.start()

        try:
            # Wait for the background thread to hold the lock
            assert acquired_event.wait(timeout=5), "Background thread did not acquire lock"

            # Now try to acquire the same lock — should fail (timeout=1s)
            assert acquire_epic_lock("test_epic") is False
        finally:
            release_event.set()
            holder.join(timeout=5)

        assert not errors, f"Background thread errors: {errors}"

    def test_clears_stale_lock(self, lock_dir):
        """Stale lock file (no flock held) does not block acquisition."""
        lock_file = lock_dir / "orchestrate_test_epic.lock"
        # Write a stale lock file — no flock is held on it
        lock_file.write_text(json.dumps({"pid": 99999, "timestamp": 0}))

        # Acquire succeeds because no flock is held (file content is irrelevant)
        assert acquire_epic_lock("test_epic") is True
        data = json.loads(lock_file.read_text())
        assert data["pid"] == os.getpid()

    def test_corrupt_lock_file_overwritten(self, lock_dir):
        """Corrupt lock file is overwritten on acquire."""
        lock_file = lock_dir / "orchestrate_test_epic.lock"
        lock_file.write_text("not json")
        assert acquire_epic_lock("test_epic") is True

    def test_different_epics_independent(self, lock_dir):
        """Locks for different epics don't interfere."""
        assert acquire_epic_lock("epic_a") is True
        assert acquire_epic_lock("epic_b") is True


@pytest.mark.story("US-SES-020")
class TestReleaseEpicLock:
    def test_release_allows_reacquisition(self, lock_dir):
        """After release, another process can acquire the lock."""
        acquire_epic_lock("test_epic")
        release_epic_lock("test_epic")

        # Lock should no longer be in _held_locks
        assert "test_epic" not in _held_locks

        # Re-acquisition should succeed immediately
        assert acquire_epic_lock("test_epic") is True

    def test_noop_when_no_lock(self, lock_dir):
        """Releasing a non-existent lock does nothing."""
        release_epic_lock("nonexistent_epic")  # Should not raise
