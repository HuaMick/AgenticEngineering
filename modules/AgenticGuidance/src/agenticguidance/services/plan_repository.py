"""Plan Repository - TinyDB-backed storage for plan data.

Provides a repository abstraction over TinyDB for fast plan/task/phase
queries while keeping YAML files as the git-committed source of truth.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from tinydb import Query, TinyDB

from .state import FileLock

from .plan import (
    PlanCreateResult,
    PlanData,
    PlanDeleteResult,
    PlanMetadata,
    PlanUpdateResult,
    PhaseData,
    TaskData,
)

logger = logging.getLogger(__name__)


class PlanRepository:
    """TinyDB-backed repository for plan data access.

    Manages three tables:
    - plans: one document per plan (keyed by plan_folder_name)
    - tasks: one document per task (keyed by plan_folder_name + task_id)
    - phases: one document per phase (keyed by plan_folder_name + phase_name)
    """

    def __init__(self, db_path: Optional[Path] = None, plans_base: Optional[Path] = None, auto_bootstrap: bool = True):
        """Initialize PlanRepository.

        Args:
            db_path: Path to TinyDB JSON file.
                     Defaults to ~/.agentic/plans.db.
            plans_base: Path to docs/plans folder for auto-bootstrap.
            auto_bootstrap: If True, populate empty DB with existing YAML plans.
        """
        if db_path is None:
            db_path = Path.home() / ".agentic" / "plans.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = FileLock(self.db_path)
        self._db = TinyDB(str(self.db_path))
        self._plans = self._db.table("plans")
        self._tasks = self._db.table("tasks")
        self._phases = self._db.table("phases")

        if auto_bootstrap and len(self._plans) == 0:
            base = plans_base
            if base is None:
                from .plan import PlanService
                base = PlanService._find_repo_root() / "docs" / "plans"
            
            if base.exists():
                logger.debug("Auto-bootstrapping PlanRepository from %s", base)
                self.import_all_yaml(base)

    def close(self):
        """Close the database."""
        self._db.close()

    # ------------------------------------------------------------------
    # Plan CRUD
    # ------------------------------------------------------------------

    def create_plan(self, plan_data: dict) -> PlanCreateResult:
        """Insert a new plan document.

        Args:
            plan_data: Dictionary with plan fields. Must include
                       'plan_folder_name' and 'plan_folder'.

        Returns:
            PlanCreateResult indicating success or failure.
        """
        plan_folder_name = plan_data.get("plan_folder_name", "")
        plan_folder = plan_data.get("plan_folder", "")

        if not plan_folder_name:
            return PlanCreateResult(
                plan_folder=Path(str(plan_folder)),
                plan_folder_name=plan_folder_name,
                success=False,
                message="plan_folder_name is required",
            )

        with self._lock:
            Plan = Query()
            if self._plans.search(Plan.plan_folder_name == plan_folder_name):
                return PlanCreateResult(
                    plan_folder=Path(str(plan_folder)),
                    plan_folder_name=plan_folder_name,
                    success=False,
                    message=f"Plan already exists in DB: {plan_folder_name}",
                )

            doc = {
                "plan_folder_name": plan_folder_name,
                "plan_folder": str(plan_folder),
                "name": plan_data.get("name", plan_folder_name),
                "worktree_path": plan_data.get("worktree_path", ""),
                "branch": plan_data.get("branch", ""),
                "status": plan_data.get("status", "pending"),
                "priority": plan_data.get("priority", "medium"),
                "objective": plan_data.get("objective", ""),
                "created": plan_data.get("created", datetime.now().strftime("%Y-%m-%d")),
                "context": plan_data.get("context", ""),
            }
            self._plans.insert(doc)

        return PlanCreateResult(
            plan_folder=Path(str(plan_folder)),
            plan_folder_name=plan_folder_name,
            success=True,
            message=f"Plan inserted into DB: {plan_folder_name}",
        )

    def get_plan(self, plan_id_or_name: str) -> Optional[PlanData]:
        """Retrieve a plan by folder name or short ID prefix.

        Args:
            plan_id_or_name: Full folder name or 8-char ID prefix.

        Returns:
            PlanData if found, None otherwise.
        """
        doc = self._find_plan_doc(plan_id_or_name)
        if not doc:
            return None

        plan_folder_name = doc["plan_folder_name"]

        # Gather phases and tasks from their tables
        Phase = Query()
        phase_docs = self._phases.search(Phase.plan_folder_name == plan_folder_name)
        phase_docs.sort(key=lambda d: d.get("_order", 0))

        Task = Query()
        task_docs = self._tasks.search(Task.plan_folder_name == plan_folder_name)

        # Build task lookup by phase
        tasks_by_phase: dict[str, list[TaskData]] = {}
        all_tasks: list[TaskData] = []
        for td in task_docs:
            task_obj = TaskData(
                id=td.get("task_id", ""),
                name=td.get("name", ""),
                description=td.get("description"),
                status=td.get("status"),
                agent=td.get("agent"),
                phase_name=td.get("phase_name"),
            )
            all_tasks.append(task_obj)
            phase_key = td.get("phase_name", "")
            tasks_by_phase.setdefault(phase_key, []).append(task_obj)

        phases: list[PhaseData] = []
        for pd in phase_docs:
            phase_name = pd.get("phase_name", "")
            phases.append(
                PhaseData(
                    name=phase_name,
                    description=pd.get("description"),
                    execution=pd.get("execution"),
                    status=pd.get("status"),
                    tasks=tasks_by_phase.get(phase_name, []),
                )
            )

        return PlanData(
            plan_folder=Path(doc.get("plan_folder", "")),
            plan_folder_name=plan_folder_name,
            objective=doc.get("objective"),
            status=doc.get("status"),
            branch=doc.get("branch"),
            phases=phases,
            tasks=all_tasks,
        )

    def list_plans(self, status: Optional[str] = None) -> list[PlanMetadata]:
        """List plans, optionally filtered by status.

        Args:
            status: If provided, filter to plans whose folder lives
                    under this status directory (e.g. 'live', 'completed').
                    Also matches the plan's own status field.

        Returns:
            List of PlanMetadata sorted newest-first by folder name.
        """
        if status:
            Plan = Query()
            # Match either the status field value or plans whose folder
            # path contains the status directory segment.
            docs = self._plans.search(
                (Plan.status == status)
                | Plan.plan_folder.test(lambda pf: f"/plans/{status}/" in pf)
            )
        else:
            docs = self._plans.all()

        results = []
        for doc in docs:
            results.append(
                PlanMetadata(
                    plan_folder=Path(doc.get("plan_folder", "")),
                    plan_folder_name=doc["plan_folder_name"],
                    objective=doc.get("objective"),
                    status=doc.get("status"),
                    created=doc.get("created"),
                )
            )

        results.sort(key=lambda m: m.plan_folder_name, reverse=True)
        return results

    def update_plan(self, plan_folder_name: str, updates: dict) -> PlanUpdateResult:
        """Update fields on an existing plan document.

        Args:
            plan_folder_name: Folder name identifying the plan.
            updates: Dictionary of fields to update.

        Returns:
            PlanUpdateResult indicating success or failure.
        """
        with self._lock:
            doc = self._find_plan_doc(plan_folder_name)
            if not doc:
                return PlanUpdateResult(
                    success=False,
                    message=f"Plan not found in DB: {plan_folder_name}",
                )

            old_status = doc.get("status")
            Plan = Query()
            self._plans.update(updates, Plan.plan_folder_name == doc["plan_folder_name"])

        new_status = updates.get("status", old_status)
        return PlanUpdateResult(
            success=True,
            message=f"Plan updated in DB: {doc['plan_folder_name']}",
            plan_folder=doc.get("plan_folder"),
            old_status=old_status,
            new_status=new_status,
        )

    def delete_plan(self, plan_folder_name: str) -> PlanDeleteResult:
        """Remove a plan and all its tasks/phases from the database.

        Args:
            plan_folder_name: Folder name identifying the plan.

        Returns:
            PlanDeleteResult indicating success or failure.
        """
        with self._lock:
            doc = self._find_plan_doc(plan_folder_name)
            if not doc:
                return PlanDeleteResult(
                    success=False,
                    message=f"Plan not found in DB: {plan_folder_name}",
                )

            actual_name = doc["plan_folder_name"]
            Q = Query()
            self._plans.remove(Q.plan_folder_name == actual_name)
            self._tasks.remove(Q.plan_folder_name == actual_name)
            self._phases.remove(Q.plan_folder_name == actual_name)

        return PlanDeleteResult(
            success=True,
            message=f"Plan and associated data removed from DB: {actual_name}",
        )

    def resync_plan_folder(self, plan_folder_name: str, new_folder: str) -> bool:
        """Update plan_folder path and re-import tasks/phases from new location.

        Called when a stale TinyDB path is detected (e.g. plan was resurrected
        from completed/ back to live/).

        Args:
            plan_folder_name: Folder name identifying the plan.
            new_folder: New filesystem path for the plan folder.

        Returns:
            True if the resync succeeded.
        """
        doc = self._find_plan_doc(plan_folder_name)
        if not doc:
            return False

        new_path = Path(new_folder)
        if not new_path.is_dir():
            return False

        # Update the plan_folder path
        actual_name = doc["plan_folder_name"]
        with self._lock:
            Plan = Query()
            self._plans.update(
                {"plan_folder": str(new_path)},
                Plan.plan_folder_name == actual_name,
            )

        # Re-import tasks and phases from the new location
        try:
            self.import_from_yaml(new_path)
        except Exception:
            logger.warning(
                "resync_plan_folder: re-import failed for %s", actual_name, exc_info=True
            )

        return True

    # ------------------------------------------------------------------
    # Task CRUD
    # ------------------------------------------------------------------

    def get_tasks(
        self,
        plan_folder_name: str,
        status_filter: Optional[str] = None,
    ) -> list[TaskData]:
        """Get all tasks for a plan.

        Args:
            plan_folder_name: Plan folder name.
            status_filter: Optional status string to filter by.

        Returns:
            List of TaskData objects.
        """
        Task = Query()
        if status_filter:
            docs = self._tasks.search(
                (Task.plan_folder_name == plan_folder_name)
                & (Task.status == status_filter)
            )
        else:
            docs = self._tasks.search(Task.plan_folder_name == plan_folder_name)

        return [
            TaskData(
                id=d.get("task_id", ""),
                name=d.get("name", ""),
                description=d.get("description"),
                status=d.get("status"),
                agent=d.get("agent"),
                phase_name=d.get("phase_name"),
            )
            for d in docs
        ]

    def get_task(
        self, plan_folder_name: str, task_id: str
    ) -> Optional[TaskData]:
        """Get a single task.

        Args:
            plan_folder_name: Plan folder name.
            task_id: Task identifier.

        Returns:
            TaskData if found, None otherwise.
        """
        Task = Query()
        docs = self._tasks.search(
            (Task.plan_folder_name == plan_folder_name)
            & (Task.task_id == task_id)
        )
        if not docs:
            return None

        d = docs[0]
        return TaskData(
            id=d.get("task_id", ""),
            name=d.get("name", ""),
            description=d.get("description"),
            status=d.get("status"),
            agent=d.get("agent"),
            phase_name=d.get("phase_name"),
        )

    def update_task_status(
        self, plan_folder_name: str, task_id: str, new_status: str
    ) -> bool:
        """Update a task's status.

        Automatically sets completed_date when status is "completed".

        Args:
            plan_folder_name: Plan folder name.
            task_id: Task identifier.
            new_status: New status value.

        Returns:
            True if the task was found and updated.
        """
        updates = {"status": new_status}
        if new_status == "completed":
            updates["completed_date"] = datetime.now().strftime("%Y-%m-%d")
        with self._lock:
            Task = Query()
            updated = self._tasks.update(
                updates,
                (Task.plan_folder_name == plan_folder_name) & (Task.task_id == task_id),
            )
        return len(updated) > 0

    def add_task(
        self, plan_folder_name: str, phase_name: str, task_data: dict
    ) -> bool:
        """Add a task to the database.

        Args:
            plan_folder_name: Plan folder name.
            phase_name: Phase the task belongs to.
            task_data: Task fields (must include 'id' or 'task_id').

        Returns:
            True if inserted successfully.
        """
        task_id = task_data.get("id") or task_data.get("task_id", "")
        if not task_id:
            return False

        with self._lock:
            # Check for duplicates
            Task = Query()
            if self._tasks.search(
                (Task.plan_folder_name == plan_folder_name) & (Task.task_id == task_id)
            ):
                return False

            doc = {
                "plan_folder_name": plan_folder_name,
                "phase_name": phase_name,
                "task_id": task_id,
                "name": task_data.get("name", ""),
                "description": task_data.get("description", ""),
                "status": task_data.get("status", "pending"),
                "agent": task_data.get("agent"),
                "inputs": task_data.get("inputs", []),
                "target_files": task_data.get("target_files", []),
                "guidance": task_data.get("guidance"),
                "completed_date": task_data.get("completed_date"),
            }
            self._tasks.insert(doc)
        return True

    def get_current_task(self, plan_folder_name: str) -> Optional[TaskData]:
        """Get the current actionable task for a plan.

        Returns first in_progress task, or first pending task if none
        are in progress.

        Args:
            plan_folder_name: Plan folder name.

        Returns:
            TaskData if found, None otherwise.
        """
        Task = Query()

        # Try in_progress first
        in_progress = self._tasks.search(
            (Task.plan_folder_name == plan_folder_name)
            & (Task.status == "in_progress")
        )
        if in_progress:
            d = in_progress[0]
            return TaskData(
                id=d.get("task_id", ""),
                name=d.get("name", ""),
                description=d.get("description"),
                status=d.get("status"),
                agent=d.get("agent"),
                phase_name=d.get("phase_name"),
            )

        # Fall back to first pending
        pending = self._tasks.search(
            (Task.plan_folder_name == plan_folder_name)
            & (Task.status == "pending")
        )
        if pending:
            d = pending[0]
            return TaskData(
                id=d.get("task_id", ""),
                name=d.get("name", ""),
                description=d.get("description"),
                status=d.get("status"),
                agent=d.get("agent"),
                phase_name=d.get("phase_name"),
            )

        return None

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def import_from_yaml(self, plan_folder: Path) -> bool:
        """Import a single plan from its YAML files into TinyDB.

        Reads all plan_*.yml files in the folder, extracts plan metadata,
        phases, and tasks, and upserts them into the database.

        Args:
            plan_folder: Path to a plan folder containing plan_*.yml files.

        Returns:
            True if import succeeded, False on error.
        """
        if not plan_folder.is_dir():
            return False

        plan_folder_name = plan_folder.name
        plan_files = list(plan_folder.glob("plan_*.yml"))
        if not plan_files:
            return False

        # Merge all plan_*.yml into a single dict (last value wins)
        merged: dict = {}
        for pf in sorted(plan_files):
            try:
                data = yaml.safe_load(pf.read_text())
                if data and isinstance(data, dict):
                    merged.update(data)
            except (yaml.YAMLError, OSError):
                continue

        if not merged:
            return False

        # ------ Upsert plan document, phases, and tasks under lock ------
        with self._lock:
            Plan = Query()
            plan_doc = {
                "plan_folder_name": plan_folder_name,
                "plan_folder": str(plan_folder),
                "name": merged.get("name", plan_folder_name),
                "worktree_path": merged.get("worktree_path", ""),
                "branch": merged.get("branch", ""),
                "status": merged.get("status", "pending"),
                "priority": merged.get("priority", "medium"),
                "objective": merged.get("objective", merged.get("context", "")),
                "created": merged.get("created", ""),
                "context": merged.get("context", ""),
            }

            existing = self._plans.search(Plan.plan_folder_name == plan_folder_name)
            if existing:
                self._plans.update(plan_doc, Plan.plan_folder_name == plan_folder_name)
            else:
                self._plans.insert(plan_doc)

            # Remove old phases/tasks for this plan (idempotent reimport)
            Q = Query()
            self._phases.remove(Q.plan_folder_name == plan_folder_name)
            self._tasks.remove(Q.plan_folder_name == plan_folder_name)

            phases_data = merged.get("phases", [])
            for order, phase in enumerate(phases_data):
                # Skip non-dict phases (legacy plans may have string entries)
                if not isinstance(phase, dict):
                    continue
                phase_name = phase.get("name", f"Phase {order + 1}")

                self._phases.insert(
                    {
                        "plan_folder_name": plan_folder_name,
                        "phase_name": phase_name,
                        "execution": phase.get("execution"),
                        "description": phase.get("description"),
                        "status": phase.get("status"),
                        "_order": order,
                    }
                )

                for task in phase.get("tasks", []):
                    task_id = task.get("id") or task.get("task_id", "")
                    if not task_id:
                        continue
                    self._tasks.insert(
                        {
                            "plan_folder_name": plan_folder_name,
                            "phase_name": phase_name,
                            "task_id": task_id,
                            "name": task.get("name", ""),
                            "description": task.get("description", ""),
                            "status": task.get("status", "pending"),
                            "agent": task.get("agent"),
                            "inputs": task.get("inputs", []),
                            "target_files": task.get("target_files", []),
                            "guidance": task.get("guidance"),
                            "completed_date": task.get("completed_date"),
                        }
                    )

        return True

    def export_to_yaml(self, plan_folder_name: str, output_folder: Path) -> bool:
        """Export a plan from TinyDB to YAML files.

        Writes a plan_build.yml containing all plan data, phases, and tasks.

        Args:
            plan_folder_name: Plan folder name in the database.
            output_folder: Directory to write YAML files into.

        Returns:
            True if export succeeded, False on error.
        """
        doc = self._find_plan_doc(plan_folder_name)
        if not doc:
            return False

        actual_name = doc["plan_folder_name"]
        output_folder.mkdir(parents=True, exist_ok=True)

        Phase = Query()
        phase_docs = self._phases.search(Phase.plan_folder_name == actual_name)
        phase_docs.sort(key=lambda d: d.get("_order", 0))

        Task = Query()
        task_docs = self._tasks.search(Task.plan_folder_name == actual_name)

        # Group tasks by phase
        tasks_by_phase: dict[str, list[dict]] = {}
        for td in task_docs:
            phase_key = td.get("phase_name", "")
            task_dict = {
                "id": td.get("task_id", ""),
                "name": td.get("name", ""),
                "description": td.get("description", ""),
                "status": td.get("status", "pending"),
                "agent": td.get("agent"),
            }
            # Only include non-None optional fields
            for key in ("inputs", "target_files", "guidance", "completed_date"):
                val = td.get(key)
                if val:
                    task_dict[key] = val
            tasks_by_phase.setdefault(phase_key, []).append(task_dict)

        phases_out = []
        for pd in phase_docs:
            phase_name = pd.get("phase_name", "")
            phase_dict: dict = {"name": phase_name}
            if pd.get("execution"):
                phase_dict["execution"] = pd["execution"]
            if pd.get("description"):
                phase_dict["description"] = pd["description"]
            phase_dict["tasks"] = tasks_by_phase.get(phase_name, [])
            phases_out.append(phase_dict)

        plan_out = {
            "name": doc.get("name", actual_name),
            "worktree_path": doc.get("worktree_path", ""),
            "branch": doc.get("branch", ""),
            "status": doc.get("status", "pending"),
            "priority": doc.get("priority", "medium"),
            "objective": doc.get("objective", ""),
            "created": doc.get("created", ""),
            "phases": phases_out,
        }

        out_file = output_folder / "plan_build.yml"
        try:
            with open(out_file, "w") as f:
                yaml.dump(
                    plan_out,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
            return True
        except OSError:
            return False

    def import_all_yaml(self, plans_base: Path) -> dict:
        """Import all plan folders under a plans base directory.

        Scans live/, completed/, and deferred/ subdirectories.

        Args:
            plans_base: Base path (e.g. <repo>/docs/plans).

        Returns:
            Stats dict: {'imported': N, 'skipped': N, 'failed': N}.
        """
        stats = {"imported": 0, "skipped": 0, "failed": 0}

        for status_dir in ("live", "completed", "deferred"):
            scan_dir = plans_base / status_dir
            if not scan_dir.is_dir():
                continue

            for folder in sorted(scan_dir.iterdir()):
                if not folder.is_dir():
                    continue
                # Must have at least one plan_*.yml
                if not list(folder.glob("plan_*.yml")):
                    stats["skipped"] += 1
                    continue

                try:
                    ok = self.import_from_yaml(folder)
                    if ok:
                        stats["imported"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception:
                    logger.warning("Failed to import plan: %s", folder.name, exc_info=True)
                    stats["failed"] += 1

        return stats

    def sync_to_yaml(self, plan_folder_name: str) -> bool:
        """Write current DB state for a plan back to its YAML folder.

        Uses the stored plan_folder path and writes plan_build.yml.

        Args:
            plan_folder_name: Plan folder name in the database.

        Returns:
            True if sync succeeded.
        """
        doc = self._find_plan_doc(plan_folder_name)
        if not doc:
            return False

        plan_folder = Path(doc.get("plan_folder", ""))
        if not plan_folder.is_dir():
            return False

        return self.export_to_yaml(plan_folder_name, plan_folder)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_plan_doc(self, plan_id_or_name: str) -> Optional[dict]:
        """Find a plan document by full folder name or ID prefix.

        Args:
            plan_id_or_name: Full folder name (260203PS_plan_service) or
                             short ID prefix (260203PS).

        Returns:
            Plan document dict or None.
        """
        Plan = Query()

        # Exact match first
        docs = self._plans.search(Plan.plan_folder_name == plan_id_or_name)
        if docs:
            return docs[0]

        # Prefix match (8-char plan ID)
        docs = self._plans.search(
            Plan.plan_folder_name.test(
                lambda name: name.startswith(plan_id_or_name + "_")
            )
        )
        if len(docs) == 1:
            return docs[0]

        return None
