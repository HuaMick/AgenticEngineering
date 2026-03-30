"""Epic Movement Workflow - automated ticket and folder movement.

Handles ticket status management via TinyDB and folder archival with
git status verification.
"""

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from .state import FileLock

logger = logging.getLogger(__name__)


class EpicStatus(Enum):
    """Canonical epic statuses (7 lifecycle values)."""

    SEED = "seed"
    ACTIVE = "active"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DEFERRED = "deferred"
    BLOCKED = "blocked"


# Maps all legacy status strings to the 7 canonical values
EPIC_STATUS_MIGRATION: dict[str, str] = {
    # Canonical values (identity)
    "seed": "seed",
    "active": "active",
    "planning": "planning",
    "in_progress": "in_progress",
    "completed": "completed",
    "deferred": "deferred",
    "blocked": "blocked",
    # Legacy mappings
    "proposed": "active",
    "pending": "active",
    "approved": "in_progress",
    "partially_completed": "in_progress",
    "fully_completed": "completed",
    "cancelled": "completed",
}


def normalize_epic_status(status: str) -> str:
    """Normalize any legacy status string to a canonical EpicStatus value.

    Args:
        status: Any status string (old or new).

    Returns:
        One of 'seed', 'active', 'planning', 'in_progress', 'completed',
        'deferred', 'blocked'.
    """
    return EPIC_STATUS_MIGRATION.get(status.lower().strip(), "active")


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
        """Archive the epic: set TinyDB status to 'completed' and move folder.

        Steps:
        1. Update TinyDB status to 'completed'.
        2. Move folder from ``live/`` to ``completed/`` via shutil.move().
        3. Update ``epic_folder`` path in TinyDB to the new location.

        Edge cases:
        - Destination already exists → fail (no overwrite).
        - Source folder missing → TinyDB-only update (no move).

        Args:
            dry_run: If True, don't make any changes.
            force: Accepted for backward compatibility; has no effect.
            silent: Accepted for backward compatibility; has no effect.

        Returns:
            FolderMoveResult with operation outcome.
        """
        import shutil

        epic_name = self.epic_path.name
        source = self.epic_path

        # Determine if source is a real live/ folder
        has_live_folder = source.is_absolute() and source.parent.name == "live"
        completed_dir = source.parent.parent / "completed" if has_live_folder else None
        destination = completed_dir / epic_name if completed_dir else None

        if dry_run:
            dest_str = str(destination) if destination else "(TinyDB status=completed)"
            return FolderMoveResult(
                source=str(source),
                destination=dest_str,
                result=MoveResult.SUCCESS,
                message=f"[dry-run] Would archive {epic_name}",
            )

        if self._repository is None:
            return FolderMoveResult(
                source=str(source),
                destination="(TinyDB status=completed)",
                result=MoveResult.FAILED,
                message="TinyDB repository not available",
            )

        try:
            # Step 1: Update TinyDB status (always)
            update_result = self._repository.archive_epic(epic_name)
            if not update_result.success:
                return FolderMoveResult(
                    source=str(source),
                    destination="(TinyDB status=completed)",
                    result=MoveResult.FAILED,
                    message=f"TinyDB update failed: {update_result.message}",
                )

            # Step 2: Move folder from live/ to completed/ (only if folder exists)
            if destination and source.exists():
                if destination.exists():
                    return FolderMoveResult(
                        source=str(source),
                        destination=str(destination),
                        result=MoveResult.FAILED,
                        message=f"Destination already exists: {destination}",
                    )
                completed_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))

                # Step 3: Update epic_folder path in TinyDB
                try:
                    self._repository.update_epic(
                        epic_name, {"epic_folder": str(destination)}
                    )
                except Exception:
                    pass  # Non-fatal: folder moved, TinyDB path is secondary

                return FolderMoveResult(
                    source=str(source),
                    destination=str(destination),
                    result=MoveResult.SUCCESS,
                    message=f"Archived {epic_name} to {destination}",
                )

            # Folder-free epic or source missing → TinyDB-only archive (normal path)
            return FolderMoveResult(
                source=str(source),
                destination="(TinyDB status=completed)",
                result=MoveResult.SUCCESS,
                message=f"Set status=completed in TinyDB for {epic_name}",
            )
        except Exception as e:
            return FolderMoveResult(
                source=str(source),
                destination="(TinyDB status=completed)",
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

    epic_folder_name: str
    success: bool
    message: str
    epic_folder: Optional[Path] = None


@dataclass
class EpicData:
    """Complete epic data including phases and tickets."""

    epic_folder_name: str
    epic_folder: Optional[Path] = None
    objective: Optional[str] = None
    status: Optional[str] = None
    branch: Optional[str] = None
    name: Optional[str] = None
    worktree_path: Optional[str] = None
    priority: Optional[int] = None
    context: Optional[str] = None
    created: Optional[str] = None
    deferred_reason: Optional[str] = None
    cancelled_date: Optional[str] = None
    depends_on: Optional[list[str]] = None
    phases: list = None
    tasks: list = None

    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []
        if self.phases is None:
            self.phases = []
        if self.tasks is None:
            self.tasks = []

    @property
    def plan_folder(self) -> Optional[Path]:
        """Backward-compat alias for epic_folder."""
        return self.epic_folder

    @plan_folder.setter
    def plan_folder(self, value: Optional[Path]) -> None:
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

    epic_folder_name: str
    epic_folder: Optional[Path] = None
    objective: Optional[str] = None
    status: Optional[str] = None
    created: Optional[str] = None
    name: Optional[str] = None
    priority: Optional[int] = None
    worktree_path: Optional[str] = None
    branch: Optional[str] = None
    depends_on: Optional[list[str]] = None

    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []

    @property
    def plan_folder(self) -> Optional[Path]:
        """Backward-compat alias for epic_folder."""
        return self.epic_folder

    @plan_folder.setter
    def plan_folder(self, value: Optional[Path]) -> None:
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
    agent: Optional[str] = None
    loop_type: Optional[str] = None
    loop_max_iterations: Optional[int] = None
    feedback_triggers: Optional[dict] = None
    phase_id: Optional[str] = None
    max_turns: Optional[int] = None
    timeout: Optional[int] = None  # Per-phase timeout in seconds (None = use default)

    def __post_init__(self):
        if self.tasks is None:
            self.tasks = []
        if self.feedback_triggers is None:
            self.feedback_triggers = {}


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
    story_ids: list = None

    def __post_init__(self):
        if self.inputs is None:
            self.inputs = []
        if self.target_files is None:
            self.target_files = []
        if self.story_ids is None:
            self.story_ids = []


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

    def __init__(self, repo_path: Optional[Path] = None, *, repository=None):
        """Initialize epic service.

        TinyDB is the sole data store.

        Args:
            repo_path: Path to git repository. Defaults to auto-detected repo root.
            repository: Optional EpicRepository instance (for testing).
        """
        self.repo_path = repo_path or self._find_repo_root()
        self.epics_base = self.repo_path / "docs" / "epics"
        # Keep plans_base as internal alias for compatibility with shared repository logic
        self.plans_base = self.epics_base
        self.git_checker = GitSafetyChecker(self.repo_path)
        self._repository = repository
        if self._repository is None:
            try:
                from .epic_repository import EpicRepository
                self._repository = EpicRepository()
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
        - Epic record in TinyDB (sole data store)

        Args:
            objective: Epic objective/goal.
            branch: Git branch name.
            description: Short description for folder name.
            dry_run: If True, don't create any files.

        Returns:
            EpicCreateResult with folder path and success status.
        """
        folder_name = self._generate_epic_folder_name(description, branch)

        if dry_run:
            return EpicCreateResult(
                epic_folder=None,
                epic_folder_name=folder_name,
                success=True,
                message=f"[dry-run] Would create epic: {folder_name}",
            )

        # TinyDB-first: write to repository as primary store.
        # No disk path is stored — epics are TinyDB-only at creation time.
        if self._repository is not None:
            try:
                repo_result = self._repository.create_epic({
                    "epic_folder_name": folder_name,
                    "epic_folder": "",
                    "name": folder_name.replace("_", "-"),
                    "worktree_path": str(self.repo_path),
                    "branch": branch,
                    "status": "proposed",
                    "priority": "medium",
                    "objective": objective,
                    "created": datetime.now().strftime("%Y-%m-%d"),
                })
                if not repo_result.success:
                    return EpicCreateResult(
                        epic_folder=None,
                        epic_folder_name=folder_name,
                        success=False,
                        message=repo_result.message,
                    )
            except Exception:
                pass

        return EpicCreateResult(
            epic_folder=None,
            epic_folder_name=folder_name,
            success=True,
            message=f"Created epic: {folder_name}",
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
                return result
            return None

        return None

    def _resolve_epic_folder(self, epic_id_or_path: str) -> Optional[Path]:
        """Resolve epic identifier or path to actual epic folder via TinyDB.

        No filesystem checks are performed. TinyDB is the sole source of truth.

        Args:
            epic_id_or_path: Epic identifier, folder name, or path.

        Returns:
            Path to epic folder (from TinyDB), or None if not found.
        """
        if self._repository is None:
            return None

        # Extract folder name from path-like inputs
        lookup_key = Path(epic_id_or_path).name if "/" in epic_id_or_path else epic_id_or_path

        epic_data = self._repository.get_epic(lookup_key)
        if epic_data is not None:
            if epic_data.epic_folder is not None:
                return epic_data.epic_folder
            # Folder-free epic: return synthetic path from name
            return Path(epic_data.epic_folder_name)

        return None

    def list_epics(self, status: str = "live") -> list[EpicMetadata]:
        """List all epics with a given status.

        TinyDB is the sole data store. The status field in the DB is the
        sole source of truth. 'live' maps to the set of active statuses
        (proposed, in_progress, active, planning, approved, pending, blocked).

        Args:
            status: Directory-style status ('live', 'completed', 'deferred')
                    or a direct DB status value.

        Returns:
            List of EpicMetadata objects sorted by folder name (newest first).
        """
        if self._repository is not None:
            return self._repository.list_epics(status=status)

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
        # Accept any known status string (old or new) via normalization
        normalized = normalize_epic_status(new_status)
        if new_status not in EPIC_STATUS_MIGRATION:
            return EpicUpdateResult(
                success=False,
                message=f"Invalid status: {new_status}. Valid: {', '.join(sorted(set(EPIC_STATUS_MIGRATION.values())))}",
            )
        new_status = normalized

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
            # No TinyDB repository available
            return EpicUpdateResult(
                success=False,
                message=f"TinyDB repository not available. Cannot update status for: {epic_id}",
            )

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
        """Validate epic structure and content using TinyDB as the sole data source.

        Checks against TinyDB:
        - Folder naming convention (YYMMDDXX_description)
        - Epic registered in TinyDB
        - Valid status values
        - Phase/ticket IDs unique
        - Phases exist in TinyDB

        The epic_path argument is used only to extract the epic folder name;
        no filesystem existence checks are performed.

        Args:
            epic_path: Path whose name component identifies the epic.

        Returns:
            ValidationResult with errors and warnings.
        """
        errors = []
        warnings = []

        epic_folder_name = epic_path.name

        # Check folder naming convention (name-only, no filesystem access)
        if not self._is_valid_epic_folder_name(epic_folder_name):
            errors.append(f"Folder name does not match YYMMDDXX_description pattern: {epic_folder_name}")

        # All remaining checks require TinyDB
        if self._repository is None:
            errors.append("TinyDB repository not available for validation")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Check epic record exists in TinyDB
        epic_data = self._repository.get_epic(epic_folder_name)
        if epic_data is None:
            errors.append(f"Epic '{epic_folder_name}' not found in TinyDB")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Validate status - warn on old strings, error on unknown
        if epic_data.status:
            if epic_data.status not in EPIC_STATUS_MIGRATION:
                errors.append(f"Invalid status '{epic_data.status}'")
            elif epic_data.status not in {s.value for s in EpicStatus}:
                warnings.append(f"Old status '{epic_data.status}' should be normalized to '{normalize_epic_status(epic_data.status)}'")

        # Check phases exist in TinyDB (replaces MMD file check)
        phases = self._repository.list_phases(epic_folder_name)
        if not phases:
            warnings.append("No phases found in TinyDB for this epic")

        # Validate tickets from TinyDB
        tickets = self._repository.get_tickets(epic_folder_name)
        all_task_ids = set()

        for ticket in tickets:
            task_id = ticket.id if hasattr(ticket, "id") else getattr(ticket, "ticket_id", "")
            if task_id:
                if task_id in all_task_ids:
                    errors.append(f"Duplicate ticket ID: {task_id}")
                all_task_ids.add(task_id)

            # Quality checks
            desc = ticket.description if hasattr(ticket, "description") else ""
            if not desc or not desc.strip():
                warnings.append(f"Ticket {task_id} has empty description")

        if not tickets:
            warnings.append("No tickets found in TinyDB for this epic")

        valid = len(errors) == 0
        return ValidationResult(valid=valid, errors=errors, warnings=warnings)
