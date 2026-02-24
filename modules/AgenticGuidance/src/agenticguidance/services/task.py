"""Task Service - CRUD operations for tasks in plan YAML files.

Provides programmatic access to task data within plan files, supporting both
modern (phases[].tasks[]) and legacy (plan.tasks[]) structures.
"""

import yaml
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from .state import FileLock


class TaskStatus(Enum):
    """Status of a task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class Task:
    """Task data structure from plan YAML files."""

    id: str
    name: str
    description: str
    status: TaskStatus
    agent: Optional[str] = None
    inputs: list[str] = field(default_factory=list)
    target_files: list[str] = field(default_factory=list)
    guidance: Optional[str] = None
    completed_date: Optional[str] = None


class TaskService:
    """Service for managing tasks in plan YAML files.

    Handles both modern (phases[].tasks[]) and legacy (tasks[]) plan structures
    with atomic file operations using FileLock.
    """

    def __init__(self, plan_path: Path, yaml_sync_enabled: bool = True):
        """Initialize TaskService.

        TinyDB is the primary data store for all writes. YAML files are
        optionally kept in sync for git visibility. If TinyDB is unavailable
        (import failure), YAML serves as emergency fallback.

        Args:
            plan_path: Path to plan folder (e.g., docs/plans/live/260203TS_task_service/).
                       The service will look for plan_build.yml in this folder.
            yaml_sync_enabled: If True, keep YAML files in sync with TinyDB
                              after writes. Defaults to True.
        """
        self.plan_path = plan_path
        self.plan_file = plan_path / "plan_build.yml"
        self._yaml_sync_enabled = yaml_sync_enabled
        self._plan_folder_name = plan_path.name  # For TinyDB lookups
        self._repository = None
        try:
            from .plan_repository import PlanRepository
            # Derive db_path from plan_path's repo root for test isolation
            repo_root = plan_path
            while repo_root != repo_root.parent:
                if (repo_root / ".git").exists():
                    break
                repo_root = repo_root.parent
            db_path = repo_root / ".agentic" / "plans.db"
            self._repository = PlanRepository(db_path=db_path)
        except Exception:
            pass  # Emergency: fall back to pure YAML

    def _load_plan_file(self) -> dict:
        """Load plan YAML file.

        Returns:
            Dictionary containing plan data with root-level keys.

        Raises:
            FileNotFoundError: If plan file doesn't exist.
            yaml.YAMLError: If YAML parsing fails.
        """
        if not self.plan_file.exists():
            raise FileNotFoundError(f"Plan file not found: {self.plan_file}")

        with open(self.plan_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            return {}

        return data

    def _save_plan_file(self, data: dict) -> None:
        """Save plan data to YAML file.

        Note: Caller is responsible for file locking if needed.

        Args:
            data: Plan data dictionary to save.
        """
        with open(self.plan_file, "w", encoding="utf-8") as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    @staticmethod
    def _get_task_id(task_data: dict) -> str:
        """Extract task ID from dict, checking both 'id' and 'task_id' keys."""
        return task_data.get("id") or task_data.get("task_id") or ""

    def _task_dict_to_dataclass(self, task_data: dict) -> Task:
        """Convert task dictionary to Task dataclass.

        Args:
            task_data: Raw task dictionary from YAML.

        Returns:
            Task dataclass instance.
        """
        # Parse status enum
        status_str = task_data.get("status", "pending")
        try:
            status = TaskStatus(status_str)
        except ValueError:
            # Default to pending if status is invalid
            status = TaskStatus.PENDING

        return Task(
            id=self._get_task_id(task_data),
            name=task_data.get("name", ""),
            description=task_data.get("description", ""),
            status=status,
            agent=task_data.get("agent"),
            inputs=task_data.get("inputs") or task_data.get("file_inputs", []),
            target_files=task_data.get("target_files", []),
            guidance=task_data.get("guidance"),
            completed_date=task_data.get("completed_date"),
        )

    def _taskdata_to_task(self, td) -> Optional[Task]:
        """Convert PlanRepository's TaskData to the Task dataclass.

        Args:
            td: TaskData instance from PlanRepository, or None.

        Returns:
            Task dataclass if td is not None, None otherwise.
        """
        if td is None:
            return None
        try:
            status = TaskStatus(td.status) if td.status else TaskStatus.PENDING
        except ValueError:
            status = TaskStatus.PENDING
        return Task(
            id=td.id,
            name=td.name,
            description=td.description or "",
            status=status,
            agent=td.agent,
            inputs=td.inputs or [],
            target_files=td.target_files or [],
            guidance=td.guidance,
            completed_date=td.completed_date,
        )

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID.

        Reads from YAML to get full task details.
        Searches in phases[].tasks[] first, then root-level tasks[].

        Args:
            task_id: Task identifier to search for.

        Returns:
            Task dataclass if found, None otherwise.
        """
        # Always use YAML for get_task - needs full detail (inputs, guidance, etc.)
        try:
            data = self._load_plan_file()
        except (FileNotFoundError, yaml.YAMLError):
            return None

        # Search in phases[].tasks[]
        phases = data.get("phases", [])
        if phases:
            for phase in phases:
                tasks = phase.get("tasks", [])
                for task_data in tasks:
                    if self._get_task_id(task_data) == task_id:
                        return self._task_dict_to_dataclass(task_data)

        # Fall back to root-level tasks[] for backward compatibility
        root_tasks = data.get("tasks", [])
        for task_data in root_tasks:
            if self._get_task_id(task_data) == task_id:
                return self._task_dict_to_dataclass(task_data)

        return None

    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[Task]:
        """List all tasks, optionally filtered by status.

        Tries TinyDB first if available, then falls back to YAML.
        Collects tasks from both phases[].tasks[] and root-level tasks[].

        Args:
            status: Optional status filter. If None, returns all tasks.

        Returns:
            List of Task dataclasses.
        """
        # Try TinyDB first - only trust the result if the plan is confirmed in DB
        # (an empty list may mean plan was never imported, not that it has no tasks)
        if self._repository is not None:
            try:
                plan_in_db = self._repository.get_plan(self._plan_folder_name) is not None
                if plan_in_db:
                    status_filter = status.value if status is not None else None
                    tdb_tasks = self._repository.get_tasks(self._plan_folder_name, status_filter)
                    return [self._taskdata_to_task(td) for td in tdb_tasks]
            except Exception:
                pass

        try:
            data = self._load_plan_file()
        except (FileNotFoundError, yaml.YAMLError):
            return []

        all_tasks = []

        # Collect from phases[].tasks[]
        phases = data.get("phases", [])
        if phases:
            for phase in phases:
                tasks = phase.get("tasks", [])
                for task_data in tasks:
                    task = self._task_dict_to_dataclass(task_data)
                    all_tasks.append(task)

        # Collect from root-level tasks[]
        root_tasks = data.get("tasks", [])
        for task_data in root_tasks:
            task = self._task_dict_to_dataclass(task_data)
            all_tasks.append(task)

        # Filter by status if provided
        if status is not None:
            all_tasks = [t for t in all_tasks if t.status == status]

        return all_tasks

    def get_current_task(self) -> Optional[Task]:
        """Get the current actionable task.

        Tries TinyDB first if available, then falls back to YAML.
        Returns first task with status=in_progress. If none found,
        returns first task with status=pending.

        Returns:
            Task dataclass if found, None if no actionable tasks.
        """
        # Try TinyDB first
        if self._repository is not None:
            try:
                td = self._repository.get_current_task(self._plan_folder_name)
                if td is not None:
                    return self._taskdata_to_task(td)
            except Exception:
                pass

        try:
            data = self._load_plan_file()
        except (FileNotFoundError, yaml.YAMLError):
            return None

        # First pass: look for in_progress tasks
        in_progress_task = None
        pending_task = None

        # Search in phases[].tasks[]
        phases = data.get("phases", [])
        if phases:
            for phase in phases:
                tasks = phase.get("tasks", [])
                for task_data in tasks:
                    task = self._task_dict_to_dataclass(task_data)
                    if task.status == TaskStatus.IN_PROGRESS and in_progress_task is None:
                        in_progress_task = task
                    elif task.status == TaskStatus.PENDING and pending_task is None:
                        pending_task = task

        # Search in root-level tasks[]
        root_tasks = data.get("tasks", [])
        for task_data in root_tasks:
            task = self._task_dict_to_dataclass(task_data)
            if task.status == TaskStatus.IN_PROGRESS and in_progress_task is None:
                in_progress_task = task
            elif task.status == TaskStatus.PENDING and pending_task is None:
                pending_task = task

        # Return in_progress first, then pending, then None
        return in_progress_task or pending_task

    def update_task_status(self, task_id: str, status: TaskStatus) -> bool:
        """Update task status. TinyDB is primary, YAML sync is optional.

        Writes to TinyDB via PlanRepository first (which handles its own
        FileLock). Optionally syncs YAML for git visibility. Falls back
        to direct YAML writes only if TinyDB is unavailable.

        Args:
            task_id: Task identifier to update.
            status: New status to set.

        Returns:
            True if task was found and updated, False otherwise.
        """
        # TinyDB-first: write via repository (handles its own locking)
        if self._repository is not None:
            try:
                updated = self._repository.update_task_status(
                    self._plan_folder_name, task_id, status.value
                )
                if not updated:
                    return False
                # Optionally sync to YAML for git visibility
                if self._yaml_sync_enabled:
                    try:
                        self._repository.sync_to_yaml(self._plan_folder_name)
                    except Exception:
                        pass  # YAML sync failure is non-fatal
                return True
            except Exception:
                pass  # Fall through to YAML emergency fallback

        # Emergency YAML fallback (only when repository import failed)
        return self._update_task_status_yaml(task_id, status)

    def _update_task_status_yaml(self, task_id: str, status: TaskStatus) -> bool:
        """Emergency YAML fallback for task status updates.

        Used only when PlanRepository is unavailable (import failure at init).
        """
        try:
            with FileLock(self.plan_file):
                data = self._load_plan_file()
                task_found = False

                # Try to find and update task in phases[].tasks[]
                phases = data.get("phases", [])
                if phases:
                    for phase in phases:
                        tasks = phase.get("tasks", [])
                        for task_data in tasks:
                            if self._get_task_id(task_data) == task_id:
                                task_data["status"] = status.value
                                if status == TaskStatus.COMPLETED:
                                    task_data["completed_date"] = datetime.now().strftime("%Y-%m-%d")
                                task_found = True
                                break
                        if task_found:
                            break

                # If not found in phases, try root-level tasks[]
                if not task_found:
                    root_tasks = data.get("tasks", [])
                    for task_data in root_tasks:
                        if self._get_task_id(task_data) == task_id:
                            task_data["status"] = status.value
                            if status == TaskStatus.COMPLETED:
                                task_data["completed_date"] = datetime.now().strftime("%Y-%m-%d")
                            task_found = True
                            break

                if task_found:
                    self._save_plan_file(data)
                    return True

                return False

        except (FileNotFoundError, yaml.YAMLError):
            return False

    def start_task(self, task_id: str) -> bool:
        """Mark task as in_progress.

        Convenience wrapper for update_task_status with IN_PROGRESS status.

        Args:
            task_id: Task identifier to start.

        Returns:
            True if task was found and updated, False otherwise.
        """
        return self.update_task_status(task_id, TaskStatus.IN_PROGRESS)

    def complete_task(self, task_id: str) -> bool:
        """Mark task as completed with timestamp.

        Convenience wrapper for update_task_status with COMPLETED status.
        Automatically adds completed_date in ISO 8601 format (YYYY-MM-DD).

        Args:
            task_id: Task identifier to complete.

        Returns:
            True if task was found and updated, False otherwise.
        """
        return self.update_task_status(task_id, TaskStatus.COMPLETED)
