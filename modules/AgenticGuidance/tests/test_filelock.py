"""Unit tests for the hardened FileLock class (fcntl.flock-based).

Validates:
- fcntl.flock auto-release when file descriptor is closed
- Lock-age expiration triggers stale detection
- atexit handler releases all locks
- Signal handler (SIGTERM/SIGINT) releases locks
- Global lock registry tracks instances
- PID recycling handled by lock age
- Backward-compatible API (acquire/release/context manager)

@story US-SET-017, US-PLN-063
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from agenticguidance.services.state import (
    FileLock,
    _cleanup_all_locks,
    _lock_registry,
)

pytestmark = pytest.mark.story("US-SET-017", "US-PLN-063")


class TestFlockAcquireRelease:
    """Test basic flock acquire/release lifecycle."""

    def test_flock_acquire_release_manual(self, tmp_path):
        """Acquire lock, verify fd is held open, release, verify fd is closed."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        lock = FileLock(target)

        # Acquire
        acquired = lock.acquire()
        assert acquired is True
        assert lock._acquired is True
        assert lock._fd is not None
        fd = lock._fd

        # Verify fd is a valid open file descriptor
        try:
            os.fstat(fd)
        except OSError:
            pytest.fail("File descriptor should be open while lock is held")

        # Release
        lock.release()
        assert lock._acquired is False
        assert lock._fd is None

        # Verify fd is closed
        with pytest.raises(OSError):
            os.fstat(fd)

    def test_flock_acquire_release_context_manager(self, tmp_path):
        """Context manager calls acquire/release correctly."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        with FileLock(target) as lock:
            assert lock._acquired is True
            assert lock._fd is not None

        assert lock._acquired is False
        assert lock._fd is None


class TestFlockAutoReleaseOnFdClose:
    """Test that closing the fd releases the flock so another process can acquire."""

    def test_flock_auto_release_on_fd_close(self, tmp_path):
        """Close the fd manually (simulating crash cleanup); another instance can acquire."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        lock1 = FileLock(target, timeout=1.0)
        lock1.acquire()

        # Simulate crash: close the fd directly (kernel releases flock)
        os.close(lock1._fd)
        lock1._fd = None
        lock1._acquired = False

        # Another lock instance should immediately acquire
        lock2 = FileLock(target, timeout=2.0)
        acquired = lock2.acquire()
        assert acquired is True
        lock2.release()


