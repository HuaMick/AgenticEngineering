"""Tests for status normalization and backward compatibility.

Validates that old status strings are correctly mapped to the 6 canonical
values: active, planning, in_progress, completed, deferred, blocked.
"""

import pytest
from pathlib import Path

pytestmark = pytest.mark.story("US-PLN-082")

from agenticguidance.services.epic import (
    EpicService,
    EpicStatus,
    EPIC_STATUS_MIGRATION,
    normalize_epic_status,
)
from agenticguidance.services.epic_repository import EpicRepository
from agenticguidance.services.ticket import TicketStatus


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / ".agentic" / "epics.db"
    return EpicRepository(db_path=db_path)


@pytest.fixture
def epic_service(tmp_path, repo):
    epics_dir = tmp_path / "docs" / "epics" / "live"
    epics_dir.mkdir(parents=True)
    (tmp_path / ".git").mkdir()
    return EpicService(repo_path=tmp_path, repository=repo)


class TestEpicStatusNormalization:
    """Test normalize_epic_status for all legacy strings."""

    def test_active_is_canonical(self):
        assert normalize_epic_status("active") == "active"

    def test_approved_normalizes_to_in_progress(self):
        assert normalize_epic_status("approved") == "in_progress"

    def test_pending_normalizes_to_active(self):
        assert normalize_epic_status("pending") == "active"

    def test_planning_is_canonical(self):
        assert normalize_epic_status("planning") == "planning"

    def test_proposed_normalizes_to_active(self):
        assert normalize_epic_status("proposed") == "active"

    def test_canonical_values_unchanged(self):
        assert normalize_epic_status("active") == "active"
        assert normalize_epic_status("planning") == "planning"
        assert normalize_epic_status("in_progress") == "in_progress"
        assert normalize_epic_status("completed") == "completed"
        assert normalize_epic_status("deferred") == "deferred"
        assert normalize_epic_status("blocked") == "blocked"

    def test_cancelled_normalizes_to_completed(self):
        assert normalize_epic_status("cancelled") == "completed"

    def test_fully_completed_normalizes_to_completed(self):
        assert normalize_epic_status("fully_completed") == "completed"

    def test_partially_completed_normalizes_to_in_progress(self):
        assert normalize_epic_status("partially_completed") == "in_progress"

    def test_unknown_defaults_to_active(self):
        assert normalize_epic_status("nonsense") == "active"


class TestTicketStatusBackwardCompat:
    """Test that TicketStatus handles old 'pending' string."""

    def test_pending_string_maps_to_proposed(self):
        assert TicketStatus("pending") == TicketStatus.PROPOSED

    def test_proposed_value(self):
        assert TicketStatus.PROPOSED.value == "proposed"

    def test_proposed_string_works(self):
        assert TicketStatus("proposed") == TicketStatus.PROPOSED


class TestUpdateEpicStatusAcceptsOldStrings:
    """Test that update_epic_status accepts old status strings."""

    def test_active_accepted_as_canonical(self, epic_service, repo):
        epic_name = "260307TE_status_norm"
        epic_dir = epic_service.epics_base / "live" / epic_name
        epic_dir.mkdir(parents=True)
        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(epic_dir),
            "status": "planning",
        })

        result = epic_service.update_epic_status(epic_name, "active")
        assert result.success is True
        assert result.new_status == "active"

    def test_approved_accepted_and_normalized(self, epic_service, repo):
        epic_name = "260307TE_approved_norm"
        epic_dir = epic_service.epics_base / "live" / epic_name
        epic_dir.mkdir(parents=True)
        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(epic_dir),
            "status": "active",
        })

        result = epic_service.update_epic_status(epic_name, "approved")
        assert result.success is True
        assert result.new_status == "in_progress"


class TestValidateEpicWarnsOnOldStatuses:
    """Test that validate_epic warns on old statuses instead of erroring."""

    def test_warns_on_proposed_status(self, epic_service, repo):
        epic_name = "260307TE_warn_proposed"
        epic_dir = epic_service.epics_base / "live" / epic_name
        epic_dir.mkdir(parents=True)
        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(epic_dir),
            "status": "proposed",
        })

        result = epic_service.validate_epic_structure(epic_dir)
        assert result.valid is True  # Not an error
        assert any("proposed" in w for w in result.warnings)

    def test_no_warning_on_canonical_status(self, epic_service, repo):
        epic_name = "260307TE_no_warn"
        epic_dir = epic_service.epics_base / "live" / epic_name
        epic_dir.mkdir(parents=True)
        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(epic_dir),
            "status": "in_progress",
        })

        result = epic_service.validate_epic_structure(epic_dir)
        assert result.valid is True
        assert not any("status" in w.lower() for w in result.warnings)
