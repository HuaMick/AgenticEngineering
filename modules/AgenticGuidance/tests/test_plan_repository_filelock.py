"""Tests for FileLock protecting concurrent EpicRepository writes.

Updated for fcntl.flock-based locking. Key changes from O_CREAT|O_EXCL era:
- Lock file persists after release (flock is tied to fd, not file existence)
- Cross-process serialization is the primary guarantee (flock is per-fd)
- Stale lock files without a held flock do not block acquisition

Validates that:
- Concurrent writes from separate processes are serialized via FileLock
- Lock file appears during write operations
- Stale lock files (no flock held) do not block acquisition
- Read operations work without acquiring the lock
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from agenticguidance.services.epic_repository import EpicRepository

pytestmark = pytest.mark.story("US-SES-020")

_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")


@pytest.fixture
def repo(tmp_path):
    """Create an isolated EpicRepository backed by tmp_path."""
    db_path = tmp_path / "epics.db"
    r = EpicRepository(db_path=db_path, auto_bootstrap=False)
    yield r
    r.close()


def _make_epic_data(name: str) -> dict:
    """Helper to build minimal epic data for create_epic."""
    return {
        "plan_folder_name": name,
        "plan_folder": f"/tmp/epics/{name}",
        "name": name,
        "status": "pending",
        "objective": f"Objective for {name}",
    }


@pytest.mark.story("US-SES-020")
class TestConcurrentWritesSerialized:
    """FL_002-1: Concurrent create_epic calls are serialized by FileLock.

    Uses subprocesses instead of threads because fcntl.flock is per-open-file-
    description — threads in the same process each opening the file get
    independent locks.  Cross-process serialization is the production use case.
    """

    def test_concurrent_writes_are_serialized(self, tmp_path):
        """Two subprocesses calling create_epic concurrently both succeed."""
        db_path = tmp_path / "epics.db"

        script = textwrap.dedent(f"""\
            import sys, json
            from pathlib import Path
            sys.path.insert(0, "{_SRC_DIR}")
            from agenticguidance.services.epic_repository import EpicRepository

            epic_name = sys.argv[1]
            db_path = Path("{db_path}")
            r = EpicRepository(db_path=db_path, auto_bootstrap=False)
            data = {{
                "plan_folder_name": epic_name,
                "plan_folder": f"/tmp/epics/{{epic_name}}",
                "name": epic_name,
                "status": "pending",
                "objective": f"Objective for {{epic_name}}",
            }}
            result = r.create_epic(data)
            r.close()
            # Exit 0 on success, 1 on failure
            sys.exit(0 if result.success else 1)
        """)
        script_path = tmp_path / "create_epic.py"
        script_path.write_text(script)

        p1 = subprocess.Popen(
            [sys.executable, str(script_path), "plan_alpha"],
            stderr=subprocess.PIPE,
        )
        p2 = subprocess.Popen(
            [sys.executable, str(script_path), "plan_beta"],
            stderr=subprocess.PIPE,
        )

        p1.wait(timeout=15)
        p2.wait(timeout=15)

        assert p1.returncode == 0, f"plan_alpha failed: {p1.stderr.read().decode()}"
        assert p2.returncode == 0, f"plan_beta failed: {p2.stderr.read().decode()}"

        # Verify both epics exist in the DB
        verify = EpicRepository(db_path=db_path, auto_bootstrap=False)
        assert verify.get_epic("plan_alpha") is not None
        assert verify.get_epic("plan_beta") is not None
        verify.close()


@pytest.mark.story("US-SES-020")
class TestLockFileCreatedDuringWrite:
    """FL_002-2: .lock file appears while a write operation holds the lock."""

    def test_lock_file_created_during_write(self, tmp_path):
        """The .lock file must exist while inside the locked section."""
        db_path = tmp_path / "epics.db"
        lock_path = Path(str(db_path) + ".lock")
        lock_seen = False

        original_insert = None

        def spy_insert(doc):
            """Intercept TinyDB insert to check lock file mid-write."""
            nonlocal lock_seen
            if lock_path.exists():
                lock_seen = True
            return original_insert(doc)

        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        original_insert = repo._epics.insert
        repo._epics.insert = spy_insert

        result = repo.create_epic(_make_epic_data("plan_lock_test"))
        repo.close()

        assert result.success is True
        assert lock_seen, "Lock file was not observed during write"
        # With fcntl.flock, the lock FILE persists but the flock is released.
        # Verify the lock is released by acquiring it.
        from agenticguidance.services.state import FileLock

        lock = FileLock(db_path, timeout=1.0)
        assert lock.acquire() is True, "Lock should be acquirable after write completes"
        lock.release()


@pytest.mark.story("US-SES-020")
class TestStaleLockRecovery:
    """FL_002-3: EpicRepository recovers from stale lock files."""

    def test_stale_lock_file_does_not_block(self, tmp_path):
        """A stale lock file (no flock held) does not block acquisition.

        With fcntl.flock, a lock file on disk without a held flock is
        just a regular file — it does not block new acquisitions.
        """
        db_path = tmp_path / "epics.db"
        lock_path = Path(str(db_path) + ".lock")

        # Create a stale lock file — no flock is held on it
        lock_path.write_text(json.dumps({"pid": 4194304, "timestamp": 0}))

        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        result = repo.create_epic(_make_epic_data("plan_after_stale"))
        repo.close()

        assert result.success is True
        # Lock file now contains current process's PID
        data = json.loads(lock_path.read_text())
        assert data["pid"] == os.getpid()


@pytest.mark.story("US-SES-020")
class TestReadOperationsDontLock:
    """FL_002-4: Read operations (get_epic, list_epics) work without lock."""

    def test_get_epic_works_without_lock(self, repo):
        """get_epic succeeds even when lock file exists on disk."""
        repo.create_epic(_make_epic_data("plan_readable"))

        # Lock file exists on disk (flock persists file after release)
        # but no flock is held — reads should not be affected
        epic = repo.get_epic("plan_readable")
        assert epic is not None
        assert epic.plan_folder_name == "plan_readable"

    def test_list_epics_works_without_lock(self, repo):
        """list_epics succeeds regardless of lock file presence."""
        repo.create_epic(_make_epic_data("plan_listable"))

        epics = repo.list_epics()
        assert len(epics) >= 1
        names = [p.plan_folder_name for p in epics]
        assert "plan_listable" in names

    def test_get_tickets_works_without_lock(self, repo):
        """get_tickets succeeds regardless of lock file presence."""
        repo.create_epic(_make_epic_data("plan_with_tasks"))
        repo.add_ticket(
            "plan_with_tasks",
            "Phase 1",
            {"id": "T1", "name": "task", "status": "pending"},
        )

        tickets = repo.get_tickets("plan_with_tasks")
        assert len(tickets) == 1
        assert tickets[0].id == "T1"
