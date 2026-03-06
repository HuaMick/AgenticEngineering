"""Tests for ticket service (formerly task service)."""

import yaml
from pathlib import Path

import pytest

from agenticguidance.services.ticket import Ticket, TicketService, TicketStatus


# test_001: Test file structure with fixtures


@pytest.fixture
def sample_epic_path(tmp_path):
    """Create temporary epic directory with sample YAML."""
    epic_dir = tmp_path / "test_epic"
    epic_dir.mkdir()

    # Write ticket_build.yml with phases and tasks:
    # - 3 tickets: one pending, one in_progress, one completed
    # - Use phases[].tasks[] structure
    # - Include ticket without optional fields
    epic_content = {
        "name": "test-epic",
        "status": "active",
        "phases": [
            {
                "name": "Phase 1",
                "tickets": [
                    {
                        "id": "task_001",
                        "name": "First task",
                        "description": "A pending task",
                        "status": "pending",
                        "agent": "builder",
                        "inputs": ["input1.txt"],
                        "target_files": ["output1.py"],
                        "guidance": "Do the first thing",
                    },
                    {
                        "id": "task_002",
                        "name": "Second task",
                        "description": "An in-progress task",
                        "status": "in_progress",
                        "agent": "builder",
                    },
                    {
                        "id": "task_003",
                        "name": "Third task",
                        "description": "A completed task",
                        "status": "completed",
                        "completed_date": "2026-02-03",
                    },
                ],
            }
        ],
    }

    epic_file = epic_dir / "ticket_build.yml"
    with open(epic_file, "w", encoding="utf-8") as f:
        yaml.dump(epic_content, f, default_flow_style=False, sort_keys=False)

    return epic_dir


@pytest.fixture
def flat_plan_path(tmp_path):
    """Create epic with root-level tasks[] (legacy flat structure)."""
    epic_dir = tmp_path / "flat_epic"
    epic_dir.mkdir()

    # Write ticket_build.yml with root tasks: key
    epic_content = {
        "name": "flat-epic",
        "status": "active",
        "tasks": [
            {
                "id": "flat_001",
                "name": "Flat task",
                "description": "Root-level task",
                "status": "pending",
                "agent": "builder",
            },
            {
                "id": "flat_002",
                "name": "Flat completed",
                "description": "Completed flat task",
                "status": "completed",
                "completed_date": "2026-02-03",
            },
        ],
    }

    epic_file = epic_dir / "ticket_build.yml"
    with open(epic_file, "w", encoding="utf-8") as f:
        yaml.dump(epic_content, f, default_flow_style=False, sort_keys=False)

    return epic_dir


@pytest.fixture
def ticket_service(sample_epic_path):
    """Create TicketService with sample epic."""
    return TicketService(sample_epic_path)


# test_002: Ticket retrieval tests


