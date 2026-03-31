"""Session cleanup service — removes stale session artifacts.

Provides a unified domain service that cleans ALL session artifacts:
- Session JSON state files for dead/completed sessions
- Stdout/stderr log files in sessions/logs/
- Context files in sessions/context/
- Stale .json.lock files
- Orphaned agentic-* tmux sessions

Supports age-based purging, dry-run mode, and produces a cleanup report.
Never cleans running sessions with alive PIDs.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from agenticcli.utils.state_store import StateStore, is_process_running

logger = logging.getLogger(__name__)

# Lock files older than this are considered stale
_LOCK_STALE_SECONDS = 300  # 5 minutes


@dataclass
class CleanupReport:
    """Report of cleanup actions taken (or previewed in dry-run mode)."""

    sessions_cleaned: int = 0
    log_files_removed: int = 0
    context_files_removed: int = 0
    lock_files_removed: int = 0
    tmux_sessions_killed: int = 0
    bytes_freed: int = 0
    details: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to a plain dict for JSON serialization."""
        return {
            "sessions_cleaned": self.sessions_cleaned,
            "log_files_removed": self.log_files_removed,
            "context_files_removed": self.context_files_removed,
            "lock_files_removed": self.lock_files_removed,
            "tmux_sessions_killed": self.tmux_sessions_killed,
            "bytes_freed": self.bytes_freed,
            "details": self.details,
        }


