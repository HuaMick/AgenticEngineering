"""Tests for PhaseData max_turns field and EpicRepository round-trip (FX_008).

Verifies that the max_turns field on PhaseData is correctly stored in and
retrieved from TinyDB via EpicRepository.
"""

import pytest

from agenticguidance.services.epic import PhaseData
from agenticguidance.services.epic_repository import EpicRepository

pytestmark = [pytest.mark.unit, pytest.mark.story("US-PLN-061")]


@pytest.fixture
def repo(tmp_path):
    """Isolated EpicRepository."""
    db_path = tmp_path / "epics.db"
    r = EpicRepository(db_path=db_path, auto_bootstrap=False)
    yield r
    r.close()


def _create_epic(repo, name="test_epic"):
    """Register a minimal epic in the repository."""
    repo.create_epic({
        "epic_folder_name": name,
        "epic_folder": f"/tmp/{name}",
        "name": name,
        "status": "active",
    })


class TestPhaseDataMaxTurns:
    """Verify PhaseData dataclass supports the max_turns field."""

    def test_max_turns_defaults_to_none(self):
        """PhaseData.max_turns should default to None."""
        phase = PhaseData(name="Build")
        assert phase.max_turns is None

    def test_max_turns_can_be_set(self):
        """PhaseData.max_turns should accept an integer."""
        phase = PhaseData(name="Build", max_turns=100)
        assert phase.max_turns == 100

    def test_max_turns_zero(self):
        """PhaseData.max_turns=0 is a valid value (edge case)."""
        phase = PhaseData(name="Build", max_turns=0)
        assert phase.max_turns == 0


class TestEpicRepositoryPhaseMaxTurnsRoundTrip:
    """Verify max_turns survives add_phase -> list_phases / get_phase round-trip."""

    def test_add_and_list_with_max_turns(self, repo):
        """max_turns should be preserved through add_phase -> list_phases."""
        _create_epic(repo)

        repo.add_phase("test_epic", {
            "name": "Build",
            "phase_id": "P1",
            "status": "pending",
            "agent": "build-python",
            "max_turns": 150,
        })

        phases = repo.list_phases("test_epic")
        assert len(phases) == 1
        assert phases[0].name == "Build"
        assert phases[0].max_turns == 150

    def test_add_and_get_with_max_turns(self, repo):
        """max_turns should be preserved through add_phase -> get_phase."""
        _create_epic(repo)

        repo.add_phase("test_epic", {
            "name": "Test",
            "phase_id": "P2",
            "status": "pending",
            "agent": "test-builder",
            "max_turns": 75,
        })

        phase = repo.get_phase("test_epic", "Test")
        assert phase is not None
        assert phase.max_turns == 75

    def test_add_without_max_turns_returns_none(self, repo):
        """Phases added without max_turns should return None on retrieval."""
        _create_epic(repo)

        repo.add_phase("test_epic", {
            "name": "Deploy",
            "phase_id": "P3",
            "status": "pending",
            "agent": "deploy-agent",
        })

        phase = repo.get_phase("test_epic", "Deploy")
        assert phase is not None
        assert phase.max_turns is None

    def test_update_phase_max_turns(self, repo):
        """max_turns should be updatable via update_phase."""
        _create_epic(repo)

        repo.add_phase("test_epic", {
            "name": "Build",
            "phase_id": "P1",
            "status": "pending",
            "agent": "build-python",
        })

        # Initially None
        phase = repo.get_phase("test_epic", "Build")
        assert phase.max_turns is None

        # Update to 300
        repo.update_phase("test_epic", "Build", {"max_turns": 300})

        phase = repo.get_phase("test_epic", "Build")
        assert phase.max_turns == 300

    def test_max_turns_in_epic_data(self, repo):
        """max_turns should also be included when phases are read via get_epic."""
        _create_epic(repo)

        repo.add_phase("test_epic", {
            "name": "Build",
            "phase_id": "P1",
            "status": "pending",
            "agent": "build-python",
            "max_turns": 250,
        })

        epic = repo.get_epic("test_epic")
        assert epic is not None
        assert len(epic.phases) == 1
        assert epic.phases[0].max_turns == 250

    def test_multiple_phases_different_max_turns(self, repo):
        """Multiple phases should each independently store their max_turns."""
        _create_epic(repo)

        repo.add_phase("test_epic", {
            "name": "Build",
            "phase_id": "P1",
            "status": "pending",
            "agent": "build-python",
            "max_turns": 100,
        })
        repo.add_phase("test_epic", {
            "name": "Test",
            "phase_id": "P2",
            "status": "pending",
            "agent": "test-builder",
            "max_turns": 50,
        })
        repo.add_phase("test_epic", {
            "name": "Deploy",
            "phase_id": "P3",
            "status": "pending",
            "agent": "deploy-agent",
            # No max_turns
        })

        phases = repo.list_phases("test_epic")
        assert len(phases) == 3

        by_name = {p.name: p for p in phases}
        assert by_name["Build"].max_turns == 100
        assert by_name["Test"].max_turns == 50
        assert by_name["Deploy"].max_turns is None
