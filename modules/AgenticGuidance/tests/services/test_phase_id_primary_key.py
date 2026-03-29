"""Tests for phase_id as primary key in EpicRepository.

Validates:
- Duplicate phase_id rejection
- Duplicate phase_name rejection (existing behavior)
- update_phase resolves by phase_id
- delete_phase resolves by phase_id
- get_phase prioritizes phase_id over phase_name
"""

import pytest

from agenticguidance.services.epic_repository import EpicRepository


@pytest.fixture
def repo(tmp_path):
    """Create an isolated EpicRepository backed by tmp_path."""
    db_path = tmp_path / "epics.db"
    r = EpicRepository(db_path=db_path, auto_bootstrap=False)
    r.create_epic({
        "epic_folder_name": "test_epic",
        "epic_folder": str(tmp_path / "test_epic"),
        "name": "test_epic",
        "status": "active",
    })
    yield r
    r.close()


EPIC = "test_epic"


def test_add_phase_duplicate_phase_id_rejected(repo):
    """Second insert with same phase_id returns False."""
    assert repo.add_phase(EPIC, {"name": "Build", "phase_id": "P1"})
    assert not repo.add_phase(EPIC, {"name": "Build v2", "phase_id": "P1"})
    # Only one phase should exist
    phases = repo.list_phases(EPIC)
    assert len(phases) == 1
    assert phases[0].name == "Build"


def test_add_phase_duplicate_phase_name_still_rejected(repo):
    """Existing duplicate phase_name guard still works."""
    assert repo.add_phase(EPIC, {"name": "Build", "phase_id": "P1"})
    assert not repo.add_phase(EPIC, {"name": "Build", "phase_id": "P2"})
    phases = repo.list_phases(EPIC)
    assert len(phases) == 1


def test_add_phase_empty_phase_id_allows_multiple(repo):
    """Phases without phase_id can still be added (no ID collision)."""
    assert repo.add_phase(EPIC, {"name": "Phase A"})
    assert repo.add_phase(EPIC, {"name": "Phase B"})
    phases = repo.list_phases(EPIC)
    assert len(phases) == 2


def test_update_phase_by_phase_id(repo):
    """update_phase resolves by phase_id."""
    repo.add_phase(EPIC, {"name": "Build", "phase_id": "P1"})
    assert repo.update_phase(EPIC, "P1", {"status": "completed"})
    phase = repo.get_phase(EPIC, "P1")
    assert phase.status == "completed"


def test_update_phase_by_name_still_works(repo):
    """update_phase still works when given phase_name."""
    repo.add_phase(EPIC, {"name": "Build", "phase_id": "P1"})
    assert repo.update_phase(EPIC, "Build", {"status": "in_progress"})
    phase = repo.get_phase(EPIC, "P1")
    assert phase.status == "in_progress"


def test_update_phase_not_found(repo):
    """update_phase returns False for nonexistent phase."""
    assert not repo.update_phase(EPIC, "nonexistent", {"status": "done"})


def test_delete_phase_by_phase_id(repo):
    """delete_phase resolves by phase_id."""
    repo.add_phase(EPIC, {"name": "Build", "phase_id": "P1"})
    assert repo.delete_phase(EPIC, "P1")
    assert repo.get_phase(EPIC, "P1") is None
    assert len(repo.list_phases(EPIC)) == 0


def test_delete_phase_by_name_still_works(repo):
    """delete_phase still works when given phase_name."""
    repo.add_phase(EPIC, {"name": "Build", "phase_id": "P1"})
    assert repo.delete_phase(EPIC, "Build")
    assert len(repo.list_phases(EPIC)) == 0


def test_delete_phase_without_phase_id(repo):
    """delete_phase works for phases with no phase_id (falls back to name)."""
    repo.add_phase(EPIC, {"name": "Legacy Phase"})
    assert repo.delete_phase(EPIC, "Legacy Phase")
    assert len(repo.list_phases(EPIC)) == 0


def test_get_phase_prioritizes_phase_id(repo):
    """get_phase searches phase_id before phase_name."""
    # Create two phases: one named "P1" (phase_name), another with phase_id "P1"
    repo.add_phase(EPIC, {"name": "P1", "phase_id": "NAME_IS_P1"})
    repo.add_phase(EPIC, {"name": "Other", "phase_id": "P1"})

    # Looking up "P1" should find the one with phase_id="P1", not phase_name="P1"
    result = repo.get_phase(EPIC, "P1")
    assert result is not None
    assert result.name == "Other"
    assert result.phase_id == "P1"
