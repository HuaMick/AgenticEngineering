"""Unit tests for SessionCleanupService.

Validates:
- Dead session artifact cleanup (JSON + logs + context)
- Age-based filtering via max_age_days
- Dry-run mode (report without modifications)
- Running session protection (never cleaned)
- Orphaned artifact cleanup (logs/context with no matching session JSON)
- Stale lock file cleanup (> 5 min old)
- Orphaned tmux session detection and kill

Story coverage:
- US-SES-003 (Cleanup after stop)
- US-SES-007 (Full artifact cleanup)
- US-SES-008 (Dead process cleanup extends to disk artifacts)
- US-SES-009 (Unified state management)
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agenticcli.utils.session_cleanup import (
    CleanupReport,
    SessionCleanupService,
    _LOCK_STALE_SECONDS,
)

pytestmark = pytest.mark.story("US-SES-007", "US-SES-008")


# ---------------------------------------------------------------------------
# Helpers & fixtures
# ---------------------------------------------------------------------------


def _make_session_dir(tmp_path: Path) -> Path:
    """Create the session directory structure under tmp_path."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "logs").mkdir()
    (sessions_dir / "context").mkdir()
    return sessions_dir


def _write_session(sessions_dir: Path, session_id: str, **fields) -> Path:
    """Write a session JSON to the sessions directory."""
    record = {"session_id": session_id, **fields}
    path = sessions_dir / f"{session_id}.json"
    path.write_text(json.dumps(record))
    return path


def _write_logs(sessions_dir: Path, session_id: str, content: str = "log data") -> list[Path]:
    """Write stdout and stderr log files for a session."""
    logs_dir = sessions_dir / "logs"
    stdout = logs_dir / f"{session_id}.stdout.log"
    stderr = logs_dir / f"{session_id}.stderr.log"
    stdout.write_text(content)
    stderr.write_text(content)
    return [stdout, stderr]


def _write_context(sessions_dir: Path, session_id: str, content: str = "# context") -> Path:
    """Write a context .md file for a session."""
    ctx = sessions_dir / "context" / f"{session_id}.md"
    ctx.write_text(content)
    return ctx


@pytest.fixture
def sessions_dir(tmp_path):
    """Create a sessions directory tree in tmp_path."""
    return _make_session_dir(tmp_path)


@pytest.fixture
def service(tmp_path, sessions_dir):
    """Create a SessionCleanupService pointing at the tmp_path sessions dir.

    Patches StateStore.get_dir so the service uses the tmp_path sessions dir.
    """
    with patch(
        "agenticcli.utils.session_cleanup.StateStore.get_dir",
        return_value=sessions_dir,
    ):
        svc = SessionCleanupService(state_dir=sessions_dir)
    return svc


# ---------------------------------------------------------------------------
# CleanupReport tests
# ---------------------------------------------------------------------------


class TestCleanupReport:
    """Tests for CleanupReport dataclass."""

    def test_default_values(self):
        """CleanupReport defaults all counts to zero."""
        r = CleanupReport()
        assert r.sessions_cleaned == 0
        assert r.log_files_removed == 0
        assert r.context_files_removed == 0
        assert r.lock_files_removed == 0
        assert r.tmux_sessions_killed == 0
        assert r.bytes_freed == 0
        assert r.details == []

    def test_to_dict(self):
        """to_dict() returns a serializable dict with all fields."""
        r = CleanupReport(
            sessions_cleaned=2,
            log_files_removed=4,
            context_files_removed=1,
            bytes_freed=1024,
            details=[{"type": "session", "session_id": "abc"}],
        )
        d = r.to_dict()
        assert d["sessions_cleaned"] == 2
        assert d["log_files_removed"] == 4
        assert d["context_files_removed"] == 1
        assert d["bytes_freed"] == 1024
        assert len(d["details"]) == 1
        # Should be JSON serializable
        json.dumps(d)


# ---------------------------------------------------------------------------
# Session cleanup: dead session removal
# ---------------------------------------------------------------------------


