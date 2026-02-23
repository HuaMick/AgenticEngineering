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


# Data models for PlanService
@dataclass
class PlanCreateResult:
    """Result of creating a plan."""

    plan_folder: Path
    plan_folder_name: str
    success: bool
    message: str


@dataclass
class PlanData:
    """Complete plan data including phases and tasks."""

    plan_folder: Path
    plan_folder_name: str
    objective: Optional[str] = None
    status: Optional[str] = None
    branch: Optional[str] = None
    phases: list = None
    tasks: list = None

    def __post_init__(self):
        if self.phases is None:
            self.phases = []
        if self.tasks is None:
            self.tasks = []


@dataclass
class PlanMetadata:
    """Summary information about a plan."""

    plan_folder: Path
    plan_folder_name: str
    objective: Optional[str] = None
    status: Optional[str] = None
    created: Optional[str] = None


@dataclass
class PlanUpdateResult:
    """Result of updating a plan."""

    success: bool
    message: str
    plan_folder: Optional[str] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None


@dataclass
class PlanDeleteResult:
    """Result of deleting a plan."""

    success: bool
    message: str


@dataclass
class ValidationResult:
    """Result of validating plan structure."""

    valid: bool
    errors: list = None
    warnings: list = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


@dataclass
class PhaseData:
    """Data for a single phase."""

    name: str
    description: Optional[str] = None
    execution: Optional[str] = None
    status: Optional[str] = None
    tasks: list = None

    def __post_init__(self):
        if self.tasks is None:
            self.tasks = []


@dataclass
class TaskData:
    """Data for a single task."""

    id: str
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    agent: Optional[str] = None
    phase_name: Optional[str] = None


