"""Tests for Ticket.story_ids field and TicketData.story_ids field (P4-T2).

Validates the story_ids field added to both Ticket and TicketData dataclasses
in the 260308PD_planner_design_agent_story_alignment epic.
"""

import tempfile
from pathlib import Path

import pytest

from agenticguidance.services.epic import TicketData
from agenticguidance.services.ticket import Ticket, TicketStatus

pytestmark = pytest.mark.story("US-STR-009")


# ---------------------------------------------------------------------------
# Ticket dataclass tests
# ---------------------------------------------------------------------------

@pytest.mark.story("US-STR-011")
class TestTicketStoryIds:
    """Test Ticket dataclass story_ids field."""

    def test_default_story_ids_is_empty_list(self):
        """Verify story_ids defaults to empty list."""
        ticket = Ticket(
            id="T1",
            name="Test ticket",
            description="A test ticket",
            status=TicketStatus.PROPOSED,
        )
        assert ticket.story_ids == []

    def test_story_ids_set_via_constructor(self):
        """Verify story_ids can be set via constructor."""
        ticket = Ticket(
            id="T1",
            name="Test ticket",
            description="A test ticket",
            status=TicketStatus.PROPOSED,
            story_ids=["US-CLI-110", "US-CLI-111"],
        )
        assert ticket.story_ids == ["US-CLI-110", "US-CLI-111"]

    def test_story_ids_single_id(self):
        """Verify story_ids works with a single ID."""
        ticket = Ticket(
            id="T1",
            name="Test ticket",
            description="A test ticket",
            status=TicketStatus.PROPOSED,
            story_ids=["US-ORCH-001"],
        )
        assert len(ticket.story_ids) == 1
        assert ticket.story_ids[0] == "US-ORCH-001"

    def test_story_ids_mutable(self):
        """Verify story_ids list is mutable (can append)."""
        ticket = Ticket(
            id="T1",
            name="Test ticket",
            description="A test ticket",
            status=TicketStatus.PROPOSED,
        )
        ticket.story_ids.append("US-CLI-110")
        assert ticket.story_ids == ["US-CLI-110"]

    def test_ticket_fields_unchanged(self):
        """Verify existing Ticket fields still work after adding story_ids."""
        ticket = Ticket(
            id="T1",
            name="Test ticket",
            description="A test ticket",
            status=TicketStatus.PROPOSED,
            agent="build-python",
            inputs=["file1.py"],
            target_files=["output.py"],
            guidance="Build it right",
            completed_date="2026-03-08",
            story_ids=["US-CLI-110"],
        )
        assert ticket.id == "T1"
        assert ticket.agent == "build-python"
        assert ticket.inputs == ["file1.py"]
        assert ticket.target_files == ["output.py"]
        assert ticket.guidance == "Build it right"
        assert ticket.completed_date == "2026-03-08"


# ---------------------------------------------------------------------------
# TicketData dataclass tests
# ---------------------------------------------------------------------------

@pytest.mark.story("US-STR-011")
class TestTicketDataStoryIds:
    """Test TicketData dataclass story_ids field."""

    def test_default_story_ids_is_empty_list(self):
        """Verify story_ids defaults to empty list via __post_init__."""
        td = TicketData(id="T1", name="Test")
        assert td.story_ids == []

    def test_story_ids_set_via_constructor(self):
        """Verify story_ids can be set via constructor."""
        td = TicketData(
            id="T1",
            name="Test",
            story_ids=["US-CLI-110", "US-CLI-111"],
        )
        assert td.story_ids == ["US-CLI-110", "US-CLI-111"]

    def test_none_story_ids_becomes_empty_list(self):
        """Verify None story_ids is converted to empty list by __post_init__."""
        td = TicketData(id="T1", name="Test", story_ids=None)
        assert td.story_ids == []

    def test_ticket_data_fields_unchanged(self):
        """Verify existing TicketData fields still work."""
        td = TicketData(
            id="T1",
            name="Test",
            description="desc",
            status="proposed",
            agent="build-python",
            phase_name="Build",
            inputs=["f1.py"],
            target_files=["out.py"],
            guidance="guidance text",
            completed_date="2026-03-08",
            success_criteria="All tests pass",
            story_ids=["US-CLI-110"],
        )
        assert td.id == "T1"
        assert td.agent == "build-python"
        assert td.story_ids == ["US-CLI-110"]


# ---------------------------------------------------------------------------
# TicketService conversion tests
# ---------------------------------------------------------------------------