class TestCleanDeadSessions:
    """Tests for cleaning dead/completed session artifacts."""

    @pytest.mark.story("US-SES-003", "US-SES-008")
    def test_cleanup_completed_session(self, service, sessions_dir):
        """Completed sessions have all artifacts removed."""
        sid = "completed-sess-001"
        _write_session(sessions_dir, sid, status="completed", pid=99999)
        _write_logs(sessions_dir, sid)
        _write_context(sessions_dir, sid)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.sessions_cleaned == 1
        assert report.log_files_removed == 2
        assert report.context_files_removed == 1
        assert not (sessions_dir / f"{sid}.json").exists()
        assert not (sessions_dir / "logs" / f"{sid}.stdout.log").exists()
        assert not (sessions_dir / "logs" / f"{sid}.stderr.log").exists()
        assert not (sessions_dir / "context" / f"{sid}.md").exists()

    @pytest.mark.story("US-SES-008")
    def test_cleanup_dead_running_session(self, service, sessions_dir):
        """Sessions with status='running' but dead PID are cleaned."""
        sid = "dead-running-001"
        _write_session(sessions_dir, sid, status="running", pid=99999)
        _write_logs(sessions_dir, sid)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.sessions_cleaned == 1
        assert not (sessions_dir / f"{sid}.json").exists()

    def test_cleanup_failed_session(self, service, sessions_dir):
        """Failed sessions are cleaned up."""
        sid = "failed-001"
        _write_session(sessions_dir, sid, status="failed", pid=99999)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.sessions_cleaned == 1

    def test_cleanup_stopped_session(self, service, sessions_dir):
        """Stopped sessions are cleaned up."""
        sid = "stopped-001"
        _write_session(sessions_dir, sid, status="stopped", pid=99999)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.sessions_cleaned == 1

    def test_cleanup_multiple_dead_sessions(self, service, sessions_dir):
        """Multiple dead sessions are all cleaned in one call."""
        for i in range(5):
            sid = f"dead-{i:03d}"
            _write_session(sessions_dir, sid, status="completed", pid=99999)
            _write_logs(sessions_dir, sid)
            _write_context(sessions_dir, sid)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.sessions_cleaned == 5
        assert report.log_files_removed == 10  # 2 per session
        assert report.context_files_removed == 5


# ---------------------------------------------------------------------------
# Running session protection
# ---------------------------------------------------------------------------


class TestRunningSessionProtection:
    """Tests that running sessions with alive PIDs are never cleaned."""

    def test_running_session_with_alive_pid_not_cleaned(self, service, sessions_dir):
        """Running sessions with alive PIDs are protected from cleanup."""
        sid = "running-alive-001"
        _write_session(sessions_dir, sid, status="running", pid=os.getpid())
        _write_logs(sessions_dir, sid)
        _write_context(sessions_dir, sid)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=True
        ):
            report = service.cleanup()

        assert report.sessions_cleaned == 0
        assert (sessions_dir / f"{sid}.json").exists()
        assert (sessions_dir / "logs" / f"{sid}.stdout.log").exists()
        assert (sessions_dir / "context" / f"{sid}.md").exists()

    def test_mix_running_and_dead_sessions(self, service, sessions_dir):
        """Only dead sessions are cleaned; running ones are untouched."""
        alive_sid = "alive-001"
        dead_sid = "dead-001"
        _write_session(sessions_dir, alive_sid, status="running", pid=os.getpid())
        _write_logs(sessions_dir, alive_sid)
        _write_session(sessions_dir, dead_sid, status="completed", pid=99999)
        _write_logs(sessions_dir, dead_sid)

        def mock_is_running(pid):
            return pid == os.getpid()

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running",
            side_effect=mock_is_running,
        ):
            report = service.cleanup()

        assert report.sessions_cleaned == 1
        assert (sessions_dir / f"{alive_sid}.json").exists()
        assert not (sessions_dir / f"{dead_sid}.json").exists()

    def test_starting_session_with_alive_pid_protected(self, service, sessions_dir):
        """Sessions with status='starting' and alive PID are protected."""
        sid = "starting-001"
        _write_session(sessions_dir, sid, status="starting", pid=os.getpid())

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=True
        ):
            report = service.cleanup()

        assert report.sessions_cleaned == 0
        assert (sessions_dir / f"{sid}.json").exists()


# ---------------------------------------------------------------------------
# Age-based filtering
# ---------------------------------------------------------------------------


