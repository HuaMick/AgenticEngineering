"""UAT: Orchestration dependency gating and priority ordering behavior.

Validates:
- US-PLN-059: discover returns priority-ordered with blocked filtered
- US-PLN-062: dependency gates prevent blocked execution

Scenario: 3 epics:
- A = critical priority, no deps
- B = medium priority, depends on A
- C = low priority, no deps
Expected: A first, B blocked until A completes, C after A (lower priority).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agenticguidance.services.epic_repository import EpicRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    """Create an isolated EpicRepository backed by tmp_path."""
    db_path = tmp_path / "epics.db"
    r = EpicRepository(db_path=db_path, auto_bootstrap=False)
    yield r
    r.close()


def _create_epic(repo, name, status="in_progress", priority="medium", depends_on=None):
    """Helper to seed an epic."""
    repo.create_epic({
        "epic_folder_name": name,
        "epic_folder": f"/tmp/epics/{name}",
        "name": name,
        "status": status,
        "priority": priority,
        "objective": f"Objective for {name}",
        "depends_on": depends_on or [],
    })


def _add_phase(repo, epic_name, phase_name, agent="build-python", status="pending"):
    """Helper to add a routed phase to an epic."""
    repo.add_phase(epic_name, {
        "name": phase_name,
        "phase_id": phase_name,
        "description": f"Phase {phase_name}",
        "status": status,
        "execution": "sequential",
        "agent": agent,
    })


def _make_workflow(repo, tmp_path):
    """Create an OrchestrationWorkflow with the given repo."""
    from agenticcli.workflows.orchestration import OrchestrationWorkflow

    workflow = OrchestrationWorkflow(
        epics_dir=tmp_path / "epics",
        working_dir=str(tmp_path),
    )
    workflow._repository = repo
    return workflow


# ---------------------------------------------------------------------------
# UAT Scenario: A=critical, B=medium depends-on A, C=low
# ---------------------------------------------------------------------------


class TestUATOrchestrationDependencyGating:
    """UAT: Full scenario with priority ordering and dependency gating."""

    def _seed_scenario(self, repo):
        """Seed the 3-epic scenario: A critical, B medium (dep A), C low."""
        _create_epic(repo, "260301AA_epic_a", priority="critical")
        _add_phase(repo, "260301AA_epic_a", "P1_build")

        _create_epic(repo, "260201BB_epic_b", priority="medium", depends_on=["260301AA_epic_a"])
        _add_phase(repo, "260201BB_epic_b", "P1_build")

        _create_epic(repo, "260101CC_epic_c", priority="low")
        _add_phase(repo, "260101CC_epic_c", "P1_build")

    def test_discover_returns_a_and_c_not_b(self, repo, tmp_path):
        """Discovery returns A and C (unblocked), excludes B (blocked).

        US-PLN-059: Blocked epics are filtered out of discovery results.
        """
        self._seed_scenario(repo)
        workflow = _make_workflow(repo, tmp_path)
        plans = workflow.discover_plans_needing_execution()

        assert "260301AA_epic_a" in plans, "A (critical, no deps) should be discovered"
        assert "260101CC_epic_c" in plans, "C (low, no deps) should be discovered"
        assert "260201BB_epic_b" not in plans, "B (blocked by A) should NOT be discovered"

    def test_priority_ordering_a_before_c(self, repo, tmp_path):
        """A (critical) comes before C (low) in discovery results.

        US-PLN-059: Results are priority-sorted.
        """
        self._seed_scenario(repo)
        workflow = _make_workflow(repo, tmp_path)
        plans = workflow.discover_plans_needing_execution()

        idx_a = plans.index("260301AA_epic_a")
        idx_c = plans.index("260101CC_epic_c")
        assert idx_a < idx_c, f"A (critical) should come before C (low): {plans}"

    def test_b_unblocked_after_a_completes(self, repo, tmp_path):
        """After A completes, B becomes unblocked and appears in discovery.

        US-PLN-062: Dependency gates are dynamic.
        """
        self._seed_scenario(repo)
        workflow = _make_workflow(repo, tmp_path)

        # Initially B is blocked
        plans_before = workflow.discover_plans_needing_execution()
        assert "260201BB_epic_b" not in plans_before

        # Complete A
        repo.update_epic("260301AA_epic_a", {"status": "completed"})

        # Now B should be unblocked
        plans_after = workflow.discover_plans_needing_execution()
        assert "260201BB_epic_b" in plans_after, "B should be unblocked after A completes"

    def test_execution_runner_skips_blocked_b(self, repo, tmp_path):
        """ExecutionRunner runtime check skips B when A hasn't completed.

        US-PLN-062: Runtime dependency gate prevents execution of blocked epics.
        """
        from agenticcli.workflows.orchestration import ExecutionRunner

        self._seed_scenario(repo)
        workflow = _make_workflow(repo, tmp_path)

        runner = ExecutionRunner(workflow=workflow)
        workflow.run_health_check = MagicMock()
        workflow.get_plan_status = MagicMock(return_value="in_progress")

        executed_plans = []

        def mock_execute(plan_folder, max_iterations):
            executed_plans.append(plan_folder)
            return True

        # Force discovery to include all 3 (simulating somehow B gets into the list)
        with patch.object(workflow, "discover_plans_needing_execution",
                          return_value=["260301AA_epic_a", "260201BB_epic_b", "260101CC_epic_c"]):
            with patch.object(runner, "_execute_plan", side_effect=mock_execute):
                with patch("agenticcli.workflows.orchestration.acquire_epic_lock", return_value=True), \
                     patch("agenticcli.workflows.orchestration.release_epic_lock"):
                    runner.run(max_iterations=10)

        # A and C should be executed; B should be skipped (blocked)
        assert "260301AA_epic_a" in executed_plans, "A should be executed"
        assert "260101CC_epic_c" in executed_plans, "C should be executed"
        assert "260201BB_epic_b" not in executed_plans, "B should be skipped (blocked)"

    def test_full_lifecycle_a_then_b(self, repo, tmp_path):
        """Full lifecycle: execute A first, then B becomes available.

        Validates the complete dependency gating lifecycle.
        """
        from agenticcli.workflows.orchestration import ExecutionRunner

        self._seed_scenario(repo)
        workflow = _make_workflow(repo, tmp_path)

        # Round 1: Only A and C are ready
        plans_round1 = workflow.discover_plans_needing_execution()
        assert "260301AA_epic_a" in plans_round1
        assert "260201BB_epic_b" not in plans_round1
        assert "260101CC_epic_c" in plans_round1

        # Simulate completing A and C
        repo.update_epic("260301AA_epic_a", {"status": "completed"})
        repo.update_phase("260301AA_epic_a", "P1_build", {"status": "completed"})
        repo.update_epic("260101CC_epic_c", {"status": "completed"})
        repo.update_phase("260101CC_epic_c", "P1_build", {"status": "completed"})

        # Round 2: Now B is unblocked
        plans_round2 = workflow.discover_plans_needing_execution()
        assert "260201BB_epic_b" in plans_round2, "B should be discoverable after A completes"
        # A and C should no longer appear (completed)
        assert "260301AA_epic_a" not in plans_round2, "A (completed) should not be in discovery"
        assert "260101CC_epic_c" not in plans_round2, "C (completed) should not be in discovery"

    def test_planning_includes_blocked_epics(self, repo, tmp_path):
        """Planning discovery includes blocked epics (no dep filtering).

        Ensures planning can happen even for epics that can't be executed yet.
        """
        self._seed_scenario(repo)

        # Remove phases so all need orchestration
        # (Actually they already need it - phases exist but let's check the method)
        # Create epics without phases for a clean test
        from agenticguidance.services.epic_repository import EpicRepository

        db_path2 = tmp_path / "epics2.db"
        repo2 = EpicRepository(db_path=db_path2, auto_bootstrap=False)
        _create_epic(repo2, "260301XX_epic_x", priority="critical")
        _create_epic(repo2, "260201YY_epic_y", priority="medium", depends_on=["260301XX_epic_x"])
        _create_epic(repo2, "260101ZZ_epic_z", priority="low")

        from agenticcli.workflows.orchestration import OrchestrationWorkflow

        workflow2 = OrchestrationWorkflow(
            epics_dir=tmp_path / "epics2",
            working_dir=str(tmp_path),
        )
        workflow2._repository = repo2

        plans = workflow2.discover_plans_needing_orchestration()

        # All three should need planning (no phases)
        assert "260301XX_epic_x" in plans
        assert "260201YY_epic_y" in plans, "Blocked epic should still need planning"
        assert "260101ZZ_epic_z" in plans

        # Priority ordering: X (critical) < Y (medium) < Z (low)
        assert plans.index("260301XX_epic_x") < plans.index("260201YY_epic_y")
        assert plans.index("260201YY_epic_y") < plans.index("260101ZZ_epic_z")

        repo2.close()
