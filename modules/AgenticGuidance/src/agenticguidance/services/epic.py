"""Epic Movement Workflow - automated ticket and folder movement.

Handles ticket status management via TinyDB and folder archival with
git status verification.
"""

import logging
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml

from .state import FileLock

logger = logging.getLogger(__name__)


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
    """Workflow for managing ticket completion and archiving epic folders.

    Uses TinyDB as the sole data source for ticket status. Provides safe
    operations for:
    - Confirming ticket completion status in TinyDB
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

        # Find repo root
        self.repo_path = repo_path or self._find_repo_root(epic_path)
        self.git_checker = GitSafetyChecker(self.repo_path)

        # Initialize EpicRepository for TinyDB-based lookups
        self._repository = None
        try:
            from .epic_repository import EpicRepository

            db_path = self.repo_path / ".agentic" / "epics.db"
            self._repository = EpicRepository(db_path=db_path)
        except Exception:
            logger.warning("Failed to initialize EpicRepository for EpicMovementWorkflow")

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
        """Confirm a ticket is completed in TinyDB.

        In the TinyDB-only model, ticket status is already tracked in
        the database. This method verifies the ticket has 'completed'
        status and returns a result.

        Args:
            task_id: ID of the ticket to verify.
            dry_run: If True, don't make any changes.
            force: If True, skip git status checks.
            silent: If True, run without any user interaction (implies force=True).

        Returns:
            TicketMoveResult with operation outcome.
        """
        if silent:
            force = True

        epic_folder_name = self.epic_path.name

        if self._repository is None:
            return TicketMoveResult(
                task_id=task_id,
                result=MoveResult.FAILED,
                message="TinyDB repository not available",
            )

        try:
            ticket = self._repository.get_ticket(epic_folder_name, task_id)
        except Exception as e:
            return TicketMoveResult(
                task_id=task_id,
                result=MoveResult.FAILED,
                message=f"Failed to look up ticket: {e}",
            )

        if not ticket:
            return TicketMoveResult(
                task_id=task_id,
                result=MoveResult.FAILED,
                message=f"Ticket '{task_id}' not found in TinyDB for epic '{epic_folder_name}'",
            )

        if ticket.status != "completed":
            return TicketMoveResult(
                task_id=task_id,
                result=MoveResult.SKIPPED,
                message=f"Ticket status is '{ticket.status or 'unknown'}', not 'completed'",
                source_file="(TinyDB)",
            )

        if dry_run:
            return TicketMoveResult(
                task_id=task_id,
                result=MoveResult.SUCCESS,
                message="[dry-run] Ticket is already completed in TinyDB",
                source_file="(TinyDB)",
            )

        return TicketMoveResult(
            task_id=task_id,
            result=MoveResult.SUCCESS,
            message="Ticket confirmed completed in TinyDB",
            source_file="(TinyDB)",
        )

    def move_all_completed_tasks(
        self,
        dry_run: bool = False,
        force: bool = False,
        silent: bool = False,
    ) -> list[TicketMoveResult]:
        """Confirm all completed tickets in TinyDB.

        Args:
            dry_run: If True, don't make any changes.
            force: If True, skip git status checks.
            silent: If True, run without any user interaction (implies force=True).

        Returns:
            List of TicketMoveResult for each completed ticket.
        """
        if silent:
            force = True
        results = []
        epic_folder_name = self.epic_path.name

        if self._repository is None:
            return results

        try:
            completed_tickets = self._repository.get_tickets(
                epic_folder_name, status_filter="completed"
            )
        except Exception:
            return results

        for ticket in completed_tickets:
            result = self.move_task_to_completed(
                ticket.id, dry_run=dry_run, force=force, silent=silent
            )
            results.append(result)

        return results

    def archive_epic_folder(
        self,
        dry_run: bool = False,
        force: bool = False,
        silent: bool = False,
    ) -> FolderMoveResult:
        """Archive the epic folder to docs/epics/completed/.

        Moves the folder on disk and updates TinyDB status to 'completed'.

        Args:
            dry_run: If True, don't make any changes.
            force: If True, archive even if git status is unclean.
            silent: If True, run without any user interaction (implies force=True).

        Returns:
            FolderMoveResult with operation outcome.
        """
        if silent:
            force = True

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
            # Copy the folder (keeps non-YAML artifacts like .mmd files)
            shutil.copytree(self.epic_path, dest_dir)

            # Update TinyDB status to completed
            if self._repository:
                try:
                    self._repository.archive_epic(self.epic_path.name)
                except Exception:
                    logger.warning(
                        "Failed to update TinyDB status for archived epic %s",
                        self.epic_path.name,
                    )

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

    # Backward compatibility alias
    archive_plan_folder = archive_epic_folder

    def get_completed_tasks(self) -> list[dict]:
        """Get list of tickets marked as completed from TinyDB.

        Returns:
            List of ticket dictionaries with status='completed'.
        """
        epic_folder_name = self.epic_path.name

        if self._repository is None:
            return []

        try:
            completed = self._repository.get_tickets(
                epic_folder_name, status_filter="completed"
            )
            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description or "",
                    "status": "completed",
                    "completed_date": t.completed_date,
                    "_source": "TinyDB",
                }
                for t in completed
            ]
        except Exception:
            return []

    def get_archived_tasks(self) -> list[dict]:
        """Get list of completed tickets (same as get_completed_tasks in TinyDB model).

        In the TinyDB-only model, there is no separate epic_completed.yml.
        Completed tickets are simply those with status='completed' in TinyDB.

        Returns:
            List of completed ticket dictionaries.
        """
        return self.get_completed_tasks()


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

    def __init__(self, repo_path: Optional[Path] = None, yaml_sync_enabled: bool = False):
        """Initialize epic service.

        TinyDB is the sole data store. YAML sync is disabled.

        Args:
            repo_path: Path to git repository. Defaults to auto-detected repo root.
            yaml_sync_enabled: Deprecated, ignored. Kept for API compatibility.
        """
        self.repo_path = repo_path or self._find_repo_root()
        self.epics_base = self.repo_path / "docs" / "epics"
        # Keep plans_base as internal alias for compatibility with shared repository logic
        self.plans_base = self.epics_base
        self.git_checker = GitSafetyChecker(self.repo_path)
        self._yaml_sync_enabled = False  # YAML sync permanently disabled
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
            pass

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
                pass

        # Create epic folder on disk (for orchestration MMD files, etc.)
        epic_folder.mkdir(parents=True, exist_ok=True)

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

            return None

        return None

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

        TinyDB is the sole data store.

        Args:
            status: Epic status folder (live, completed, deferred).

        Returns:
            List of EpicMetadata objects sorted by folder name (newest first).
        """
        if self._repository is not None:
            results = self._repository.list_epics(status=status)

            # Fix stale paths (resurrection detection)
            epics_dir = self.epics_base / status
            if epics_dir.exists():
                for r in results:
                    if r.epic_folder and f"/epics/{status}/" not in str(r.epic_folder):
                        correct_path = epics_dir / r.epic_folder_name
                        if correct_path.exists():
                            self._repository.resync_epic_folder(
                                r.epic_folder_name, str(correct_path)
                            )
                            r.epic_folder = correct_path

            return results

        return []

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
                return []
            return self._repository.get_tickets(
                epic.epic_folder_name, status_filter=status_filter
            )

        return []

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