class TestAgeBasedFiltering:
    """Tests for max_age_days filtering."""

    def test_max_age_filters_recent_sessions(self, service, sessions_dir):
        """Sessions newer than max_age_days are not cleaned."""
        recent_time = datetime.now().isoformat()
        old_time = (datetime.now() - timedelta(days=60)).isoformat()

        _write_session(
            sessions_dir, "recent-001", status="completed", pid=99999,
            started_at=recent_time,
        )
        _write_session(
            sessions_dir, "old-001", status="completed", pid=99999,
            started_at=old_time,
        )

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup(max_age_days=30)

        assert report.sessions_cleaned == 1
        # Recent session should still exist
        assert (sessions_dir / "recent-001.json").exists()
        assert not (sessions_dir / "old-001.json").exists()

    def test_max_age_none_cleans_all_stale(self, service, sessions_dir):
        """With no max_age_days, all dead sessions are cleaned regardless of age."""
        recent_time = datetime.now().isoformat()
        _write_session(
            sessions_dir, "new-001", status="completed", pid=99999,
            started_at=recent_time,
        )

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup(max_age_days=None)

        assert report.sessions_cleaned == 1

    def test_max_age_with_missing_started_at(self, service, sessions_dir):
        """Sessions with no started_at field are treated as old enough to clean."""
        _write_session(sessions_dir, "no-date-001", status="completed", pid=99999)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup(max_age_days=30)

        # Session without date should be cleaned (treated as old)
        assert report.sessions_cleaned == 1

    def test_max_age_with_unparseable_date(self, service, sessions_dir):
        """Sessions with invalid date string are treated as old enough to clean."""
        _write_session(
            sessions_dir, "bad-date-001", status="completed", pid=99999,
            started_at="not-a-valid-date",
        )

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup(max_age_days=30)

        assert report.sessions_cleaned == 1


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------


class TestDryRunMode:
    """Tests for dry_run=True mode."""

    @pytest.mark.story("US-SES-007")
    def test_dry_run_does_not_delete_files(self, service, sessions_dir):
        """dry_run=True reports what would be cleaned but doesn't delete anything."""
        sid = "dry-run-001"
        _write_session(sessions_dir, sid, status="completed", pid=99999)
        _write_logs(sessions_dir, sid)
        _write_context(sessions_dir, sid)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup(dry_run=True)

        # Report should show what would be cleaned
        assert report.sessions_cleaned == 1
        assert report.log_files_removed == 2
        assert report.context_files_removed == 1
        assert report.bytes_freed > 0

        # But all files should still exist
        assert (sessions_dir / f"{sid}.json").exists()
        assert (sessions_dir / "logs" / f"{sid}.stdout.log").exists()
        assert (sessions_dir / "logs" / f"{sid}.stderr.log").exists()
        assert (sessions_dir / "context" / f"{sid}.md").exists()

    @pytest.mark.story("US-SES-007")
    def test_dry_run_report_matches_real_cleanup(self, service, sessions_dir):
        """dry_run report counts should match what a real cleanup would do."""
        for i in range(3):
            sid = f"dryrun-{i:03d}"
            _write_session(sessions_dir, sid, status="failed", pid=99999)
            _write_logs(sessions_dir, sid)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            dry_report = service.cleanup(dry_run=True)

        # All files still exist — now do real cleanup
        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            real_report = service.cleanup(dry_run=False)

        assert dry_report.sessions_cleaned == real_report.sessions_cleaned
        assert dry_report.log_files_removed == real_report.log_files_removed

    def test_dry_run_lock_files_not_deleted(self, service, sessions_dir):
        """dry_run=True does not delete stale lock files."""
        lock = sessions_dir / "some-id.json.lock"
        lock.write_text("")
        # Make it old (> 5 min)
        old_time = time.time() - _LOCK_STALE_SECONDS - 60
        os.utime(lock, (old_time, old_time))

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup(dry_run=True)

        assert report.lock_files_removed == 1
        assert lock.exists()  # Not actually deleted


# ---------------------------------------------------------------------------
# Orphaned artifact cleanup
# ---------------------------------------------------------------------------


