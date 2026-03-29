"""Epic Repository - TinyDB-backed storage for epic data.

Provides a repository abstraction over TinyDB as the sole data store for
epic/ticket/phase data. YAML files are no longer used as a data source.

Replaces the legacy PlanRepository (plan_repository.py) with renamed
tables, fields, and methods aligned to the epic/ticket terminology.
"""

import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from tinydb import Query, TinyDB
from tinydb.storages import Storage

from .state import FileLock, RetryingFileLock

from .epic import (
    EpicCreateResult,
    EpicData,
    EpicDeleteResult,
    EpicMetadata,
    EpicUpdateResult,
    PhaseData,
    TicketData,
)

logger = logging.getLogger(__name__)


class AtomicJSONStorage(Storage):
    """TinyDB storage backend with atomic writes and corruption recovery.

    Writes go to a temporary file in the same directory, then are atomically
    renamed over the target. This prevents truncated/invalid JSON from
    mid-write crashes. A backup (.bak) is maintained so that if the primary
    file is corrupted, the last known-good state can be recovered.
    """

    def __init__(self, path: str, **kwargs: Any):
        super().__init__()
        self._path = Path(path)
        self._backup_path = self._path.with_suffix(self._path.suffix + ".bak")

    def read(self) -> Optional[dict]:
        """Read the database, recovering from backup on corruption."""
        if not self._path.exists():
            return None

        try:
            raw = self._path.read_text(encoding="utf-8")
            if not raw.strip():
                return None
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Corrupted DB file %s: %s. Attempting backup recovery.",
                self._path,
                exc,
            )
            return self._recover_from_backup()

    def _recover_from_backup(self) -> Optional[dict]:
        """Restore from .bak file if the primary is corrupted."""
        if not self._backup_path.exists():
            logger.error(
                "No backup file at %s — returning empty database.",
                self._backup_path,
            )
            return None

        try:
            raw = self._backup_path.read_text(encoding="utf-8")
            if not raw.strip():
                return None
            data = json.loads(raw)
            logger.warning(
                "Recovered database from backup %s.", self._backup_path
            )
            # Restore the primary file from backup
            shutil.copy2(str(self._backup_path), str(self._path))
            return data
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            logger.error(
                "Backup %s also corrupted: %s — returning empty database.",
                self._backup_path,
                exc,
            )
            return None

    def write(self, data: dict) -> None:
        """Write data atomically via temp-file + rename.

        Steps:
        1. Back up current file to .bak (if it exists and is valid)
        2. Write new data to a temp file in the same directory
        3. Atomically rename temp file over the target
        """
        # Back up current file before writing
        if self._path.exists():
            try:
                shutil.copy2(str(self._path), str(self._backup_path))
            except OSError as exc:
                logger.warning("Failed to create backup: %s", exc)

        # Write to temp file then atomically rename
        dir_path = str(self._path.parent)
        fd = None
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=dir_path, suffix=".tmp", prefix=".epics_"
            )
            serialized = json.dumps(data, indent=2, ensure_ascii=False)
            os.write(fd, serialized.encode("utf-8"))
            os.fsync(fd)
            os.close(fd)
            fd = None
            os.rename(tmp_path, str(self._path))
            tmp_path = None
        except BaseException:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise

    def close(self) -> None:
        """No persistent file handle to close."""
        pass


# DB status values that correspond to a "live" (active/in-progress) epic.
# "completed", "deferred", and "cancelled" are their own direct status values.
_LIVE_STATUSES: frozenset[str] = frozenset(
    {"proposed", "in_progress", "active", "planning", "approved", "pending", "blocked", "seed"}
)


