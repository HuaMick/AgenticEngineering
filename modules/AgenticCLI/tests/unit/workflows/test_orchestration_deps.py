"""Integration tests for orchestration dependency gating and priority sorting.

Tests:
- discover_plans_needing_execution returns in_progress epics (simple query)
- discover_plans_needing_orchestration returns seed/planning epics
- refresh_blocked_statuses transitions epics based on dep changes
- ExecutionRunner.run() processes in_progress epics without runtime dep checks
"""

import logging
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
# discover_plans_needing_execution - status-based query
# ---------------------------------------------------------------------------


class TestDiscoverPlansNeedingExecution:
    """Tests for OrchestrationWorkflow.discover_plans_needing_execution().

    Discovery is now a simple status query: list_epics(status="in_progress").
    Preconditions are enforced at transition time, not at discovery time.
    """

    def test_returns_in_progress_epics(self, repo, tmp_path):
        """Only in_progress epics are returned."""
        _create_epic(repo, "epic_A", status="in_progress")
        _add_phase(repo, "epic_A", "P1")
        _create_epic(repo, "epic_B", status="planning")
        _create_epic(repo, "epic_C", status="seed")
        _create_epic(repo, "epic_D", status="blocked")

        workflow = _make_workflow(repo, tmp_path)
        plans = workflow.discover_plans_needing_execution()

        assert "epic_A" in plans
        assert "epic_B" not in plans
        assert "epic_C" not in plans
        assert "epic_D" not in plans

    def test_excludes_completed_epics(self, repo, tmp_path):
        """Completed epics are excluded."""
        _create_epic(repo, "epic_A", status="completed")
        _create_epic(repo, "epic_B", status="in_progress")
        _add_phase(repo, "epic_B", "P1")

        workflow = _make_workflow(repo, tmp_path)
        plans = workflow.discover_plans_needing_execution()

        assert "epic_A" not in plans
        assert "epic_B" in plans

    def test_sorted_by_priority(self, repo, tmp_path):
        """Results are sorted: critical first, then high, medium, low."""
        _create_epic(repo, "260101AA_low", status="in_progress", priority="low")
        _add_phase(repo, "260101AA_low", "P1")
        _create_epic(repo, "260101BB_critical", status="in_progress", priority="critical")
        _add_phase(repo, "260101BB_critical", "P1")
        _create_epic(repo, "260101CC_high", status="in_progress", priority="high")
        _add_phase(repo, "260101CC_high", "P1")

        workflow = _make_workflow(repo, tmp_path)
        plans = workflow.discover_plans_needing_execution()

        assert plans.index("260101BB_critical") < plans.index("260101CC_high")
        assert plans.index("260101CC_high") < plans.index("260101AA_low")

    def test_empty_when_none_in_progress(self, repo, tmp_path):
        """Returns empty when no epics have in_progress status."""
        _create_epic(repo, "epic_A", status="planning")
        _create_epic(repo, "epic_B", status="blocked")

        workflow = _make_workflow(repo, tmp_path)
        plans = workflow.discover_plans_needing_execution()

        assert plans == []

    def test_refresh_blocked_unblocks_epic(self, repo, tmp_path):
        """refresh_blocked_statuses promotes blocked → in_progress when deps satisfied."""
        _create_epic(repo, "epic_A", status="blocked", depends_on=["epic_B"])
        _add_phase(repo, "epic_A", "P1")
        _create_epic(repo, "epic_B", status="completed")

        workflow = _make_workflow(repo, tmp_path)
        # Discovery calls refresh_blocked_statuses which should unblock epic_A
        plans = workflow.discover_plans_needing_execution()

        assert "epic_A" in plans


# ---------------------------------------------------------------------------
# discover_plans_needing_orchestration - seed/planning query
# ---------------------------------------------------------------------------


class TestDiscoverPlansNeedingOrchestration:
    """Tests for PlannerLoopWorkflow.discover_plans_needing_orchestration()."""

    def test_returns_seed_and_planning(self, repo, tmp_path):
        """Returns epics with seed or planning status."""
        _create_epic(repo, "epic_A", status="seed")
        _create_epic(repo, "epic_B", status="planning")
        _create_epic(repo, "epic_C", status="in_progress")

        workflow = _make_workflow(repo, tmp_path)
        plans = workflow.discover_plans_needing_orchestration()

        assert "epic_A" in plans
        assert "epic_B" in plans
        assert "epic_C" not in plans

    def test_sorted_by_priority(self, repo, tmp_path):
        """Results sorted by priority: critical first."""
        _create_epic(repo, "260101AA_low", status="seed", priority="low")
        _create_epic(repo, "260101BB_critical", status="seed", priority="critical")
        _create_epic(repo, "260101CC_high", status="planning", priority="high")

        workflow = _make_workflow(repo, tmp_path)
        plans = workflow.discover_plans_needing_orchestration()

        assert plans.index("260101BB_critical") < plans.index("260101CC_high")
        assert plans.index("260101CC_high") < plans.index("260101AA_low")

    def test_empty_when_all_in_progress(self, repo, tmp_path):
        """Returns empty when all epics are past the planning stage."""
        _create_epic(repo, "epic_A", status="in_progress")
        _add_phase(repo, "epic_A", "P1")

        workflow = _make_workflow(repo, tmp_path)
        plans = workflow.discover_plans_needing_orchestration()

        assert "epic_A" not in plans


# ---------------------------------------------------------------------------
# ExecutionRunner processes in_progress epics
# ---------------------------------------------------------------------------


class TestExecutionRunnerExecution:
    """Tests that ExecutionRunner.run() processes in_progress epics."""

    def test_executes_in_progress_epics(self, repo, tmp_path):
        """ExecutionRunner executes all in_progress epics from discovery."""
        from agenticcli.workflows.orchestration import ExecutionRunner

        _create_epic(repo, "epic_A", status="in_progress")
        _add_phase(repo, "epic_A", "P1")
        _create_epic(repo, "epic_B", status="in_progress")
        _add_phase(repo, "epic_B", "P1")

        workflow = _make_workflow(repo, tmp_path)
        runner = ExecutionRunner(workflow=workflow)

        workflow.run_health_check = MagicMock()
        workflow.get_plan_status = MagicMock(return_value="in_progress")

        with patch.object(workflow, "discover_plans_needing_execution", return_value=["epic_A", "epic_B"]):
            with patch.object(runner, "_execute_plan", return_value=True):
                with patch("agenticcli.workflows.orchestration.acquire_epic_lock", return_value=True), \
                     patch("agenticcli.workflows.orchestration.release_epic_lock"):
                    result = runner.run(max_iterations=5)

        assert result is True
        assert "epic_A" in runner.state["plans_processed"]
        assert "epic_B" in runner.state["plans_processed"]