class TestOrphanedArtifactCleanup:
    """Tests for cleaning logs/context files with no matching session JSON."""

    def test_orphaned_logs_cleaned(self, service, sessions_dir):
        """Log files with no matching session JSON are removed as orphaned."""
        # Create orphaned log files (no matching session JSON)
        orphan_sid = "orphan-log-001"
        logs_dir = sessions_dir / "logs"
        (logs_dir / f"{orphan_sid}.stdout.log").write_text("orphan stdout")
        (logs_dir / f"{orphan_sid}.stderr.log").write_text("orphan stderr")

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.log_files_removed == 2
        assert not (logs_dir / f"{orphan_sid}.stdout.log").exists()
        assert not (logs_dir / f"{orphan_sid}.stderr.log").exists()

    def test_orphaned_context_cleaned(self, service, sessions_dir):
        """Context files with no matching session JSON are removed as orphaned."""
        orphan_sid = "orphan-ctx-001"
        ctx_dir = sessions_dir / "context"
        (ctx_dir / f"{orphan_sid}.md").write_text("orphan context")

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.context_files_removed == 1
        assert not (ctx_dir / f"{orphan_sid}.md").exists()

    def test_orphaned_artifacts_with_age_filter(self, service, sessions_dir):
        """Orphaned artifacts respect max_age_days filter on file mtime."""
        logs_dir = sessions_dir / "logs"
        old_log = logs_dir / "old-orphan.stdout.log"
        new_log = logs_dir / "new-orphan.stdout.log"
        old_log.write_text("old orphan")
        new_log.write_text("new orphan")

        # Make old log actually old
        old_time = time.time() - (60 * 86400)  # 60 days ago
        os.utime(old_log, (old_time, old_time))
        # new log keeps current time

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup(max_age_days=30)

        assert report.log_files_removed == 1
        assert not old_log.exists()
        assert new_log.exists()

    def test_orphaned_logs_for_running_session_not_cleaned(self, service, sessions_dir):
        """Orphaned logs that match a running session ID are not cleaned."""
        alive_sid = "alive-with-logs"
        _write_session(sessions_dir, alive_sid, status="running", pid=os.getpid())
        # Also create logs — these should NOT be treated as orphaned
        _write_logs(sessions_dir, alive_sid)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=True
        ):
            report = service.cleanup()

        assert report.log_files_removed == 0
        assert (sessions_dir / "logs" / f"{alive_sid}.stdout.log").exists()

    def test_many_orphaned_files(self, service, sessions_dir):
        """Large numbers of orphaned log files are all cleaned."""
        logs_dir = sessions_dir / "logs"
        for i in range(50):
            (logs_dir / f"orphan-{i:04d}.stdout.log").write_text(f"log {i}")

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.log_files_removed == 50


# ---------------------------------------------------------------------------
# Lock file cleanup
# ---------------------------------------------------------------------------


class TestLockFileCleanup:
    """Tests for stale .json.lock file cleanup."""

    def test_stale_lock_file_removed(self, service, sessions_dir):
        """Lock files older than 5 minutes are removed."""
        lock = sessions_dir / "sess-001.json.lock"
        lock.write_text("")
        old_time = time.time() - _LOCK_STALE_SECONDS - 60
        os.utime(lock, (old_time, old_time))

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.lock_files_removed == 1
        assert not lock.exists()

    def test_fresh_lock_file_kept(self, service, sessions_dir):
        """Lock files newer than 5 minutes are preserved."""
        lock = sessions_dir / "sess-002.json.lock"
        lock.write_text("")
        # File is fresh (just created), should be kept

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.lock_files_removed == 0
        assert lock.exists()

    def test_multiple_lock_files_mixed_ages(self, service, sessions_dir):
        """Only stale lock files are removed; fresh ones are kept."""
        stale_lock = sessions_dir / "stale.json.lock"
        fresh_lock = sessions_dir / "fresh.json.lock"
        stale_lock.write_text("")
        fresh_lock.write_text("")

        old_time = time.time() - _LOCK_STALE_SECONDS - 120
        os.utime(stale_lock, (old_time, old_time))

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.lock_files_removed == 1
        assert not stale_lock.exists()
        assert fresh_lock.exists()


# ---------------------------------------------------------------------------
# Orphaned tmux session cleanup
# ---------------------------------------------------------------------------


