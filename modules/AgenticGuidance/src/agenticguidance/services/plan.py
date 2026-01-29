"""Plan Movement Workflow - automated task and folder movement.

Handles physical movement of completed tasks to plan_completed.yml and
folder archival with git status verification and file locking.
"""

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml

from .state import FileLock


class MoveResult(Enum):
    """Result of a move operation."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class TaskMoveResult:
    """Result of moving a task."""

    task_id: str
    result: MoveResult
    message: str
    source_file: Optional[str] = None
    target_file: Optional[str] = None


@dataclass
class FolderMoveResult:
    """Result of moving a folder."""

    source: str
    destination: str
    result: MoveResult
    message: str


class GitSafetyChecker:
    """Check git status before potentially destructive operations."""

    def __init__(self, repo_path: Optional[Path] = None):
        """Initialize git safety checker.

        Args:
            repo_path: Path to git repository. Defaults to current directory.
        """
        self.repo_path = repo_path or Path.cwd()

    def has_uncommitted_changes(self, path: Optional[Path] = None) -> bool:
        """Check if there are uncommitted changes in a path.

        Args:
            path: Specific path to check. If None, checks entire repo.

        Returns:
            True if there are uncommitted changes.
        """
        cmd = ["git", "status", "--porcelain"]
        if path:
            cmd.append(str(path.relative_to(self.repo_path) if path.is_absolute() else path))

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError:
            return True  # Assume changes if git fails

    def is_clean(self) -> bool:
        """Check if the repository is clean (no uncommitted changes).

        Returns:
            True if repository has no uncommitted changes.
        """
        return not self.has_uncommitted_changes()

    def get_status(self, path: Optional[Path] = None) -> list[str]:
        """Get list of files with changes.

        Args:
            path: Specific path to check. If None, checks entire repo.

        Returns:
            List of file paths with changes.
        """
        cmd = ["git", "status", "--porcelain"]
        if path:
            cmd.append(str(path.relative_to(self.repo_path) if path.is_absolute() else path))

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return [line[3:] for line in result.stdout.strip().split("\n") if line]
        except subprocess.CalledProcessError:
            return []


class PlanMovementWorkflow:
    """Workflow for moving completed tasks and archiving plan folders.

    Provides safe operations for:
    - Moving completed tasks to plan_completed.yml
    - Archiving plan folders to completed/ directory
    - Validating git status before moves
    """

    def __init__(self, plan_path: Path, repo_path: Optional[Path] = None):
        """Initialize movement workflow.

        Args:
            plan_path: Path to the plan folder (e.g., docs/plans/live/260103AE_feature).
            repo_path: Path to git repository. Defaults to plan_path ancestor.
        """
        self.plan_path = plan_path
        # Flattened structure: YAML files are directly in plan_path, not nested
        self.completed_file = plan_path / "plan_completed.yml"

        # Find repo root
        self.repo_path = repo_path or self._find_repo_root(plan_path)
        self.git_checker = GitSafetyChecker(self.repo_path)

    @staticmethod
    def _find_repo_root(start: Path) -> Path:
        """Find git repository root from starting path."""
        current = start.resolve()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return start  # Fallback

    def move_task_to_completed(
        self,
        task_id: str,
        dry_run: bool = False,
        force: bool = False,
        silent: bool = False,
    ) -> TaskMoveResult:
        """Move a completed task to plan_completed.yml.

        Args:
            task_id: ID of the task to move.
            dry_run: If True, don't make any changes.
            force: If True, move even if git status is unclean.
            silent: If True, run without any user interaction (implies force=True).
                   Skips confirmation prompts and uses sensible defaults.

        Returns:
            TaskMoveResult with operation outcome.
        """
        # Silent mode implies force mode - no prompts, no git checks
        if silent:
            force = True
        # Find the task in plan files (directly in plan_path, flattened structure)
        task_data = None
        source_file = None

        for yaml_file in self.plan_path.glob("*.yml"):
            try:
                content = yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError:
                continue

            if not content:
                continue

            plan = content.get("plan", content.get("feature", {}))
            for key in ["phases", "implementation_steps", "tasks"]:
                items = plan.get(key, [])
                for i, item in enumerate(items):
                    if item.get("id") == task_id:
                        if item.get("status") != "completed":
                            return TaskMoveResult(
                                task_id=task_id,
                                result=MoveResult.SKIPPED,
                                message=f"Task status is '{item.get('status', 'unknown')}', not 'completed'",
                                source_file=yaml_file.name,
                            )
                        task_data = item.copy()
                        task_data["moved_at"] = datetime.now().isoformat()
                        task_data["moved_from"] = yaml_file.name
                        source_file = yaml_file
                        break
                if task_data:
                    break
            if task_data:
                break

        if not task_data:
            return TaskMoveResult(
                task_id=task_id,
                result=MoveResult.FAILED,
                message=f"Task '{task_id}' not found in any plan file",
            )

        # Check git status if not forcing
        if not force and self.git_checker.has_uncommitted_changes(source_file):
            return TaskMoveResult(
                task_id=task_id,
                result=MoveResult.SKIPPED,
                message="Uncommitted changes in source file. Use --force to override.",
                source_file=source_file.name,
            )

        if dry_run:
            return TaskMoveResult(
                task_id=task_id,
                result=MoveResult.SUCCESS,
                message="[dry-run] Would move task to plan_completed.yml",
                source_file=source_file.name,
                target_file="plan_completed.yml",
            )

        # Ensure plan_path exists (flattened structure)
        self.plan_path.mkdir(parents=True, exist_ok=True)

        # Use file lock for atomic operation
        with FileLock(self.completed_file):
            # Load or create completed file
            if self.completed_file.exists():
                try:
                    completed_data = yaml.safe_load(self.completed_file.read_text())
                except yaml.YAMLError:
                    completed_data = None
            else:
                completed_data = None

            if completed_data is None:
                completed_data = {
                    "completed_tasks": [],
                    "metadata": {
                        "created_at": datetime.now().isoformat(),
                        "version": 1,
                    },
                }

            if "completed_tasks" not in completed_data:
                completed_data["completed_tasks"] = []

            # Check for duplicate before appending
            existing_ids = {t.get("id") for t in completed_data["completed_tasks"] if t.get("id")}
            if task_id in existing_ids:
                return TaskMoveResult(
                    task_id=task_id,
                    result=MoveResult.SKIPPED,
                    message=f"Task '{task_id}' already exists in plan_completed.yml",
                    source_file=source_file.name,
                    target_file="plan_completed.yml",
                )

            # Add the task
            completed_data["completed_tasks"].append(task_data)
            completed_data["metadata"] = completed_data.get("metadata", {})
            completed_data["metadata"]["last_updated"] = datetime.now().isoformat()

            # Write completed file
            with open(self.completed_file, "w") as f:
                yaml.dump(completed_data, f, default_flow_style=False, sort_keys=False)

        # Remove the task from the source file to prevent duplicates
        removal_error = self._remove_task_from_source(source_file, task_id)
        if removal_error:
            return TaskMoveResult(
                task_id=task_id,
                result=MoveResult.SUCCESS,
                message=f"Task moved to plan_completed.yml (warning: {removal_error})",
                source_file=source_file.name,
                target_file="plan_completed.yml",
            )

        return TaskMoveResult(
            task_id=task_id,
            result=MoveResult.SUCCESS,
            message="Task moved to plan_completed.yml and removed from source",
            source_file=source_file.name,
            target_file="plan_completed.yml",
        )

    def _remove_task_from_source(self, source_file: Path, task_id: str) -> Optional[str]:
        """Remove a task from the source YAML file.

        Handles both flat task lists (plan.tasks, plan.implementation_steps)
        and nested tasks in phases (plan.phases[].tasks[]).

        Args:
            source_file: Path to the source YAML file.
            task_id: ID of the task to remove.

        Returns:
            None on success, error message string on failure.
        """
        try:
            content = yaml.safe_load(source_file.read_text())
        except yaml.YAMLError as e:
            return f"failed to parse source file: {e}"

        if not content:
            return "source file is empty"

        plan = content.get("plan", content.get("feature", {}))
        task_removed = False

        # Handle flat task lists (plan.tasks, plan.implementation_steps)
        for key in ["tasks", "implementation_steps"]:
            items = plan.get(key, [])
            if items:
                original_len = len(items)
                plan[key] = [item for item in items if item.get("id") != task_id]
                if len(plan[key]) < original_len:
                    task_removed = True
                    break

        # Handle nested tasks in phases (plan.phases[].tasks[])
        if not task_removed:
            phases = plan.get("phases", [])
            for phase in phases:
                phase_tasks = phase.get("tasks", [])
                if phase_tasks:
                    original_len = len(phase_tasks)
                    phase["tasks"] = [t for t in phase_tasks if t.get("id") != task_id]
                    if len(phase["tasks"]) < original_len:
                        task_removed = True
                        break

        if not task_removed:
            return f"task '{task_id}' not found in source file for removal"

        # Write back the modified content
        try:
            with open(source_file, "w") as f:
                yaml.dump(
                    content,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                    width=120,
                )
        except OSError as e:
            return f"failed to write source file: {e}"

        return None

    def move_all_completed_tasks(
        self,
        dry_run: bool = False,
        force: bool = False,
        silent: bool = False,
    ) -> list[TaskMoveResult]:
        """Move all completed tasks to plan_completed.yml.

        Args:
            dry_run: If True, don't make any changes.
            force: If True, move even if git status is unclean.
            silent: If True, run without any user interaction (implies force=True).
                   Skips confirmation prompts and uses sensible defaults.

        Returns:
            List of TaskMoveResult for each task.
        """
        # Silent mode implies force mode
        if silent:
            force = True
        results = []
        completed_task_ids = []

        # Find all completed tasks (directly in plan_path, flattened structure)
        for yaml_file in self.plan_path.glob("*.yml"):
            try:
                content = yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError:
                continue

            if not content:
                continue

            plan = content.get("plan", content.get("feature", {}))
            for key in ["phases", "implementation_steps", "tasks"]:
                items = plan.get(key, [])
                for item in items:
                    if item.get("status") == "completed" and item.get("id"):
                        completed_task_ids.append(item["id"])

        # Move each one
        for task_id in completed_task_ids:
            result = self.move_task_to_completed(task_id, dry_run=dry_run, force=force, silent=silent)
            results.append(result)

        return results

    def archive_plan_folder(
        self,
        dry_run: bool = False,
        force: bool = False,
        silent: bool = False,
    ) -> FolderMoveResult:
        """Archive the plan folder to docs/plans/completed/.

        Args:
            dry_run: If True, don't make any changes.
            force: If True, archive even if git status is unclean.
            silent: If True, run without any user interaction (implies force=True).
                   Skips confirmation prompts and uses sensible defaults.

        Returns:
            FolderMoveResult with operation outcome.
        """
        # Silent mode implies force mode - no prompts, no git checks
        if silent:
            force = True
        # Determine destination
        # Go up from docs/plans/live/FOLDER to docs/plans/completed/FOLDER
        dest_dir = self.plan_path.parent.parent / "completed" / self.plan_path.name

        # Check git status if not forcing
        if not force and self.git_checker.has_uncommitted_changes(self.plan_path):
            return FolderMoveResult(
                source=str(self.plan_path),
                destination=str(dest_dir),
                result=MoveResult.SKIPPED,
                message="Uncommitted changes in plan folder. Use --force to override.",
            )

        if dry_run:
            return FolderMoveResult(
                source=str(self.plan_path),
                destination=str(dest_dir),
                result=MoveResult.SUCCESS,
                message=f"[dry-run] Would archive to {dest_dir}",
            )

        # Check if destination exists
        if dest_dir.exists():
            return FolderMoveResult(
                source=str(self.plan_path),
                destination=str(dest_dir),
                result=MoveResult.SKIPPED,
                message=f"Destination already exists: {dest_dir}",
            )

        try:
            # Copy the folder
            shutil.copytree(self.plan_path, dest_dir)

            # Update archive metadata (flattened structure: plan_completed.yml in dest_dir)
            archive_meta_file = dest_dir / "plan_completed.yml"
            if archive_meta_file.exists():
                try:
                    data = yaml.safe_load(archive_meta_file.read_text())
                    if data is None:
                        data = {}
                except yaml.YAMLError:
                    data = {}

                data["archived_date"] = datetime.now().strftime("%Y-%m-%d")
                data["archived_from"] = str(self.plan_path)

                with open(archive_meta_file, "w") as f:
                    yaml.dump(data, f, default_flow_style=False)

            # Remove the source folder after successful copy
            rmtree_error = None
            try:
                shutil.rmtree(self.plan_path)
            except OSError as e:
                rmtree_error = str(e)

            if rmtree_error:
                return FolderMoveResult(
                    source=str(self.plan_path),
                    destination=str(dest_dir),
                    result=MoveResult.SUCCESS,
                    message=f"Archived to {dest_dir} (warning: failed to remove source: {rmtree_error})",
                )

            return FolderMoveResult(
                source=str(self.plan_path),
                destination=str(dest_dir),
                result=MoveResult.SUCCESS,
                message=f"Archived to {dest_dir}",
            )

        except OSError as e:
            return FolderMoveResult(
                source=str(self.plan_path),
                destination=str(dest_dir),
                result=MoveResult.FAILED,
                message=f"Archive failed: {e}",
            )

    def get_completed_tasks(self) -> list[dict]:
        """Get list of tasks marked as completed.

        Returns:
            List of task dictionaries with status='completed'.
        """
        completed = []

        for yaml_file in self.plan_path.glob("*.yml"):
            try:
                content = yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError:
                continue

            if not content:
                continue

            plan = content.get("plan", content.get("feature", {}))
            for key in ["phases", "implementation_steps", "tasks"]:
                items = plan.get(key, [])
                for item in items:
                    if item.get("status") == "completed":
                        task = item.copy()
                        task["_source_file"] = yaml_file.name
                        completed.append(task)

        return completed

    def get_archived_tasks(self) -> list[dict]:
        """Get list of tasks already in plan_completed.yml.

        Returns:
            List of archived task dictionaries.
        """
        if not self.completed_file.exists():
            return []

        try:
            data = yaml.safe_load(self.completed_file.read_text())
            return data.get("completed_tasks", []) if data else []
        except yaml.YAMLError:
            return []