# @story US-001
class SessionCleanupService:
    """Domain service for cleaning up stale session artifacts.

    Designed as a pure domain service: no CLI imports, no console output.
    Returns data structures (CleanupReport) for callers to render.
    """

    def __init__(self, *, state_dir: Path | None = None) -> None:
        """Initialize the cleanup service.

        Args:
            state_dir: Optional directory override for the sessions state store.
                       Used in tests with tmp_path to avoid touching real data.
        """
        self._store = StateStore("sessions", id_key="session_id")
        self._state_dir = state_dir
        self._sessions_dir = self._store.get_dir(state_dir)
        self._logs_dir = self._sessions_dir / "logs"
        self._context_dir = self._sessions_dir / "context"

    def cleanup(
        self,
        *,
        max_age_days: int | None = None,
        dry_run: bool = False,
    ) -> CleanupReport:
        """Run full cleanup of stale session artifacts.

        Args:
            max_age_days: If set, only clean sessions older than N days.
                          If None, clean all stale sessions regardless of age.
            dry_run: If True, calculate what would be removed but don't
                     actually delete anything.

        Returns:
            CleanupReport with counts of cleaned artifacts.
        """
        report = CleanupReport()

        # Step 1-3: Identify cleanable and protected sessions
        running_ids = self._get_running_session_ids()
        cleanable_ids = self._get_cleanable_session_ids(
            running_ids=running_ids, max_age_days=max_age_days,
        )
        known_ids = self._get_known_session_ids()

        # Step 4: Clean session artifacts for each cleanable session
        for session_id in cleanable_ids:
            self._clean_session(session_id, report, dry_run=dry_run)

        # Step 5: Clean orphaned artifacts (logs/context with no matching JSON)
        self._clean_orphaned_artifacts(
            known_ids=known_ids,
            running_ids=running_ids,
            cleaned_ids=cleanable_ids,
            max_age_days=max_age_days,
            report=report,
            dry_run=dry_run,
        )

        # Step 6: Clean stale lock files
        self._clean_lock_files(report, dry_run=dry_run)

        # Step 7: Clean orphaned tmux sessions
        self._clean_orphaned_tmux(running_ids, report, dry_run=dry_run)

        return report

    def _get_running_session_ids(self) -> set[str]:
        """Return session IDs with status='running'/'starting' and alive PIDs."""
        running = set()
        all_records = self._store.list_all(state_dir=self._state_dir)
        for record in all_records:
            status = record.get("status", "")
            pid = record.get("pid")
            if status in ("running", "starting") and pid and is_process_running(pid):
                sid = record.get("session_id", "")
                if sid:
                    running.add(sid)
        return running

    def _get_known_session_ids(self) -> set[str]:
        """Return ALL session IDs in the store."""
        all_records = self._store.list_all(state_dir=self._state_dir)
        return {r.get("session_id", "") for r in all_records if r.get("session_id")}

    def _get_cleanable_session_ids(
        self,
        *,
        running_ids: set[str],
        max_age_days: int | None,
    ) -> set[str]:
        """Identify session IDs eligible for cleanup.

        A session is cleanable if:
        - Its status is terminal (completed/stopped/failed), OR
        - Its status is running/starting but its PID is dead
        AND (if max_age_days is set) it's older than the threshold.
        """
        cutoff = None
        if max_age_days is not None:
            cutoff = datetime.now() - timedelta(days=max_age_days)

        def is_alive(record: dict) -> bool:
            """Return True if the session should be KEPT (alive/protected)."""
            sid = record.get("session_id", "")
            if sid in running_ids:
                return True  # Protected: running with alive PID
            return False

        stale_records = self._store.list_stale(is_alive, state_dir=self._state_dir)

        cleanable = set()
        for record in stale_records:
            sid = record.get("session_id", "")
            if not sid:
                continue

            # Apply age filter if specified
            if cutoff is not None:
                started_at = record.get("started_at", "")
                if started_at:
                    try:
                        session_time = datetime.fromisoformat(started_at)
                        if session_time > cutoff:
                            continue  # Too recent, skip
                    except (ValueError, TypeError):
                        pass  # Can't parse date — treat as old enough

            cleanable.add(sid)

        return cleanable

    def _clean_session(
        self,
        session_id: str,
        report: CleanupReport,
        *,
        dry_run: bool,
    ) -> None:
        """Clean all artifacts for a single session."""
        detail = {"session_id": session_id, "type": "session", "files_removed": []}

        # Session JSON
        json_file = self._sessions_dir / f"{session_id}.json"
        if json_file.exists():
            bytes_size = self._safe_file_size(json_file)
            detail["files_removed"].append(str(json_file))
            if not dry_run:
                self._store.delete(session_id, state_dir=self._state_dir)
            report.bytes_freed += bytes_size

        report.sessions_cleaned += 1

        # Log files
        for suffix in (".stdout.log", ".stderr.log"):
            log_file = self._logs_dir / f"{session_id}{suffix}"
            if log_file.exists():
                bytes_size = self._safe_file_size(log_file)
                detail["files_removed"].append(str(log_file))
                if not dry_run:
                    log_file.unlink(missing_ok=True)
                report.log_files_removed += 1
                report.bytes_freed += bytes_size

        # Context file
        context_file = self._context_dir / f"{session_id}.md"
        if context_file.exists():
            bytes_size = self._safe_file_size(context_file)
            detail["files_removed"].append(str(context_file))
            if not dry_run:
                context_file.unlink(missing_ok=True)
            report.context_files_removed += 1
            report.bytes_freed += bytes_size

        report.details.append(detail)

    def _clean_orphaned_artifacts(
        self,
        *,
        known_ids: set[str],
        running_ids: set[str],
        cleaned_ids: set[str],
        max_age_days: int | None,
        report: CleanupReport,
        dry_run: bool,
    ) -> None:
        """Clean log and context files that have no matching session JSON.

        Production data shows thousands of orphaned log/context files.
        Cross-reference file names against known session IDs in the store.
        """
        cutoff_mtime = None
        if max_age_days is not None:
            cutoff_mtime = time.time() - (max_age_days * 86400)

        # IDs that are either still known in the store or just cleaned —
        # skip them (they were handled above or are protected)
        skip_ids = known_ids | cleaned_ids

        # Orphaned log files
        if self._logs_dir.exists():
            for log_file in self._logs_dir.glob("*.log"):
                sid = self._extract_session_id_from_log(log_file.name)
                if not sid:
                    continue
                if sid in running_ids:
                    continue  # Protected
                if sid in skip_ids:
                    continue  # Already handled or still known

                # Age filter on file mtime
                if cutoff_mtime is not None:
                    try:
                        if log_file.stat().st_mtime > cutoff_mtime:
                            continue  # Too recent
                    except OSError:
                        continue

                bytes_size = self._safe_file_size(log_file)
                if not dry_run:
                    log_file.unlink(missing_ok=True)
                report.log_files_removed += 1
                report.bytes_freed += bytes_size
                report.details.append({
                    "type": "orphaned_log",
                    "file": str(log_file),
                    "session_id": sid,
                })

        # Orphaned context files
        if self._context_dir.exists():
            for ctx_file in self._context_dir.glob("*.md"):
                sid = ctx_file.stem  # e.g. "abc-def.md" -> "abc-def"
                if not sid:
                    continue
                if sid in running_ids:
                    continue
                if sid in skip_ids:
                    continue

                if cutoff_mtime is not None:
                    try:
                        if ctx_file.stat().st_mtime > cutoff_mtime:
                            continue
                    except OSError:
                        continue

                bytes_size = self._safe_file_size(ctx_file)
                if not dry_run:
                    ctx_file.unlink(missing_ok=True)
                report.context_files_removed += 1
                report.bytes_freed += bytes_size
                report.details.append({
                    "type": "orphaned_context",
                    "file": str(ctx_file),
                    "session_id": sid,
                })

    def _clean_lock_files(
        self,
        report: CleanupReport,
        *,
        dry_run: bool,
    ) -> None:
        """Remove stale .json.lock files older than 5 minutes."""
        now = time.time()
        for lock_file in self._sessions_dir.glob("*.json.lock"):
            try:
                mtime = lock_file.stat().st_mtime
                if (now - mtime) < _LOCK_STALE_SECONDS:
                    continue  # Still fresh, skip
            except OSError:
                continue  # Can't stat — skip

            bytes_size = self._safe_file_size(lock_file)
            if not dry_run:
                lock_file.unlink(missing_ok=True)
            report.lock_files_removed += 1
            report.bytes_freed += bytes_size
            report.details.append({
                "type": "lock_file",
                "file": str(lock_file),
            })

    def _clean_orphaned_tmux(
        self,
        running_ids: set[str],
        report: CleanupReport,
        *,
        dry_run: bool,
    ) -> None:
        """Kill orphaned agentic-* tmux sessions.

        Cross-references tmux sessions with the agentic-* prefix against
        running session records that have a tmux_session field.
        """
        # Collect tmux_session names for all running sessions
        protected_tmux = set()
        all_records = self._store.list_all(state_dir=self._state_dir)
        for record in all_records:
            sid = record.get("session_id", "")
            tmux_name = record.get("tmux_session", "")
            if sid in running_ids and tmux_name:
                protected_tmux.add(tmux_name)

        # List all tmux sessions
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return  # tmux not running or no sessions
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return  # tmux not installed or unresponsive

        for session_name in result.stdout.strip().splitlines():
            if not session_name.startswith("agentic-"):
                continue  # Not ours
            if session_name in protected_tmux:
                continue  # Active, don't kill

            if not dry_run:
                try:
                    subprocess.run(
                        ["tmux", "kill-session", "-t", session_name],
                        capture_output=True,
                        timeout=5,
                    )
                except (subprocess.TimeoutExpired, OSError):
                    logger.debug("Failed to kill tmux session %s", session_name)
                    continue

            report.tmux_sessions_killed += 1
            report.details.append({
                "type": "orphaned_tmux",
                "tmux_session": session_name,
            })

    @staticmethod
    def _extract_session_id_from_log(filename: str) -> str | None:
        """Extract session_id from a log filename.

        Expected patterns:
            {session_id}.stdout.log
            {session_id}.stderr.log

        Returns:
            The session_id string or None if pattern doesn't match.
        """
        for suffix in (".stdout.log", ".stderr.log"):
            if filename.endswith(suffix):
                return filename[: -len(suffix)]
        return None

    @staticmethod
    def _safe_file_size(path: Path) -> int:
        """Get file size in bytes, returning 0 on any error."""
        try:
            return path.stat().st_size
        except OSError:
            return 0
