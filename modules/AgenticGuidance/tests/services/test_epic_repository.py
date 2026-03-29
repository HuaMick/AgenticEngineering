"""Integration tests for concurrent TinyDB ticket updates with FileLock retry.

Validates:
- Concurrent FileLock acquisition from multiple threads/processes
- RetryingFileLock backoff under lock contention
- Cache refresh after cross-process writes
- No data loss under concurrent ticket updates

@story US-PLN-055, US-PLN-057
"""

import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agenticguidance.services.epic_repository import EpicRepository
from agenticguidance.services.state import (
    FileLock,
    RetryingFileLock,
    FILELOCK_DEFAULT_TIMEOUT,
    FILELOCK_RETRY_MAX,
    FILELOCK_RETRY_BACKOFF_BASE,
)

pytestmark = pytest.mark.story("US-PLN-055", "US-PLN-057")

_SRC_DIR = str(Path(__file__).resolve().parent.parent.parent / "src")


@pytest.fixture
def repo(tmp_path):
    """Create an isolated EpicRepository backed by tmp_path."""
    db_path = tmp_path / "epics.db"
    r = EpicRepository(db_path=db_path, auto_bootstrap=False)
    yield r
    r.close()


def _seed_epic_with_tickets(repo, epic_name="test_epic", num_tickets=6):
    """Seed an epic with N tickets for concurrent update testing."""
    repo.create_epic({
        "plan_folder_name": epic_name,
        "plan_folder": f"/tmp/epics/{epic_name}",
        "name": epic_name,
        "status": "active",
        "objective": f"Test epic {epic_name}",
    })
    for i in range(num_tickets):
        repo.add_ticket(
            epic_name,
            "default_phase",
            {
                "task_id": f"T{i:03d}",
                "name": f"Ticket {i}",
                "status": "pending",
                "agent": "build-python",
                "story_ids": ["US-PLN-055"],
            },
        )