class TestTicketRetrieval:
    """Tests for ticket retrieval methods."""

    def test_get_ticket_returns_ticket_by_id(self, ticket_service):
        """Test getting a ticket by ID returns correct ticket."""
        ticket = ticket_service.get_ticket("task_001")

        assert ticket is not None
        assert ticket.id == "task_001"
        assert ticket.name == "First task"
        assert ticket.description == "A pending task"
        assert ticket.status == TicketStatus.PENDING
        assert ticket.agent == "builder"
        assert ticket.inputs == ["input1.txt"]
        assert ticket.target_files == ["output1.py"]
        assert ticket.guidance == "Do the first thing"

    def test_get_ticket_returns_none_for_invalid_id(self, ticket_service):
        """Test getting a non-existent ticket returns None."""
        ticket = ticket_service.get_ticket("nonexistent_ticket")

        assert ticket is None

    def test_list_tickets_returns_all_tickets(self, ticket_service):
        """Test listing all tickets returns all tickets."""
        tickets = ticket_service.list_tickets()

        assert len(tickets) == 3
        ticket_ids = [t.id for t in tickets]
        assert "task_001" in ticket_ids
        assert "task_002" in ticket_ids
        assert "task_003" in ticket_ids

    def test_list_tickets_filters_by_status_pending(self, ticket_service):
        """Test listing tickets filtered by pending status."""
        tickets = ticket_service.list_tickets(status=TicketStatus.PENDING)

        assert len(tickets) == 1
        assert tickets[0].id == "task_001"
        assert tickets[0].status == TicketStatus.PENDING

    def test_list_tickets_filters_by_status_in_progress(self, ticket_service):
        """Test listing tickets filtered by in_progress status."""
        tickets = ticket_service.list_tickets(status=TicketStatus.IN_PROGRESS)

        assert len(tickets) == 1
        assert tickets[0].id == "task_002"
        assert tickets[0].status == TicketStatus.IN_PROGRESS

    def test_list_tickets_filters_by_status_completed(self, ticket_service):
        """Test listing tickets filtered by completed status."""
        tickets = ticket_service.list_tickets(status=TicketStatus.COMPLETED)

        assert len(tickets) == 1
        assert tickets[0].id == "task_003"
        assert tickets[0].status == TicketStatus.COMPLETED

    def test_get_current_ticket_returns_in_progress(self, ticket_service):
        """Test getting current ticket returns in_progress ticket."""
        ticket = ticket_service.get_current_ticket()

        assert ticket is not None
        assert ticket.id == "task_002"
        assert ticket.status == TicketStatus.IN_PROGRESS

    def test_get_current_ticket_returns_pending_when_none_in_progress(self, tmp_path):
        """Test current ticket returns pending when no in_progress tickets."""
        epic_dir = tmp_path / "pending_epic"
        epic_dir.mkdir()

        epic_content = {
            "name": "pending-epic",
            "phases": [
                {
                    "name": "Phase 1",
                    "tickets": [
                        {
                            "id": "task_001",
                            "name": "Pending task",
                            "description": "A pending task",
                            "status": "pending",
                        },
                    ],
                }
            ],
        }

        epic_file = epic_dir / "ticket_build.yml"
        with open(epic_file, "w", encoding="utf-8") as f:
            yaml.dump(epic_content, f, default_flow_style=False, sort_keys=False)

        service = TicketService(epic_dir)
        ticket = service.get_current_ticket()

        assert ticket is not None
        assert ticket.id == "task_001"
        assert ticket.status == TicketStatus.PENDING

    def test_get_current_ticket_returns_none_for_nonexistent_file(self, tmp_path):
        """Test current ticket returns None when epic file doesn't exist."""
        epic_dir = tmp_path / "missing_epic"
        epic_dir.mkdir()

        service = TicketService(epic_dir)
        ticket = service.get_current_ticket()

        assert ticket is None

    def test_get_current_ticket_works_with_flat_structure(self, flat_plan_path):
        """Test current ticket works with flat (root-level tasks) structure."""
        service = TicketService(flat_plan_path)
        ticket = service.get_current_ticket()

        # Should return pending ticket since no in_progress in flat structure
        assert ticket is not None
        assert ticket.id == "flat_001"
        assert ticket.status == TicketStatus.PENDING

    def test_get_current_ticket_returns_none_when_all_completed(self, tmp_path):
        """Test current ticket returns None when all tickets are completed."""
        epic_dir = tmp_path / "completed_epic"
        epic_dir.mkdir()

        epic_content = {
            "name": "completed-epic",
            "phases": [
                {
                    "name": "Phase 1",
                    "tickets": [
                        {
                            "id": "task_001",
                            "name": "Completed task",
                            "description": "A completed task",
                            "status": "completed",
                            "completed_date": "2026-02-03",
                        },
                    ],
                }
            ],
        }

        epic_file = epic_dir / "ticket_build.yml"
        with open(epic_file, "w", encoding="utf-8") as f:
            yaml.dump(epic_content, f, default_flow_style=False, sort_keys=False)

        service = TicketService(epic_dir)
        ticket = service.get_current_ticket()

        assert ticket is None


# test_003: Ticket update tests


