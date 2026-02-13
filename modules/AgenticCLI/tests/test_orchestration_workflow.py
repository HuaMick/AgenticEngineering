"""Tests for the orchestration workflow and runner."""

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

    def test_spawn_execution_agent_calls_subprocess(self, monkeypatch):
        """spawn_execution_agent calls subprocess with correct args."""
        from agenticcli.workflows.orchestration import OrchestrationWorkflow

        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(
                cmd, 0,
                stdout=json.dumps({"session_id": "test-session-123"}),
                stderr=""
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = OrchestrationWorkflow()
        session_id = workflow.spawn_execution_agent("my_plan", "phase-1", "build-python")

        assert session_id == "test-session-123"
        assert len(calls) == 1
        assert "agentic" in calls[0]
        assert "session" in calls[0]
        assert "spawn" in calls[0]
        assert "--role" in calls[0]
        assert "build-python" in calls[0]
        assert "--plan" in calls[0]
        assert "my_plan" in calls[0]

    def test_spawn_execution_agent_returns_none_on_failure(self, monkeypatch):
        """spawn_execution_agent returns None when subprocess fails."""
        from agenticcli.workflows.orchestration import OrchestrationWorkflow

        def mock_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error")

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = OrchestrationWorkflow()
        result = workflow.spawn_execution_agent("my_plan", "phase-1", "build-python")

        assert result is None

    def test_archive_plan_calls_subprocess(self, monkeypatch):
        """archive_plan calls subprocess with correct args."""
        from agenticcli.workflows.orchestration import OrchestrationWorkflow

        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = OrchestrationWorkflow()
        result = workflow.archive_plan("my_plan")

        assert result is True
        assert len(calls) == 1
        assert "agentic" in calls[0]
        assert "plan" in calls[0]
        assert "archive" in calls[0]
        assert "my_plan" in calls[0]

    def test_archive_plan_returns_false_on_failure(self, monkeypatch):
        """archive_plan returns False when subprocess fails."""
        from agenticcli.workflows.orchestration import OrchestrationWorkflow

        def mock_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error")

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = OrchestrationWorkflow()
        result = workflow.archive_plan("my_plan")

        assert result is False


# ---------------------------------------------------------------------------
# OrchestrationRunner tests
# ---------------------------------------------------------------------------


class TestOrchestrationRunner:
    """Test OrchestrationRunner class."""

    def test_run_single_plan_success(self, tmp_path, monkeypatch):
        """run() succeeds for single plan with all phases passing."""
        from agenticcli.workflows.orchestration import OrchestrationRunner, OrchestrationWorkflow

        # Create mock workflow
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.run_health_check.return_value = None
        workflow.load_mmd.return_value = """
%% AGENT_ROUTING: phase-1 -> build-python
%% STATUS: phase-1=pending
%% PHASES:
%%   1. phase-1 - Build
"""
        workflow.parse_routing.return_value = {
            "agent_routing": {"phase-1": "build-python"},
            "status": {"phase-1": "pending"},
            "feedback_triggers": {},
            "phases": [{"id": "phase-1", "description": "Build"}],
        }
        workflow.spawn_execution_agent.return_value = "session-123"
        workflow.archive_plan.return_value = True

        # Mock subprocess for session status checks
        def mock_run(cmd, **kwargs):
            if "status" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 0,
                    stdout=json.dumps({"status": "completed"}),
                    stderr=""
                )
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr("time.sleep", lambda x: None)  # Speed up test

        # Mock PlannerLoopRunner
        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.return_value = True
            mock_planner_runner.state = {
                "iteration": 1,
                "plans_processed": ["test_plan"],
                "errors": [],
            }
            MockRunner.return_value = mock_planner_runner

            runner = OrchestrationRunner(workflow=workflow, plan_folder="test_plan")
            result = runner.run(max_iterations=10)

            assert result is True
            assert "test_plan" in runner.state["plans_processed"]
            assert len(runner.state["plans_failed"]) == 0

    def test_run_discovery_mode(self, tmp_path, monkeypatch):
        """run() discovers and processes multiple plans when no --plan flag."""
        from agenticcli.workflows.orchestration import OrchestrationRunner, OrchestrationWorkflow

        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.run_health_check.return_value = None
        workflow.discover_plans_needing_orchestration.return_value = ["plan_a", "plan_b"]
        workflow.load_mmd.return_value = """
%% AGENT_ROUTING: phase-1 -> build-python
%% PHASES:
%%   1. phase-1 - Build
"""
        workflow.parse_routing.return_value = {
            "agent_routing": {"phase-1": "build-python"},
            "status": {},
            "feedback_triggers": {},
            "phases": [{"id": "phase-1", "description": "Build"}],
        }
        workflow.spawn_execution_agent.return_value = "session-123"
        workflow.archive_plan.return_value = True

        def mock_run(cmd, **kwargs):
            if "status" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 0,
                    stdout=json.dumps({"status": "completed"}),
                    stderr=""
                )
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr("time.sleep", lambda x: None)

        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.return_value = True
            mock_planner_runner.state = {"iteration": 1, "plans_processed": [], "errors": []}
            MockRunner.return_value = mock_planner_runner

            runner = OrchestrationRunner(workflow=workflow, plan_folder=None)
            result = runner.run()

            assert result is True
            assert len(runner.state["plans_processed"]) == 2

    def test_phase_retry_on_failure(self, tmp_path, monkeypatch):
        """_execute_phase retries on failure up to max_phase_retries."""
        from agenticcli.workflows.orchestration import OrchestrationRunner, OrchestrationWorkflow

        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.run_health_check.return_value = None
        workflow.load_mmd.return_value = """
%% AGENT_ROUTING: phase-1 -> build-python
%% PHASES:
%%   1. phase-1 - Build
"""
        workflow.parse_routing.return_value = {
            "agent_routing": {"phase-1": "build-python"},
            "status": {},
            "feedback_triggers": {},
            "phases": [{"id": "phase-1", "description": "Build"}],
        }
        workflow.archive_plan.return_value = True

        # First two calls fail, third succeeds
        call_count = [0]

        def spawn_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                return None  # Fail
            return "session-123"  # Success

        workflow.spawn_execution_agent.side_effect = spawn_side_effect

        def mock_run(cmd, **kwargs):
            if "status" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 0,
                    stdout=json.dumps({"status": "completed"}),
                    stderr=""
                )
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr("time.sleep", lambda x: None)

        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.return_value = True
            mock_planner_runner.state = {"iteration": 1, "plans_processed": [], "errors": []}
            MockRunner.return_value = mock_planner_runner

            runner = OrchestrationRunner(workflow=workflow, plan_folder="test_plan")
            result = runner.run(max_phase_retries=2)

            assert result is True
            assert call_count[0] == 3  # Two failures + one success

    def test_max_retries_respected(self, tmp_path, monkeypatch):
        """Phase execution fails after max_phase_retries."""
        from agenticcli.workflows.orchestration import OrchestrationRunner, OrchestrationWorkflow

        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.run_health_check.return_value = None
        workflow.load_mmd.return_value = """
%% AGENT_ROUTING: phase-1 -> build-python
%% PHASES:
%%   1. phase-1 - Build
"""
        workflow.parse_routing.return_value = {
            "agent_routing": {"phase-1": "build-python"},
            "status": {},
            "feedback_triggers": {},
            "phases": [{"id": "phase-1", "description": "Build"}],
        }
        workflow.spawn_execution_agent.return_value = None  # Always fail
        workflow.archive_plan.return_value = True

        monkeypatch.setattr("time.sleep", lambda x: None)

        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.return_value = True
            mock_planner_runner.state = {"iteration": 1, "plans_processed": [], "errors": []}
            MockRunner.return_value = mock_planner_runner

            runner = OrchestrationRunner(workflow=workflow, plan_folder="test_plan")
            result = runner.run(max_phase_retries=1)

            assert result is False
            assert "test_plan" in runner.state["plans_failed"]
            assert len(runner.state["errors"]) > 0

    def test_state_tracking_updates(self, tmp_path, monkeypatch):
        """State dict updates correctly throughout lifecycle."""
        from agenticcli.workflows.orchestration import OrchestrationRunner, OrchestrationWorkflow

        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.run_health_check.return_value = None
        workflow.load_mmd.return_value = """
%% AGENT_ROUTING: phase-1 -> build-python, phase-2 -> test-runner
%% PHASES:
%%   1. phase-1 - Build
%%   2. phase-2 - Test
"""
        workflow.parse_routing.return_value = {
            "agent_routing": {"phase-1": "build-python", "phase-2": "test-runner"},
            "status": {},
            "feedback_triggers": {},
            "phases": [
                {"id": "phase-1", "description": "Build"},
                {"id": "phase-2", "description": "Test"},
            ],
        }
        workflow.spawn_execution_agent.return_value = "session-123"
        workflow.archive_plan.return_value = True

        def mock_run(cmd, **kwargs):
            if "status" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 0,
                    stdout=json.dumps({"status": "completed"}),
                    stderr=""
                )
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr("time.sleep", lambda x: None)

        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.return_value = True
            mock_planner_runner.state = {"iteration": 1, "plans_processed": [], "errors": []}
            MockRunner.return_value = mock_planner_runner

            runner = OrchestrationRunner(workflow=workflow, plan_folder="test_plan")
            runner.run()

            # Check execution results tracking
            assert "test_plan" in runner.state["execution_results"]
            assert runner.state["execution_results"]["test_plan"]["phase-1"] == "success"
            assert runner.state["execution_results"]["test_plan"]["phase-2"] == "success"

    def test_archives_on_success(self, tmp_path, monkeypatch):
        """archive_plan is called after successful execution."""
        from agenticcli.workflows.orchestration import OrchestrationRunner, OrchestrationWorkflow

        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.run_health_check.return_value = None
        workflow.load_mmd.return_value = """
%% AGENT_ROUTING: phase-1 -> build-python
%% PHASES:
%%   1. phase-1 - Build
"""
        workflow.parse_routing.return_value = {
            "agent_routing": {"phase-1": "build-python"},
            "status": {},
            "feedback_triggers": {},
            "phases": [{"id": "phase-1", "description": "Build"}],
        }
        workflow.spawn_execution_agent.return_value = "session-123"
        workflow.archive_plan.return_value = True

        def mock_run(cmd, **kwargs):
            if "status" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 0,
                    stdout=json.dumps({"status": "completed"}),
                    stderr=""
                )
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr("time.sleep", lambda x: None)

        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.return_value = True
            mock_planner_runner.state = {"iteration": 1, "plans_processed": [], "errors": []}
            MockRunner.return_value = mock_planner_runner

            runner = OrchestrationRunner(workflow=workflow, plan_folder="test_plan")
            runner.run()

            workflow.archive_plan.assert_called_once_with("test_plan")