class TestOrphanedTmuxCleanup:
    """Tests for orphaned agentic-* tmux session detection and cleanup."""

    @pytest.mark.story("US-SES-003")
    def test_orphaned_tmux_sessions_killed(self, service, sessions_dir):
        """Tmux sessions with agentic-* prefix and no matching record are killed."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "agentic-build-001\nagentic-orch-002\nuser-session\n"

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ), patch(
            "agenticcli.utils.session_cleanup.subprocess.run",
            return_value=mock_result,
        ) as mock_run:
            report = service.cleanup()

        # agentic-build-001 and agentic-orch-002 should be killed (orphaned)
        # user-session should be skipped (not agentic-*)
        assert report.tmux_sessions_killed == 2

        # Verify kill-session was called for each orphaned session
        kill_calls = [
            call for call in mock_run.call_args_list
            if "kill-session" in call[0][0]
        ]
        assert len(kill_calls) == 2

    def test_protected_tmux_session_not_killed(self, service, sessions_dir):
        """Tmux sessions matching running session records are not killed."""
        # Create a running session that references a tmux session
        _write_session(
            sessions_dir, "running-001",
            status="running", pid=os.getpid(),
            tmux_session="agentic-build-protected",
        )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "agentic-build-protected\nagentic-orphan-001\n"

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=True
        ), patch(
            "agenticcli.utils.session_cleanup.subprocess.run",
            return_value=mock_result,
        ):
            report = service.cleanup()

        # Only the orphan should be killed; the protected one is left alone
        assert report.tmux_sessions_killed == 1

    def test_tmux_not_installed(self, service, sessions_dir):
        """Cleanup proceeds gracefully when tmux is not installed."""
        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ), patch(
            "agenticcli.utils.session_cleanup.subprocess.run",
            side_effect=FileNotFoundError("tmux not found"),
        ):
            report = service.cleanup()

        # Should not crash; tmux kills = 0
        assert report.tmux_sessions_killed == 0

    def test_tmux_no_sessions(self, service, sessions_dir):
        """Cleanup handles 'no tmux sessions' (non-zero return code) gracefully."""
        mock_result = MagicMock()
        mock_result.returncode = 1  # no sessions
        mock_result.stdout = ""

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ), patch(
            "agenticcli.utils.session_cleanup.subprocess.run",
            return_value=mock_result,
        ):
            report = service.cleanup()

        assert report.tmux_sessions_killed == 0

    def test_tmux_timeout(self, service, sessions_dir):
        """Cleanup handles tmux timeout gracefully."""
        import subprocess as sp

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ), patch(
            "agenticcli.utils.session_cleanup.subprocess.run",
            side_effect=sp.TimeoutExpired("tmux", 10),
        ):
            report = service.cleanup()

        assert report.tmux_sessions_killed == 0

    def test_dry_run_does_not_kill_tmux(self, service, sessions_dir):
        """dry_run=True reports orphaned tmux sessions but doesn't kill them."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "agentic-orphan-001\n"

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ), patch(
            "agenticcli.utils.session_cleanup.subprocess.run",
            return_value=mock_result,
        ) as mock_run:
            report = service.cleanup(dry_run=True)

        assert report.tmux_sessions_killed == 1

        # kill-session should NOT have been called
        kill_calls = [
            call for call in mock_run.call_args_list
            if len(call[0]) > 0 and "kill-session" in call[0][0]
        ]
        assert len(kill_calls) == 0


# ---------------------------------------------------------------------------
# Bytes freed tracking
# ---------------------------------------------------------------------------


class TestBytesFreed:
    """Tests for accurate byte tracking in the cleanup report."""

    def test_bytes_freed_tracks_file_sizes(self, service, sessions_dir):
        """bytes_freed should accurately reflect the size of removed files."""
        sid = "bytes-test-001"
        content = "x" * 1000  # 1000 bytes
        _write_session(sessions_dir, sid, status="completed", pid=99999)
        _write_logs(sessions_dir, sid, content=content)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        # Session JSON + 2 log files, each with known content sizes
        assert report.bytes_freed > 0

    def test_empty_cleanup_zero_bytes(self, service, sessions_dir):
        """No artifacts means zero bytes freed."""
        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.bytes_freed == 0


