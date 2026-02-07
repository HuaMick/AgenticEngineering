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

    def __init__(self, plan_path: Path):
        """Initialize TaskService.

        Args:
            plan_path: Path to plan folder (e.g., docs/plans/live/260203TS_task_service/).
                       The service will look for plan_build.yml in this folder.
        """
        self.plan_path = plan_path
        self.plan_file = plan_path / "plan_build.yml"

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
            id=task_data.get("id", ""),
            name=task_data.get("name", ""),
            description=task_data.get("description", ""),
            status=status,
            agent=task_data.get("agent"),
            inputs=task_data.get("inputs", []),
            target_files=task_data.get("target_files", []),
            guidance=task_data.get("guidance"),
            completed_date=task_data.get("completed_date"),
        )

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID.

        Searches in phases[].tasks[] first, then falls back to root-level tasks[].

        Args:
            task_id: Task identifier to search for.

        Returns:
            Task dataclass if found, None otherwise.
        """
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
                    if task_data.get("id") == task_id:
                        return self._task_dict_to_dataclass(task_data)

        # Fall back to root-level tasks[] for backward compatibility
        root_tasks = data.get("tasks", [])
        for task_data in root_tasks:
            if task_data.get("id") == task_id:
                return self._task_dict_to_dataclass(task_data)

        return None

    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[Task]:
        """List all tasks, optionally filtered by status.

        Collects tasks from both phases[].tasks[] and root-level tasks[].

        Args:
            status: Optional status filter. If None, returns all tasks.

        Returns:
            List of Task dataclasses.
        """
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

        Returns first task with status=in_progress. If none found,
        returns first task with status=pending.

        Returns:
            Task dataclass if found, None if no actionable tasks.
        """
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
        """Update task status with atomic file locking.

        Args:
            task_id: Task identifier to update.
            status: New status to set.

        Returns:
            True if task was found and updated, False otherwise.
        """
        try:
            # Acquire lock for atomic read-modify-write
            with FileLock(self.plan_file):
                data = self._load_plan_file()
                task_found = False

                # Try to find and update task in phases[].tasks[]
                phases = data.get("phases", [])
                if phases:
                    for phase in phases:
                        tasks = phase.get("tasks", [])
                        for task_data in tasks:
                            if task_data.get("id") == task_id:
                                task_data["status"] = status.value
                                # Add completed_date if status is completed
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
                        if task_data.get("id") == task_id:
                            task_data["status"] = status.value
                            # Add completed_date if status is completed
                            if status == TaskStatus.COMPLETED:
                                task_data["completed_date"] = datetime.now().strftime("%Y-%m-%d")
                            task_found = True
                            break

                # Save if task was found
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