class PlanService:
    """Plan management service providing CRUD operations for plans.

    This service provides comprehensive plan management capabilities including:
    - Creating new plans with proper naming conventions
    - Retrieving plan data and metadata
    - Listing plans by status (live, completed, deferred)
    - Updating plan status
    - Extracting tasks and phases
    - Validating plan structure

    Examples:
        Create a new plan:
        >>> service = PlanService()
        >>> result = service.create_plan(
        ...     objective="Implement feature X",
        ...     branch="main",
        ...     description="feature_x"
        ... )
        >>> print(result.plan_folder_name)
        260203MA_feature_x

        Retrieve plan data:
        >>> plan = service.get_plan("260203MA")
        >>> print(plan.objective)
        Implement feature X

        List all live plans:
        >>> plans = service.list_plans(status="live")
        >>> for plan_meta in plans:
        ...     print(f"{plan_meta.plan_folder_name}: {plan_meta.objective}")

        Validate plan structure:
        >>> validation = service.validate_plan_structure(Path("docs/plans/live/260203MA_feature_x"))
        >>> if not validation.valid:
        ...     print(validation.errors)
    """

    def __init__(self, repo_path: Optional[Path] = None, yaml_sync_enabled: bool = True):
        """Initialize plan service.

        TinyDB is the primary data store. YAML files are optionally kept in sync
        for git-committed state. If TinyDB is unavailable (import failure),
        YAML serves as emergency fallback.

        Args:
            repo_path: Path to git repository. Defaults to auto-detected repo root.
            yaml_sync_enabled: If True, keep YAML files in sync with TinyDB for
                              git commits. Defaults to True.
        """
        self.repo_path = repo_path or self._find_repo_root()
        self.plans_base = self.repo_path / "docs" / "plans"
        self.git_checker = GitSafetyChecker(self.repo_path)
        self._yaml_sync_enabled = yaml_sync_enabled
        self._repository = None
        try:
            from .plan_repository import PlanRepository
            # Use repo-local DB so tests with tmp_path get isolated instances
            db_path = self.repo_path / ".agentic" / "plans.db"
            self._repository = PlanRepository(
                db_path=db_path,
                plans_base=self.plans_base,
            )
        except Exception:
            pass  # Emergency: fall back to pure YAML

    @staticmethod
    def _find_repo_root(start: Optional[Path] = None) -> Path:
        """Find git repository root from starting path.

        Args:
            start: Starting path for search. Defaults to current directory.

        Returns:
            Path to repository root.
        """
        current = (start or Path.cwd()).resolve()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return start or Path.cwd()

    def _generate_plan_folder_name(self, description: str, branch: str) -> str:
        """Generate plan folder name following YYMMDDXX_description convention.

        Args:
            description: Description part of the name.
            branch: Branch name to derive XX from.

        Returns:
            Plan folder name (e.g., "260203MA_feature_name").
        """
        # YYMMDD: Current date
        date_part = datetime.now().strftime("%y%m%d")

        # XX: 2 uppercase letters from branch
        branch_clean = branch.replace("-", "").replace("_", "").upper()
        if len(branch_clean) >= 2:
            branch_code = branch_clean[:2]
        elif len(branch_clean) == 1:
            branch_code = branch_clean + "X"
        else:
            branch_code = "XX"

        # Sanitize description: lowercase, underscores, max 50 chars
        desc_clean = description.lower()
        desc_clean = "".join(c if c.isalnum() or c == "_" else "_" for c in desc_clean)
        desc_clean = desc_clean[:50].strip("_")

        return f"{date_part}{branch_code}_{desc_clean}"

    def _normalize_plan_id(self, plan_id_or_path: str) -> str:
        """Normalize plan identifier to a folder name for repository lookup.

        Handles absolute paths, relative paths, folder names, and short IDs.

        Args:
            plan_id_or_path: Any plan identifier format.

        Returns:
            Folder name or short ID suitable for PlanRepository lookup.
        """
        if "/" in plan_id_or_path or Path(plan_id_or_path).is_absolute():
            return Path(plan_id_or_path).name
        return plan_id_or_path

    def create_plan(
        self,
        objective: str,
        branch: str,
        description: str,
        dry_run: bool = False,
    ) -> PlanCreateResult:
        """Create a new plan with scaffolding.

        Creates a new plan folder in docs/plans/live/ with:
        - Plan folder named according to YYMMDDXX_description convention
        - README.md with objective and status
        - plan_build.yml with basic structure

        Args:
            objective: Plan objective/goal.
            branch: Git branch name.
            description: Short description for folder name.
            dry_run: If True, don't create any files.

        Returns:
            PlanCreateResult with folder path and success status.
        """
        folder_name = self._generate_plan_folder_name(description, branch)
        plan_folder = self.plans_base / "live" / folder_name

        if plan_folder.exists():
            return PlanCreateResult(
                plan_folder=plan_folder,
                plan_folder_name=folder_name,
                success=False,
                message=f"Plan folder already exists: {folder_name}",
            )

        if dry_run:
            return PlanCreateResult(
                plan_folder=plan_folder,
                plan_folder_name=folder_name,
                success=True,
                message=f"[dry-run] Would create plan folder: {folder_name}",
            )

        plan_scaffold = {
            "name": folder_name.replace("_", "-"),
            "worktree_path": str(self.repo_path),
            "branch": branch,
            "status": "pending",
            "priority": "medium",
            "created": datetime.now().strftime("%Y-%m-%d"),
            "objective": objective,
            "phases": [],
            "success_criteria": [],
            "dependencies": [],
            "target_files": {"primary": [], "tests": []},
        }

        # TinyDB-first: write to repository as primary store
        if self._repository is not None:
            try:
                self._repository.create_plan({
                    "plan_folder_name": folder_name,
                    "plan_folder": str(plan_folder),
                    "name": plan_scaffold["name"],
                    "worktree_path": plan_scaffold["worktree_path"],
                    "branch": branch,
                    "status": "pending",
                    "priority": "medium",
                    "objective": objective,
                    "created": plan_scaffold["created"],
                })
            except Exception:
                pass  # Continue with YAML sync

        # YAML sync: create filesystem scaffold for git commits
        if self._yaml_sync_enabled:
            plan_folder.mkdir(parents=True, exist_ok=True)

            readme_content = f"""# {folder_name}

## Objective

{objective}

## Status

pending

## Branch

{branch}

## Created

{datetime.now().strftime("%Y-%m-%d")}
"""
            (plan_folder / "README.md").write_text(readme_content)

            with open(plan_folder / "plan_build.yml", "w") as f:
                yaml.dump(plan_scaffold, f, default_flow_style=False, sort_keys=False)

        return PlanCreateResult(
            plan_folder=plan_folder,
            plan_folder_name=folder_name,
            success=True,
            message=f"Created plan folder: {folder_name}",
        )

    def get_plan(self, plan_id_or_path: str) -> Optional[PlanData]:
        """Retrieve complete plan data.

        TinyDB is the primary store. YAML is only used as emergency fallback
        when TinyDB is unavailable (import failure at init).

        Supports multiple input formats:
        - Short ID: "260203PS"
        - Folder name: "260203PS_plan_service"
        - Relative path: "docs/plans/live/260203PS_plan_service"
        - Absolute path: "/home/code/.../docs/plans/live/260203PS_plan_service"

        Args:
            plan_id_or_path: Plan identifier or path.

        Returns:
            PlanData with phases and tasks, or None if not found.
        """
        if self._repository is not None:
            lookup_key = self._normalize_plan_id(plan_id_or_path)
            result = self._repository.get_plan(lookup_key)
            if result is not None:
                # Resurrection detection: if TinyDB has completed/ path but
                # live/ version exists, resync to the live path
                if result.plan_folder and "/completed/" in str(result.plan_folder):
                    live_path = self.plans_base / "live" / result.plan_folder_name
                    if live_path.exists():
                        self._repository.resync_plan_folder(
                            result.plan_folder_name, str(live_path)
                        )
                        # Update the result object directly (works with mocks too)
                        result.plan_folder = live_path
                return result

            # Read-through: plan may exist on disk but not in TinyDB yet
            # (e.g., created externally, git pull, or test fixture)
            plan_folder = self._resolve_plan_folder(plan_id_or_path)
            if plan_folder and plan_folder.exists():
                self._repository.import_from_yaml(plan_folder)
                return self._repository.get_plan(plan_folder.name)

            return None

        # Emergency YAML fallback (only when repository import failed)
        return self._get_plan_from_yaml(plan_id_or_path)

    def _get_plan_from_yaml(self, plan_id_or_path: str) -> Optional[PlanData]:
        """Emergency YAML fallback for get_plan when TinyDB is unavailable."""
        plan_folder = self._resolve_plan_folder(plan_id_or_path)
        if not plan_folder or not plan_folder.exists():
            return None

        plan_data = {}
        for plan_file in plan_folder.glob("plan_*.yml"):
            try:
                with open(plan_file) as f:
                    data = yaml.safe_load(f)
                if data:
                    plan_data.update(data)
            except (yaml.YAMLError, IOError):
                continue

        if not plan_data:
            return None

        phases_data = plan_data.get("phases", [])
        phases = []
        all_tasks = []

        for phase in phases_data:
            phase_tasks = phase.get("tasks", [])
            task_data_list = []

            for task in phase_tasks:
                task_obj = TaskData(
                    id=task.get("id", ""),
                    name=task.get("name", ""),
                    description=task.get("description"),
                    status=task.get("status"),
                    agent=task.get("agent"),
                    phase_name=phase.get("name"),
                )
                task_data_list.append(task_obj)
                all_tasks.append(task_obj)

            phases.append(PhaseData(
                name=phase.get("name", ""),
                description=phase.get("description"),
                execution=phase.get("execution"),
                status=phase.get("status"),
                tasks=task_data_list,
            ))

        return PlanData(
            plan_folder=plan_folder,
            plan_folder_name=plan_folder.name,
            objective=plan_data.get("objective"),
            status=plan_data.get("status"),
            branch=plan_data.get("branch"),
            phases=phases,
            tasks=all_tasks,
        )

    def _resolve_plan_folder(self, plan_id_or_path: str) -> Optional[Path]:
        """Resolve plan identifier or path to actual plan folder.

        Args:
            plan_id_or_path: Plan identifier or path.

        Returns:
            Path to plan folder or None.
        """
        # If it's an absolute path, use it directly
        path = Path(plan_id_or_path)
        if path.is_absolute() and path.exists():
            return path

        # If it's a relative path from repo root
        rel_path = self.repo_path / plan_id_or_path
        if rel_path.exists():
            return rel_path

        # Search in plans directories for matching ID or folder name
        for status in ["live", "completed", "deferred"]:
            plans_dir = self.plans_base / status
            if not plans_dir.exists():
                continue

            for folder in plans_dir.iterdir():
                if not folder.is_dir():
                    continue

                # Match by folder name or ID prefix
                if folder.name == plan_id_or_path or folder.name.startswith(plan_id_or_path + "_"):
                    return folder

        return None

    def list_plans(self, status: str = "live") -> list[PlanMetadata]:
        """List all plans with a given status.

        TinyDB is the primary store. YAML scan is only used as emergency
        fallback when TinyDB is unavailable.

        Args:
            status: Plan status folder (live, completed, deferred).

        Returns:
            List of PlanMetadata objects sorted by folder name (newest first).
        """
        if self._repository is not None:
            results = self._repository.list_plans(status=status)

            # Reconcile with filesystem: check for plans on disk that TinyDB
            # doesn't know about, and fix stale paths (resurrection detection)
            plans_dir = self.plans_base / status
            if plans_dir.exists():
                known_names = {r.plan_folder_name for r in results}
                disk_plans = []
                for folder in sorted(plans_dir.iterdir(), reverse=True):
                    if not folder.is_dir() or not list(folder.glob("plan_*.yml")):
                        continue
                    if folder.name not in known_names:
                        # Plan on disk but not in TinyDB for this status
                        self._repository.import_from_yaml(folder)
                        disk_plans.append(folder)

                # Also check if any TinyDB results have stale paths
                for r in results:
                    if r.plan_folder and f"/plans/{status}/" not in str(r.plan_folder):
                        correct_path = plans_dir / r.plan_folder_name
                        if correct_path.exists():
                            self._repository.resync_plan_folder(
                                r.plan_folder_name, str(correct_path)
                            )
                            r.plan_folder = correct_path

                if disk_plans:
                    # Re-fetch to include newly imported plans
                    fresh = self._repository.list_plans(status=status)
                    fresh_names = {f.plan_folder_name for f in fresh}
                    # Merge fresh results
                    for f in fresh:
                        if f.plan_folder_name not in known_names:
                            results.append(f)
                    # For any disk plans still missing from fresh (mock scenario),
                    # create minimal metadata entries
                    for folder in disk_plans:
                        if folder.name not in known_names and folder.name not in fresh_names:
                            results.append(PlanMetadata(
                                plan_folder=folder,
                                plan_folder_name=folder.name,
                            ))

            return results

        # Emergency YAML fallback (only when repository import failed)
        return self._list_plans_from_yaml(status)

    def _list_plans_from_yaml(self, status: str) -> list[PlanMetadata]:
        """Emergency YAML fallback for list_plans when TinyDB is unavailable."""
        plans_dir = self.plans_base / status
        if not plans_dir.exists():
            return []

        results = []

        for folder in sorted(plans_dir.iterdir(), key=lambda x: x.name, reverse=True):
            if not folder.is_dir():
                continue

            if not self._is_valid_plan_folder_name(folder.name):
                continue

            plan_meta = PlanMetadata(
                plan_folder=folder,
                plan_folder_name=folder.name,
            )

            for plan_file in folder.glob("plan_*.yml"):
                try:
                    with open(plan_file) as f:
                        data = yaml.safe_load(f)
                    if data:
                        plan_meta.objective = data.get("objective", plan_meta.objective)
                        plan_meta.status = data.get("status", plan_meta.status)
                        plan_meta.created = data.get("created", plan_meta.created)
                        break
                except (yaml.YAMLError, IOError):
                    continue

            results.append(plan_meta)

        return results

    def _is_valid_plan_folder_name(self, name: str) -> bool:
        """Check if folder name matches YYMMDDXX_description pattern.

        Args:
            name: Folder name to validate.

        Returns:
            True if valid.
        """
        if "_" not in name or len(name) < 10:
            return False

        prefix = name.split("_")[0]
        return len(prefix) == 8 and prefix[:6].isdigit() and prefix[6:].isalpha()

    def update_plan_status(
        self,
        plan_id: str,
        new_status: str,
        dry_run: bool = False,
    ) -> PlanUpdateResult:
        """Update plan status.

        TinyDB is the primary store. YAML files are optionally synced.

        Valid statuses: planning, active, partially_completed, fully_completed.

        Args:
            plan_id: Plan identifier or path.
            new_status: New status value.
            dry_run: If True, don't make any changes.

        Returns:
            PlanUpdateResult with update outcome.
        """
        valid_statuses = ["planning", "pending", "active", "completed", "partially_completed", "fully_completed", "blocked"]
        if new_status not in valid_statuses:
            return PlanUpdateResult(
                success=False,
                message=f"Invalid status: {new_status}. Valid: {', '.join(valid_statuses)}",
            )

        # Resolve plan and get old status
        if self._repository is not None:
            lookup_key = self._normalize_plan_id(plan_id)
            plan_data = self._repository.get_plan(lookup_key)
            if plan_data is None:
                # Read-through: try YAML import if plan exists on disk
                plan_folder = self._resolve_plan_folder(plan_id)
                if plan_folder and plan_folder.exists():
                    self._repository.import_from_yaml(plan_folder)
                    plan_data = self._repository.get_plan(plan_folder.name)
            if plan_data is None:
                return PlanUpdateResult(
                    success=False,
                    message=f"Plan not found: {plan_id}",
                )
            plan_folder = plan_data.plan_folder
            old_status = plan_data.status
        else:
            # Emergency YAML fallback
            plan_folder = self._resolve_plan_folder(plan_id)
            if not plan_folder or not plan_folder.exists():
                return PlanUpdateResult(
                    success=False,
                    message=f"Plan not found: {plan_id}",
                )
            old_status = None
            for plan_file in plan_folder.glob("plan_*.yml"):
                try:
                    with open(plan_file) as f:
                        data = yaml.safe_load(f)
                    if data and "status" in data:
                        old_status = data["status"]
                        break
                except (yaml.YAMLError, IOError):
                    continue

        if dry_run:
            return PlanUpdateResult(
                success=True,
                message=f"[dry-run] Would update status from {old_status} to {new_status}",
                plan_folder=str(plan_folder),
                old_status=old_status,
                new_status=new_status,
            )

        # TinyDB-first: update via repository
        if self._repository is not None:
            self._repository.update_plan(
                plan_data.plan_folder_name,
                {"status": new_status},
            )

        # YAML sync: update all plan files on disk
        if self._yaml_sync_enabled and plan_folder.exists():
            for plan_file in plan_folder.glob("plan_*.yml"):
                with FileLock(plan_file):
                    try:
                        with open(plan_file) as f:
                            data = yaml.safe_load(f)
                        if data:
                            data["status"] = new_status
                            with open(plan_file, "w") as f:
                                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                    except (yaml.YAMLError, IOError):
                        continue

        return PlanUpdateResult(
            success=True,
            message=f"Updated status from {old_status} to {new_status}",
            plan_folder=str(plan_folder),
            old_status=old_status,
            new_status=new_status,
        )

    def get_plan_tasks(
        self,
        plan_id: str,
        status_filter: Optional[str] = None,
    ) -> list[TaskData]:
        """Extract all tasks from a plan.

        TinyDB is the primary store. Delegates to repository for task queries.

        Args:
            plan_id: Plan identifier or path.
            status_filter: Optional status to filter by (pending, in_progress, completed, blocked).

        Returns:
            List of TaskData objects.
        """
        if self._repository is not None:
            lookup_key = self._normalize_plan_id(plan_id)
            plan = self._repository.get_plan(lookup_key)
            if plan is None:
                # Read-through: try YAML import
                plan_folder = self._resolve_plan_folder(plan_id)
                if plan_folder and plan_folder.exists():
                    self._repository.import_from_yaml(plan_folder)
                    plan = self._repository.get_plan(plan_folder.name)
            if plan is None:
                return []
            return self._repository.get_tasks(
                plan.plan_folder_name, status_filter=status_filter
            )

        # Emergency YAML fallback
        plan_data = self._get_plan_from_yaml(plan_id)
        if not plan_data:
            return []

        tasks = plan_data.tasks
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        return tasks

    def validate_plan_structure(self, plan_path: Path) -> ValidationResult:
        """Validate plan folder structure and content.

        Checks:
        - Folder naming convention (YYMMDDXX_description)
        - Plan files in folder root (not subdirectories)
        - Required fields present
        - Valid status values
        - Phase/task IDs unique

        Args:
            plan_path: Path to plan folder.

        Returns:
            ValidationResult with errors and warnings.
        """
        errors = []
        warnings = []

        # Check folder exists
        if not plan_path.exists():
            errors.append(f"Plan folder does not exist: {plan_path}")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Check folder naming convention
        if not self._is_valid_plan_folder_name(plan_path.name):
            errors.append(f"Folder name does not match YYMMDDXX_description pattern: {plan_path.name}")

        # Check for plan files in root
        plan_files = list(plan_path.glob("plan_*.yml"))
        if not plan_files:
            errors.append("No plan_*.yml files found in folder root")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Check plan files are not in subdirectories
        for subdir in plan_path.iterdir():
            if subdir.is_dir() and list(subdir.glob("plan_*.yml")):
                warnings.append(f"Found plan files in subdirectory: {subdir.name}")

        # Validate YAML structure
        required_fields = ["name", "status", "phases"]
        valid_statuses = ["planning", "pending", "active", "completed", "partially_completed", "fully_completed", "blocked"]

        all_task_ids = set()
        all_phase_ids = set()

        for plan_file in plan_files:
            try:
                with open(plan_file) as f:
                    data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                errors.append(f"Invalid YAML in {plan_file.name}: {e}")
                continue

            if not data:
                errors.append(f"Empty plan file: {plan_file.name}")
                continue

            # Skip scaffold templates (created by `agentic plan init`)
            if data.get("_template_status") == "stub":
                warnings.append(f"Scaffold template not yet populated: {plan_file.name}")
                continue

            # Skip completed-items tracking files
            if set(data.keys()) <= {"completed_items"}:
                continue

            # Check for root-level tasks: key (tasks must be nested under phases[].tasks[])
            if "tasks" in data:
                errors.append(
                    f"Root-level 'tasks' key found in {plan_file.name}. "
                    "Tasks must be nested under phases[].tasks[], not at the root level."
                )

            # Check required fields
            for field in required_fields:
                if field not in data:
                    errors.append(f"Missing required field '{field}' in {plan_file.name}")

            if "worktree_path" not in data:
                warnings.append(f"Missing recommended field 'worktree_path' in {plan_file.name}")

            # Validate status
            if "status" in data and data["status"] not in valid_statuses:
                errors.append(f"Invalid status '{data['status']}' in {plan_file.name}")

            # Check phase/task IDs for uniqueness
            phases = data.get("phases", [])
            for phase in phases:
                phase_id = phase.get("id", "")
                if phase_id:
                    if phase_id in all_phase_ids:
                        errors.append(f"Duplicate phase ID: {phase_id}")
                    all_phase_ids.add(phase_id)

                # Warn about phases with no tasks
                phase_name = phase.get("name", phase_id or "unnamed")
                if "tasks" not in phase or not phase.get("tasks"):
                    warnings.append(f"Phase '{phase_name}' has no tasks")

                for task in phase.get("tasks", []):
                    task_id = task.get("id", "")
                    if task_id:
                        if task_id in all_task_ids:
                            errors.append(f"Duplicate task ID: {task_id}")
                        all_task_ids.add(task_id)

                    # Quality checks
                    if not task.get("description", "").strip():
                        warnings.append(f"Task {task_id} has empty description")

                    if not task.get("success_criteria"):
                        warnings.append(f"Task {task_id} has no success criteria")

        valid = len(errors) == 0
        return ValidationResult(valid=valid, errors=errors, warnings=warnings)
