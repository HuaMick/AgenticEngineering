"""Tests for planner-design agent spawning in PlannerLoopRunner (P4-T4).

Validates:
- spawn_design_agent method exists and calls _run_role_agent("planner-design")
- planner-design is in _PLANNING_PHASE_ROLES frozenset
- _build_agent_prompt includes PLANNING-ONLY instruction for planner-design
- _process_plan calls spawn_design_agent after story-generator
- Design agent failure is handled as non-fatal (continues processing)
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

from agenticcli.utils.sdk_runner import SessionResult


def _ok_result(**kwargs) -> SessionResult:
    """Create a successful SessionResult for testing."""
    return SessionResult(status="completed", result="ok", **kwargs)


def _fail_result(**kwargs) -> SessionResult:
    """Create a failed SessionResult for testing."""
    return SessionResult(status="failed", result="design agent failed", is_error=True, **kwargs)


# ---------------------------------------------------------------------------
# Tests for _PLANNING_PHASE_ROLES inclusion
# ---------------------------------------------------------------------------

class TestPlannerDesignInPlanningRoles:
    """Test planner-design is registered as a planning-phase role."""

    def test_planner_design_in_planning_roles(self):
        """Verify planner-design is in _PLANNING_PHASE_ROLES frozenset."""
        from agenticcli.workflows.planner_loop import _PLANNING_PHASE_ROLES

        assert "planner-design" in _PLANNING_PHASE_ROLES

    def test_planning_roles_is_frozenset(self):
        """Verify _PLANNING_PHASE_ROLES is immutable (frozenset)."""
        from agenticcli.workflows.planner_loop import _PLANNING_PHASE_ROLES

        assert isinstance(_PLANNING_PHASE_ROLES, frozenset)

    def test_planning_roles_contains_other_planners(self):
        """Verify other planning roles are also present (structural integrity)."""
        from agenticcli.workflows.planner_loop import _PLANNING_PHASE_ROLES

        expected_roles = {
            "planner-design",
            "planner-build",
            "planner-test",
            "planner-guidance",
            "planner-cleaning",
        }
        for role in expected_roles:
            assert role in _PLANNING_PHASE_ROLES, f"Missing role: {role}"


# ---------------------------------------------------------------------------
# Tests for _build_agent_prompt with planner-design
# ---------------------------------------------------------------------------

class TestBuildAgentPromptForDesign:
    """Test _build_agent_prompt generates correct prompt for planner-design."""

    def test_prompt_includes_planning_only_instruction(self):
        """Verify planner-design prompt includes PLANNING-ONLY constraint."""
        from agenticcli.workflows.planner_loop import _build_agent_prompt

        prompt = _build_agent_prompt("planner-design", "test_epic")
        assert "PLANNING-ONLY" in prompt

    def test_prompt_includes_role_reference(self):
        """Verify prompt references the planner-design role."""
        from agenticcli.workflows.planner_loop import _build_agent_prompt

        prompt = _build_agent_prompt("planner-design", "test_epic")
        assert "planner-design" in prompt

    def test_prompt_includes_epic_reference(self):
        """Verify prompt references the epic folder name."""
        from agenticcli.workflows.planner_loop import _build_agent_prompt

        prompt = _build_agent_prompt("planner-design", "260308PD_test")
        assert "260308PD_test" in prompt

    def test_prompt_forbids_code_modification(self):
        """Verify prompt instructs agent not to modify source files."""
        from agenticcli.workflows.planner_loop import _build_agent_prompt

        prompt = _build_agent_prompt("planner-design", "test_epic")
        assert "NOT implement code" in prompt or "must NOT" in prompt

    def test_non_planning_role_does_not_get_planning_constraint(self):
        """Verify non-planning roles don't get the PLANNING-ONLY instruction."""
        from agenticcli.workflows.planner_loop import _build_agent_prompt

        prompt = _build_agent_prompt("build-python", "test_epic")
        assert "PLANNING-ONLY" not in prompt


# ---------------------------------------------------------------------------
# Tests for spawn_design_agent method
# ---------------------------------------------------------------------------

class TestSpawnDesignAgent:
    """Test PlannerLoopWorkflow.spawn_design_agent method."""

    def test_spawn_design_agent_exists(self):
        """Verify spawn_design_agent method exists on PlannerLoopWorkflow."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        assert hasattr(PlannerLoopWorkflow, "spawn_design_agent")
        assert callable(getattr(PlannerLoopWorkflow, "spawn_design_agent"))

    def test_spawn_design_agent_calls_run_role_agent(self):
        """Verify spawn_design_agent delegates to _run_role_agent('planner-design')."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow.__new__(PlannerLoopWorkflow)
        workflow._run_role_agent = MagicMock(return_value=_ok_result())

        result = workflow.spawn_design_agent("test_epic")

        workflow._run_role_agent.assert_called_once_with("planner-design", "test_epic")
        assert result.status == "completed"

    def test_spawn_design_agent_returns_session_result(self):
        """Verify spawn_design_agent returns a SessionResult."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow.__new__(PlannerLoopWorkflow)
        workflow._run_role_agent = MagicMock(return_value=_ok_result())

        result = workflow.spawn_design_agent("test_epic")
        assert isinstance(result, SessionResult)

    def test_spawn_design_agent_propagates_failure(self):
        """Verify spawn_design_agent propagates failure from _run_role_agent."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow.__new__(PlannerLoopWorkflow)
        workflow._run_role_agent = MagicMock(return_value=_fail_result())

        result = workflow.spawn_design_agent("test_epic")
        assert result.status == "failed"


