"""Ticket Service - CRUD operations for tickets in epic YAML files.

Provides programmatic access to ticket data within epic files, supporting both
modern (phases[].tasks[]) and legacy (tasks[]) structures.
"""

import yaml
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from .state import FileLock


class TicketStatus(Enum):
    """Status of a ticket."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class Ticket:
    """Ticket data structure from epic YAML files."""

    id: str
    name: str
    description: str
    status: TicketStatus
    agent: Optional[str] = None
    inputs: list[str] = field(default_factory=list)
    target_files: list[str] = field(default_factory=list)
    guidance: Optional[str] = None
    completed_date: Optional[str] = None


class TicketService:
    """Service for managing tickets in epic YAML files.

    Handles both modern (phases[].tasks[]) and legacy (tasks[]) plan structures
    with atomic file operations using FileLock.
    """

    def __init__(self, epic_path: Path, yaml_sync_enabled: bool = True):
        """Initialize TicketService.

        TinyDB is the primary data store for all writes. YAML files are
        optionally kept in sync for git visibility. If TinyDB is unavailable
        (import failure), YAML serves as emergency fallback.

        Args:
            epic_path: Path to epic folder (e.g., docs/plans/live/260203TS_task_service/).
                       The service will look for ticket_build.yml in this folder.
            yaml_sync_enabled: If True, keep YAML files in sync with TinyDB
                              after writes. Defaults to True.
        """
        self.epic_path = epic_path
        self.ticket_file = epic_path / "ticket_build.yml"
        self._yaml_sync_enabled = yaml_sync_enabled
        self._epic_folder_name = epic_path.name  # For TinyDB lookups
        self._repository = None
        try:
            from .epic_repository import EpicRepository
            # Derive db_path from epic_path's repo root for test isolation
            repo_root = epic_path
            while repo_root != repo_root.parent:
                if (repo_root / ".git").exists():
                    break
                repo_root = repo_root.parent
            db_path = repo_root / ".agentic" / "epics.db"
            self._repository = EpicRepository(db_path=db_path)
        except Exception:
            pass  # Emergency: fall back to pure YAML

    def _load_ticket_file(self) -> dict:
        """Load ticket YAML file.

        Returns:
            Dictionary containing ticket data with root-level keys.

        Raises:
            FileNotFoundError: If ticket file doesn't exist.
            yaml.YAMLError: If YAML parsing fails.
        """
        if not self.ticket_file.exists():
            raise FileNotFoundError(f"Ticket file not found: {self.ticket_file}")

        with open(self.ticket_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            return {}

        return data

    def _save_ticket_file(self, data: dict) -> None:
        """Save ticket data to YAML file.

        Note: Caller is responsible for file locking if needed.

        Args:
            data: Ticket data dictionary to save.
        """
        with open(self.ticket_file, "w", encoding="utf-8") as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    @staticmethod
    def _get_ticket_id(ticket_data: dict) -> str:
        """Extract ticket ID from dict, checking both 'id' and 'task_id' keys."""
        return ticket_data.get("id") or ticket_data.get("task_id") or ""

    def _ticket_dict_to_dataclass(self, ticket_data: dict) -> Ticket:
        """Convert ticket dictionary to Ticket dataclass.

        Args:
            ticket_data: Raw ticket dictionary from YAML.

        Returns:
            Ticket dataclass instance.
        """
        # Parse status enum
        status_str = ticket_data.get("status", "pending")
        try:
            status = TicketStatus(status_str)
        except ValueError:
            # Default to pending if status is invalid
            status = TicketStatus.PENDING

        return Ticket(
            id=self._get_ticket_id(ticket_data),
            name=ticket_data.get("name", ""),
            description=ticket_data.get("description", ""),
            status=status,
            agent=ticket_data.get("agent"),
            inputs=ticket_data.get("inputs") or ticket_data.get("file_inputs", []),
            target_files=ticket_data.get("target_files", []),
            guidance=ticket_data.get("guidance"),
            completed_date=ticket_data.get("completed_date"),
        )

    def _taskdata_to_ticket(self, td) -> Optional[Ticket]:
        """Convert PlanRepository's TaskData to the Ticket dataclass.

        Args:
            td: TaskData instance from PlanRepository, or None.

        Returns:
            Ticket dataclass if td is not None, None otherwise.
        """
        if td is None:
            return None
        try:
            status = TicketStatus(td.status) if td.status else TicketStatus.PENDING
        except ValueError:
            status = TicketStatus.PENDING
        return Ticket(
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

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Get a ticket by ID.

        Reads from YAML to get full ticket details.
        Searches in phases[].tasks[] first, then root-level tasks[].

        Args:
            ticket_id: Ticket identifier to search for.

        Returns:
            Ticket dataclass if found, None otherwise.
        """
        # Always use YAML for get_ticket - needs full detail (inputs, guidance, etc.)
        try:
            data = self._load_ticket_file()
        except (FileNotFoundError, yaml.YAMLError):
            return None

        # Search in phases[].tasks[]
        phases = data.get("phases", [])
        if phases:
            for phase in phases:
                tasks = phase.get("tickets", [])
                for ticket_data in tasks:
                    if self._get_ticket_id(ticket_data) == ticket_id:
                        return self._ticket_dict_to_dataclass(ticket_data)

        # Fall back to root-level tasks[] for backward compatibility
        root_tasks = data.get("tasks", [])
        for ticket_data in root_tasks:
            if self._get_ticket_id(ticket_data) == ticket_id:
                return self._ticket_dict_to_dataclass(ticket_data)

        return None

    def list_tickets(self, status: Optional[TicketStatus] = None) -> list[Ticket]:
        """List all tickets, optionally filtered by status.

        Tries TinyDB first if available, then falls back to YAML.
        Collects tickets from both phases[].tasks[] and root-level tasks[].

        Args:
            status: Optional status filter. If None, returns all tickets.

        Returns:
            List of Ticket dataclasses.
        """
        # Try TinyDB first - only trust the result if the plan is confirmed in DB
        # (an empty list may mean plan was never imported, not that it has no tickets)
        if self._repository is not None:
            try:
                plan_in_db = self._repository.get_epic(self._epic_folder_name) is not None
                if plan_in_db:
                    status_filter = status.value if status is not None else None
                    tdb_tasks = self._repository.get_tickets(self._epic_folder_name, status_filter)
                    return [self._taskdata_to_ticket(td) for td in tdb_tasks]
            except Exception:
                pass

        try:
            data = self._load_ticket_file()
        except (FileNotFoundError, yaml.YAMLError):
            return []

        all_tickets = []

        # Collect from phases[].tasks[]
        phases = data.get("phases", [])
        if phases:
            for phase in phases:
                tasks = phase.get("tickets", [])
                for ticket_data in tasks:
                    ticket = self._ticket_dict_to_dataclass(ticket_data)
                    all_tickets.append(ticket)

        # Collect from root-level tasks[]
        root_tasks = data.get("tasks", [])
        for ticket_data in root_tasks:
            ticket = self._ticket_dict_to_dataclass(ticket_data)
            all_tickets.append(ticket)

        # Filter by status if provided
        if status is not None:
            all_tickets = [t for t in all_tickets if t.status == status]

        return all_tickets

    def get_current_ticket(self) -> Optional[Ticket]:
        """Get the current actionable ticket.

        Tries TinyDB first if available, then falls back to YAML.
        Returns first ticket with status=in_progress. If none found,
        returns first ticket with status=pending.

        Returns:
            Ticket dataclass if found, None if no actionable tickets.
        """
        # Try TinyDB first
        if self._repository is not None:
            try:
                td = self._repository.get_current_task(self._epic_folder_name)
                if td is not None:
                    return self._taskdata_to_ticket(td)
            except Exception:
                pass

        try:
            data = self._load_ticket_file()
        except (FileNotFoundError, yaml.YAMLError):
            return None

        # First pass: look for in_progress tickets
        in_progress_ticket = None
        pending_ticket = None

        # Search in phases[].tasks[]
        phases = data.get("phases", [])
        if phases:
            for phase in phases:
                tasks = phase.get("tickets", [])
                for ticket_data in tasks:
                    ticket = self._ticket_dict_to_dataclass(ticket_data)
                    if ticket.status == TicketStatus.IN_PROGRESS and in_progress_ticket is None:
                        in_progress_ticket = ticket
                    elif ticket.status == TicketStatus.PENDING and pending_ticket is None:
                        pending_ticket = ticket

        # Search in root-level tasks[]
        root_tasks = data.get("tasks", [])
        for ticket_data in root_tasks:
            ticket = self._ticket_dict_to_dataclass(ticket_data)
            if ticket.status == TicketStatus.IN_PROGRESS and in_progress_ticket is None:
                in_progress_ticket = ticket
            elif ticket.status == TicketStatus.PENDING and pending_ticket is None:
                pending_ticket = ticket

        # Return in_progress first, then pending, then None
        return in_progress_ticket or pending_ticket

    def update_ticket_status(self, ticket_id: str, status: TicketStatus) -> bool:
        """Update ticket status. TinyDB is primary, YAML sync is optional.

        Writes to TinyDB via PlanRepository first (which handles its own
        FileLock). Optionally syncs YAML for git visibility. Falls back
        to direct YAML writes only if TinyDB is unavailable.

        Args:
            ticket_id: Ticket identifier to update.
            status: New status to set.

        Returns:
            True if ticket was found and updated, False otherwise.
        """
        # TinyDB-first: write via repository (handles its own locking)
        if self._repository is not None:
            try:
                updated = self._repository.update_ticket_status(
                    self._epic_folder_name, ticket_id, status.value
                )
                if not updated:
                    return False
                # Optionally sync to YAML for git visibility
                if self._yaml_sync_enabled:
                    try:
                        self._repository.sync_to_yaml(self._epic_folder_name)
                    except Exception:
                        pass  # YAML sync failure is non-fatal
                return True
            except Exception:
                pass  # Fall through to YAML emergency fallback

        # Emergency YAML fallback (only when repository import failed)
        return self._update_ticket_status_yaml(ticket_id, status)

    def _update_ticket_status_yaml(self, ticket_id: str, status: TicketStatus) -> bool:
        """Emergency YAML fallback for ticket status updates.

        Used only when PlanRepository is unavailable (import failure at init).
        """
        try:
            with FileLock(self.ticket_file):
                data = self._load_ticket_file()
                ticket_found = False

                # Try to find and update ticket in phases[].tasks[]
                phases = data.get("phases", [])
                if phases:
                    for phase in phases:
                        tasks = phase.get("tickets", [])
                        for ticket_data in tasks:
                            if self._get_ticket_id(ticket_data) == ticket_id:
                                ticket_data["status"] = status.value
                                if status == TicketStatus.COMPLETED:
                                    ticket_data["completed_date"] = datetime.now().strftime("%Y-%m-%d")
                                ticket_found = True
                                break
                        if ticket_found:
                            break

                # If not found in phases, try root-level tasks[]
                if not ticket_found:
                    root_tasks = data.get("tasks", [])
                    for ticket_data in root_tasks:
                        if self._get_ticket_id(ticket_data) == ticket_id:
                            ticket_data["status"] = status.value
                            if status == TicketStatus.COMPLETED:
                                ticket_data["completed_date"] = datetime.now().strftime("%Y-%m-%d")
                            ticket_found = True
                            break

                if ticket_found:
                    self._save_ticket_file(data)
                    return True

                return False

        except (FileNotFoundError, yaml.YAMLError):
            return False

    def start_ticket(self, ticket_id: str) -> bool:
        """Mark ticket as in_progress.

        Convenience wrapper for update_ticket_status with IN_PROGRESS status.

        Args:
            ticket_id: Ticket identifier to start.

        Returns:
            True if ticket was found and updated, False otherwise.
        """
        return self.update_ticket_status(ticket_id, TicketStatus.IN_PROGRESS)

    def complete_ticket(self, ticket_id: str) -> bool:
        """Mark ticket as completed with timestamp.

        Convenience wrapper for update_ticket_status with COMPLETED status.
        Automatically adds completed_date in ISO 8601 format (YYYY-MM-DD).

        Args:
            ticket_id: Ticket identifier to complete.

        Returns:
            True if ticket was found and updated, False otherwise.
        """
        return self.update_ticket_status(ticket_id, TicketStatus.COMPLETED)
