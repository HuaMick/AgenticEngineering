"""Tests for the orchestrate command with --planning-loop flag."""

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# cmd_orchestrate --planning-loop tests
# ---------------------------------------------------------------------------


class TestOrchestratePlanningLoop:
    """Test orchestrate command with --planning-loop flag."""

    def test_planning_loop_flag_triggers_runner(self, tmp_path, monkeypatch):
        """--planning-loop flag triggers OrchestrationRunner instead of interactive session."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        # Mock OrchestrationRunner and OrchestrationWorkflow at the import location
        with patch("agenticcli.workflows.orchestration.OrchestrationRunner") as MockRunner, \
             patch("agenticcli.workflows.orchestration.OrchestrationWorkflow") as MockWorkflow:
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
                planning_loop=True,
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

    def test_no_flag_launches_interactive(self, monkeypatch):
        """Without --planning-loop flag, launches interactive Claude session."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        # Mock os.execvp to prevent actually launching Claude
        mock_execvp = MagicMock()
        monkeypatch.setattr(os, "execvp", mock_execvp)

        args = SimpleNamespace(
            planning_loop=False,
            mode="planning",
            prompt_file=None,
            role=None,
            plan=None,
            model=None,
        )

        cmd_orchestrate(args)

        # Verify execvp was called with claude command
        mock_execvp.assert_called_once()
        call_args = mock_execvp.call_args[0]
        assert call_args[0] == "claude"
        assert "claude" in call_args[1]
        assert "--dangerously-skip-permissions" in call_args[1]

    def test_background_mode_spawns_subprocess(self, tmp_path, monkeypatch):
        """--background flag spawns subprocess instead of running foreground."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        mock_popen = MagicMock()
        mock_popen.return_value.pid = 12345
        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        # Mock open to prevent file creation errors
        monkeypatch.setattr("builtins.open", MagicMock())

        args = SimpleNamespace(
            planning_loop=True,
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
        assert "--planning-loop" in cmd_args
        assert "--max-iterations" in cmd_args
        assert "5" in cmd_args
        assert "--plan" in cmd_args
        assert "test_plan" in cmd_args

    def test_state_persistence(self, tmp_path, monkeypatch):
        """State file is created with correct structure."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        state_dir = tmp_path / ".agentic" / "orchestration_loops"
        state_dir.mkdir(parents=True)

        # Mock _get_orchestration_loops_dir to use tmp_path
        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._get_orchestration_loops_dir",
            lambda: state_dir
        )

        with patch("agenticcli.workflows.orchestration.OrchestrationRunner") as MockRunner, \
             patch("agenticcli.workflows.orchestration.OrchestrationWorkflow") as MockWorkflow:
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
                planning_loop=True,
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
        """--json flag produces JSON output."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        # Mock console functions at their import location
        mock_print_json = MagicMock()
        monkeypatch.setattr("agenticcli.console.print_json", mock_print_json)
        monkeypatch.setattr("agenticcli.console.is_json_output", lambda: True)

        state_dir = tmp_path / ".agentic" / "orchestration_loops"
        state_dir.mkdir(parents=True)
        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._get_orchestration_loops_dir",
            lambda: state_dir
        )

        with patch("agenticcli.workflows.orchestration.OrchestrationRunner") as MockRunner, \
             patch("agenticcli.workflows.orchestration.OrchestrationWorkflow") as MockWorkflow:
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
                planning_loop=True,
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
            "agenticcli.commands.orchestrate._get_orchestration_loops_dir",
            lambda: state_dir
        )

        with patch("agenticcli.workflows.orchestration.OrchestrationRunner") as MockRunner, \
             patch("agenticcli.workflows.orchestration.OrchestrationWorkflow") as MockWorkflow:
            mock_runner = MagicMock()
            mock_runner.run.side_effect = RuntimeError("Test error")
            MockRunner.return_value = mock_runner

            mock_workflow = MagicMock()
            MockWorkflow.return_value = mock_workflow

            args = SimpleNamespace(
                planning_loop=True,
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
        """--plan parameter is correctly passed to OrchestrationRunner."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        with patch("agenticcli.workflows.orchestration.OrchestrationRunner") as MockRunner, \
             patch("agenticcli.workflows.orchestration.OrchestrationWorkflow") as MockWorkflow:
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
                planning_loop=True,
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
            )

    def test_completion_promise_parameter_passed(self, tmp_path, monkeypatch):
        """--completion-promise parameter is correctly passed to runner.run()."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        with patch("agenticcli.workflows.orchestration.OrchestrationRunner") as MockRunner, \
             patch("agenticcli.workflows.orchestration.OrchestrationWorkflow") as MockWorkflow:
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
                planning_loop=True,
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


# ---------------------------------------------------------------------------
# Tmux Layout Integration Tests
# ---------------------------------------------------------------------------


class TestOrchestrateWithTmuxLayout:
    """Test orchestrate command tmux layout integration."""

    def test_attempts_tmux_layout_creation_by_default(self, monkeypatch):
        """Without --no-tmux flag, orchestrate attempts to create tmux layout."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        mock_layout = MagicMock()
        mock_layout.created_new_session = True
        mock_layout.session_name = "test-session"

        mock_create_layout = MagicMock(return_value=mock_layout)
        mock_attach = MagicMock()
        mock_tmux_available = MagicMock(return_value=True)

        # Mock tmux layout functions
        monkeypatch.setattr("agenticcli.utils.tmux_layout.create_orchestration_layout", mock_create_layout)
        monkeypatch.setattr("agenticcli.utils.tmux_layout.attach_to_session", mock_attach)
        monkeypatch.setattr("agenticcli.utils.tmux_layout.tmux_available", mock_tmux_available)
        monkeypatch.setattr("agenticcli.utils.tmux.is_in_tmux", lambda: False)

        args = SimpleNamespace(
            planning_loop=False,
            mode="planning",
            prompt_file=None,
            role=None,
            plan=None,
            model=None,
            no_tmux=False,
            dashboard_refresh=5,
            question_refresh=10,
        )

        cmd_orchestrate(args)

        # Verify create_orchestration_layout was called with correct arguments
        mock_create_layout.assert_called_once()
        call_kwargs = mock_create_layout.call_args[1]
        assert "claude_cmd" in call_kwargs
        assert call_kwargs["dashboard_refresh"] == 5
        assert call_kwargs["question_refresh"] == 10

        # Verify attach was called for new session
        mock_attach.assert_called_once_with("test-session")

    def test_execvp_for_inplace_layout(self, monkeypatch):
        """For in-place layout (already in tmux), execvp to Claude in main pane."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        mock_layout = MagicMock()
        mock_layout.created_new_session = False
        mock_layout.session_name = "existing-session"

        mock_create_layout = MagicMock(return_value=mock_layout)
        mock_tmux_available = MagicMock(return_value=True)
        mock_execvp = MagicMock()

        monkeypatch.setattr("agenticcli.utils.tmux_layout.create_orchestration_layout", mock_create_layout)
        monkeypatch.setattr("agenticcli.utils.tmux_layout.tmux_available", mock_tmux_available)
        monkeypatch.setattr("agenticcli.utils.tmux.is_in_tmux", lambda: True)
        monkeypatch.setattr(os, "execvp", mock_execvp)

        args = SimpleNamespace(
            planning_loop=False,
            mode="planning",
            prompt_file=None,
            role=None,
            plan=None,
            model=None,
            no_tmux=False,
            dashboard_refresh=5,
            question_refresh=10,
        )

        cmd_orchestrate(args)

        # Verify create_orchestration_layout was called
        mock_create_layout.assert_called_once()

        # Verify execvp was called (since created_new_session = False)
        mock_execvp.assert_called_once()
        assert mock_execvp.call_args[0][0] == "claude"

    def test_fallback_when_tmux_layout_fails(self, monkeypatch):
        """Falls back to plain Claude session when tmux layout creation fails."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        mock_create_layout = MagicMock(side_effect=RuntimeError("tmux split-window failed"))
        mock_tmux_available = MagicMock(return_value=True)
        mock_execvp = MagicMock()

        monkeypatch.setattr("agenticcli.utils.tmux_layout.create_orchestration_layout", mock_create_layout)
        monkeypatch.setattr("agenticcli.utils.tmux_layout.tmux_available", mock_tmux_available)
        monkeypatch.setattr("agenticcli.utils.tmux.is_in_tmux", lambda: False)
        monkeypatch.setattr(os, "execvp", mock_execvp)

        args = SimpleNamespace(
            planning_loop=False,
            mode="planning",
            prompt_file=None,
            role=None,
            plan=None,
            model=None,
            no_tmux=False,
            dashboard_refresh=5,
            question_refresh=10,
        )

        cmd_orchestrate(args)

        # Verify create_orchestration_layout was attempted
        mock_create_layout.assert_called_once()

        # Verify fallback to plain execvp
        mock_execvp.assert_called_once()
        assert mock_execvp.call_args[0][0] == "claude"

    def test_no_tmux_flag_bypasses_layout_creation(self, monkeypatch):
        """--no-tmux flag bypasses tmux layout creation entirely."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        mock_create_layout = MagicMock()
        mock_execvp = MagicMock()

        monkeypatch.setattr("agenticcli.utils.tmux_layout.create_orchestration_layout", mock_create_layout)
        monkeypatch.setattr(os, "execvp", mock_execvp)

        args = SimpleNamespace(
            planning_loop=False,
            mode="planning",
            prompt_file=None,
            role=None,
            plan=None,
            model=None,
            no_tmux=True,
            dashboard_refresh=5,
            question_refresh=10,
        )

        cmd_orchestrate(args)

        # Verify create_orchestration_layout was NOT called
        mock_create_layout.assert_not_called()

        # Verify direct execvp to claude
        mock_execvp.assert_called_once()
        assert mock_execvp.call_args[0][0] == "claude"

    def test_dashboard_refresh_parameters_passed_through(self, monkeypatch):
        """Dashboard refresh parameters are correctly passed to tmux layout."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        mock_layout = MagicMock()
        mock_layout.created_new_session = True
        mock_layout.session_name = "test-session"

        mock_create_layout = MagicMock(return_value=mock_layout)
        mock_attach = MagicMock()
        mock_tmux_available = MagicMock(return_value=True)

        monkeypatch.setattr("agenticcli.utils.tmux_layout.create_orchestration_layout", mock_create_layout)
        monkeypatch.setattr("agenticcli.utils.tmux_layout.attach_to_session", mock_attach)
        monkeypatch.setattr("agenticcli.utils.tmux_layout.tmux_available", mock_tmux_available)
        monkeypatch.setattr("agenticcli.utils.tmux.is_in_tmux", lambda: False)

        args = SimpleNamespace(
            planning_loop=False,
            mode="planning",
            prompt_file=None,
            role=None,
            plan=None,
            model=None,
            no_tmux=False,
            dashboard_refresh=20,
            question_refresh=40,
        )

        cmd_orchestrate(args)

        # Verify custom refresh intervals were passed
        call_kwargs = mock_create_layout.call_args[1]
        assert call_kwargs["dashboard_refresh"] == 20
        assert call_kwargs["question_refresh"] == 40
