"""Tests for agenticcli.utils.phase_validation module.

Tests validate_phase_routing() and has_any_routed_phase() — the shared
phase-routing validation utilities extracted from duplicated inline checks
in planner_loop.py and orchestration.py.

Uses real EpicRepository backed by TinyDB (via conftest _isolate_tinydb fixture)
rather than mocks, so tests exercise the real data path.
"""

import pytest

from agenticguidance.services.epic_repository import EpicRepository

from agenticcli.utils.phase_validation import (
    has_any_routed_phase,
    validate_phase_routing,
)

pytestmark = pytest.mark.story("US-PLN-093")

# ── Helpers ──────────────────────────────────────────────────────────────────

EPIC_FOLDER = "260328AG_test_validation"


def _make_repo(tmp_path):
    """Create an isolated EpicRepository with auto_bootstrap disabled."""
    db_path = tmp_path / ".agentic" / "epics.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return EpicRepository(db_path=db_path, auto_bootstrap=False)


def _seed_epic(repo, folder=EPIC_FOLDER):
    """Insert a minimal epic document and return the folder name."""
    repo.create_epic({
        "epic_folder_name": folder,
        "epic_folder": f"/tmp/{folder}",
        "name": "Test Validation Epic",
        "status": "in_progress",
    })
    return folder


# ── validate_phase_routing tests ─────────────────────────────────────────────


@pytest.mark.story("US-PLN-093")
class TestValidatePhaseRouting:
    """Tests for the validate_phase_routing() utility."""

    def test_all_phases_routed_and_tickets_beyond_proposed(self, tmp_path):
        """Fully routed epic with active tickets → (True, None).

        Story step 1: phases all have agent routing, tickets beyond proposed.
        """
        repo = _make_repo(tmp_path)
        _seed_epic(repo)

        repo.add_phase(EPIC_FOLDER, {"name": "Build", "agent": "build-python"})
        repo.add_phase(EPIC_FOLDER, {"name": "Test", "agent": "test-builder"})

        repo.add_ticket(EPIC_FOLDER, "Build", {
            "task_id": "T01", "name": "Implement feature", "status": "pending",
        })
        repo.add_ticket(EPIC_FOLDER, "Test", {
            "task_id": "T02", "name": "Write tests", "status": "pending",
        })

        is_valid, reason = validate_phase_routing(repo, EPIC_FOLDER)

        assert is_valid is True
        assert reason is None

    def test_no_phases_returns_invalid(self, tmp_path):
        """Epic with no phases at all → (False, "no phases in TinyDB").

        Story step 2: no phases exist.
        """
        repo = _make_repo(tmp_path)
        _seed_epic(repo)

        is_valid, reason = validate_phase_routing(repo, EPIC_FOLDER)

        assert is_valid is False
        assert reason == "no phases in TinyDB"

    def test_some_phases_missing_agent(self, tmp_path):
        """Epic where one phase lacks agent routing → invalid with names listed.

        Story step 3: some phases lack the agent field.
        """
        repo = _make_repo(tmp_path)
        _seed_epic(repo)

        repo.add_phase(EPIC_FOLDER, {"name": "Build", "agent": "build-python"})
        repo.add_phase(EPIC_FOLDER, {"name": "Test"})  # No agent

        repo.add_ticket(EPIC_FOLDER, "Build", {
            "task_id": "T01", "name": "Implement", "status": "pending",
        })

        is_valid, reason = validate_phase_routing(repo, EPIC_FOLDER)

        assert is_valid is False
        assert "Test" in reason
        assert "phases missing agent routing" in reason

    def test_all_phases_missing_agent(self, tmp_path):
        """Epic where ALL phases lack agent routing → invalid, all names listed."""
        repo = _make_repo(tmp_path)
        _seed_epic(repo)

        repo.add_phase(EPIC_FOLDER, {"name": "Build"})
        repo.add_phase(EPIC_FOLDER, {"name": "Test"})

        is_valid, reason = validate_phase_routing(repo, EPIC_FOLDER)

        assert is_valid is False
        assert "Build" in reason
        assert "Test" in reason
        assert "phases missing agent routing" in reason

    def test_all_tickets_proposed(self, tmp_path):
        """Phases routed but all tickets still proposed → invalid.

        Story step 4: all tickets are still in 'proposed' status.
        """
        repo = _make_repo(tmp_path)
        _seed_epic(repo)

        repo.add_phase(EPIC_FOLDER, {"name": "Build", "agent": "build-python"})

        repo.add_ticket(EPIC_FOLDER, "Build", {
            "task_id": "T01", "name": "Task one", "status": "proposed",
        })
        repo.add_ticket(EPIC_FOLDER, "Build", {
            "task_id": "T02", "name": "Task two", "status": "proposed",
        })

        is_valid, reason = validate_phase_routing(repo, EPIC_FOLDER)

        assert is_valid is False
        assert "2 tickets still proposed" in reason

    def test_mixed_ticket_statuses_valid(self, tmp_path):
        """Routed phases with some proposed + some pending tickets → valid.

        Story step 5: mixed ticket statuses means not all proposed.
        """
        repo = _make_repo(tmp_path)
        _seed_epic(repo)

        repo.add_phase(EPIC_FOLDER, {"name": "Build", "agent": "build-python"})

        repo.add_ticket(EPIC_FOLDER, "Build", {
            "task_id": "T01", "name": "Task one", "status": "proposed",
        })
        repo.add_ticket(EPIC_FOLDER, "Build", {
            "task_id": "T02", "name": "Task two", "status": "pending",
        })

        is_valid, reason = validate_phase_routing(repo, EPIC_FOLDER)

        assert is_valid is True
        assert reason is None

    def test_no_tickets_with_routed_phases(self, tmp_path):
        """Phases routed but no tickets at all → valid (edge case).

        Story step 5 notes: empty epic with phases but no tickets is graceful.
        The 'all proposed' check only triggers when tickets exist.
        """
        repo = _make_repo(tmp_path)
        _seed_epic(repo)

        repo.add_phase(EPIC_FOLDER, {"name": "Build", "agent": "build-python"})

        is_valid, reason = validate_phase_routing(repo, EPIC_FOLDER)

        assert is_valid is True
        assert reason is None

    def test_nonexistent_epic_returns_no_phases(self, tmp_path):
        """Querying a non-existent epic folder → no phases, invalid."""
        repo = _make_repo(tmp_path)

        is_valid, reason = validate_phase_routing(repo, "nonexistent_epic")

        assert is_valid is False
        assert reason == "no phases in TinyDB"

    def test_single_proposed_ticket(self, tmp_path):
        """One routed phase with exactly one proposed ticket → invalid."""
        repo = _make_repo(tmp_path)
        _seed_epic(repo)

        repo.add_phase(EPIC_FOLDER, {"name": "Build", "agent": "build-python"})
        repo.add_ticket(EPIC_FOLDER, "Build", {
            "task_id": "T01", "name": "Only task", "status": "proposed",
        })

        is_valid, reason = validate_phase_routing(repo, EPIC_FOLDER)

        assert is_valid is False
        assert "1 tickets still proposed" in reason

    def test_completed_tickets_are_valid(self, tmp_path):
        """Tickets with 'completed' status → not proposed, so valid."""
        repo = _make_repo(tmp_path)
        _seed_epic(repo)

        repo.add_phase(EPIC_FOLDER, {"name": "Build", "agent": "build-python"})
        repo.add_ticket(EPIC_FOLDER, "Build", {
            "task_id": "T01", "name": "Done task", "status": "completed",
        })

        is_valid, reason = validate_phase_routing(repo, EPIC_FOLDER)

        assert is_valid is True
        assert reason is None