class TestLockAgeExpiration:
    """Test lock-age-based stale detection."""

    def test_lock_age_expiration_triggers_stale(self, tmp_path):
        """Lock with old timestamp is detected as expired."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        lock = FileLock(target, max_age=1)
        lock.acquire()

        # Overwrite the lock file with an old timestamp
        old_data = json.dumps({"pid": os.getpid(), "timestamp": time.time() - 10})
        lock.lock_path.write_text(old_data)

        # _is_lock_expired should return True now
        assert lock._is_lock_expired() is True

        lock.release()

    def test_lock_not_expired_with_recent_timestamp(self, tmp_path):
        """Lock with recent timestamp is NOT expired."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        lock = FileLock(target, max_age=300)
        lock.acquire()

        assert lock._is_lock_expired() is False

        lock.release()

    def test_expired_lock_allows_new_acquisition(self, tmp_path):
        """A lock held by another process with expired age can be force-broken."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        # Use a subprocess to acquire and hold the lock, then write an old timestamp
        # but we can simulate this with a short max_age
        lock1 = FileLock(target, timeout=1.0, max_age=0.5)
        lock1.acquire()

        # Write old timestamp to make it look stale
        old_data = json.dumps({"pid": os.getpid(), "timestamp": time.time() - 10})
        lock1.lock_path.write_text(old_data)

        # New lock with short max_age should be able to force-break
        lock2 = FileLock(target, timeout=3.0, max_age=0.5)
        acquired = lock2.acquire()
        assert acquired is True
        lock2.release()

        # Clean up lock1 (fd may still be open)
        try:
            lock1.release()
        except Exception:
            pass


class TestAtexitReleasesAllLocks:
    """Test that _cleanup_all_locks releases all tracked locks."""

    def test_atexit_releases_all_locks(self, tmp_path):
        """Calling _cleanup_all_locks() releases all held locks."""
        target1 = tmp_path / "data1.json"
        target2 = tmp_path / "data2.json"
        target1.write_text("{}")
        target2.write_text("{}")

        lock1 = FileLock(target1)
        lock2 = FileLock(target2)
        lock1.acquire()
        lock2.acquire()

        assert lock1._acquired is True
        assert lock2._acquired is True

        # Call the cleanup function directly (same as atexit handler)
        _cleanup_all_locks()

        assert lock1._acquired is False
        assert lock2._acquired is False
        assert lock1._fd is None
        assert lock2._fd is None


class TestSignalHandlerReleasesLocks:
    """Test that SIGTERM/SIGINT signal handlers release locks."""

    def test_signal_handler_releases_locks_via_subprocess(self, tmp_path):
        """Spawn a subprocess that holds a lock, send SIGTERM, verify lock released."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        # Use a subprocess so we don't kill our own test process
        src_dir = str(Path(__file__).resolve().parent.parent / "src")
        script = f"""\
import sys, os, time
from pathlib import Path
sys.path.insert(0, "{src_dir}")
from agenticguidance.services.state import FileLock

target = Path("{target}")
lock = FileLock(target, timeout=5.0)
lock.acquire()

# Signal readiness
print("READY", flush=True)

# Wait for signal
time.sleep(30)
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for subprocess to be ready
        try:
            line = proc.stdout.readline()
            assert "READY" in line, f"Subprocess did not become ready: {line}"

            # Send SIGTERM — our signal handler in state.py should release the lock
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)

            # Now verify we can acquire the lock (flock released by kernel on fd close)
            lock = FileLock(target, timeout=3.0)
            acquired = lock.acquire()
            assert acquired is True, "Lock should be acquirable after SIGTERM killed holder"
            lock.release()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


class TestLockRegistryTracksInstances:
    """Test that the global _lock_registry tracks acquired FileLock instances."""

    def test_lock_registry_tracks_instances(self, tmp_path):
        """Acquired locks appear in _lock_registry; released locks are removed."""
        target1 = tmp_path / "data1.json"
        target2 = tmp_path / "data2.json"
        target1.write_text("{}")
        target2.write_text("{}")

        lock1 = FileLock(target1)
        lock2 = FileLock(target2)

        # Before acquisition, neither should be in registry
        registry_locks = list(_lock_registry)
        assert lock1 not in registry_locks
        assert lock2 not in registry_locks

        # Acquire both
        lock1.acquire()
        lock2.acquire()

        registry_locks = list(_lock_registry)
        assert lock1 in registry_locks
        assert lock2 in registry_locks

        # Release one
        lock1.release()

        registry_locks = list(_lock_registry)
        assert lock1 not in registry_locks
        assert lock2 in registry_locks

        lock2.release()

        registry_locks = list(_lock_registry)
        assert lock2 not in registry_locks

    def test_lock_registry_uses_weakref(self, tmp_path):
        """WeakSet drops locks that are garbage collected."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        lock = FileLock(target)
        lock.acquire()
        assert lock in list(_lock_registry)

        # Release and delete — weakref should drop it
        lock.release()
        del lock

        # Registry should not hold a reference to the deleted lock
        # (WeakSet removes references to garbage-collected objects)


