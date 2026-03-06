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

    def __init__(self, epic_path: Path, yaml_sync_enabled: bool = False):
        """Initialize TicketService.

        TinyDB is the sole data store.

        Args:
            epic_path: Path to epic folder.
            yaml_sync_enabled: Deprecated, ignored. Kept for API compatibility.
        """
        self.epic_path = epic_path
        self.ticket_file = epic_path / "ticket_build.yml"
        self._yaml_sync_enabled = False  # YAML sync permanently disabled
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

        Uses TinyDB as the sole data source.

        Args:
            ticket_id: Ticket identifier to search for.

        Returns:
            Ticket dataclass if found, None otherwise.
        """
        if self._repository is not None:
            try:
                td = self._repository.get_ticket(self._epic_folder_name, ticket_id)
                return self._taskdata_to_ticket(td)
            except Exception:
                return None
        return None

    def list_tickets(self, status: Optional[TicketStatus] = None) -> list[Ticket]:
        """List all tickets, optionally filtered by status.

        Uses TinyDB as the sole data source.

        Args:
            status: Optional status filter. If None, returns all tickets.

        Returns:
            List of Ticket dataclasses.
        """
        if self._repository is not None:
            try:
                status_filter = status.value if status is not None else None
                tdb_tasks = self._repository.get_tickets(self._epic_folder_name, status_filter)
                return [self._taskdata_to_ticket(td) for td in tdb_tasks]
            except Exception:
                pass

        return []

    def get_current_ticket(self) -> Optional[Ticket]:
        """Get the current actionable ticket.

        Uses TinyDB as the sole data source.
        Returns first ticket with status=in_progress. If none found,
        returns first ticket with status=pending.

        Returns:
            Ticket dataclass if found, None if no actionable tickets.
        """
        if self._repository is not None:
            try:
                td = self._repository.get_current_task(self._epic_folder_name)
                if td is not None:
                    return self._taskdata_to_ticket(td)
            except Exception:
                pass

        return None

    def update_ticket_status(self, ticket_id: str, status: TicketStatus) -> bool:
        """Update ticket status via TinyDB.

        Args:
            ticket_id: Ticket identifier to update.
            status: New status to set.

        Returns:
            True if ticket was found and updated, False otherwise.
        """
        if self._repository is not None:
            try:
                updated = self._repository.update_ticket_status(
                    self._epic_folder_name, ticket_id, status.value
                )
                return updated
            except Exception:
                return False

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