@pytest.mark.story("US-STR-011")
class TestTicketServiceStoryIds:
    """Test TicketService conversion methods handle story_ids."""

    def test_ticket_dict_to_dataclass_with_story_ids(self):
        """Verify _ticket_dict_to_dataclass includes story_ids."""
        from agenticguidance.services.ticket import TicketService

        # Create a minimal TicketService (repository=None is fine for this test)
        svc = TicketService(
            epic_path=Path("/tmp/fake_epic"),
            repository=None,
        )

        ticket_data = {
            "id": "T1",
            "name": "Test ticket",
            "description": "desc",
            "status": "proposed",
            "story_ids": ["US-CLI-110", "US-CLI-111"],
        }
        ticket = svc._ticket_dict_to_dataclass(ticket_data)
        assert ticket.story_ids == ["US-CLI-110", "US-CLI-111"]

    def test_ticket_dict_to_dataclass_without_story_ids(self):
        """Verify _ticket_dict_to_dataclass defaults story_ids to empty list."""
        from agenticguidance.services.ticket import TicketService

        svc = TicketService(
            epic_path=Path("/tmp/fake_epic"),
            repository=None,
        )

        ticket_data = {
            "id": "T1",
            "name": "Test ticket",
            "description": "desc",
            "status": "proposed",
        }
        ticket = svc._ticket_dict_to_dataclass(ticket_data)
        assert ticket.story_ids == []

    def test_taskdata_to_ticket_with_story_ids(self):
        """Verify _taskdata_to_ticket includes story_ids from TicketData."""
        from agenticguidance.services.ticket import TicketService

        svc = TicketService(
            epic_path=Path("/tmp/fake_epic"),
            repository=None,
        )

        td = TicketData(
            id="T1",
            name="Test",
            story_ids=["US-CLI-110"],
        )
        ticket = svc._taskdata_to_ticket(td)
        assert ticket.story_ids == ["US-CLI-110"]

    def test_taskdata_to_ticket_without_story_ids(self):
        """Verify _taskdata_to_ticket handles TicketData without story_ids attr."""
        from agenticguidance.services.ticket import TicketService

        svc = TicketService(
            epic_path=Path("/tmp/fake_epic"),
            repository=None,
        )

        td = TicketData(id="T1", name="Test")
        ticket = svc._taskdata_to_ticket(td)
        assert ticket.story_ids == []


# ---------------------------------------------------------------------------
# EpicRepository story_ids persistence tests
# ---------------------------------------------------------------------------

@pytest.mark.story("US-STR-011")
class TestEpicRepositoryStoryIds:
    """Test EpicRepository stores and retrieves story_ids."""

    def test_add_ticket_with_story_ids(self, tmp_path):
        """Verify add_ticket persists story_ids to TinyDB."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path)

        # Create epic and phase first
        repo.create_epic({
            "epic_folder_name": "test_epic",
            "epic_folder": str(tmp_path / "test_epic"),
            "description": "Test epic",
        })
        repo.add_phase("test_epic", {
            "name": "Build",
            "status": "pending",
        })

        # Add ticket with story_ids
        ticket_data = {
            "id": "T1",
            "name": "Build feature",
            "description": "Build the feature",
            "status": "proposed",
            "story_ids": ["US-CLI-110", "US-CLI-111"],
        }
        added = repo.add_ticket("test_epic", "Build", ticket_data)
        assert added is True

        # Retrieve and verify
        ticket = repo.get_ticket("test_epic", "T1")
        assert ticket is not None
        assert ticket.story_ids == ["US-CLI-110", "US-CLI-111"]

    def test_get_tickets_includes_story_ids(self, tmp_path):
        """Verify get_tickets returns story_ids."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path)

        repo.create_epic({
            "epic_folder_name": "test_epic",
            "epic_folder": str(tmp_path / "test_epic"),
            "description": "Test epic",
        })
        repo.add_phase("test_epic", {"name": "Build", "status": "pending"})
        repo.add_ticket("test_epic", "Build", {
            "id": "T1",
            "name": "Task 1",
            "description": "Task 1 desc",
            "status": "proposed",
            "story_ids": ["US-CLI-110"],
        })

        tickets = repo.get_tickets("test_epic")
        assert len(tickets) == 1
        assert tickets[0].story_ids == ["US-CLI-110"]

    def test_ticket_without_story_ids_defaults_to_empty(self, tmp_path):
        """Verify tickets created without story_ids get empty list."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path)

        repo.create_epic({
            "epic_folder_name": "test_epic",
            "epic_folder": str(tmp_path / "test_epic"),
            "description": "Test epic",
        })
        repo.add_phase("test_epic", {"name": "Build", "status": "pending"})
        repo.add_ticket("test_epic", "Build", {
            "id": "T1",
            "name": "Task 1",
            "description": "Task 1 desc",
            "status": "proposed",
        })

        ticket = repo.get_ticket("test_epic", "T1")
        assert ticket is not None
        assert ticket.story_ids == []

    def test_update_ticket_story_ids(self, tmp_path):
        """Verify story_ids can be updated via update_ticket."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path)

        repo.create_epic({
            "epic_folder_name": "test_epic",
            "epic_folder": str(tmp_path / "test_epic"),
            "description": "Test epic",
        })
        repo.add_phase("test_epic", {"name": "Build", "status": "pending"})
        repo.add_ticket("test_epic", "Build", {
            "id": "T1",
            "name": "Task 1",
            "description": "Task 1 desc",
            "status": "proposed",
        })

        # Update story_ids
        repo.update_ticket("test_epic", "T1", {"story_ids": ["US-CLI-110"]})

        ticket = repo.get_ticket("test_epic", "T1")
        assert ticket is not None
        assert ticket.story_ids == ["US-CLI-110"]
