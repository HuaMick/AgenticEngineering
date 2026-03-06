"""Epic Movement Workflow - automated ticket and folder movement.

Handles physical movement of completed tickets to epic_completed.yml and
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
class TicketMoveResult:
    """Result of moving a ticket."""

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


class EpicMovementWorkflow:
    """Workflow for moving completed tickets and archiving epic folders.

    Provides safe operations for:
    - Moving completed tickets to epic_completed.yml
    - Archiving epic folders to completed/ directory
    - Validating git status before moves
    """

    def __init__(self, epic_path: Path, repo_path: Optional[Path] = None):
        """Initialize movement workflow.

        Args:
            epic_path: Path to the epic folder (e.g., docs/epics/live/260103AE_feature).
            repo_path: Path to git repository. Defaults to epic_path ancestor.
        """
        self.plan_path = epic_path  # Keep internal attribute for compatibility
        self.epic_path = epic_path
        # Flattened structure: YAML files are directly in epic_path, not nested
        self.completed_file = epic_path / "epic_completed.yml"

        # Find repo root
        self.repo_path = repo_path or self._find_repo_root(epic_path)
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
    ) -> TicketMoveResult:
        """Move a completed ticket to epic_completed.yml.

        Args:
            task_id: ID of the ticket to move.
            dry_run: If True, don't make any changes.
            force: If True, move even if git status is unclean.
            silent: If True, run without any user interaction (implies force=True).
                   Skips confirmation prompts and uses sensible defaults.

        Returns:
            TicketMoveResult with operation outcome.
        """
        # Silent mode implies force mode - no prompts, no git checks
        if silent:
            force = True
        # Find the ticket in epic files (directly in epic_path, flattened structure)
        task_data = None
        source_file = None

        for yaml_file in self.epic_path.glob("*.yml"):
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
                            return TicketMoveResult(
                                task_id=task_id,
                                result=MoveResult.SKIPPED,
                                message=f"Ticket status is '{item.get('status', 'unknown')}', not 'completed'",
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
            return TicketMoveResult(
                task_id=task_id,
                result=MoveResult.FAILED,
                message=f"Ticket '{task_id}' not found in any epic file",
            )

        # Check git status if not forcing
        if not force and self.git_checker.has_uncommitted_changes(source_file):
            return TicketMoveResult(
                task_id=task_id,
                result=MoveResult.SKIPPED,
                message="Uncommitted changes in source file. Use --force to override.",
                source_file=source_file.name,
            )

        if dry_run:
            return TicketMoveResult(
                task_id=task_id,
                result=MoveResult.SUCCESS,
                message="[dry-run] Would move ticket to epic_completed.yml",
                source_file=source_file.name,
                target_file="epic_completed.yml",
            )

        # Ensure epic_path exists (flattened structure)
        self.epic_path.mkdir(parents=True, exist_ok=True)

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
                return TicketMoveResult(
                    task_id=task_id,
                    result=MoveResult.SKIPPED,
                    message=f"Ticket '{task_id}' already exists in epic_completed.yml",
                    source_file=source_file.name,
                    target_file="epic_completed.yml",
                )

            # Add the ticket
            completed_data["completed_tasks"].append(task_data)
            completed_data["metadata"] = completed_data.get("metadata", {})
            completed_data["metadata"]["last_updated"] = datetime.now().isoformat()

            # Write completed file
            with open(self.completed_file, "w") as f:
                yaml.dump(completed_data, f, default_flow_style=False, sort_keys=False)

        # Remove the ticket from the source file to prevent duplicates
        removal_error = self._remove_task_from_source(source_file, task_id)
        if removal_error:
            return TicketMoveResult(
                task_id=task_id,
                result=MoveResult.SUCCESS,
                message=f"Ticket moved to epic_completed.yml (warning: {removal_error})",
                source_file=source_file.name,
                target_file="epic_completed.yml",
            )

        return TicketMoveResult(
            task_id=task_id,
            result=MoveResult.SUCCESS,
            message="Ticket moved to epic_completed.yml and removed from source",
            source_file=source_file.name,
            target_file="epic_completed.yml",
        )

    def _remove_task_from_source(self, source_file: Path, task_id: str) -> Optional[str]:
        """Remove a ticket from the source YAML file.

        Handles both flat ticket lists (epic.tasks, epic.implementation_steps)
        and nested tickets in phases (epic.phases[].tasks[]).

        Args:
            source_file: Path to the source YAML file.
            task_id: ID of the ticket to remove.

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

        # Handle flat ticket lists (epic.tasks, epic.implementation_steps)
        for key in ["tasks", "implementation_steps"]:
            items = plan.get(key, [])
            if items:
                original_len = len(items)
                plan[key] = [item for item in items if item.get("id") != task_id]
                if len(plan[key]) < original_len:
                    task_removed = True
                    break

        # Handle nested tickets in phases (epic.phases[].tickets[])
        if not task_removed:
            phases = plan.get("phases", [])
            for phase in phases:
                phase_tasks = phase.get("tickets", [])
                if phase_tasks:
                    original_len = len(phase_tasks)
                    phase["tickets"] = [t for t in phase_tasks if t.get("id") != task_id]
                    if len(phase["tickets"]) < original_len:
                        task_removed = True
                        break

        if not task_removed:
            return f"ticket '{task_id}' not found in source file for removal"

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
    ) -> list[TicketMoveResult]:
        """Move all completed tickets to epic_completed.yml.

        Args:
            dry_run: If True, don't make any changes.
            force: If True, move even if git status is unclean.
            silent: If True, run without any user interaction (implies force=True).
                   Skips confirmation prompts and uses sensible defaults.

        Returns:
            List of TicketMoveResult for each ticket.
        """
        # Silent mode implies force mode
        if silent:
            force = True
        results = []
        completed_task_ids = []

        # Find all completed tickets (directly in epic_path, flattened structure)
        for yaml_file in self.epic_path.glob("*.yml"):
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

    def archive_epic_folder(
        self,
        dry_run: bool = False,
        force: bool = False,
        silent: bool = False,
    ) -> FolderMoveResult:
        """Archive the epic folder to docs/epics/completed/.

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
        # Go up from docs/epics/live/FOLDER to docs/epics/completed/FOLDER
        dest_dir = self.epic_path.parent.parent / "completed" / self.epic_path.name

        # Check git status if not forcing
        if not force and self.git_checker.has_uncommitted_changes(self.epic_path):
            return FolderMoveResult(
                source=str(self.epic_path),
                destination=str(dest_dir),
                result=MoveResult.SKIPPED,
                message="Uncommitted changes in epic folder. Use --force to override.",
            )

        if dry_run:
            return FolderMoveResult(
                source=str(self.epic_path),
                destination=str(dest_dir),
                result=MoveResult.SUCCESS,
                message=f"[dry-run] Would archive to {dest_dir}",
            )

        # Check if destination exists
        if dest_dir.exists():
            return FolderMoveResult(
                source=str(self.epic_path),
                destination=str(dest_dir),
                result=MoveResult.SKIPPED,
                message=f"Destination already exists: {dest_dir}",
            )

        try:
            # Copy the folder
            shutil.copytree(self.epic_path, dest_dir)

            # Update archive metadata (flattened structure: epic_completed.yml in dest_dir)
            archive_meta_file = dest_dir / "epic_completed.yml"
            if archive_meta_file.exists():
                try:
                    data = yaml.safe_load(archive_meta_file.read_text())
                    if data is None:
                        data = {}
                except yaml.YAMLError:
                    data = {}

                data["archived_date"] = datetime.now().strftime("%Y-%m-%d")
                data["archived_from"] = str(self.epic_path)

                with open(archive_meta_file, "w") as f:
                    yaml.dump(data, f, default_flow_style=False)

            # Remove the source folder after successful copy
            rmtree_error = None
            try:
                shutil.rmtree(self.epic_path)
            except OSError as e:
                rmtree_error = str(e)

            if rmtree_error:
                return FolderMoveResult(
                    source=str(self.epic_path),
                    destination=str(dest_dir),
                    result=MoveResult.SUCCESS,
                    message=f"Archived to {dest_dir} (warning: failed to remove source: {rmtree_error})",
                )

            return FolderMoveResult(
                source=str(self.epic_path),
                destination=str(dest_dir),
                result=MoveResult.SUCCESS,
                message=f"Archived to {dest_dir}",
            )

        except OSError as e:
            return FolderMoveResult(
                source=str(self.epic_path),
                destination=str(dest_dir),
                result=MoveResult.FAILED,
                message=f"Archive failed: {e}",
            )

    def get_completed_tasks(self) -> list[dict]:
        """Get list of tickets marked as completed.

        Returns:
            List of ticket dictionaries with status='completed'.
        """
        completed = []

        for yaml_file in self.epic_path.glob("*.yml"):
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
        """Get list of tickets already in epic_completed.yml.

        Returns:
            List of archived ticket dictionaries.
        """
        if not self.completed_file.exists():
            return []

        try:
            data = yaml.safe_load(self.completed_file.read_text())
            return data.get("completed_tasks", []) if data else []
        except yaml.YAMLError:
            return []


# Data models for EpicService
@dataclass
class EpicCreateResult:
    """Result of creating an epic."""

    epic_folder: Path
    epic_folder_name: str
    success: bool
    message: str


@dataclass
class EpicData:
    """Complete epic data including phases and tickets."""

    epic_folder: Path
    epic_folder_name: str
    objective: Optional[str] = None
    status: Optional[str] = None
    branch: Optional[str] = None
    name: Optional[str] = None
    worktree_path: Optional[str] = None
    priority: Optional[str] = None
    context: Optional[str] = None
    created: Optional[str] = None
    deferred_reason: Optional[str] = None
    cancelled_date: Optional[str] = None
    phases: list = None
    tasks: list = None

    def __post_init__(self):
        if self.phases is None:
            self.phases = []
        if self.tasks is None:
            self.tasks = []

    @property
    def plan_folder(self) -> Path:
        """Backward-compat alias for epic_folder."""
        return self.epic_folder

    @plan_folder.setter
    def plan_folder(self, value: Path) -> None:
        self.epic_folder = value

    @property
    def plan_folder_name(self) -> str:
        """Backward-compat alias for epic_folder_name."""
        return self.epic_folder_name

    @plan_folder_name.setter
    def plan_folder_name(self, value: str) -> None:
        self.epic_folder_name = value


@dataclass
class EpicMetadata:
    """Summary information about an epic."""

    epic_folder: Path
    epic_folder_name: str
    objective: Optional[str] = None
    status: Optional[str] = None
    created: Optional[str] = None
    name: Optional[str] = None
    priority: Optional[str] = None
    worktree_path: Optional[str] = None
    branch: Optional[str] = None

    @property
    def plan_folder(self) -> Path:
        """Backward-compat alias for epic_folder."""
        return self.epic_folder

    @plan_folder.setter
    def plan_folder(self, value: Path) -> None:
        self.epic_folder = value

    @property
    def plan_folder_name(self) -> str:
        """Backward-compat alias for epic_folder_name."""
        return self.epic_folder_name

    @plan_folder_name.setter
    def plan_folder_name(self, value: str) -> None:
        self.epic_folder_name = value


@dataclass
class EpicUpdateResult:
    """Result of updating an epic."""

    success: bool
    message: str
    epic_folder: Optional[str] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None


@dataclass
class EpicDeleteResult:
    """Result of deleting an epic."""

    success: bool
    message: str


@dataclass
class ValidationResult:
    """Result of validating epic structure."""

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
class TicketData:
    """Data for a single ticket."""

    id: str
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    agent: Optional[str] = None
    phase_name: Optional[str] = None
    inputs: list = None
    target_files: list = None
    guidance: Optional[str] = None
    completed_date: Optional[str] = None
    success_criteria: Optional[str] = None

    def __post_init__(self):
        if self.inputs is None:
            self.inputs = []
        if self.target_files is None:
            self.target_files = []


class EpicService:
    """Epic management service providing CRUD operations for epics.

    This service provides comprehensive epic management capabilities including:
    - Creating new epics with proper naming conventions
    - Retrieving epic data and metadata
    - Listing epics by status (live, completed, deferred)
    - Updating epic status
    - Extracting tickets and phases
    - Validating epic structure

    Examples:
        Create a new epic:
        >>> service = EpicService()
        >>> result = service.create_epic(
        ...     objective="Implement feature X",
        ...     branch="main",
        ...     description="feature_x"
        ... )
        >>> print(result.epic_folder_name)
        260203MA_feature_x

        Retrieve epic data:
        >>> epic = service.get_epic("260203MA")
        >>> print(epic.objective)
        Implement feature X

        List all live epics:
        >>> epics = service.list_epics(status="live")
        >>> for epic_meta in epics:
        ...     print(f"{epic_meta.epic_folder_name}: {epic_meta.objective}")

        Validate epic structure:
        >>> validation = service.validate_epic_structure(Path("docs/epics/live/260203MA_feature_x"))
        >>> if not validation.valid:
        ...     print(validation.errors)
    """

    def __init__(self, repo_path: Optional[Path] = None, yaml_sync_enabled: bool = True):
        """Initialize epic service.

        TinyDB is the primary data store. YAML files are optionally kept in sync
        for git-committed state. If TinyDB is unavailable (import failure),
        YAML serves as emergency fallback.

        Args:
            repo_path: Path to git repository. Defaults to auto-detected repo root.
            yaml_sync_enabled: If True, keep YAML files in sync with TinyDB for
                              git commits. Defaults to True.
        """
        self.repo_path = repo_path or self._find_repo_root()
        self.epics_base = self.repo_path / "docs" / "epics"
        # Keep plans_base as internal alias for compatibility with shared repository logic
        self.plans_base = self.epics_base
        self.git_checker = GitSafetyChecker(self.repo_path)
        self._yaml_sync_enabled = yaml_sync_enabled
        self._repository = None
        try:
            from .epic_repository import EpicRepository
            # Use repo-local DB so tests with tmp_path get isolated instances
            db_path = self.repo_path / ".agentic" / "epics.db"
            self._repository = EpicRepository(
                db_path=db_path,
                epics_base=self.epics_base,
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

    def _generate_epic_folder_name(self, description: str, branch: str) -> str:
        """Generate epic folder name following YYMMDDXX_description convention.

        Args:
            description: Description part of the name.
            branch: Branch name to derive XX from.

        Returns:
            Epic folder name (e.g., "260203MA_feature_name").
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

    def _normalize_epic_id(self, epic_id_or_path: str) -> str:
        """Normalize epic identifier to a folder name for repository lookup.

        Handles absolute paths, relative paths, folder names, and short IDs.

        Args:
            epic_id_or_path: Any epic identifier format.

        Returns:
            Folder name or short ID suitable for PlanRepository lookup.
        """
        if "/" in epic_id_or_path or Path(epic_id_or_path).is_absolute():
            return Path(epic_id_or_path).name
        return epic_id_or_path

    def create_epic(
        self,
        objective: str,
        branch: str,
        description: str,
        dry_run: bool = False,
    ) -> EpicCreateResult:
        """Create a new epic with scaffolding.

        Creates a new epic folder in docs/epics/live/ with:
        - Epic folder named according to YYMMDDXX_description convention
        - README.md with objective and status
        - plan_build.yml with basic structure

        Args:
            objective: Epic objective/goal.
            branch: Git branch name.
            description: Short description for folder name.
            dry_run: If True, don't create any files.

        Returns:
            EpicCreateResult with folder path and success status.
        """
        folder_name = self._generate_epic_folder_name(description, branch)
        epic_folder = self.epics_base / "live" / folder_name

        if epic_folder.exists():
            return EpicCreateResult(
                epic_folder=epic_folder,
                epic_folder_name=folder_name,
                success=False,
                message=f"Epic folder already exists: {folder_name}",
            )

        if dry_run:
            return EpicCreateResult(
                epic_folder=epic_folder,
                epic_folder_name=folder_name,
                success=True,
                message=f"[dry-run] Would create epic folder: {folder_name}",
            )

        epic_scaffold = {
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
                self._repository.create_epic({
                    "epic_folder_name": folder_name,
                    "epic_folder": str(epic_folder),
                    "name": epic_scaffold["name"],
                    "worktree_path": epic_scaffold["worktree_path"],
                    "branch": branch,
                    "status": "pending",
                    "priority": "medium",
                    "objective": objective,
                    "created": epic_scaffold["created"],
                })
            except Exception:
                pass  # Continue with YAML sync

        # YAML sync: create filesystem scaffold for git commits
        if self._yaml_sync_enabled:
            epic_folder.mkdir(parents=True, exist_ok=True)

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
            (epic_folder / "README.md").write_text(readme_content)

            with open(epic_folder / "plan_build.yml", "w") as f:
                yaml.dump(epic_scaffold, f, default_flow_style=False, sort_keys=False)

        return EpicCreateResult(
            epic_folder=epic_folder,
            epic_folder_name=folder_name,
            success=True,
            message=f"Created epic folder: {folder_name}",
        )

    def get_epic(self, epic_id_or_path: str) -> Optional[EpicData]:
        """Retrieve complete epic data.

        TinyDB is the primary store. YAML is only used as emergency fallback
        when TinyDB is unavailable (import failure at init).

        Supports multiple input formats:
        - Short ID: "260203PS"
        - Folder name: "260203PS_plan_service"
        - Relative path: "docs/epics/live/260203PS_plan_service"
        - Absolute path: "/home/code/.../docs/epics/live/260203PS_plan_service"

        Args:
            epic_id_or_path: Epic identifier or path.

        Returns:
            EpicData with phases and tickets, or None if not found.
        """
        if self._repository is not None:
            lookup_key = self._normalize_epic_id(epic_id_or_path)
            result = self._repository.get_epic(lookup_key)
            if result is not None:
                # Resurrection detection: if TinyDB has completed/ path but
                # live/ version exists, resync to the live path
                _folder_str = ""
                _val = getattr(result, "epic_folder", None)
                if _val and "/completed/" in str(_val):
                    _folder_str = str(_val)

                _result_folder_name = getattr(result, "epic_folder_name", None)

                if _folder_str and _result_folder_name:
                    live_path = self.epics_base / "live" / _result_folder_name
                    if live_path.exists():
                        self._repository.resync_epic_folder(
                            _result_folder_name, str(live_path)
                        )
                        # Update the result object directly (works with mocks too)
                        result.epic_folder = live_path
                return result

            # Read-through: epic may exist on disk but not in TinyDB yet
            # (e.g., created externally, git pull, or test fixture)
            epic_folder = self._resolve_epic_folder(epic_id_or_path)
            if epic_folder and epic_folder.exists():
                self._repository.import_from_yaml(epic_folder)
                return self._repository.get_epic(epic_folder.name)

            return None

        # Emergency YAML fallback (only when repository import failed)
        return self._get_epic_from_yaml(epic_id_or_path)

    def _get_epic_from_yaml(self, epic_id_or_path: str) -> Optional[EpicData]:
        """Emergency YAML fallback for get_epic when TinyDB is unavailable."""
        epic_folder = self._resolve_epic_folder(epic_id_or_path)
        if not epic_folder or not epic_folder.exists():
            return None

        epic_data = {}
        for epic_file in epic_folder.glob("plan_*.yml"):
            try:
                with open(epic_file) as f:
                    data = yaml.safe_load(f)
                if data:
                    epic_data.update(data)
            except (yaml.YAMLError, IOError):
                continue

        if not epic_data:
            return None

        phases_data = epic_data.get("phases", [])
        phases = []
        all_tasks = []

        for phase in phases_data:
            phase_tasks = phase.get("tickets", [])
            task_data_list = []

            for task in phase_tasks:
                task_obj = TicketData(
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

        return EpicData(
            epic_folder=epic_folder,
            epic_folder_name=epic_folder.name,
            objective=epic_data.get("objective"),
            status=epic_data.get("status"),
            branch=epic_data.get("branch"),
            phases=phases,
            tasks=all_tasks,
        )

    def _resolve_epic_folder(self, epic_id_or_path: str) -> Optional[Path]:
        """Resolve epic identifier or path to actual epic folder.

        Args:
            epic_id_or_path: Epic identifier or path.

        Returns:
            Path to epic folder or None.
        """
        # If it's an absolute path, use it directly
        path = Path(epic_id_or_path)
        if path.is_absolute() and path.exists():
            return path

        # If it's a relative path from repo root
        rel_path = self.repo_path / epic_id_or_path
        if rel_path.exists():
            return rel_path

        # Search in epics directories for matching ID or folder name
        for status in ["live", "completed", "deferred"]:
            epics_dir = self.epics_base / status
            if not epics_dir.exists():
                continue

            for folder in epics_dir.iterdir():
                if not folder.is_dir():
                    continue

                # Match by folder name or ID prefix
                if folder.name == epic_id_or_path or folder.name.startswith(epic_id_or_path + "_"):
                    return folder

        return None

    def list_epics(self, status: str = "live") -> list[EpicMetadata]:
        """List all epics with a given status.

        TinyDB is the primary store. YAML scan is only used as emergency
        fallback when TinyDB is unavailable.

        Args:
            status: Epic status folder (live, completed, deferred).

        Returns:
            List of EpicMetadata objects sorted by folder name (newest first).
        """
        if self._repository is not None:
            results = self._repository.list_epics(status=status)

            # Reconcile with filesystem: check for epics on disk that TinyDB
            # doesn't know about, and fix stale paths (resurrection detection)
            epics_dir = self.epics_base / status
            if epics_dir.exists():
                known_names = {r.epic_folder_name for r in results}
                disk_epics = []
                for folder in sorted(epics_dir.iterdir(), reverse=True):
                    if not folder.is_dir() or not (
                        list(folder.glob("plan_*.yml")) or list(folder.glob("ticket_*.yml"))
                    ):
                        continue
                    if folder.name not in known_names:
                        # Epic on disk but not in TinyDB for this status
                        self._repository.import_from_yaml(folder)
                        disk_epics.append(folder)

                # Also check if any TinyDB results have stale paths
                for r in results:
                    if r.epic_folder and f"/epics/{status}/" not in str(r.epic_folder):
                        correct_path = epics_dir / r.epic_folder_name
                        if correct_path.exists():
                            self._repository.resync_epic_folder(
                                r.epic_folder_name, str(correct_path)
                            )
                            r.epic_folder = correct_path

                if disk_epics:
                    # Re-fetch to include newly imported epics
                    fresh = self._repository.list_epics(status=status)
                    fresh_names = {f.epic_folder_name for f in fresh}
                    # Merge fresh results
                    for f in fresh:
                        if f.epic_folder_name not in known_names:
                            results.append(f)
                    # For any disk epics still missing from fresh (mock scenario),
                    # create minimal metadata entries
                    for folder in disk_epics:
                        if folder.name not in known_names and folder.name not in fresh_names:
                            results.append(EpicMetadata(
                                epic_folder=folder,
                                epic_folder_name=folder.name,
                            ))

            return results

        # Emergency YAML fallback (only when repository import failed)
        return self._list_epics_from_yaml(status)

    def _list_epics_from_yaml(self, status: str) -> list[EpicMetadata]:
        """Emergency YAML fallback for list_epics when TinyDB is unavailable."""
        epics_dir = self.epics_base / status
        if not epics_dir.exists():
            return []

        results = []

        for folder in sorted(epics_dir.iterdir(), key=lambda x: x.name, reverse=True):
            if not folder.is_dir():
                continue

            if not self._is_valid_epic_folder_name(folder.name):
                continue

            epic_meta = EpicMetadata(
                epic_folder=folder,
                epic_folder_name=folder.name,
            )

            for epic_file in folder.glob("plan_*.yml"):
                try:
                    with open(epic_file) as f:
                        data = yaml.safe_load(f)
                    if data:
                        epic_meta.objective = data.get("objective", epic_meta.objective)
                        epic_meta.status = data.get("status", epic_meta.status)
                        epic_meta.created = data.get("created", epic_meta.created)
                        break
                except (yaml.YAMLError, IOError):
                    continue

            results.append(epic_meta)

        return results

    def _is_valid_epic_folder_name(self, name: str) -> bool:
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

    def update_epic_status(
        self,
        epic_id: str,
        new_status: str,
        dry_run: bool = False,
    ) -> EpicUpdateResult:
        """Update epic status.

        TinyDB is the primary store. YAML files are optionally synced.

        Valid statuses: planning, active, partially_completed, fully_completed.

        Args:
            epic_id: Epic identifier or path.
            new_status: New status value.
            dry_run: If True, don't make any changes.

        Returns:
            EpicUpdateResult with update outcome.
        """
        valid_statuses = ["planning", "pending", "active", "in_progress", "completed", "partially_completed", "fully_completed", "blocked", "cancelled", "deferred"]
        if new_status not in valid_statuses:
            return EpicUpdateResult(
                success=False,
                message=f"Invalid status: {new_status}. Valid: {', '.join(valid_statuses)}",
            )

        # Resolve epic and get old status
        if self._repository is not None:
            lookup_key = self._normalize_epic_id(epic_id)
            epic_data = self._repository.get_epic(lookup_key)
            if epic_data is None:
                # Read-through: try YAML import if epic exists on disk
                epic_folder = self._resolve_epic_folder(epic_id)
                if epic_folder and epic_folder.exists():
                    self._repository.import_from_yaml(epic_folder)
                    epic_data = self._repository.get_epic(epic_folder.name)
            if epic_data is None:
                return EpicUpdateResult(
                    success=False,
                    message=f"Epic not found: {epic_id}",
                )
            epic_folder = epic_data.epic_folder
            old_status = epic_data.status
        else:
            # Emergency YAML fallback
            epic_folder = self._resolve_epic_folder(epic_id)
            if not epic_folder or not epic_folder.exists():
                return EpicUpdateResult(
                    success=False,
                    message=f"Epic not found: {epic_id}",
                )
            old_status = None
            for epic_file in epic_folder.glob("plan_*.yml"):
                try:
                    with open(epic_file) as f:
                        data = yaml.safe_load(f)
                    if data and "status" in data:
                        old_status = data["status"]
                        break
                except (yaml.YAMLError, IOError):
                    continue

        if dry_run:
            return EpicUpdateResult(
                success=True,
                message=f"[dry-run] Would update status from {old_status} to {new_status}",
                epic_folder=str(epic_folder),
                old_status=old_status,
                new_status=new_status,
            )

        # TinyDB-first: update via repository
        if self._repository is not None:
            self._repository.update_epic(
                epic_data.epic_folder_name,
                {"status": new_status},
            )

        # YAML sync: update all epic files on disk
        if self._yaml_sync_enabled and epic_folder.exists():
            for epic_file in epic_folder.glob("plan_*.yml"):
                with FileLock(epic_file):
                    try:
                        with open(epic_file) as f:
                            data = yaml.safe_load(f)
                        if data:
                            data["status"] = new_status
                            with open(epic_file, "w") as f:
                                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                    except (yaml.YAMLError, IOError):
                        continue

        return EpicUpdateResult(
            success=True,
            message=f"Updated status from {old_status} to {new_status}",
            epic_folder=str(epic_folder),
            old_status=old_status,
            new_status=new_status,
        )

    def get_epic_tickets(
        self,
        epic_id: str,
        status_filter: Optional[str] = None,
    ) -> list[TicketData]:
        """Extract all tickets from an epic.

        TinyDB is the primary store. Delegates to repository for ticket queries.

        Args:
            epic_id: Epic identifier or path.
            status_filter: Optional status to filter by (pending, in_progress, completed, blocked).

        Returns:
            List of TicketData objects.
        """
        if self._repository is not None:
            lookup_key = self._normalize_epic_id(epic_id)
            epic = self._repository.get_epic(lookup_key)
            if epic is None:
                # Read-through: try YAML import
                epic_folder = self._resolve_epic_folder(epic_id)
                if epic_folder and epic_folder.exists():
                    self._repository.import_from_yaml(epic_folder)
                    epic = self._repository.get_epic(epic_folder.name)
            if epic is None:
                return []
            return self._repository.get_tickets(
                epic.epic_folder_name, status_filter=status_filter
            )

        # Emergency YAML fallback
        epic_data = self._get_epic_from_yaml(epic_id)
        if not epic_data:
            return []

        tasks = epic_data.tasks
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        return tasks

    def validate_epic_structure(self, epic_path: Path) -> ValidationResult:
        """Validate epic folder structure and content.

        Checks:
        - Folder naming convention (YYMMDDXX_description)
        - Epic files in folder root (not subdirectories)
        - Required fields present
        - Valid status values
        - Phase/ticket IDs unique

        Args:
            epic_path: Path to epic folder.

        Returns:
            ValidationResult with errors and warnings.
        """
        errors = []
        warnings = []

        # Check folder exists
        if not epic_path.exists():
            errors.append(f"Epic folder does not exist: {epic_path}")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Check folder naming convention
        if not self._is_valid_epic_folder_name(epic_path.name):
            errors.append(f"Folder name does not match YYMMDDXX_description pattern: {epic_path.name}")

        # Check for epic files in root
        epic_files = list(epic_path.glob("plan_*.yml"))
        if not epic_files:
            errors.append("No plan_*.yml files found in folder root")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Check epic files are not in subdirectories
        for subdir in epic_path.iterdir():
            if subdir.is_dir() and list(subdir.glob("plan_*.yml")):
                warnings.append(f"Found epic files in subdirectory: {subdir.name}")

        # Validate YAML structure
        required_fields = ["name", "status", "phases"]
        valid_statuses = ["planning", "pending", "active", "in_progress", "completed", "partially_completed", "fully_completed", "blocked", "cancelled", "deferred"]

        all_task_ids = set()
        all_phase_ids = set()

        for epic_file in epic_files:
            try:
                with open(epic_file) as f:
                    data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                errors.append(f"Invalid YAML in {epic_file.name}: {e}")
                continue

            if not data:
                errors.append(f"Empty epic file: {epic_file.name}")
                continue

            # Skip scaffold templates (created by `agentic epic init`)
            if data.get("_template_status") == "stub":
                warnings.append(f"Scaffold template not yet populated: {epic_file.name}")
                continue

            # Skip completed-items tracking files
            if set(data.keys()) <= {"completed_items"}:
                continue

            # Check for root-level tasks: key (tickets must be nested under phases[].tasks[])
            if "tasks" in data:
                errors.append(
                    f"Root-level 'tasks' key found in {epic_file.name}. "
                    "Tickets must be nested under phases[].tasks[], not at the root level."
                )

            # Check required fields
            for field in required_fields:
                if field not in data:
                    errors.append(f"Missing required field '{field}' in {epic_file.name}")

            if "worktree_path" not in data:
                warnings.append(f"Missing recommended field 'worktree_path' in {epic_file.name}")

            # Validate status
            if "status" in data and data["status"] not in valid_statuses:
                errors.append(f"Invalid status '{data['status']}' in {epic_file.name}")

            # Check phase/ticket IDs for uniqueness
            phases = data.get("phases", [])
            for phase in phases:
                phase_id = phase.get("id", "")
                if phase_id:
                    if phase_id in all_phase_ids:
                        errors.append(f"Duplicate phase ID: {phase_id}")
                    all_phase_ids.add(phase_id)

                # Warn about phases with no tickets
                phase_name = phase.get("name", phase_id or "unnamed")
                if not phase.get("tickets"):
                    warnings.append(f"Phase '{phase_name}' has no tickets")

                for task in phase.get("tickets", []):
                    task_id = task.get("id", "")
                    if task_id:
                        if task_id in all_task_ids:
                            errors.append(f"Duplicate ticket ID: {task_id}")
                        all_task_ids.add(task_id)

                    # Quality checks
                    if not task.get("description", "").strip():
                        warnings.append(f"Ticket {task_id} has empty description")

                    if not task.get("success_criteria"):
                        warnings.append(f"Ticket {task_id} has no success criteria")

        valid = len(errors) == 0
        return ValidationResult(valid=valid, errors=errors, warnings=warnings)