class TestTicketUpdates:
    """Tests for ticket update methods."""

    def test_update_ticket_status_changes_status(self, ticket_service):
        """Test updating ticket status changes the status."""
        result = ticket_service.update_ticket_status("task_001", TicketStatus.IN_PROGRESS)

        assert result is True

        # Verify the change
        ticket = ticket_service.get_ticket("task_001")
        assert ticket.status == TicketStatus.IN_PROGRESS

    def test_update_ticket_status_adds_completed_date(self, ticket_service):
        """Test updating to completed status adds completed_date."""
        result = ticket_service.update_ticket_status("task_001", TicketStatus.COMPLETED)

        assert result is True

        # Verify the change
        ticket = ticket_service.get_ticket("task_001")
        assert ticket.status == TicketStatus.COMPLETED
        assert ticket.completed_date is not None
        # Check date format (YYYY-MM-DD)
        assert len(ticket.completed_date) == 10
        assert ticket.completed_date.count("-") == 2

    def test_update_ticket_status_returns_false_for_invalid_id(self, ticket_service):
        """Test updating non-existent ticket returns False."""
        result = ticket_service.update_ticket_status("nonexistent", TicketStatus.COMPLETED)

        assert result is False

    def test_start_ticket_sets_in_progress(self, ticket_service):
        """Test start_ticket convenience method sets status to in_progress."""
        result = ticket_service.start_ticket("task_001")

        assert result is True

        # Verify the change
        ticket = ticket_service.get_ticket("task_001")
        assert ticket.status == TicketStatus.IN_PROGRESS

    def test_complete_ticket_sets_completed_with_date(self, ticket_service):
        """Test complete_ticket convenience method sets completed status with date."""
        result = ticket_service.complete_ticket("task_001")

        assert result is True

        # Verify the change
        ticket = ticket_service.get_ticket("task_001")
        assert ticket.status == TicketStatus.COMPLETED
        assert ticket.completed_date is not None

    def test_yaml_persists_after_update(self, ticket_service):
        """Test that updates are persisted to YAML file."""
        # Update ticket
        ticket_service.update_ticket_status("task_001", TicketStatus.COMPLETED)

        # Create new service instance (re-read file)
        new_service = TicketService(ticket_service.epic_path)
        ticket = new_service.get_ticket("task_001")

        # Verify persisted change
        assert ticket.status == TicketStatus.COMPLETED
        assert ticket.completed_date is not None

    def test_complete_ticket_works_with_flat_structure(self, flat_plan_path):
        """Test completing a ticket in flat structure adds completed date."""
        service = TicketService(flat_plan_path)

        # Complete flat ticket
        result = service.complete_ticket("flat_001")
        assert result is True

        # Verify the change
        ticket = service.get_ticket("flat_001")
        assert ticket.status == TicketStatus.COMPLETED
        assert ticket.completed_date is not None