# ── has_any_routed_phase tests ───────────────────────────────────────────────


@pytest.mark.story("US-PLN-094")
class TestHasAnyRoutedPhase:
    """Tests for the has_any_routed_phase() helper."""

    def test_empty_list(self):
        """Empty phase list → False."""
        assert has_any_routed_phase([]) is False

    def test_all_routed(self, tmp_path):
        """All phases have agents → True."""
        repo = _make_repo(tmp_path)
        _seed_epic(repo)
        repo.add_phase(EPIC_FOLDER, {"name": "Build", "agent": "build-python"})
        repo.add_phase(EPIC_FOLDER, {"name": "Test", "agent": "test-builder"})

        phases = repo.list_phases(EPIC_FOLDER)
        assert has_any_routed_phase(phases) is True

    def test_some_routed(self, tmp_path):
        """One routed + one unrouted → True (any, not all)."""
        repo = _make_repo(tmp_path)
        _seed_epic(repo)
        repo.add_phase(EPIC_FOLDER, {"name": "Build", "agent": "build-python"})
        repo.add_phase(EPIC_FOLDER, {"name": "Test"})  # No agent

        phases = repo.list_phases(EPIC_FOLDER)
        assert has_any_routed_phase(phases) is True

    def test_none_routed(self, tmp_path):
        """No phases have agents → False."""
        repo = _make_repo(tmp_path)
        _seed_epic(repo)
        repo.add_phase(EPIC_FOLDER, {"name": "Build"})
        repo.add_phase(EPIC_FOLDER, {"name": "Test"})

        phases = repo.list_phases(EPIC_FOLDER)
        assert has_any_routed_phase(phases) is False
