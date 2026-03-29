"""Integration tests for FileLock crash recovery via SIGKILL.

Validates the core objective of the flock migration: when a process holding
a lock is killed with SIGKILL (or OOM-killed), the kernel automatically
releases the flock and a new process can acquire the same lock without
manual cleanup.

@story US-PLN-067, US-SES-008
"""

import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from agenticguidance.services.state import FileLock

pytestmark = pytest.mark.story("US-PLN-067", "US-SES-008")

# Path to AgenticGuidance src directory for subprocess imports
_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")


def _write_helper_script(tmp_path: Path, script_body: str) -> Path:
    """Write a helper Python script to tmp_path and return its path."""
    script_path = tmp_path / "helper.py"
    script_path.write_text(script_body)
    return script_path


class TestSigkillReleasesFileLock:
    """Test that SIGKILL on a process holding a FileLock releases the flock."""

    def test_sigkill_releases_filelock(self, tmp_path):
        """Parent acquires lock within 1s after SIGKILLing child."""
        target = tmp_path / "data.json"
        target.write_text("{}")
        ready_sentinel = tmp_path / "ready"

        script = textwrap.dedent(f"""\
            import sys, time
            from pathlib import Path
            sys.path.insert(0, "{_SRC_DIR}")
            from agenticguidance.services.state import FileLock

            target = Path("{target}")
            lock = FileLock(target, timeout=5.0)
            lock.acquire()

            # Signal that lock is held
            Path("{ready_sentinel}").write_text("ready")

            # Sleep forever (simulating an agent doing work)
            time.sleep(3600)
        """)

        script_path = _write_helper_script(tmp_path, script)
        proc = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            # Wait for child to acquire lock
            deadline = time.time() + 30
            while not ready_sentinel.exists():
                assert time.time() < deadline, "Child did not acquire lock within 30s"
                time.sleep(0.05)

            # SIGKILL the child
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)

            # Parent should be able to acquire the lock immediately
            # (fcntl.flock auto-releases when fd is closed by kernel on SIGKILL)
            start = time.time()
            lock = FileLock(target, timeout=3.0)
            acquired = lock.acquire()
            elapsed = time.time() - start

            assert acquired is True, "Parent failed to acquire lock after SIGKILLing child"
            assert elapsed < 1.0, (
                f"Lock acquisition took {elapsed:.2f}s — expected < 1s "
                f"(kernel should release flock immediately)"
            )
            lock.release()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


class TestSigkillReleasesEpicRepositoryLock:
    """Test SIGKILL crash recovery with EpicRepository end-to-end."""

    def test_sigkill_releases_epicrepository_lock(self, tmp_path):
        """Parent creates epic after SIGKILLing child that held the DB lock."""
        db_path = tmp_path / "epics.db"
        ready_sentinel = tmp_path / "ready"

        script = textwrap.dedent(f"""\
            import sys, time
            from pathlib import Path
            sys.path.insert(0, "{_SRC_DIR}")
            from agenticguidance.services.epic_repository import EpicRepository

            db_path = Path("{db_path}")
            repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
            repo.create_epic({{
                "plan_folder_name": "child_epic",
                "plan_folder": "/tmp/child_epic",
                "name": "child_epic",
                "status": "pending",
                "objective": "Test epic from child process",
            }})

            # Signal that DB write completed (lock was held during create_epic)
            Path("{ready_sentinel}").write_text("ready")

            # Now re-acquire the lock and hold it to simulate a long operation
            from agenticguidance.services.state import FileLock
            lock = FileLock(db_path, timeout=5.0)
            lock.acquire()
            Path("{ready_sentinel}").write_text("locked")

            time.sleep(3600)
        """)

        script_path = _write_helper_script(tmp_path, script)
        proc = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            # Wait for child to hold the lock
            deadline = time.time() + 15
            while True:
                if ready_sentinel.exists() and ready_sentinel.read_text() == "locked":
                    break
                assert time.time() < deadline, "Child did not acquire lock within 15s"
                time.sleep(0.05)

            # SIGKILL the child
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)

            # Parent should be able to create an epic without timeout
            from agenticguidance.services.epic_repository import EpicRepository

            repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
            result = repo.create_epic({
                "plan_folder_name": "parent_epic",
                "plan_folder": "/tmp/parent_epic",
                "name": "parent_epic",
                "status": "pending",
                "objective": "Test epic from parent process",
            })
            repo.close()

            assert result.success is True, (
                f"Parent failed to create epic after SIGKILLing child: {result}"
            )

            # Verify both epics exist
            verify = EpicRepository(db_path=db_path, auto_bootstrap=False)
            assert verify.get_epic("child_epic") is not None
            assert verify.get_epic("parent_epic") is not None
            verify.close()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


class TestOomSimulationViaSigkill:
    """OOM killer sends SIGKILL — validate that the same mechanism works.

    This test is functionally identical to test_sigkill_releases_filelock
    but is named to document that SIGKILL == OOM kill behavior for lock
    release purposes.
    """

    def test_oom_kill_releases_lock(self, tmp_path):
        """Simulated OOM kill (SIGKILL) releases flock — same kernel mechanism."""
        target = tmp_path / "data.json"
        target.write_text("{}")
        ready_sentinel = tmp_path / "ready"

        script = textwrap.dedent(f"""\
            import sys, time
            from pathlib import Path
            sys.path.insert(0, "{_SRC_DIR}")
            from agenticguidance.services.state import FileLock

            target = Path("{target}")
            lock = FileLock(target, timeout=5.0)
            lock.acquire()

            Path("{ready_sentinel}").write_text("ready")
            time.sleep(3600)
        """)

        script_path = _write_helper_script(tmp_path, script)
        proc = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            deadline = time.time() + 30
            while not ready_sentinel.exists():
                assert time.time() < deadline, "Child did not acquire lock within 30s"
                time.sleep(0.05)

            # Simulate OOM kill (kernel sends SIGKILL to the process)
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)

            # Verify lock is released by kernel
            lock = FileLock(target, timeout=3.0)
            acquired = lock.acquire()
            assert acquired is True, (
                "Lock not released after simulated OOM kill (SIGKILL). "
                "Kernel should auto-release flock when process dies."
            )
            lock.release()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
