"""Tests for the orchestration workflow and PlanningRunner."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# parse_mmd_routing tests
# ---------------------------------------------------------------------------


class TestParseMmdRouting:
    """Test parse_mmd_routing function."""

    def test_parses_agent_routing_from_header(self):
        """Parses AGENT_ROUTING into {phase_id: agent_type} dict."""
        from agenticcli.workflows.orchestration import parse_mmd_routing

        mmd_content = """
%% AGENT_ROUTING: phase-1 -> build-python, phase-2 -> test-builder
"""
        result = parse_mmd_routing(mmd_content)
        assert result["agent_routing"] == {
            "phase-1": "build-python",
            "phase-2": "test-builder",
        }

    def test_parses_status_from_header(self):
        """Parses STATUS into {phase_id: status} dict."""
        from agenticcli.workflows.orchestration import parse_mmd_routing

        mmd_content = """
%% STATUS: phase-1=pending, phase-2=in_progress, phase-3=completed
"""
        result = parse_mmd_routing(mmd_content)
        assert result["status"] == {
            "phase-1": "pending",
            "phase-2": "in_progress",
            "phase-3": "completed",
        }

    def test_parses_feedback_triggers(self):
        """Parses FEEDBACK_TRIGGERS into {trigger: action} dict."""
        from agenticcli.workflows.orchestration import parse_mmd_routing

        mmd_content = """
%% FEEDBACK_TRIGGERS: TEST_FAILURE -> test-fix-loop, BUILD_FAILURE -> escalate
"""
        result = parse_mmd_routing(mmd_content)
        assert result["feedback_triggers"] == {
            "TEST_FAILURE": "test-fix-loop",
            "BUILD_FAILURE": "escalate",
        }

    def test_parses_phases_list(self):
        """Parses PHASES into [{id, description}] list."""
        from agenticcli.workflows.orchestration import parse_mmd_routing

        mmd_content = """
%% PHASES:
%%   1. phase-1 - Build components
%%   2. phase-2 - Run tests
%%   3. phase-3 - Deploy
"""
        result = parse_mmd_routing(mmd_content)
        assert len(result["phases"]) == 3
        assert result["phases"][0] == {"id": "phase-1", "description": "Build components"}
        assert result["phases"][1] == {"id": "phase-2", "description": "Run tests"}
        assert result["phases"][2] == {"id": "phase-3", "description": "Deploy"}

    def test_handles_empty_content(self):
        """Returns empty dicts/lists for empty content."""
        from agenticcli.workflows.orchestration import parse_mmd_routing

        result = parse_mmd_routing("")
        assert result["agent_routing"] == {}
        assert result["status"] == {}
        assert result["feedback_triggers"] == {}
        assert result["phases"] == []

    def test_handles_missing_headers(self):
        """Returns partial result with empty defaults for missing headers."""
        from agenticcli.workflows.orchestration import parse_mmd_routing

        mmd_content = """