class EpicRepository:
    """TinyDB-backed repository for epic data access.

    Manages three tables:
    - epics: one document per epic (keyed by epic_folder_name)
    - tickets: one document per ticket (keyed by epic_folder_name + task_id)
    - phases: one document per phase (keyed by epic_folder_name + phase_name)

    DB Migration: On first open, detects an existing "plans" table from
    PlanRepository and migrates all records to the "epics" and "tickets"
    tables using the updated field names.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        epics_base: Optional[Path] = None,
        auto_bootstrap: bool = True,
    ):
        """Initialize EpicRepository.

        Args:
            db_path: Path to TinyDB JSON file.
                     Defaults to ~/.agentic/epics.db.
            epics_base: Deprecated, ignored.
            auto_bootstrap: Deprecated, ignored. TinyDB is the sole data store.
        """
        if db_path is None:
            db_path = Path.home() / ".agentic" / "epics.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = FileLock(self.db_path)
        self._retrying_lock = RetryingFileLock(self._lock)

        # Open TinyDB under lock to prevent reading a partially-written file
        with self._retrying_lock:
            self._db = TinyDB(str(self.db_path), storage=AtomicJSONStorage)
            self._epics = self._db.table("epics")
            self._tickets = self._db.table("tickets")
            self._phases = self._db.table("phases")
            self._story_tests = self._db.table("story_tests")
            self._story_code = self._db.table("story_code")

            # Migrate legacy "plans" / "tasks" tables if they exist
            self._migrate_from_plans_table()

        # auto_bootstrap parameter kept for API compat but no longer imports YAML.
        # TinyDB is the sole data store; if the DB is empty, it stays empty until
        # epics are created through the normal create_epic() API.

    def close(self):
        """Close the database."""
        self._db.close()

    def __enter__(self) -> "EpicRepository":
        """Context manager entry — returns self."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit — closes the database."""
        self.close()

    def refresh(self):
        """Clear all TinyDB query caches so the next read hits disk.

        Required after external processes (e.g. SDK agents in tmux panes)
        have written to the same database file. TinyDB caches query results
        per-table; without clearing, the in-process cache returns stale data.
        """
        for table in (self._epics, self._tickets, self._phases,
                      self._story_tests, self._story_code):
            table.clear_cache()

    # ------------------------------------------------------------------
    # DB Migration
    # ------------------------------------------------------------------

    def _migrate_from_plans_table(self) -> None:
        """Migrate legacy PlanRepository tables to EpicRepository tables.

        Detects the old "plans" table and copies all records into "epics",
        renaming plan_folder_name -> epic_folder_name and
        plan_folder -> epic_folder.  Also migrates the "tasks" table to
        "tickets" using the same field renames.

        Migration only runs once; after migration the old tables are cleared.
        """
        old_plans_table = self._db.table("plans")
        old_tasks_table = self._db.table("tasks")

        old_plan_docs = old_plans_table.all()
        if not old_plan_docs:
            return  # Nothing to migrate

        logger.info(
            "Migrating %d plan records from 'plans' table to 'epics' table",
            len(old_plan_docs),
        )

        # NOTE: Caller must hold self._lock (called from __init__ under lock)
        for doc in old_plan_docs:
            epic_folder_name = doc.get("plan_folder_name", "")
            if not epic_folder_name:
                continue

            # Skip if already migrated
            Epic = Query()
            if self._epics.search(Epic.epic_folder_name == epic_folder_name):
                continue

            new_doc = dict(doc)
            # Rename fields
            new_doc["epic_folder_name"] = new_doc.pop("plan_folder_name", "")
            new_doc["epic_folder"] = new_doc.pop("plan_folder", "")
            # Remove TinyDB internal doc_id if present
            new_doc.pop("doc_id", None)
            self._epics.insert(new_doc)

        # Migrate tasks -> tickets
        old_task_docs = old_tasks_table.all()
        for doc in old_task_docs:
            epic_folder_name = doc.get("plan_folder_name", "")
            if not epic_folder_name:
                continue

            Ticket = Query()
            if self._tickets.search(
                (Ticket.epic_folder_name == epic_folder_name)
                & (Ticket.task_id == doc.get("task_id", ""))
            ):
                continue

            new_doc = dict(doc)
            new_doc["epic_folder_name"] = new_doc.pop("plan_folder_name", "")
            new_doc.pop("doc_id", None)
            self._tickets.insert(new_doc)

        # Migrate phases (only rename the key field)
        old_phases_table = self._db.table("phases")
        # phases table is shared; check if already populated
        phase_docs_check = old_phases_table.all()
        has_old_key = any("plan_folder_name" in d for d in phase_docs_check)
        if has_old_key:
            for doc in phase_docs_check:
                if "plan_folder_name" in doc and "epic_folder_name" not in doc:
                    Phase = Query()
                    old_phases_table.update(
                        {"epic_folder_name": doc["plan_folder_name"]},
                        Phase.plan_folder_name == doc["plan_folder_name"],
                    )

        # Clear old tables after migration
        old_plans_table.truncate()
        old_tasks_table.truncate()

        logger.info("Migration from 'plans' to 'epics' table complete.")

    # ------------------------------------------------------------------
    # Epic CRUD
    # ------------------------------------------------------------------

    def create_epic(self, epic_data: dict) -> EpicCreateResult:
        """Insert a new epic document.

        Args:
            epic_data: Dictionary with epic fields. Must include
                       'epic_folder_name' and 'epic_folder'.

        Returns:
            EpicCreateResult indicating success or failure.
        """
        epic_folder_name = (
            epic_data.get("epic_folder_name", "")
            or epic_data.get("plan_folder_name", "")
        )
        epic_folder = (
            epic_data.get("epic_folder", "")
            or epic_data.get("plan_folder", "")
        )

        if not epic_folder_name:
            return EpicCreateResult(
                epic_folder=Path(str(epic_folder)) if epic_folder else None,
                epic_folder_name=epic_folder_name,
                success=False,
                message="epic_folder_name is required",
            )

        with self._retrying_lock:
            Epic = Query()
            if self._epics.search(Epic.epic_folder_name == epic_folder_name):
                return EpicCreateResult(
                    epic_folder=Path(str(epic_folder)) if epic_folder else None,
                    epic_folder_name=epic_folder_name,
                    success=False,
                    message=f"Epic already exists in DB: {epic_folder_name}",
                )

            doc = {
                "epic_folder_name": epic_folder_name,
                "epic_folder": str(epic_folder) if epic_folder else "",
                "name": epic_data.get("name", epic_folder_name),
                "worktree_path": epic_data.get("worktree_path", ""),
                "branch": epic_data.get("branch", ""),
                "status": epic_data.get("status", "proposed"),
                "priority": epic_data.get("priority", "medium"),
                "objective": epic_data.get("objective", ""),
                "created": epic_data.get("created", datetime.now().strftime("%Y-%m-%d")),
                "context": epic_data.get("context", ""),
            }
            self._epics.insert(doc)

        return EpicCreateResult(
            epic_folder=Path(str(epic_folder)) if epic_folder else None,
            epic_folder_name=epic_folder_name,
            success=True,
            message=f"Epic inserted into DB: {epic_folder_name}",
        )

    def get_epic(self, epic_id_or_name: str) -> Optional[EpicData]:
        """Retrieve an epic by folder name or short ID prefix.

        Args:
            epic_id_or_name: Full folder name or 8-char ID prefix.

        Returns:
            EpicData if found, None otherwise.
        """
        doc = self._find_epic_doc(epic_id_or_name)
        if not doc:
            return None

        epic_folder_name = doc["epic_folder_name"]

        # Gather phases and tickets from their tables
        Phase = Query()
        phase_docs = self._phases.search(Phase.epic_folder_name == epic_folder_name)
        phase_docs.sort(key=lambda d: d.get("_order", 0))

        Ticket = Query()
        ticket_docs = self._tickets.search(Ticket.epic_folder_name == epic_folder_name)

        # Build ticket lookup by phase
        tickets_by_phase: dict[str, list[TicketData]] = {}
        all_tickets: list[TicketData] = []
        for td in ticket_docs:
            ticket_obj = TicketData(
                id=td.get("task_id", ""),
                name=td.get("name", ""),
                description=td.get("description"),
                status=td.get("status"),
                agent=td.get("agent"),
                phase_name=td.get("phase_name"),
                inputs=td.get("inputs", []),
                target_files=td.get("target_files", []),
                guidance=td.get("guidance"),
                completed_date=td.get("completed_date"),
                success_criteria=td.get("success_criteria"),
                story_ids=td.get("story_ids", []),
            )
            all_tickets.append(ticket_obj)
            phase_key = td.get("phase_name", "")
            tickets_by_phase.setdefault(phase_key, []).append(ticket_obj)

        phases: list[PhaseData] = []
        for pd in phase_docs:
            phase_name = pd.get("phase_name", "")
            phases.append(
                PhaseData(
                    name=phase_name,
                    description=pd.get("description"),
                    execution=pd.get("execution"),
                    status=pd.get("status"),
                    tasks=tickets_by_phase.get(phase_name, []),
                    agent=pd.get("agent"),
                    loop_type=pd.get("loop_type"),
                    loop_max_iterations=pd.get("loop_max_iterations"),
                    max_turns=pd.get("max_turns"),
                    feedback_triggers=pd.get("feedback_triggers") or {},
                    phase_id=pd.get("phase_id"),
                )
            )

        raw_folder = doc.get("epic_folder", "")
        return EpicData(
            epic_folder=Path(raw_folder) if raw_folder else None,
            epic_folder_name=epic_folder_name,
            objective=doc.get("objective"),
            status=doc.get("status"),
            branch=doc.get("branch"),
            name=doc.get("name"),
            worktree_path=doc.get("worktree_path"),
            priority=doc.get("priority"),
            context=doc.get("context"),
            created=doc.get("created"),
            deferred_reason=doc.get("deferred_reason"),
            cancelled_date=doc.get("cancelled_date"),
            phases=phases,
            tasks=all_tickets,
        )

    def list_epics(self, status: Optional[str] = None) -> list[EpicMetadata]:
        """List epics, optionally filtered by status.

        Args:
            status: 'live' to return all active/in-progress epics (any status
                    in _LIVE_STATUSES), or a direct DB status value such as
                    'completed', 'deferred', 'cancelled', 'in_progress', etc.
                    The status field in TinyDB is the sole source of truth.

        Returns:
            List of EpicMetadata sorted newest-first by folder name.
        """
        if status:
            Epic = Query()
            if status.lower() == "live":
                live_lower = {s.lower() for s in _LIVE_STATUSES}
                docs = self._epics.search(
                    Epic.status.test(lambda s: (s or "").lower() in live_lower)
                )
            elif status.lower() == "completed":
                # Normalise legacy capitalisation variants
                docs = self._epics.search(
                    Epic.status.test(
                        lambda s: (s or "").lower() in {"completed", "fully_completed"}
                    )
                )
            else:
                # Direct DB status match (e.g. "in_progress", "deferred", "cancelled")
                docs = self._epics.search(Epic.status == status)
        else:
            docs = self._epics.all()

        results = []
        for doc in docs:
            raw_folder = doc.get("epic_folder", "")
            results.append(
                EpicMetadata(
                    epic_folder=Path(raw_folder) if raw_folder else None,
                    epic_folder_name=doc["epic_folder_name"],
                    objective=doc.get("objective"),
                    status=doc.get("status"),
                    created=doc.get("created"),
                    name=doc.get("name"),
                    priority=doc.get("priority"),
                    worktree_path=doc.get("worktree_path"),
                    branch=doc.get("branch"),
                )
            )

        results.sort(key=lambda m: m.epic_folder_name, reverse=True)
        return results

    def update_epic(self, epic_folder_name: str, updates: dict) -> EpicUpdateResult:
        """Update fields on an existing epic document.

        Args:
            epic_folder_name: Folder name identifying the epic.
            updates: Dictionary of fields to update.

        Returns:
            EpicUpdateResult indicating success or failure.
        """
        with self._retrying_lock:
            doc = self._find_epic_doc(epic_folder_name)
            if not doc:
                return EpicUpdateResult(
                    success=False,
                    message=f"Epic not found in DB: {epic_folder_name}",
                )

            old_status = doc.get("status")
            Epic = Query()
            self._epics.update(updates, Epic.epic_folder_name == doc["epic_folder_name"])

        new_status = updates.get("status", old_status)
        return EpicUpdateResult(
            success=True,
            message=f"Epic updated in DB: {doc['epic_folder_name']}",
            epic_folder=doc.get("epic_folder"),
            old_status=old_status,
            new_status=new_status,
        )

    def delete_epic(self, epic_folder_name: str) -> EpicDeleteResult:
        """Remove an epic and all its tickets/phases from the database.

        Args:
            epic_folder_name: Folder name identifying the epic.

        Returns:
            EpicDeleteResult indicating success or failure.
        """
        with self._retrying_lock:
            doc = self._find_epic_doc(epic_folder_name)
            if not doc:
                return EpicDeleteResult(
                    success=False,
                    message=f"Epic not found in DB: {epic_folder_name}",
                )

            actual_name = doc["epic_folder_name"]
            Q = Query()
            self._epics.remove(Q.epic_folder_name == actual_name)
            self._tickets.remove(Q.epic_folder_name == actual_name)
            self._phases.remove(Q.epic_folder_name == actual_name)

        return EpicDeleteResult(
            success=True,
            message=f"Epic and associated data removed from DB: {actual_name}",
        )

    def archive_epic(
        self, epic_folder_name: str, completed_date: Optional[str] = None
    ) -> EpicUpdateResult:
        """Archive an epic by marking it completed in the database.

        Sets status to "completed" and records completed_date.
        Does NOT rewrite the epic_folder path — the status field is the
        sole source of truth for lifecycle state.

        Note: Filesystem operations (copying/moving folders) are the caller's
        responsibility. This method only updates the database record.

        Args:
            epic_folder_name: Folder name identifying the epic.
            completed_date: Date string (YYYY-MM-DD). Defaults to today.

        Returns:
            EpicUpdateResult indicating success or failure.
        """
        if completed_date is None:
            completed_date = datetime.now().strftime("%Y-%m-%d")

        doc = self._find_epic_doc(epic_folder_name)
        if not doc:
            return EpicUpdateResult(
                success=False,
                message=f"Epic not found in DB: {epic_folder_name}",
            )

        updates = {
            "status": "completed",
            "completed_date": completed_date,
        }
        return self.update_epic(doc["epic_folder_name"], updates)

    def unarchive_epic(self, epic_folder_name: str) -> EpicUpdateResult:
        """Unarchive an epic by restoring it to active status.

        Sets status to "in_progress" and clears completed_date.
        Does NOT rewrite the epic_folder path — the status field is the
        sole source of truth for lifecycle state.

        Note: Filesystem operations (moving folders) are the caller's
        responsibility. This method only updates the database record.

        Args:
            epic_folder_name: Folder name identifying the epic.

        Returns:
            EpicUpdateResult indicating success or failure.
        """
        doc = self._find_epic_doc(epic_folder_name)
        if not doc:
            return EpicUpdateResult(
                success=False,
                message=f"Epic not found in DB: {epic_folder_name}",
            )

        updates = {
            "status": "in_progress",
            "completed_date": "",
        }
        return self.update_epic(doc["epic_folder_name"], updates)

    def cancel_epic(
        self, epic_folder_name: str, reason: str = ""
    ) -> EpicUpdateResult:
        """Cancel an epic by marking it as cancelled in the database.

        Updates the epic status to "cancelled", records the cancelled_date,
        and optionally stores a cancellation reason.

        Args:
            epic_folder_name: Folder name identifying the epic.
            reason: Optional reason for cancellation.

        Returns:
            EpicUpdateResult indicating success or failure.
        """
        doc = self._find_epic_doc(epic_folder_name)
        if not doc:
            return EpicUpdateResult(
                success=False,
                message=f"Epic not found in DB: {epic_folder_name}",
            )

        updates: dict = {
            "status": "cancelled",
            "cancelled_date": datetime.now().strftime("%Y-%m-%d"),
        }
        if reason:
            updates["cancelled_reason"] = reason
        return self.update_epic(doc["epic_folder_name"], updates)

    def resync_epic_folder(self, epic_folder_name: str, new_folder: str) -> bool:
        """Update epic_folder path and re-import tickets/phases from new location.

        Called when a stale TinyDB path is detected (e.g. epic was resurrected
        from completed/ back to live/).

        Args:
            epic_folder_name: Folder name identifying the epic.
            new_folder: New filesystem path for the epic folder.

        Returns:
            True if the resync succeeded.
        """
        doc = self._find_epic_doc(epic_folder_name)
        if not doc:
            return False

        new_path = Path(new_folder)
        if not new_path.is_dir():
            return False

        actual_name = doc["epic_folder_name"]
        with self._retrying_lock:
            Epic = Query()
            self._epics.update(
                {"epic_folder": str(new_path)},
                Epic.epic_folder_name == actual_name,
            )

        return True

    # ------------------------------------------------------------------
    # Ticket CRUD
    # ------------------------------------------------------------------

    def get_tickets(
        self,
        epic_folder_name: str,
        status_filter: Optional[str] = None,
    ) -> list[TicketData]:
        """Get all tickets for an epic.

        Args:
            epic_folder_name: Epic folder name.
            status_filter: Optional status string to filter by.

        Returns:
            List of TicketData objects.
        """
        Ticket = Query()
        if status_filter:
            # Handle backward compat: "proposed" also matches legacy "pending"
            if status_filter == "proposed":
                docs = self._tickets.search(
                    (Ticket.epic_folder_name == epic_folder_name)
                    & (Ticket.status.test(lambda s: s in ("proposed", "pending")))
                )
            else:
                docs = self._tickets.search(
                    (Ticket.epic_folder_name == epic_folder_name)
                    & (Ticket.status == status_filter)
                )
        else:
            docs = self._tickets.search(Ticket.epic_folder_name == epic_folder_name)

        return [
            TicketData(
                id=d.get("task_id", ""),
                name=d.get("name", ""),
                description=d.get("description"),
                status=d.get("status"),
                agent=d.get("agent"),
                phase_name=d.get("phase_name"),
                inputs=d.get("inputs", []),
                target_files=d.get("target_files", []),
                guidance=d.get("guidance"),
                completed_date=d.get("completed_date"),
                success_criteria=d.get("success_criteria"),
                story_ids=d.get("story_ids", []),
            )
            for d in docs
        ]

    def get_ticket(
        self, epic_folder_name: str, task_id: str
    ) -> Optional[TicketData]:
        """Get a single ticket.

        Args:
            epic_folder_name: Epic folder name.
            task_id: Ticket identifier.

        Returns:
            TicketData if found, None otherwise.
        """
        Ticket = Query()
        docs = self._tickets.search(
            (Ticket.epic_folder_name == epic_folder_name)
            & (Ticket.task_id == task_id)
        )
        if not docs:
            return None

        d = docs[0]
        return TicketData(
            id=d.get("task_id", ""),
            name=d.get("name", ""),
            description=d.get("description"),
            status=d.get("status"),
            agent=d.get("agent"),
            phase_name=d.get("phase_name"),
            inputs=d.get("inputs", []),
            target_files=d.get("target_files", []),
            guidance=d.get("guidance"),
            completed_date=d.get("completed_date"),
            success_criteria=d.get("success_criteria"),
            story_ids=d.get("story_ids", []),
        )

    def update_ticket_status(
        self, epic_folder_name: str, task_id: str, new_status: str
    ) -> bool:
        """Update a ticket's status.

        Automatically sets completed_date when status is "completed".

        Args:
            epic_folder_name: Epic folder name.
            task_id: Ticket identifier.
            new_status: New status value.

        Returns:
            True if the ticket was found and updated.
        """
        updates = {"status": new_status}
        if new_status == "completed":
            updates["completed_date"] = datetime.now().strftime("%Y-%m-%d")
        with self._retrying_lock:
            Ticket = Query()
            updated = self._tickets.update(
                updates,
                (Ticket.epic_folder_name == epic_folder_name)
                & (Ticket.task_id == task_id),
            )
        return len(updated) > 0

    def add_ticket(
        self, epic_folder_name: str, phase_name: str, ticket_data: dict
    ) -> bool:
        """Add a ticket to the database.

        Args:
            epic_folder_name: Epic folder name.
            phase_name: Phase the ticket belongs to.
            ticket_data: Ticket fields (must include 'id' or 'task_id').

        Returns:
            True if inserted successfully.
        """
        task_id = ticket_data.get("id") or ticket_data.get("task_id", "")
        if not task_id:
            return False

        with self._retrying_lock:
            Ticket = Query()
            if self._tickets.search(
                (Ticket.epic_folder_name == epic_folder_name)
                & (Ticket.task_id == task_id)
            ):
                return False

            doc = {
                "epic_folder_name": epic_folder_name,
                "phase_name": phase_name,
                "task_id": task_id,
                "name": ticket_data.get("name", ""),
                "description": ticket_data.get("description", ""),
                "status": ticket_data.get("status", "proposed"),
                "agent": ticket_data.get("agent"),
                "inputs": ticket_data.get("inputs", []),
                "target_files": ticket_data.get("target_files", []),
                "guidance": ticket_data.get("guidance"),
                "completed_date": ticket_data.get("completed_date"),
                "success_criteria": ticket_data.get("success_criteria"),
                "story_ids": ticket_data.get("story_ids", []),
            }
            self._tickets.insert(doc)
        return True

    def delete_ticket(self, epic_folder_name: str, task_id: str) -> bool:
        """Remove a ticket from the database.

        Args:
            epic_folder_name: Epic folder name.
            task_id: Ticket identifier.

        Returns:
            True if the ticket was found and removed, False otherwise.
        """
        with self._retrying_lock:
            Ticket = Query()
            removed = self._tickets.remove(
                (Ticket.epic_folder_name == epic_folder_name)
                & (Ticket.task_id == task_id)
            )
        return len(removed) > 0

    def update_ticket(
        self, epic_folder_name: str, task_id: str, updates: dict
    ) -> bool:
        """Update arbitrary fields on a ticket.

        Args:
            epic_folder_name: Epic folder name.
            task_id: Ticket identifier.
            updates: Dictionary of fields to update.

        Returns:
            True if the ticket was found and updated.
        """
        with self._retrying_lock:
            Ticket = Query()
            updated = self._tickets.update(
                updates,
                (Ticket.epic_folder_name == epic_folder_name)
                & (Ticket.task_id == task_id),
            )
        return len(updated) > 0

    def get_current_ticket(self, epic_folder_name: str) -> Optional[TicketData]:
        """Get the current actionable ticket for an epic.

        Returns first in_progress ticket, or first pending ticket if none
        are in progress.

        Args:
            epic_folder_name: Epic folder name.

        Returns:
            TicketData if found, None otherwise.
        """
        Ticket = Query()

        # Try in_progress first
        in_progress = self._tickets.search(
            (Ticket.epic_folder_name == epic_folder_name)
            & (Ticket.status == "in_progress")
        )
        if in_progress:
            d = in_progress[0]
            return TicketData(
                id=d.get("task_id", ""),
                name=d.get("name", ""),
                description=d.get("description"),
                status=d.get("status"),
                agent=d.get("agent"),
                phase_name=d.get("phase_name"),
                inputs=d.get("inputs", []),
                target_files=d.get("target_files", []),
                guidance=d.get("guidance"),
                completed_date=d.get("completed_date"),
                success_criteria=d.get("success_criteria"),
                story_ids=d.get("story_ids", []),
            )

        # Fall back to first proposed (or legacy pending)
        pending = self._tickets.search(
            (Ticket.epic_folder_name == epic_folder_name)
            & (Ticket.status.test(lambda s: s in ("proposed", "pending")))
        )
        if pending:
            d = pending[0]
            return TicketData(
                id=d.get("task_id", ""),
                name=d.get("name", ""),
                description=d.get("description"),
                status=d.get("status"),
                agent=d.get("agent"),
                phase_name=d.get("phase_name"),
                inputs=d.get("inputs", []),
                target_files=d.get("target_files", []),
                guidance=d.get("guidance"),
                completed_date=d.get("completed_date"),
                success_criteria=d.get("success_criteria"),
                story_ids=d.get("story_ids", []),
            )

        return None

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def check_all_tickets_complete(self, epic_folder_name: str) -> bool:
        """Check whether every ticket for an epic has status "completed".

        Args:
            epic_folder_name: Folder name identifying the epic.

        Returns:
            True if all tickets are completed and at least one ticket exists.
            False if no tickets exist or any ticket is not completed.
        """
        Ticket = Query()
        all_tickets = self._tickets.search(Ticket.epic_folder_name == epic_folder_name)
        if not all_tickets:
            return False
        return all(t.get("status") == "completed" for t in all_tickets)

    def get_epic_branch(self, epic_folder_name: str) -> Optional[str]:
        """Get the branch associated with an epic.

        Args:
            epic_folder_name: Folder name identifying the epic.

        Returns:
            Branch name string, or None if not set or is main/master.
        """
        doc = self._find_epic_doc(epic_folder_name)
        if not doc:
            return None

        branch = doc.get("branch", "")
        if not branch or branch.strip() in ("", "main", "master"):
            return None
        return branch.strip()

    def get_ticket_counts(self, epic_folder_name: str) -> dict:
        """Get ticket status counts for an epic.

        Args:
            epic_folder_name: Folder name identifying the epic.

        Returns:
            Dict with keys: pending, in_progress, completed, total.
        """
        Ticket = Query()
        all_tickets = self._tickets.search(Ticket.epic_folder_name == epic_folder_name)

        counts = {"proposed": 0, "in_progress": 0, "completed": 0, "total": 0}
        for t in all_tickets:
            status = t.get("status", "proposed")
            # Normalize legacy "pending" to "proposed"
            if status == "pending":
                status = "proposed"
            if status in counts:
                counts[status] += 1
            counts["total"] += 1
        return counts

    # ------------------------------------------------------------------
    # Phase CRUD
    # ------------------------------------------------------------------

    def add_phase(self, epic_folder_name: str, phase_data: dict) -> bool:
        """Add a new phase to the database.

        Args:
            epic_folder_name: Epic folder name.
            phase_data: Phase fields. Must include 'name'.

        Returns:
            True if inserted successfully, False if name missing or duplicate.
        """
        phase_name = phase_data.get("name", "")
        if not phase_name:
            return False

        with self._retrying_lock:
            Phase = Query()

            # Primary key check: reject duplicate phase_id
            phase_id = phase_data.get("phase_id", "")
            if phase_id:
                existing_by_id = self._phases.search(
                    (Phase.epic_folder_name == epic_folder_name)
                    & (Phase.phase_id == phase_id)
                )
                if existing_by_id:
                    return False

            # Secondary guard: reject duplicate phase_name
            existing = self._phases.search(
                (Phase.epic_folder_name == epic_folder_name)
                & (Phase.phase_name == phase_name)
            )
            if existing:
                return False

            all_phases = self._phases.search(Phase.epic_folder_name == epic_folder_name)
            max_order = max((p.get("_order", 0) for p in all_phases), default=-1)

            self._phases.insert({
                "epic_folder_name": epic_folder_name,
                "phase_name": phase_name,
                "phase_id": phase_data.get("phase_id", ""),
                "execution": phase_data.get("execution", "sequential"),
                "description": phase_data.get("description", ""),
                "status": phase_data.get("status", "pending"),
                "agent": phase_data.get("agent"),
                "loop_type": phase_data.get("loop_type"),
                "loop_max_iterations": phase_data.get("loop_max_iterations"),
                "max_turns": phase_data.get("max_turns"),
                "timeout": phase_data.get("timeout"),
                "feedback_triggers": phase_data.get("feedback_triggers") or {},
                "_order": max_order + 1,
            })
        return True

    def update_phase(
        self, epic_folder_name: str, phase_name: str, updates: dict
    ) -> bool:
        """Update fields on an existing phase document.

        Args:
            epic_folder_name: Epic folder name.
            phase_name: Phase name or phase_id to update.
            updates: Dictionary of fields to update.

        Returns:
            True if the phase was found and updated.
        """
        # Resolve by phase_id or phase_name via get_phase()
        phase_obj = self.get_phase(epic_folder_name, phase_name)
        if phase_obj is None:
            return False
        actual_name = phase_obj.name
        with self._retrying_lock:
            Phase = Query()
            updated = self._phases.update(
                updates,
                (Phase.epic_folder_name == epic_folder_name)
                & (Phase.phase_name == actual_name),
            )
        return len(updated) > 0

    def delete_phase(self, epic_folder_name: str, phase_name: str) -> bool:
        """Remove a phase from the database.

        Args:
            epic_folder_name: Epic folder name.
            phase_name: Phase name or phase_id to remove.

        Returns:
            True if the phase was found and removed, False otherwise.
        """
        # Resolve to actual phase document (may be passed as phase_id)
        phase_obj = self.get_phase(epic_folder_name, phase_name)
        if phase_obj is None:
            return False
        with self._retrying_lock:
            Phase = Query()
            # Prefer deletion by phase_id (primary key) when available
            if phase_obj.phase_id:
                removed = self._phases.remove(
                    (Phase.epic_folder_name == epic_folder_name)
                    & (Phase.phase_id == phase_obj.phase_id)
                )
            else:
                removed = self._phases.remove(
                    (Phase.epic_folder_name == epic_folder_name)
                    & (Phase.phase_name == phase_obj.name)
                )
        return len(removed) > 0

    def get_tickets_for_phase(
        self, epic_folder_name: str, phase_name: str
    ) -> list[TicketData]:
        """Get all tickets belonging to a specific phase.

        Args:
            epic_folder_name: Epic folder name.
            phase_name: Phase name.

        Returns:
            List of TicketData objects for that phase.
        """
        Ticket = Query()
        docs = self._tickets.search(
            (Ticket.epic_folder_name == epic_folder_name)
            & (Ticket.phase_name == phase_name)
        )
        return [
            TicketData(
                id=d.get("task_id", ""),
                name=d.get("name", ""),
                description=d.get("description"),
                status=d.get("status"),
                agent=d.get("agent"),
                phase_name=d.get("phase_name"),
                inputs=d.get("inputs", []),
                target_files=d.get("target_files", []),
                guidance=d.get("guidance"),
                completed_date=d.get("completed_date"),
                success_criteria=d.get("success_criteria"),
                story_ids=d.get("story_ids", []),
            )
            for d in docs
        ]

    def list_phases(self, epic_folder_name: str) -> list[PhaseData]:
        """Return all phases for an epic, sorted by _order.

        Args:
            epic_folder_name: Epic folder name.

        Returns:
            List of PhaseData objects sorted by insertion order.
        """
        Phase = Query()
        docs = self._phases.search(Phase.epic_folder_name == epic_folder_name)
        docs.sort(key=lambda d: d.get("_order", 0))

        return [
            PhaseData(
                name=d.get("phase_name", ""),
                description=d.get("description"),
                execution=d.get("execution"),
                status=d.get("status"),
                agent=d.get("agent"),
                loop_type=d.get("loop_type"),
                loop_max_iterations=d.get("loop_max_iterations"),
                max_turns=d.get("max_turns"),
                timeout=d.get("timeout"),
                feedback_triggers=d.get("feedback_triggers") or {},
                phase_id=d.get("phase_id"),
            )
            for d in docs
        ]

    def get_phase(
        self, epic_folder_name: str, phase_name: str
    ) -> Optional[PhaseData]:
        """Get a single phase by name or phase_id.

        Args:
            epic_folder_name: Epic folder name.
            phase_name: Phase name or phase_id to look up.

        Returns:
            PhaseData if found, None otherwise.
        """
        Phase = Query()
        # Try phase_id first (primary key), then fall back to phase_name
        docs = self._phases.search(
            (Phase.epic_folder_name == epic_folder_name)
            & (Phase.phase_id == phase_name)
        )
        if not docs:
            docs = self._phases.search(
                (Phase.epic_folder_name == epic_folder_name)
                & (Phase.phase_name == phase_name)
            )
        if not docs:
            return None

        d = docs[0]
        return PhaseData(
            name=d.get("phase_name", ""),
            description=d.get("description"),
            execution=d.get("execution"),
            status=d.get("status"),
            agent=d.get("agent"),
            loop_type=d.get("loop_type"),
            loop_max_iterations=d.get("loop_max_iterations"),
            max_turns=d.get("max_turns"),
            timeout=d.get("timeout"),
            feedback_triggers=d.get("feedback_triggers") or {},
            phase_id=d.get("phase_id"),
        )

    def has_pending_phases(self, epic_folder_name: str) -> bool:
        """Check if an epic has any phases with pending or in_progress status.

        Args:
            epic_folder_name: Epic folder name.

        Returns:
            True if any phase is pending or in_progress.
        """
        Phase = Query()
        docs = self._phases.search(
            (Phase.epic_folder_name == epic_folder_name)
            & (Phase.status.test(lambda s: s in ("pending", "in_progress")))
        )
        return len(docs) > 0

    # ------------------------------------------------------------------
    # Story-Test Index
    # ------------------------------------------------------------------

    def sync_story_tests(self, mappings: dict[str, list[str]]) -> int:
        """Bulk upsert story-to-test mappings from a scan.

        Args:
            mappings: Dict of story_id -> list of test nodeids.

        Returns:
            Number of story records upserted.
        """
        now = datetime.now().isoformat()
        count = 0
        ST = Query()

        with self._retrying_lock:
            for story_id, test_nodeids in mappings.items():
                test_files = sorted({nid.split("::")[0] for nid in test_nodeids})
                doc = {
                    "story_id": story_id,
                    "test_functions": sorted(test_nodeids),
                    "test_files": test_files,
                    "last_synced": now,
                }
                existing = self._story_tests.search(ST.story_id == story_id)
                if existing:
                    self._story_tests.update(doc, ST.story_id == story_id)
                else:
                    self._story_tests.insert(doc)
                count += 1

        return count

    def get_tests_for_story(self, story_id: str) -> list[str]:
        """Get test nodeids for a story.

        Args:
            story_id: Story ID (e.g. 'US-CLI-110').

        Returns:
            List of test nodeid strings.
        """
        ST = Query()
        docs = self._story_tests.search(ST.story_id == story_id)
        if docs:
            return docs[0].get("test_functions", [])
        return []

    def get_stories_for_test(self, test_nodeid: str) -> list[str]:
        """Reverse lookup: find all story IDs linked to a test nodeid.

        Args:
            test_nodeid: Test node ID (e.g. 'tests/test_foo.py::test_bar').

        Returns:
            List of story ID strings.
        """
        story_ids = []
        for doc in self._story_tests.all():
            if test_nodeid in doc.get("test_functions", []):
                story_ids.append(doc["story_id"])
        return story_ids

    def get_uncovered_stories(self, all_story_ids: set[str]) -> list[str]:
        """Find stories with no linked tests.

        Args:
            all_story_ids: Complete set of known story IDs.

        Returns:
            Sorted list of story IDs that have no test mappings.
        """
        covered = {doc["story_id"] for doc in self._story_tests.all()}
        return sorted(all_story_ids - covered)

    def clear_story_tests(self) -> None:
        """Wipe the story_tests table for a full resync."""
        self._story_tests.truncate()

    # ------------------------------------------------------------------
    # Story-Code Index
    # ------------------------------------------------------------------

    def sync_story_code(self, mappings: dict[str, list[str]]) -> int:
        """Bulk upsert story-to-production-code mappings from a scan.

        Args:
            mappings: Dict of story_id -> list of code nodeids
                      (e.g. "rel/path.py::function_name").

        Returns:
            Number of story records upserted.
        """
        now = datetime.now().isoformat()
        count = 0
        SC = Query()

        with self._retrying_lock:
            for story_id, code_nodeids in mappings.items():
                code_files = sorted({nid.split("::")[0] for nid in code_nodeids})
                doc = {
                    "story_id": story_id,
                    "code_functions": sorted(code_nodeids),
                    "code_files": code_files,
                    "last_synced": now,
                }
                existing = self._story_code.search(SC.story_id == story_id)
                if existing:
                    self._story_code.update(doc, SC.story_id == story_id)
                else:
                    self._story_code.insert(doc)
                count += 1

        return count

    def get_code_for_story(self, story_id: str) -> list[str]:
        """Get production code nodeids for a story.

        Args:
            story_id: Story ID (e.g. 'US-CLI-110').

        Returns:
            List of code nodeid strings.
        """
        SC = Query()
        docs = self._story_code.search(SC.story_id == story_id)
        if docs:
            return docs[0].get("code_functions", [])
        return []

    def get_stories_for_code(self, code_nodeid: str) -> list[str]:
        """Reverse lookup: find all story IDs linked to a code nodeid.

        Args:
            code_nodeid: Code node ID (e.g. 'src/foo.py::bar').

        Returns:
            List of story ID strings.
        """
        story_ids = []
        for doc in self._story_code.all():
            if code_nodeid in doc.get("code_functions", []):
                story_ids.append(doc["story_id"])
        return story_ids

    def get_uncovered_stories_by_code(self, all_story_ids: set[str]) -> list[str]:
        """Find stories with no linked production code.

        Args:
            all_story_ids: Complete set of known story IDs.

        Returns:
            Sorted list of story IDs that have no code mappings.
        """
        covered = {doc["story_id"] for doc in self._story_code.all()}
        return sorted(all_story_ids - covered)

    def clear_story_code(self) -> None:
        """Wipe the story_code table for a full resync."""
        self._story_code.truncate()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_epic_doc(self, epic_id_or_name: str) -> Optional[dict]:
        """Find an epic document by full folder name or ID prefix.

        Args:
            epic_id_or_name: Full folder name (260203PS_plan_service) or
                             short ID prefix (260203PS).

        Returns:
            Epic document dict or None.
        """
        Epic = Query()

        # Exact match first
        docs = self._epics.search(Epic.epic_folder_name == epic_id_or_name)
        if docs:
            return docs[0]

        # Prefix match (8-char epic ID)
        docs = self._epics.search(
            Epic.epic_folder_name.test(
                lambda name: name.startswith(epic_id_or_name + "_")
            )
        )
        if len(docs) == 1:
            return docs[0]

        return None
