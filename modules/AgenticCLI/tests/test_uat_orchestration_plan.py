"""UAT: Orchestration planning command after agent restructure.

Validates that `agentic orchestrate session plan` invokes the correct
agent roles from the current 20-agent roster (no deleted agents).
"""

import pytest

pytestmark = pytest.mark.story("US-PLN-091")


class TestPlanningCommand:
    """Verify planning pipeline invokes current-roster agents only."""

    def test_planning_runner_invokes_build_story_writer(self, tmp_path, monkeypatch):
        """spawn_story_agent() must call _run_role_agent('build-story-writer')."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow(epics_dir=tmp_path)

        captured_roles = []

        def _capture_role(role, epic_folder, **kwargs):
            captured_roles.append(role)
            from agenticcli.utils.sdk_runner import SessionResult
            return SessionResult(status="completed", result="ok")

        monkeypatch.setattr(workflow, "_run_role_agent", _capture_role)

        workflow.spawn_story_agent("fake_epic")

        assert captured_roles == ["build-story-writer"]

    def test_planning_runner_spawns_only_current_roster_roles(self, tmp_path, monkeypatch):
        """Full pipeline must invoke only current-roster agents, no deleted ones."""
        from agenticcli.workflows.planner_loop import _PLANNING_PHASE_ROLES

        deleted_agents = {
            "test-runner", "test-cleaner", "test-final-output",
            "test-guidance-simulator", "test-service",
            "planner-cleaning", "planner-guidance",
            "planner-guidance-testing", "planner-sdk",
        }

        # All roles in _PLANNING_PHASE_ROLES must not intersect with deleted
        assert _PLANNING_PHASE_ROLES & deleted_agents == set(), (
            f"Deleted agents found in _PLANNING_PHASE_ROLES: "
            f"{_PLANNING_PHASE_ROLES & deleted_agents}"
        )

    def test_planning_phase_roles_excludes_deleted_agents(self):
        """_PLANNING_PHASE_ROLES must contain build-story-writer, not deleted agents."""
        from agenticcli.workflows.planner_loop import _PLANNING_PHASE_ROLES

        assert "build-story-writer" in _PLANNING_PHASE_ROLES

        deleted_agents = {
            "test-runner", "test-cleaner", "test-final-output",
            "test-guidance-simulator", "test-service",
            "planner-cleaning", "planner-guidance",
            "planner-guidance-testing", "planner-sdk",
            "story-writer",  # old name before rename
        }
        overlap = deleted_agents & _PLANNING_PHASE_ROLES
        assert overlap == set(), f"Deleted agents in _PLANNING_PHASE_ROLES: {overlap}"

    def test_session_planning_roles_matches_planner_loop(self):
        """_PLANNING_PHASE_ROLES_SESSION in session.py must match planner_loop.py."""
        from agenticcli.workflows.planner_loop import _PLANNING_PHASE_ROLES
        from agenticcli.commands.session import _PLANNING_PHASE_ROLES_SESSION

        assert set(_PLANNING_PHASE_ROLES) == set(_PLANNING_PHASE_ROLES_SESSION), (
            f"Mismatch:\n"
            f"  planner_loop only: {_PLANNING_PHASE_ROLES - _PLANNING_PHASE_ROLES_SESSION}\n"
            f"  session only:      {_PLANNING_PHASE_ROLES_SESSION - _PLANNING_PHASE_ROLES}"
        )
