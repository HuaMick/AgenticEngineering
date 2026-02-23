"""Tests for FileLock protecting concurrent PlanRepository writes.

Validates that:
- Concurrent writes are serialized via FileLock
- Lock file appears during write operations
- Stale locks with dead PIDs are recovered
- Read operations work without acquiring the lock
"""

import os
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from agenticguidance.services.plan_repository import PlanRepository


@pytest.fixture
def repo(tmp_path):
    """Create an isolated PlanRepository backed by tmp_path."""
    db_path = tmp_path / "plans.db"
    r = PlanRepository(db_path=db_path, auto_bootstrap=False)
    yield r
    r.close()


def _make_plan_data(name: str) -> dict:
    """Helper to build minimal plan data for create_plan."""
    return {
        "plan_folder_name": name,
        "plan_folder": f"/tmp/plans/{name}",
        "name": name,
        "status": "pending",
        "objective": f"Objective for {name}",
    }


class TestConcurrentWritesSerialized:
    """FL_002-1: Concurrent create_plan calls are serialized by FileLock."""

    def test_concurrent_writes_are_serialized(self, tmp_path):
        """Two threads calling create_plan concurrently both succeed without corruption."""
        db_path = tmp_path / "plans.db"
        results = {}
        errors = []

        def create_in_thread(plan_name: str):
            try:
                r = PlanRepository(db_path=db_path, auto_bootstrap=False)
                result = r.create_plan(_make_plan_data(plan_name))
                results[plan_name] = result
                r.close()
            except Exception as exc:
                errors.append((plan_name, exc))

        t1 = threading.Thread(target=create_in_thread, args=("plan_alpha",))
        t2 = threading.Thread(target=create_in_thread, args=("plan_beta",))

        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        assert not errors, f"Threads raised errors: {errors}"
        assert results["plan_alpha"].success is True
        assert results["plan_beta"].success is True

        # Verify both plans exist in the DB
        verify = PlanRepository(db_path=db_path, auto_bootstrap=False)
        assert verify.get_plan("plan_alpha") is not None
        assert verify.get_plan("plan_beta") is not None
        verify.close()


class TestLockFileCreatedDuringWrite:
    """FL_002-2: .lock file appears while a write operation holds the lock."""

    def test_lock_file_created_during_write(self, tmp_path):
        """The .lock file must exist while inside the locked section."""
        db_path = tmp_path / "plans.db"
        lock_path = Path(str(db_path) + ".lock")
        lock_seen = threading.Event()

        original_insert = None

        def spy_insert(doc):
            """Intercept TinyDB insert to check lock file mid-write."""
            if lock_path.exists():
                lock_seen.set()
            return original_insert(doc)

        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)
        original_insert = repo._plans.insert
        repo._plans.insert = spy_insert

        result = repo.create_plan(_make_plan_data("plan_lock_test"))
        repo.close()

        assert result.success is True
        assert lock_seen.is_set(), "Lock file was not observed during write"
        # Lock should be released after the operation
        assert not lock_path.exists(), "Lock file should be cleaned up after write"


class TestStaleLockRecovery:
    """FL_002-3: PlanRepository recovers from stale lock files with dead PIDs."""

    def test_stale_lock_recovery(self, tmp_path):
        """A stale lock file with a dead PID is cleaned up automatically."""
        db_path = tmp_path / "plans.db"
        lock_path = Path(str(db_path) + ".lock")

        # Create a stale lock file with a PID that does not exist.
        # PID 2^22 (4194304) is extremely unlikely to be running.
        dead_pid = 4194304
        lock_path.write_text(str(dead_pid))

        # Patch pid_exists / os.kill to confirm the PID is dead
        with patch("agenticguidance.services.state.HAS_PSUTIL", False):
            with patch("os.kill", side_effect=OSError("No such process")):
                repo = PlanRepository(db_path=db_path, auto_bootstrap=False)
                result = repo.create_plan(_make_plan_data("plan_after_stale"))
                repo.close()

        assert result.success is True
        assert not lock_path.exists(), "Stale lock should have been cleaned up"


class TestReadOperationsDontLock:
    """FL_002-4: Read operations (get_plan, list_plans) work without lock."""

    def test_get_plan_works_without_lock(self, repo):
        """get_plan succeeds even when lock file is held by another process."""
        repo.create_plan(_make_plan_data("plan_readable"))

        # Manually create a lock file simulating another process holding it
        lock_path = Path(str(repo.db_path) + ".lock")
        lock_path.write_text(str(os.getpid()))  # current PID = alive

        try:
            plan = repo.get_plan("plan_readable")
            assert plan is not None
            assert plan.plan_folder_name == "plan_readable"
        finally:
            lock_path.unlink(missing_ok=True)

    def test_list_plans_works_without_lock(self, repo):
        """list_plans succeeds even when lock file is held by another process."""
        repo.create_plan(_make_plan_data("plan_listable"))

        lock_path = Path(str(repo.db_path) + ".lock")
        lock_path.write_text(str(os.getpid()))

        try:
            plans = repo.list_plans()
            assert len(plans) >= 1
            names = [p.plan_folder_name for p in plans]
            assert "plan_listable" in names
        finally:
            lock_path.unlink(missing_ok=True)

    def test_get_tasks_works_without_lock(self, repo):
        """get_tasks succeeds even when lock file is held."""
        repo.create_plan(_make_plan_data("plan_with_tasks"))
        repo.add_task(
            "plan_with_tasks",
            "Phase 1",
            {"id": "T1", "name": "task", "status": "pending"},
        )

        lock_path = Path(str(repo.db_path) + ".lock")
        lock_path.write_text(str(os.getpid()))

        try:
            tasks = repo.get_tasks("plan_with_tasks")
            assert len(tasks) == 1
            assert tasks[0].id == "T1"
        finally:
            lock_path.unlink(missing_ok=True)
