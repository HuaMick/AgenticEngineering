"""Tests for agenticcli.utils.epic_lock module."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.story("US-PLN-082")

from agenticcli.utils.epic_lock import acquire_epic_lock, release_epic_lock


@pytest.fixture(autouse=True)
def lock_dir(tmp_path, monkeypatch):
    """Redirect lock directory to tmp_path."""
    lock_dir = tmp_path / ".agentic" / "locks"
    lock_dir.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return lock_dir


@pytest.mark.story("US-PLN-082")
class TestAcquireEpicLock:
    def test_acquires_fresh_lock(self, lock_dir):
        assert acquire_epic_lock("test_epic") is True
        lock_file = lock_dir / "orchestrate_test_epic.lock"
        assert lock_file.exists()
        data = json.loads(lock_file.read_text())
        assert data["pid"] == os.getpid()

    def test_blocks_when_held_by_running_process(self, lock_dir):
        """Lock held by a running process blocks acquisition."""
        lock_file = lock_dir / "orchestrate_test_epic.lock"
        lock_file.write_text(json.dumps({"pid": os.getpid(), "started_at": "2026-01-01T00:00:00"}))

        with patch("agenticcli.utils.epic_lock.is_process_running", return_value=True):
            assert acquire_epic_lock("test_epic") is False

    def test_clears_stale_lock(self, lock_dir):
        """Stale lock (dead process) is cleared and reacquired."""
        lock_file = lock_dir / "orchestrate_test_epic.lock"
        lock_file.write_text(json.dumps({"pid": 99999, "started_at": "2026-01-01T00:00:00"}))

        with patch("agenticcli.utils.epic_lock.is_process_running", return_value=False):
            assert acquire_epic_lock("test_epic") is True
        data = json.loads(lock_file.read_text())
        assert data["pid"] == os.getpid()

    def test_corrupt_lock_file_overwritten(self, lock_dir):
        """Corrupt lock file is overwritten."""
        lock_file = lock_dir / "orchestrate_test_epic.lock"
        lock_file.write_text("not json")
        assert acquire_epic_lock("test_epic") is True

    def test_different_epics_independent(self, lock_dir):
        """Locks for different epics don't interfere."""
        assert acquire_epic_lock("epic_a") is True
        assert acquire_epic_lock("epic_b") is True


@pytest.mark.story("US-PLN-082")
class TestReleaseEpicLock:
    def test_removes_lock_file(self, lock_dir):
        acquire_epic_lock("test_epic")
        release_epic_lock("test_epic")
        lock_file = lock_dir / "orchestrate_test_epic.lock"
        assert not lock_file.exists()

    def test_noop_when_no_lock(self, lock_dir):
        """Releasing a non-existent lock does nothing."""
        release_epic_lock("nonexistent_epic")  # Should not raise