# ---------------------------------------------------------------------------
# Tests for design agent in PLAN_TYPE_TO_PLANNER mapping
# ---------------------------------------------------------------------------

class TestPlanningPhaseRoles:
    """Test that planning-phase roles are properly configured."""

    def test_planner_design_in_planning_roles(self):
        """Verify planner-design is in _PLANNING_PHASE_ROLES."""
        from agenticcli.workflows.planner_loop import _PLANNING_PHASE_ROLES

        assert "planner-design" in _PLANNING_PHASE_ROLES

    def test_epic_creator_in_planning_roles(self):
        """Verify epic-creator is in _PLANNING_PHASE_ROLES."""
        from agenticcli.workflows.planner_loop import _PLANNING_PHASE_ROLES

        assert "epic-creator" in _PLANNING_PHASE_ROLES

    def test_planner_explore_in_planning_roles(self):
        """Verify planner-explore is in _PLANNING_PHASE_ROLES."""
        from agenticcli.workflows.planner_loop import _PLANNING_PHASE_ROLES

        assert "planner-explore" in _PLANNING_PHASE_ROLES


# ---------------------------------------------------------------------------
# Tests for PlannerLoopRunner._process_plan design step
# ---------------------------------------------------------------------------

class TestProcessPlanDesignStep:
    """Test that _process_plan calls spawn_design_agent in correct order."""

    def test_process_plan_calls_design_after_explore(self):
        """Verify spawn_design_agent is called after spawn_explore_agents in _process_plan."""
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, SessionResult

        # Create a minimal runner with mocked workflow
        runner = PlannerLoopRunner.__new__(PlannerLoopRunner)
        runner.state = {"errors": [], "status": "running", "iteration": 0}
        runner.budget_usd = 50.0
        runner.total_cost_usd = 0.0
        runner.workflow = MagicMock()

        # Set up all workflow methods to return success
        runner.workflow.get_plan_status.return_value = "pending"
        runner.workflow.spawn_epic_creator.return_value = _ok_result()
        runner.workflow.spawn_story_agent.return_value = _ok_result()
        runner.workflow.spawn_explore_agents.return_value = _ok_result()
        runner.workflow.spawn_design_agent.return_value = SessionResult(
            status="completed", result="DESIGN_STATUS: approved"
        )
        runner.workflow.parse_design_status.return_value = "approved"
        runner.workflow.run_review_cycle.return_value = (True, 1, "")
        runner.workflow.spawn_orchestration_agent.return_value = _ok_result()
        runner.workflow._validate_result = MagicMock()
        runner.workflow._repository = None
        runner._acquire_epic_lock = MagicMock(return_value=True)
        runner._release_epic_lock = MagicMock()

        runner._process_plan("test_epic")

        # Verify spawn_design_agent was called
        runner.workflow.spawn_design_agent.assert_called_with("test_epic")

        # Verify call order: epic_creator -> story -> explore -> design
        creator_idx = None
        story_idx = None
        explore_idx = None
        design_idx = None
        for idx, c in enumerate(runner.workflow.method_calls):
            if c[0] == "spawn_epic_creator":
                creator_idx = idx
            if c[0] == "spawn_story_agent":
                story_idx = idx
            if c[0] == "spawn_explore_agents":
                explore_idx = idx
            if c[0] == "spawn_design_agent":
                design_idx = idx

        assert creator_idx is not None, "spawn_epic_creator was not called"
        assert story_idx is not None, "spawn_story_agent was not called"
        assert explore_idx is not None, "spawn_explore_agents was not called"
        assert design_idx is not None, "spawn_design_agent was not called"
        assert creator_idx < story_idx < explore_idx < design_idx, \
            "Expected order: epic_creator -> story -> explore -> design"

    def test_design_failure_is_fatal(self):
        """Verify design agent failure stops _process_plan (design is now a review gate)."""
        from agenticcli.workflows.planner_loop import PlannerLoopRunner

        runner = PlannerLoopRunner.__new__(PlannerLoopRunner)
        runner.state = {"errors": [], "status": "running", "iteration": 0}
        runner.budget_usd = 50.0
        runner.total_cost_usd = 0.0
        runner.workflow = MagicMock()

        runner.workflow.get_plan_status.return_value = "pending"
        runner.workflow.spawn_epic_creator.return_value = _ok_result()
        runner.workflow.spawn_story_agent.return_value = _ok_result()
        runner.workflow.spawn_explore_agents.return_value = _ok_result()
        runner.workflow.spawn_design_agent.return_value = _fail_result()
        runner.workflow._validate_result = MagicMock()
        runner.workflow._repository = None

        result = runner._process_plan("test_epic")

        # Design failure should now be fatal
        assert result is False

        # Review should NOT have been called
        runner.workflow.run_review_cycle.assert_not_called()

        # Error should be recorded
        error_phases = [e.get("phase") for e in runner.state["errors"]]
        assert "design" in error_phases