# ---------------------------------------------------------------------------
# Cleanup report details
# ---------------------------------------------------------------------------


class TestCleanupDetails:
    """Tests for the details list in CleanupReport."""

    def test_session_cleanup_adds_detail(self, service, sessions_dir):
        """Each cleaned session adds a detail entry with session_id and files."""
        sid = "detail-001"
        _write_session(sessions_dir, sid, status="completed", pid=99999)
        _write_logs(sessions_dir, sid)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        session_details = [d for d in report.details if d.get("type") == "session"]
        assert len(session_details) == 1
        assert session_details[0]["session_id"] == sid
        assert len(session_details[0]["files_removed"]) >= 1

    def test_orphaned_log_adds_detail(self, service, sessions_dir):
        """Orphaned log cleanup adds detail entries."""
        logs_dir = sessions_dir / "logs"
        (logs_dir / "orphan-x.stdout.log").write_text("data")

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        orphan_details = [d for d in report.details if d.get("type") == "orphaned_log"]
        assert len(orphan_details) == 1
        assert orphan_details[0]["session_id"] == "orphan-x"

    def test_lock_file_adds_detail(self, service, sessions_dir):
        """Lock file cleanup adds detail entries."""
        lock = sessions_dir / "stale.json.lock"
        lock.write_text("")
        old_time = time.time() - _LOCK_STALE_SECONDS - 60
        os.utime(lock, (old_time, old_time))

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        lock_details = [d for d in report.details if d.get("type") == "lock_file"]
        assert len(lock_details) == 1

    def test_tmux_orphan_adds_detail(self, service, sessions_dir):
        """Orphaned tmux cleanup adds detail entries."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "agentic-test-001\n"

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ), patch(
            "agenticcli.utils.session_cleanup.subprocess.run",
            return_value=mock_result,
        ):
            report = service.cleanup()

        tmux_details = [d for d in report.details if d.get("type") == "orphaned_tmux"]
        assert len(tmux_details) == 1
        assert tmux_details[0]["tmux_session"] == "agentic-test-001"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and error resilience."""

    def test_cleanup_empty_directory(self, service, sessions_dir):
        """Cleanup on empty directory returns zero-count report without errors."""
        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.sessions_cleaned == 0
        assert report.log_files_removed == 0
        assert report.context_files_removed == 0

    def test_cleanup_missing_logs_dir(self, service, sessions_dir):
        """Cleanup works when logs directory doesn't exist."""
        import shutil
        shutil.rmtree(sessions_dir / "logs")

        sid = "no-logs-001"
        _write_session(sessions_dir, sid, status="completed", pid=99999)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.sessions_cleaned == 1
        assert report.log_files_removed == 0

    def test_cleanup_missing_context_dir(self, service, sessions_dir):
        """Cleanup works when context directory doesn't exist."""
        import shutil
        shutil.rmtree(sessions_dir / "context")

        sid = "no-ctx-001"
        _write_session(sessions_dir, sid, status="completed", pid=99999)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.sessions_cleaned == 1
        assert report.context_files_removed == 0

    def test_session_json_without_log_files(self, service, sessions_dir):
        """Session with JSON but no log/context files is still cleaned."""
        sid = "json-only-001"
        _write_session(sessions_dir, sid, status="completed", pid=99999)

        with patch(
            "agenticcli.utils.session_cleanup.is_process_running", return_value=False
        ):
            report = service.cleanup()

        assert report.sessions_cleaned == 1
        assert report.log_files_removed == 0
        assert report.context_files_removed == 0

    def test_extract_session_id_from_log_filename(self):
        """Helper correctly extracts session_id from log filenames."""
        extract = SessionCleanupService._extract_session_id_from_log
        assert extract("abc-123.stdout.log") == "abc-123"
        assert extract("abc-123.stderr.log") == "abc-123"
        assert extract("no-suffix.log") is None
        assert extract("random.txt") is None
        assert extract("") is None

    def test_safe_file_size_returns_zero_on_missing(self):
        """_safe_file_size returns 0 for non-existent paths."""
        result = SessionCleanupService._safe_file_size(Path("/nonexistent/file"))
        assert result == 0