%% AGENT_ROUTING: phase-1 -> build-python
%% Just a regular comment
"""
        result = parse_mmd_routing(mmd_content)
        assert result["agent_routing"] == {"phase-1": "build-python"}
        assert result["status"] == {}
        assert result["feedback_triggers"] == {}
        assert result["phases"] == []

    def test_parses_per_phase_routing(self):
        """Parses per-phase AGENT_ROUTING comments (logs but doesn't store)."""
        from agenticcli.workflows.orchestration import parse_mmd_routing

        mmd_content = """
%% AGENT_ROUTING: build-python agent
%% AGENT_ROUTING: test-runner agent
"""
        # This test just ensures the function doesn't crash on per-phase routing
        result = parse_mmd_routing(mmd_content)
        # Per-phase routing is logged but not returned in the result
        assert isinstance(result["agent_routing"], dict)

    def test_parses_real_template_output(self):
        """Parses realistic MMD content from header.mmd.j2 template."""
        from agenticcli.workflows.orchestration import parse_mmd_routing

        mmd_content = """
%% =============================================================================
%% GOAL: Build the orchestration feature
%% =============================================================================
%% PROFILE: Build
%% OUTPUT: /path/to/output
%%
%% PHASES:
%%   1. phase-1 - Orchestration Workflow
%%   2. phase-2 - CLI Integration
%%   3. phase-3 - Tests
%%
%% AGENT_ROUTING: phase-1 -> build-python, phase-2 -> build-python, phase-3 -> test-builder
%% STATUS: phase-1=pending, phase-2=pending, phase-3=pending
%% FEEDBACK_TRIGGERS: TEST_FAILURE -> test-fix-loop, BUILD_FAILURE -> escalate
%% =============================================================================
"""
        result = parse_mmd_routing(mmd_content)
        assert result["agent_routing"] == {
            "phase-1": "build-python",
            "phase-2": "build-python",
            "phase-3": "test-builder",
        }
        assert result["status"] == {
            "phase-1": "pending",
            "phase-2": "pending",
            "phase-3": "pending",
        }
        assert result["feedback_triggers"] == {
            "TEST_FAILURE": "test-fix-loop",
            "BUILD_FAILURE": "escalate",
        }
        assert len(result["phases"]) == 3
        assert result["phases"][0]["id"] == "phase-1"

    def test_handles_hash_comment_style(self):
        """Parses both %% and # comment styles."""
        from agenticcli.workflows.orchestration import parse_mmd_routing

        mmd_content = """
# AGENT_ROUTING: phase-1 -> build-python
# STATUS: phase-1=pending
"""
        result = parse_mmd_routing(mmd_content)
        assert result["agent_routing"] == {"phase-1": "build-python"}
        assert result["status"] == {"phase-1": "pending"}


# ---------------------------------------------------------------------------
# OrchestrationWorkflow tests
# ---------------------------------------------------------------------------


class TestOrchestrationWorkflow:
    """Test OrchestrationWorkflow class."""

    def test_load_mmd_finds_file(self, tmp_path):
        """load_mmd returns MMD content when file exists."""
        from agenticcli.workflows.orchestration import OrchestrationWorkflow

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan = plans_dir / "my_plan"
        plan.mkdir()
        mmd_file = plan / "orchestration_build.mmd"
        mmd_file.write_text("graph TD\n  A --> B")

        workflow = OrchestrationWorkflow(plans_dir=plans_dir)
        result = workflow.load_mmd("my_plan")

        assert result == "graph TD\n  A --> B"

    def test_load_mmd_returns_none_when_missing(self, tmp_path):
        """load_mmd returns None when no MMD file exists."""
        from agenticcli.workflows.orchestration import OrchestrationWorkflow

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan = plans_dir / "my_plan"
        plan.mkdir()

        workflow = OrchestrationWorkflow(plans_dir=plans_dir)
        result = workflow.load_mmd("my_plan")

        assert result is None

    def test_parse_routing_delegates_to_function(self):
        """parse_routing delegates to parse_mmd_routing correctly."""
        from agenticcli.workflows.orchestration import OrchestrationWorkflow

        mmd_content = """
%% AGENT_ROUTING: phase-1 -> build-python
"""
        workflow = OrchestrationWorkflow()
        result = workflow.parse_routing(mmd_content)

        assert result["agent_routing"] == {"phase-1": "build-python"}


# ---------------------------------------------------------------------------
# PlanningRunner tests
# ---------------------------------------------------------------------------


class TestPlanningRunner:
    """Test PlanningRunner class."""

    def test_run_single_plan_success(self, tmp_path, monkeypatch):
        """run() succeeds for single plan with all phases passing."""
        from agenticcli.workflows.orchestration import PlanningRunner, OrchestrationWorkflow

        # Create mock workflow with plans_dir that exists
        plans_dir = tmp_path / "docs" / "plans" / "live"
        plans_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.plans_dir = plans_dir
        workflow.run_health_check.return_value = None
        workflow.discover_plans_needing_orchestration.return_value = []

        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.return_value = True
            mock_planner_runner.state = {
                "iteration": 1,
                "plans_processed": ["test_plan"],
                "errors": [],
            }
            MockRunner.return_value = mock_planner_runner

            runner = PlanningRunner(workflow=workflow, plan_folder="test_plan")
            result = runner.run(max_iterations=10)

            assert result is True
            assert "test_plan" in runner.state["plans_processed"]
            assert len(runner.state["plans_failed"]) == 0

    def test_run_discovery_mode(self, tmp_path, monkeypatch):
        """run() discovers and processes multiple plans when no --plan flag."""
        from agenticcli.workflows.orchestration import PlanningRunner, OrchestrationWorkflow

        plans_dir = tmp_path / "docs" / "plans" / "live"
        plans_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.plans_dir = plans_dir
        workflow.run_health_check.return_value = None
        workflow.discover_plans_needing_orchestration.return_value = ["plan_a", "plan_b"]

        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.return_value = True
            mock_planner_runner.state = {"iteration": 1, "plans_processed": [], "errors": []}
            MockRunner.return_value = mock_planner_runner

            runner = PlanningRunner(workflow=workflow, plan_folder=None)
            result = runner.run()

            assert result is True
            assert len(runner.state["plans_processed"]) == 2

    def test_no_plans_returns_true(self, tmp_path, monkeypatch):
        """run() returns True immediately when no plans need orchestration."""
        from agenticcli.workflows.orchestration import PlanningRunner, OrchestrationWorkflow

        plans_dir = tmp_path / "docs" / "plans" / "live"
        plans_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.plans_dir = plans_dir
        workflow.run_health_check.return_value = None
        workflow.discover_plans_needing_orchestration.return_value = []

        runner = PlanningRunner(workflow=workflow, plan_folder=None)
        result = runner.run()

        assert result is True

    def test_health_check_failure_returns_false(self, tmp_path):
        """run() returns False when health check fails."""
        from agenticcli.workflows.orchestration import PlanningRunner, OrchestrationWorkflow

        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.run_health_check.side_effect = RuntimeError("Health check failed")

        runner = PlanningRunner(workflow=workflow)
        result = runner.run()

        assert result is False
        assert len(runner.state["errors"]) > 0

    def test_planner_runner_failure_tracked(self, tmp_path):
        """Plans that fail planning are added to plans_failed."""
        from agenticcli.workflows.orchestration import PlanningRunner, OrchestrationWorkflow

        plans_dir = tmp_path / "docs" / "plans" / "live"
        plans_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.plans_dir = plans_dir
        workflow.run_health_check.return_value = None
        workflow.discover_plans_needing_orchestration.return_value = ["bad_plan"]

        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.return_value = False
            mock_planner_runner.state = {
                "iteration": 1,
                "plans_processed": [],
                "errors": [{"error": "Planning failed"}],
            }
            MockRunner.return_value = mock_planner_runner

            runner = PlanningRunner(workflow=workflow, plan_folder=None)
            result = runner.run()

            assert result is False
            assert "bad_plan" in runner.state["plans_failed"]

    def test_exception_in_planner_runner_tracked(self, tmp_path):
        """Exceptions raised by PlannerLoopRunner are caught and tracked."""
        from agenticcli.workflows.orchestration import PlanningRunner, OrchestrationWorkflow

        plans_dir = tmp_path / "docs" / "plans" / "live"
        plans_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.plans_dir = plans_dir
        workflow.run_health_check.return_value = None
        workflow.discover_plans_needing_orchestration.return_value = ["crash_plan"]

        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.side_effect = RuntimeError("Unexpected crash")
            mock_planner_runner.state = {"errors": []}
            MockRunner.return_value = mock_planner_runner

            runner = PlanningRunner(workflow=workflow, plan_folder=None)
            result = runner.run()

            assert result is False
            assert "crash_plan" in runner.state["plans_failed"]
            assert any("Unexpected crash" in str(e) for e in runner.state["errors"])