# test_004: Edge case tests


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_empty_epic_file(self, tmp_path):
        """Test handling of empty epic file."""
        epic_dir = tmp_path / "empty_epic"
        epic_dir.mkdir()

        epic_file = epic_dir / "ticket_build.yml"
        epic_file.write_text("")

        service = TicketService(epic_dir)

        # Should not crash
        tickets = service.list_tickets()
        assert tickets == []

        ticket = service.get_ticket("any_id")
        assert ticket is None

        current = service.get_current_ticket()
        assert current is None

    def test_handles_missing_phases_key(self, tmp_path):
        """Test handling of epic without phases key."""
        epic_dir = tmp_path / "no_phases_epic"
        epic_dir.mkdir()

        epic_content = {
            "name": "no-phases-epic",
            "status": "active",
        }

        epic_file = epic_dir / "ticket_build.yml"
        with open(epic_file, "w", encoding="utf-8") as f:
            yaml.dump(epic_content, f, default_flow_style=False, sort_keys=False)

        service = TicketService(epic_dir)

        # Should not crash
        tickets = service.list_tickets()
        assert tickets == []

    def test_handles_ticket_without_optional_fields(self, tmp_path):
        """Test handling of ticket with minimal fields."""
        epic_dir = tmp_path / "minimal_epic"
        epic_dir.mkdir()

        epic_content = {
            "name": "minimal-epic",
            "phases": [
                {
                    "name": "Phase 1",
                    "tickets": [
                        {
                            "id": "minimal_001",
                            "name": "Minimal task",
                            "description": "Task without optional fields",
                            "status": "pending",
                            # No agent, inputs, target_files, guidance, completed_date
                        },
                    ],
                }
            ],
        }

        epic_file = epic_dir / "ticket_build.yml"
        with open(epic_file, "w", encoding="utf-8") as f:
            yaml.dump(epic_content, f, default_flow_style=False, sort_keys=False)

        service = TicketService(epic_dir)
        ticket = service.get_ticket("minimal_001")

        assert ticket is not None
        assert ticket.id == "minimal_001"
        assert ticket.agent is None
        assert ticket.inputs == []
        assert ticket.target_files == []
        assert ticket.guidance is None
        assert ticket.completed_date is None

    def test_handles_malformed_yaml(self, tmp_path):
        """Test handling of malformed YAML file."""
        epic_dir = tmp_path / "malformed_epic"
        epic_dir.mkdir()

        epic_file = epic_dir / "ticket_build.yml"
        epic_file.write_text("invalid: yaml: content: [unclosed")

        service = TicketService(epic_dir)

        # Should not crash, returns None/empty
        ticket = service.get_ticket("any_id")
        assert ticket is None

        tickets = service.list_tickets()
        assert tickets == []

    def test_handles_nonexistent_epic_file(self, tmp_path):
        """Test handling of non-existent epic file."""
        epic_dir = tmp_path / "nonexistent_epic"
        epic_dir.mkdir()

        # Don't create ticket_build.yml
        service = TicketService(epic_dir)

        # Should not crash
        ticket = service.get_ticket("any_id")
        assert ticket is None

        tickets = service.list_tickets()
        assert tickets == []

        # Update should fail gracefully
        result = service.update_ticket_status("any_id", TicketStatus.COMPLETED)
        assert result is False

    def test_supports_both_nested_and_flat_ticket_structures(self, flat_plan_path):
        """Test that service handles both modern and legacy structures."""
        service = TicketService(flat_plan_path)

        # Should retrieve flat tickets
        tickets = service.list_tickets()
        assert len(tickets) == 2

        ticket = service.get_ticket("flat_001")
        assert ticket is not None
        assert ticket.id == "flat_001"
        assert ticket.name == "Flat task"

        # Should update flat tickets
        result = service.start_ticket("flat_001")
        assert result is True

        ticket = service.get_ticket("flat_001")
        assert ticket.status == TicketStatus.IN_PROGRESS

    def test_handles_invalid_status_value(self, tmp_path):
        """Test handling of invalid status value in YAML."""
        epic_dir = tmp_path / "invalid_status_epic"
        epic_dir.mkdir()

        epic_content = {
            "name": "invalid-status-epic",
            "phases": [
                {
                    "name": "Phase 1",
                    "tickets": [
                        {
                            "id": "task_001",
                            "name": "Task with invalid status",
                            "description": "Status is not valid",
                            "status": "invalid_status_value",
                        },
                    ],
                }
            ],
        }

        epic_file = epic_dir / "ticket_build.yml"
        with open(epic_file, "w", encoding="utf-8") as f:
            yaml.dump(epic_content, f, default_flow_style=False, sort_keys=False)

        service = TicketService(epic_dir)
        ticket = service.get_ticket("task_001")

        # Should default to PENDING for invalid status
        assert ticket is not None
        assert ticket.status == TicketStatus.PENDING


# test_005: Additional tests for Ticket dataclass


