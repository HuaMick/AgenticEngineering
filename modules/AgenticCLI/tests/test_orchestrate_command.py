"""Tests for the orchestrate command with positional action argument."""

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

pytestmark = pytest.mark.story("US-PLN-053")


# ---------------------------------------------------------------------------
# cmd_orchestrate planning action tests
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-053")
class TestOrchestratePlanningAction:
    """Test orchestrate command with planning action."""

    def test_planning_action_triggers_runner(self, tmp_path, monkeypatch):
        """action='planning' triggers PlanningRunner instead of error."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        with patch("agenticcli.workflows.orchestration.PlanningRunner") as MockRunner, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow") as MockWorkflow:
            mock_runner = MagicMock()
            mock_runner.run.return_value = True
            mock_runner.state = {
                "iteration": 1,
                "plans_processed": ["test_plan"],
                "plans_failed": [],
                "errors": [],
            }
            MockRunner.return_value = mock_runner

            mock_workflow = MagicMock()
            MockWorkflow.return_value = mock_workflow

            args = SimpleNamespace(
                action="planning",
                background=False,
                max_iterations=10,
                completion_promise=None,
                project=None,
                plan="test_plan",
                directory=str(tmp_path),
                dangerously_skip_permissions=False,
                json=False,
            )

            cmd_orchestrate(args)

            # Verify runner was instantiated and run was called
            MockRunner.assert_called_once()
            mock_runner.run.assert_called_once_with(
                max_iterations=10,
                completion_promise=None,
            )

    def test_unknown_action_exits_with_error(self, monkeypatch):
        """Unknown action exits with code 1."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        args = SimpleNamespace(
            action="bogus",
            background=False,
            max_iterations=10,
            completion_promise=None,
            project=None,
            plan=None,
            directory=None,
            dangerously_skip_permissions=False,
            json=False,
        )

        with pytest.raises(SystemExit) as exc_info:
            cmd_orchestrate(args)

        assert exc_info.value.code == 1

    def test_none_action_exits_with_error(self, monkeypatch):
        """No action provided exits with code 1."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        args = SimpleNamespace(
            action=None,
            background=False,
            max_iterations=10,
            completion_promise=None,
            project=None,
            plan=None,
            directory=None,
            dangerously_skip_permissions=False,
            json=False,
        )

        with pytest.raises(SystemExit) as exc_info:
            cmd_orchestrate(args)

        assert exc_info.value.code == 1

    def test_background_mode_spawns_subprocess(self, tmp_path, monkeypatch):
        """--background flag spawns subprocess instead of running foreground."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        mock_popen = MagicMock()
        mock_popen.return_value.pid = 12345
        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        # Mock open to prevent file creation errors
        monkeypatch.setattr("builtins.open", MagicMock())

        args = SimpleNamespace(
            action="planning",
            background=True,
            max_iterations=5,
            completion_promise="All done",
            project="test_project",
            plan="test_plan",
            directory=str(tmp_path),
            dangerously_skip_permissions=True,
            json=False,
        )

        cmd_orchestrate(args)

        # Verify Popen was called
        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]
        assert "orchestrate" in cmd_args
        # New format: orchestrate session plan
        assert "plan" in cmd_args
        assert "--max-iterations" in cmd_args
        assert "5" in cmd_args
        assert "--plan" in cmd_args
        assert "test_plan" in cmd_args

    def test_state_persistence(self, tmp_path, monkeypatch):
        """State file is created with correct structure."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        state_dir = tmp_path / ".agentic" / "orchestration_loops"
        state_dir.mkdir(parents=True)

        # Mock _store.get_dir to use tmp_path
        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._store.get_dir",
            lambda override=None: state_dir
        )

        with patch("agenticcli.workflows.orchestration.PlanningRunner") as MockRunner, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow") as MockWorkflow:
            mock_runner = MagicMock()
            mock_runner.run.return_value = True
            mock_runner.state = {
                "iteration": 2,
                "plans_processed": ["plan_a", "plan_b"],
                "plans_failed": [],
                "errors": [],
            }
            MockRunner.return_value = mock_runner

            mock_workflow = MagicMock()
            MockWorkflow.return_value = mock_workflow

            args = SimpleNamespace(
                action="planning",
                background=False,
                max_iterations=10,
                completion_promise=None,
                project=None,
                plan=None,
                directory=str(tmp_path),
                dangerously_skip_permissions=False,
                json=False,
            )

            cmd_orchestrate(args)

            # Check that a state file was created
            state_files = list(state_dir.glob("orch-*.json"))
            assert len(state_files) == 1

            # Verify state file contents
            with open(state_files[0]) as f:
                state = json.load(f)
                assert state["status"] == "completed"
                assert "started_at" in state
                assert "completed_at" in state
                assert state["plans_processed"] == ["plan_a", "plan_b"]

    def test_json_output_format(self, tmp_path, monkeypatch):
        """JSON output is produced when is_json_output returns True."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        # Mock console functions at their import location
        mock_print_json = MagicMock()
        monkeypatch.setattr("agenticcli.console.print_json", mock_print_json)
        monkeypatch.setattr("agenticcli.console.is_json_output", lambda: True)

        state_dir = tmp_path / ".agentic" / "orchestration_loops"
        state_dir.mkdir(parents=True)
        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._store.get_dir",
            lambda override=None: state_dir
        )

        with patch("agenticcli.workflows.orchestration.PlanningRunner") as MockRunner, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow") as MockWorkflow:
            mock_runner = MagicMock()
            mock_runner.run.return_value = True
            mock_runner.state = {
                "iteration": 1,
                "plans_processed": ["test_plan"],
                "plans_failed": [],
                "errors": [],
            }
            MockRunner.return_value = mock_runner

            mock_workflow = MagicMock()
            MockWorkflow.return_value = mock_workflow

            args = SimpleNamespace(
                action="planning",
                background=False,
                max_iterations=10,
                completion_promise=None,
                project=None,
                plan="test_plan",
                directory=str(tmp_path),
                dangerously_skip_permissions=False,
                json=True,
            )

            cmd_orchestrate(args)

            # Verify JSON was printed
            mock_print_json.assert_called_once()
            output = mock_print_json.call_args[0][0]
            assert output["status"] == "completed"
            assert output["plans_processed"] == ["test_plan"]

    def test_error_handling_on_runner_failure(self, tmp_path, monkeypatch):
        """Errors are handled gracefully when runner fails."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        state_dir = tmp_path / ".agentic" / "orchestration_loops"
        state_dir.mkdir(parents=True)
        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._store.get_dir",
            lambda override=None: state_dir
        )

        with patch("agenticcli.workflows.orchestration.PlanningRunner") as MockRunner, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow") as MockWorkflow:
            mock_runner = MagicMock()
            mock_runner.run.side_effect = RuntimeError("Test error")
            MockRunner.return_value = mock_runner

            mock_workflow = MagicMock()
            MockWorkflow.return_value = mock_workflow

            args = SimpleNamespace(
                action="planning",
                background=False,
                max_iterations=10,
                completion_promise=None,
                project=None,
                plan="test_plan",
                directory=str(tmp_path),
                dangerously_skip_permissions=False,
                json=False,
            )

            with pytest.raises(SystemExit) as exc_info:
                cmd_orchestrate(args)

            assert exc_info.value.code == 1

            # Verify error was recorded in state
            state_files = list(state_dir.glob("orch-*.json"))
            assert len(state_files) == 1
            with open(state_files[0]) as f:
                state = json.load(f)
                assert state["status"] == "failed"
                assert len(state["errors"]) > 0
                assert "Test error" in state["errors"][0]

    def test_plan_folder_parameter_passed(self, tmp_path, monkeypatch):
        """--plan parameter is correctly passed to PlanningRunner."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        with patch("agenticcli.workflows.orchestration.PlanningRunner") as MockRunner, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow") as MockWorkflow:
            mock_runner = MagicMock()
            mock_runner.run.return_value = True
            mock_runner.state = {
                "iteration": 1,
                "plans_processed": [],
                "plans_failed": [],
                "errors": [],
            }
            MockRunner.return_value = mock_runner

            mock_workflow = MagicMock()
            MockWorkflow.return_value = mock_workflow

            args = SimpleNamespace(
                action="planning",
                background=False,
                max_iterations=10,
                completion_promise=None,
                project="test_project",
                plan="my_test_plan",
                directory=str(tmp_path),
                dangerously_skip_permissions=False,
                json=False,
            )

            cmd_orchestrate(args)

            # Verify runner was created with correct parameters
            MockRunner.assert_called_once_with(
                workflow=mock_workflow,
                project="test_project",
                plan_folder="my_test_plan",
                budget_usd=50.0,
            )

    def test_completion_promise_parameter_passed(self, tmp_path, monkeypatch):
        """--completion-promise parameter is correctly passed to runner.run()."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        with patch("agenticcli.workflows.orchestration.PlanningRunner") as MockRunner, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow") as MockWorkflow:
            mock_runner = MagicMock()
            mock_runner.run.return_value = True
            mock_runner.state = {
                "iteration": 1,
                "plans_processed": [],
                "plans_failed": [],
                "errors": [],
            }
            MockRunner.return_value = mock_runner

            mock_workflow = MagicMock()
            MockWorkflow.return_value = mock_workflow

            args = SimpleNamespace(
                action="planning",
                background=False,
                max_iterations=15,
                completion_promise="All plans completed",
                project=None,
                plan=None,
                directory=str(tmp_path),
                dangerously_skip_permissions=False,
                json=False,
            )

            cmd_orchestrate(args)

            # Verify run was called with correct parameters
            mock_runner.run.assert_called_once_with(
                max_iterations=15,
                completion_promise="All plans completed",
            )