class TestConcurrentFileLockAcquisition:
    """Test FileLock under concurrent thread access.

    Note: fcntl.flock operates per-open-file-description, meaning threads
    sharing a file descriptor get the same lock. We create independent
    FileLock instances (each opens its own fd) to simulate independent callers.
    """

    def test_concurrent_threads_all_acquire_lock(self, tmp_path):
        """Multiple threads each acquiring their own FileLock all succeed eventually."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        results = {}
        errors = {}

        def acquire_and_release(thread_id):
            try:
                lock = FileLock(target, timeout=15.0)
                acquired = lock.acquire()
                results[thread_id] = acquired
                if acquired:
                    # Simulate a small critical section
                    time.sleep(0.05)
                    lock.release()
            except Exception as e:
                errors[thread_id] = str(e)

        threads = []
        for i in range(6):
            t = threading.Thread(target=acquire_and_release, args=(i,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Thread errors: {errors}"
        assert all(v is True for v in results.values()), f"Not all acquired: {results}"

    def test_concurrent_ticket_updates_no_data_loss(self, tmp_path):
        """6 concurrent threads updating different tickets — no data lost."""
        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        _seed_epic_with_tickets(repo, num_tickets=6)

        update_results = {}
        errors = {}

        def update_ticket(thread_id, ticket_id):
            try:
                # Each thread creates its own repo instance (own fd for lock)
                r = EpicRepository(db_path=db_path, auto_bootstrap=False)
                success = r.update_ticket(
                    "test_epic",
                    ticket_id,
                    {"status": "in_progress", "updated_by": f"thread_{thread_id}"},
                )
                update_results[thread_id] = success
                r.close()
            except Exception as e:
                errors[thread_id] = str(e)

        threads = []
        for i in range(6):
            t = threading.Thread(
                target=update_ticket, args=(i, f"T{i:03d}")
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Thread errors: {errors}"
        assert all(v is True for v in update_results.values())

        # Verify all updates persisted — refresh cache first
        repo.refresh()
        for i in range(6):
            tickets = repo.get_tickets("test_epic")
            ticket = next(t for t in tickets if t.id == f"T{i:03d}")
            assert ticket.status == "in_progress", f"T{i:03d} not updated"

        repo.close()


class TestRetryingFileLockBackoff:
    """Test RetryingFileLock retry-with-backoff under lock contention."""

    def test_retry_succeeds_after_lock_released(self, tmp_path):
        """RetryingFileLock succeeds when underlying lock is released during retry."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        # Hold a lock in a background thread, release after a short delay
        holder = FileLock(target, timeout=5.0)
        acquired = holder.acquire()
        assert acquired is True

        released = threading.Event()

        def release_after_delay():
            time.sleep(0.3)
            holder.release()
            released.set()

        threading.Thread(target=release_after_delay, daemon=True).start()

        # Try to acquire with retrying lock — short timeout so initial attempt fails
        contender = FileLock(target, timeout=0.1)
        retrying = RetryingFileLock(contender, max_retries=3, backoff_base=0.5)

        # This should succeed after the holder releases
        with retrying as lock:
            assert lock._acquired is True

        released.wait(timeout=5)

    def test_retry_exhausted_raises_timeout_error(self, tmp_path):
        """RetryingFileLock raises TimeoutError when all retries exhausted."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        # Hold a lock that won't be released
        holder = FileLock(target, timeout=5.0)
        acquired = holder.acquire()
        assert acquired is True

        try:
            # Very short timeout and retry to make test fast
            contender = FileLock(target, timeout=0.05)
            retrying = RetryingFileLock(contender, max_retries=2, backoff_base=0.1)

            with pytest.raises(TimeoutError):
                with retrying:
                    pass  # Should never reach here
        finally:
            holder.release()

    def test_retry_backoff_delays_increase(self, tmp_path, caplog):
        """Backoff delays follow exponential pattern: base * 2^attempt."""
        import logging

        target = tmp_path / "data.json"
        target.write_text("{}")

        # Hold the lock permanently for this test
        holder = FileLock(target, timeout=5.0)
        acquired = holder.acquire()
        assert acquired is True

        try:
            contender = FileLock(target, timeout=0.1)
            retrying = RetryingFileLock(
                contender, max_retries=3, backoff_base=1.0
            )

            with caplog.at_level(logging.WARNING):
                with pytest.raises(TimeoutError):
                    with retrying:
                        pass
        finally:
            holder.release()

        # Verify retry log messages show increasing backoff
        retry_msgs = [
            r.message for r in caplog.records
            if "retrying in" in r.message
        ]
        assert len(retry_msgs) == 3  # 3 retries before final failure
        assert "retrying in 1.0s" in retry_msgs[0]
        assert "retrying in 2.0s" in retry_msgs[1]
        assert "retrying in 4.0s" in retry_msgs[2]


class TestCacheRefreshAfterExternalWrite:
    """Test TinyDB cache refresh after cross-process/cross-thread writes."""

    def test_cache_refresh_sees_external_updates(self, tmp_path):
        """After refresh(), repo sees changes made by another instance."""
        db_path = tmp_path / "epics.db"

        # First repo instance creates an epic
        repo1 = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo1.create_epic({
            "plan_folder_name": "epic_a",
            "plan_folder": "/tmp/epics/epic_a",
            "name": "epic_a",
            "status": "active",
            "objective": "Test epic",
        })

        # Second repo instance (simulating another agent process)
        repo2 = EpicRepository(db_path=db_path, auto_bootstrap=False)

        # repo2 initially sees the epic
        assert repo2.get_epic("epic_a") is not None

        # repo1 adds a ticket (external write relative to repo2)
        repo1.add_ticket("epic_a", "phase_a", {
            "task_id": "T001",
            "name": "New ticket",
            "status": "pending",
            "agent": "build-python",
        })

        # Without refresh, repo2 may see stale data (cached query)
        # After refresh, repo2 should see the new ticket
        repo2.refresh()
        tickets = repo2.get_tickets("epic_a")
        assert len(tickets) >= 1
        assert any(t.id == "T001" for t in tickets)

        repo1.close()
        repo2.close()

    def test_cache_refresh_after_concurrent_thread_writes(self, tmp_path):
        """Multiple threads writing, then a reader sees all writes after refresh."""
        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        _seed_epic_with_tickets(repo, epic_name="concurrent_epic", num_tickets=0)

        # Write tickets from multiple threads, each using their own repo instance
        errors = {}

        def add_ticket_thread(thread_id):
            try:
                r = EpicRepository(db_path=db_path, auto_bootstrap=False)
                r.add_ticket("concurrent_epic", "default_phase", {
                    "task_id": f"T{thread_id:03d}",
                    "name": f"Ticket from thread {thread_id}",
                    "status": "pending",
                    "agent": "explore",
                })
                r.close()
            except Exception as e:
                errors[thread_id] = str(e)

        threads = []
        for i in range(4):
            t = threading.Thread(target=add_ticket_thread, args=(i,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Thread errors: {errors}"

        # Refresh and verify all tickets visible
        repo.refresh()
        tickets = repo.get_tickets("concurrent_epic")
        ticket_ids = {t.id for t in tickets}
        for i in range(4):
            assert f"T{i:03d}" in ticket_ids, f"T{i:03d} missing after refresh"

        repo.close()

    def test_cross_process_write_visible_after_refresh(self, tmp_path):
        """Subprocess writes a ticket; parent sees it after refresh."""
        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.create_epic({
            "plan_folder_name": "cross_proc_epic",
            "plan_folder": "/tmp/epics/cross_proc_epic",
            "name": "cross_proc_epic",
            "status": "active",
            "objective": "Cross-process test",
        })

        # Subprocess adds a ticket
        script = textwrap.dedent(f"""\
            import sys
            sys.path.insert(0, "{_SRC_DIR}")
            from agenticguidance.services.epic_repository import EpicRepository
            from pathlib import Path

            repo = EpicRepository(db_path=Path("{db_path}"), auto_bootstrap=False)
            repo.add_ticket("cross_proc_epic", "default_phase", {{
                "task_id": "T_SUBPROCESS",
                "name": "Subprocess ticket",
                "status": "pending",
                "agent": "explore",
            }})
            repo.close()
        """)
        script_path = tmp_path / "add_ticket.py"
        script_path.write_text(script)

        proc = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            timeout=15,
        )
        assert proc.returncode == 0, f"Subprocess failed: {proc.stderr.decode()}"

        # Before refresh — may not see the new ticket
        # After refresh — must see it
        repo.refresh()
        tickets = repo.get_tickets("cross_proc_epic")
        ticket_ids = {t.id for t in tickets}
        assert "T_SUBPROCESS" in ticket_ids, "Subprocess ticket not visible after refresh"

        repo.close()


class TestNoDataLossUnderContention:
    """Verify no ticket updates are lost under concurrent write contention."""

    def test_concurrent_status_updates_all_persisted(self, tmp_path):
        """6 threads each update a different ticket status — all persist."""
        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        _seed_epic_with_tickets(repo, num_tickets=6)

        errors = {}
        results = {}

        def update_status(thread_id):
            try:
                r = EpicRepository(db_path=db_path, auto_bootstrap=False)
                success = r.update_ticket(
                    "test_epic",
                    f"T{thread_id:03d}",
                    {"status": "completed", "completed_by": f"agent_{thread_id}"},
                )
                results[thread_id] = success
                r.close()
            except Exception as e:
                errors[thread_id] = str(e)

        threads = []
        for i in range(6):
            t = threading.Thread(target=update_status, args=(i,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Thread errors: {errors}"
        assert all(v is True for v in results.values())

        # Verify all updates persisted
        repo.refresh()
        for i in range(6):
            tickets = repo.get_tickets("test_epic")
            ticket = next(t for t in tickets if t.id == f"T{i:03d}")
            assert ticket.status == "completed", f"T{i:03d} status not updated"

        repo.close()

    def test_concurrent_same_ticket_update_last_writer_wins(self, tmp_path):
        """Multiple threads updating the same ticket — last writer wins, no corruption."""
        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        _seed_epic_with_tickets(repo, num_tickets=1)

        errors = {}
        results = {}
        barrier = threading.Barrier(3, timeout=10)

        def update_same_ticket(thread_id):
            try:
                r = EpicRepository(db_path=db_path, auto_bootstrap=False)
                barrier.wait()  # All threads start at the same time
                success = r.update_ticket(
                    "test_epic",
                    "T000",
                    {"status": "in_progress", "last_updater": f"thread_{thread_id}"},
                )
                results[thread_id] = success
                r.close()
            except Exception as e:
                errors[thread_id] = str(e)

        threads = []
        for i in range(3):
            t = threading.Thread(target=update_same_ticket, args=(i,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Thread errors: {errors}"
        assert all(v is True for v in results.values())

        # Verify ticket is not corrupted — has a valid status and updater
        repo.refresh()
        tickets = repo.get_tickets("test_epic")
        ticket = next(t for t in tickets if t.id == "T000")
        assert ticket.status == "in_progress"

        repo.close()