class TestTicketDataclass:
    """Tests for Ticket dataclass."""

    def test_ticket_creation_with_defaults(self):
        """Test creating Ticket with default values."""
        ticket = Ticket(
            id="test_001",
            name="Test Ticket",
            description="Test description",
            status=TicketStatus.PENDING,
        )

        assert ticket.id == "test_001"
        assert ticket.name == "Test Ticket"
        assert ticket.description == "Test description"
        assert ticket.status == TicketStatus.PENDING
        assert ticket.agent is None
        assert ticket.inputs == []
        assert ticket.target_files == []
        assert ticket.guidance is None
        assert ticket.completed_date is None

    def test_ticket_creation_with_all_fields(self):
        """Test creating Ticket with all fields."""
        ticket = Ticket(
            id="test_001",
            name="Test Ticket",
            description="Test description",
            status=TicketStatus.IN_PROGRESS,
            agent="builder",
            inputs=["input1.txt", "input2.txt"],
            target_files=["output.py"],
            guidance="Do something specific",
            completed_date="2026-02-03",
        )

        assert ticket.agent == "builder"
        assert len(ticket.inputs) == 2
        assert len(ticket.target_files) == 1
        assert ticket.guidance == "Do something specific"
        assert ticket.completed_date == "2026-02-03"


class TestTicketStatus:
    """Tests for TicketStatus enum."""

    def test_status_values(self):
        """Test TicketStatus enum values."""
        assert TicketStatus.PENDING.value == "pending"
        assert TicketStatus.IN_PROGRESS.value == "in_progress"
        assert TicketStatus.COMPLETED.value == "completed"

    def test_status_from_string(self):
        """Test creating TicketStatus from string."""
        assert TicketStatus("pending") == TicketStatus.PENDING
        assert TicketStatus("in_progress") == TicketStatus.IN_PROGRESS
        assert TicketStatus("completed") == TicketStatus.COMPLETED


# Integration tests with real epic files