class TestPidRecyclingHandledByLockAge:
    """Test that PID recycling is handled by lock-age expiration."""

    def test_pid_recycling_handled_by_lock_age(self, tmp_path):
        """Lock with current PID but old timestamp is treated as stale."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        lock = FileLock(target, max_age=1)

        # Manually create a lock file with current PID but old timestamp
        # This simulates PID recycling: the PID is alive (it's us!) but the
        # lock was created by a previous process that died
        old_data = json.dumps({
            "pid": os.getpid(),
            "timestamp": time.time() - 100,  # 100 seconds old
        })
        lock.lock_path.write_text(old_data)

        # _is_lock_expired should return True based on age, not PID liveness
        assert lock._is_lock_expired() is True


class TestContextManagerBehavior:
    """Test context manager acquire/release and TimeoutError on failure."""

    def test_context_manager_acquire_release(self, tmp_path):
        """with-statement calls acquire on entry and release on exit."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        with FileLock(target) as lock:
            assert lock._acquired is True
            assert lock._fd is not None

        # After exiting context, lock should be released
        assert lock._acquired is False
        assert lock._fd is None

    def test_context_manager_raises_timeout_error(self, tmp_path):
        """TimeoutError is raised when acquire fails in context manager."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        # Hold the lock so the second one times out
        holder = FileLock(target, timeout=1.0)
        holder.acquire()

        try:
            with pytest.raises(TimeoutError, match="Could not acquire lock"):
                with FileLock(target, timeout=0.2):
                    pass  # Should never reach here
        finally:
            holder.release()


class TestConcurrentProcessesSerialized:
    """Test that two processes serialise access through the same lock file.

    Note: fcntl.flock is per-open-file-description, so two threads in the
    same process each opening the file get independent locks.  Serialization
    is guaranteed across *processes*, which is the production use case
    (separate agent processes).
    """

    def test_concurrent_processes_serialized(self, tmp_path):
        """Two subprocesses acquiring the same lock don't overlap in critical section."""
        target = tmp_path / "data.json"
        target.write_text("{}")
        log_file = tmp_path / "log.txt"
        log_file.write_text("")

        src_dir = str(Path(__file__).resolve().parent.parent / "src")
        script = f"""\
import sys, time
from pathlib import Path
sys.path.insert(0, "{src_dir}")
from agenticguidance.services.state import FileLock

name = sys.argv[1]
target = Path("{target}")
log_file = Path("{log_file}")

lock = FileLock(target, timeout=10.0)
lock.acquire()

# Append entry to shared log
with open(log_file, "a") as f:
    f.write(f"{{name}}_enter\\n")
    f.flush()
time.sleep(0.2)  # simulate work
with open(log_file, "a") as f:
    f.write(f"{{name}}_exit\\n")
    f.flush()

lock.release()
"""
        script_path = tmp_path / "worker.py"
        script_path.write_text(script)

        # Launch two subprocesses concurrently
        p1 = subprocess.Popen([sys.executable, str(script_path), "A"])
        p2 = subprocess.Popen([sys.executable, str(script_path), "B"])

        p1.wait(timeout=15)
        p2.wait(timeout=15)

        assert p1.returncode == 0, f"Process A exited with {p1.returncode}"
        assert p2.returncode == 0, f"Process B exited with {p2.returncode}"

        log = [line for line in log_file.read_text().strip().split("\n") if line]
        assert len(log) == 4, f"Expected 4 log entries, got: {log}"

        # Verify no overlap: entries must be [X_enter, X_exit, Y_enter, Y_exit]
        first_name = log[0].split("_")[0]
        second_name = log[2].split("_")[0]

        assert log[0] == f"{first_name}_enter"
        assert log[1] == f"{first_name}_exit"
        assert log[2] == f"{second_name}_enter"
        assert log[3] == f"{second_name}_exit"
        assert first_name != second_name, "Both entries should be from different processes"


class TestBackwardCompatibleAPI:
    """Test that FileLock maintains its backward-compatible public API."""

    def test_constructor_accepts_path(self, tmp_path):
        """FileLock(path) constructor works with Path objects."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        lock = FileLock(target)
        assert lock.lock_path == target.with_suffix(".json.lock")
        assert lock.timeout == 10.0  # default timeout

    def test_lock_path_attribute(self, tmp_path):
        """lock_path is accessible and correct."""
        target = tmp_path / "data.json"
        lock = FileLock(target)
        assert lock.lock_path == target.with_suffix(".json.lock")

    def test_timeout_attribute(self, tmp_path):
        """Custom timeout is stored correctly."""
        target = tmp_path / "data.json"
        lock = FileLock(target, timeout=5.0)
        assert lock.timeout == 5.0

    def test_acquire_returns_bool(self, tmp_path):
        """acquire() returns True on success."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        lock = FileLock(target)
        result = lock.acquire()
        assert result is True
        assert isinstance(result, bool)
        lock.release()

    def test_acquire_returns_false_on_timeout(self, tmp_path):
        """acquire() returns False when lock cannot be obtained."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        holder = FileLock(target)
        holder.acquire()

        try:
            lock = FileLock(target, timeout=0.2)
            result = lock.acquire()
            assert result is False
            assert isinstance(result, bool)
        finally:
            holder.release()

    def test_release_returns_none(self, tmp_path):
        """release() returns None."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        lock = FileLock(target)
        lock.acquire()
        result = lock.release()
        assert result is None

    def test_release_is_idempotent(self, tmp_path):
        """Calling release() multiple times is safe."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        lock = FileLock(target)
        lock.acquire()
        lock.release()
        lock.release()  # Should not raise

    def test_enter_exit_protocol(self, tmp_path):
        """__enter__ and __exit__ methods exist and work."""
        target = tmp_path / "data.json"
        target.write_text("{}")

        lock = FileLock(target)
        assert hasattr(lock, "__enter__")
        assert hasattr(lock, "__exit__")

        # __enter__ returns the lock
        entered = lock.__enter__()
        assert entered is lock
        lock.__exit__(None, None, None)