class TestIntegrationRealEpic:
    """Integration tests using real epic files from the repository."""

    def test_reads_real_epic_file(self):
        """Test reading actual epic file from repository."""
        # Use the actual TicketService epic file
        real_epic_path = Path("/home/code/AgenticEngineering/docs/epics/completed/260203TS_task_service")

        # Verify epic folder exists
        assert real_epic_path.exists(), f"Epic folder not found: {real_epic_path}"
        assert (real_epic_path / "ticket_build.yml").exists(), "Epic file not found"

        # Create TicketService with real epic
        service = TicketService(real_epic_path)

        # List all tickets
        tickets = service.list_tickets()

        # The epic has impl_001-004, test_001-005, integ_001, audit_001-002
        # Total: 4 + 5 + 1 + 2 = 12 tickets
        assert len(tickets) >= 12, f"Expected at least 12 tickets, got {len(tickets)}"

        # Verify Ticket objects have correct data types
        for ticket in tickets:
            assert isinstance(ticket.id, str)
            assert isinstance(ticket.name, str)
            assert isinstance(ticket.description, str)
            assert isinstance(ticket.status, TicketStatus)
            assert ticket.agent is None or isinstance(ticket.agent, str)
            assert isinstance(ticket.inputs, list)
            assert isinstance(ticket.target_files, list)
            assert ticket.guidance is None or isinstance(ticket.guidance, str)
            assert ticket.completed_date is None or isinstance(ticket.completed_date, str)

        # Verify we can find specific tickets
        ticket_ids = {t.id for t in tickets}
        assert "impl_001" in ticket_ids
        assert "impl_002" in ticket_ids
        assert "impl_003" in ticket_ids
        assert "impl_004" in ticket_ids
        assert "test_001" in ticket_ids
        assert "test_005" in ticket_ids
        assert "integ_001" in ticket_ids
        assert "audit_001" in ticket_ids

    def test_get_ticket_from_real_epic(self):
        """Test retrieving specific ticket from real epic."""
        real_epic_path = Path("/home/code/AgenticEngineering/docs/epics/completed/260203TS_task_service")
        service = TicketService(real_epic_path)

        # Get a specific ticket
        ticket = service.get_ticket("audit_001")

        assert ticket is not None
        assert ticket.id == "audit_001"
        assert ticket.name == "Test quality audit"
        assert ticket.description == "Review tests for proper assertions and real behavior validation"
        # Note: Status may vary based on execution state
        assert ticket.status in [TicketStatus.PENDING, TicketStatus.IN_PROGRESS, TicketStatus.COMPLETED]
        assert ticket.agent == "test-audit"

        # Check inputs field exists and is a list
        assert isinstance(ticket.inputs, list)
        assert len(ticket.inputs) >= 2

        # Verify guidance is present
        assert ticket.guidance is not None
        assert len(ticket.guidance) > 0

    def test_status_update_on_copy_of_real_epic(self, tmp_path):
        """Test updating ticket status on a copy of the real epic preserves YAML."""
        import shutil

        # Copy the real epic folder to tmp_path
        real_epic_path = Path("/home/code/AgenticEngineering/docs/epics/completed/260203TS_task_service")
        temp_epic_path = tmp_path / "test_epic_copy"
        shutil.copytree(real_epic_path, temp_epic_path)

        # Create TicketService pointing to temp copy
        service = TicketService(temp_epic_path)

        # Get a ticket that's currently completed
        ticket = service.get_ticket("impl_001")
        original_status = ticket.status

        # Update status (use a non-destructive change for a ticket that's already completed)
        # Let's find a pending ticket and start it
        pending_tickets = service.list_tickets(status=TicketStatus.PENDING)
        if pending_tickets:
            test_ticket_id = pending_tickets[0].id

            # Update the ticket
            result = service.start_ticket(test_ticket_id)
            assert result is True

            # Re-read the YAML file directly and verify change persisted
            epic_file = temp_epic_path / "ticket_build.yml"
            with open(epic_file, "r", encoding="utf-8") as f:
                epic_data = yaml.safe_load(f)

            # Find the ticket in the YAML
            found = False
            for phase in epic_data.get("phases", []):
                for ticket_data in phase.get("tickets", []):
                    if ticket_data.get("id") == test_ticket_id:
                        assert ticket_data.get("status") == "in_progress"
                        found = True
                        break
                if found:
                    break

            assert found, f"Ticket {test_ticket_id} not found in YAML after update"

            # Verify YAML formatting preserved - check that other fields are still present
            assert "name" in epic_data
            assert "phases" in epic_data

    def test_round_trip_preserves_yaml(self, tmp_path):
        """Test that load-update-save-reload cycle preserves data."""
        import shutil

        # Copy the real epic folder to tmp_path
        real_epic_path = Path("/home/code/AgenticEngineering/docs/epics/completed/260203TS_task_service")
        temp_epic_path = tmp_path / "roundtrip_epic"
        shutil.copytree(real_epic_path, temp_epic_path)

        # First load: get all tickets
        service1 = TicketService(temp_epic_path)
        original_tickets = service1.list_tickets()
        original_count = len(original_tickets)

        # Find a pending ticket and complete it
        pending_tickets = service1.list_tickets(status=TicketStatus.PENDING)
        if pending_tickets:
            test_ticket_id = pending_tickets[0].id

            # Update status
            result = service1.complete_ticket(test_ticket_id)
            assert result is True

            # Verify with same service instance
            updated_ticket = service1.get_ticket(test_ticket_id)
            assert updated_ticket.status == TicketStatus.COMPLETED
            assert updated_ticket.completed_date is not None

            # Create NEW service instance (simulates reload)
            service2 = TicketService(temp_epic_path)

            # Re-load the same ticket
            reloaded_ticket = service2.get_ticket(test_ticket_id)

            # Verify data is still intact
            assert reloaded_ticket is not None
            assert reloaded_ticket.id == test_ticket_id
            assert reloaded_ticket.status == TicketStatus.COMPLETED
            assert reloaded_ticket.completed_date is not None
            assert reloaded_ticket.name == updated_ticket.name
            assert reloaded_ticket.description == updated_ticket.description

            # Verify total ticket count unchanged
            reloaded_tickets = service2.list_tickets()
            assert len(reloaded_tickets) == original_count

            # Verify other tickets unchanged
            for orig_ticket in original_tickets:
                if orig_ticket.id != test_ticket_id:
                    reloaded = service2.get_ticket(orig_ticket.id)
                    assert reloaded.status == orig_ticket.status
