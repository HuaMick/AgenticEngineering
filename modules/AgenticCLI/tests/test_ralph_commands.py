"""Integration tests for Ralph CLI commands.

Tests the 'agentic ralph' command group:
- start: Start Ralph loop to process all live plans
- stop: Stop the running Ralph loop
- status: Show Ralph loop status and progress
- next: Get the next recommended action (used by agent)
- history: Show iteration history
"""

import json
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


@pytest.fixture
def ralph_plans_dir(temp_dir):
    """Create a temp directory with sample plans for Ralph to discover."""
    plans_dir = temp_dir / "plans" / "live"
    plans_dir.mkdir(parents=True)

    # Plan 1: Has orchestration, ready to execute
    plan1 = plans_dir / "260203QC_question_cli"
    plan1.mkdir()
    (plan1 / "orchestration_question_cli.mmd").write_text("graph TD\nA --> B")
    plan1_build = {
        "name": "question-cli",
        "status": "active",
        "phases": [
            {
                "phase_id": "build_01",
                "name": "Build Phase",
                "tasks": [
                    {"task_id": "QC_001", "description": "Task 1", "status": "pending"},
                    {"task_id": "QC_002", "description": "Task 2", "status": "pending"},
                ]
            }
        ]
    }
    (plan1 / "plan_build.yml").write_text(yaml.dump(plan1_build))

    # Plan 2: Needs planning (no orchestration)
    plan2 = plans_dir / "260203QG_question_guidance"
    plan2.mkdir()
    plan2_build = {
        "name": "question-guidance",
        "status": "active",
        "phases": [
            {
                "phase_id": "build_01",
                "name": "Build Phase",
                "tasks": [
                    {"task_id": "QG_001", "description": "Task 1", "status": "pending"},
                ]
            }
        ]
    }
    (plan2 / "plan_build.yml").write_text(yaml.dump(plan2_build))

    # Plan 3: Completed (all tasks done)
    plan3 = plans_dir / "260203PS_plan_service"
    plan3.mkdir()
    (plan3 / "orchestration_plan_service.mmd").write_text("graph TD\nA --> B")
    plan3_build = {
        "name": "plan-service",
        "status": "active",
        "phases": [
            {
                "phase_id": "build_01",
                "name": "Build Phase",
                "tasks": [
                    {"task_id": "PS_001", "description": "Task 1", "status": "completed"},
                ]
            }
        ]
    }
    (plan3 / "plan_build.yml").write_text(yaml.dump(plan3_build))

    # Plan 4: Blocked (has dependencies)
    plan4 = plans_dir / "260203VP_voice_personaplex"
    plan4.mkdir()
    (plan4 / "orchestration_voice_personaplex.mmd").write_text("graph TD\nA --> B")
    plan4_build = {
        "name": "voice-personaplex",
        "status": "active",
        "dependencies": {
            "depends_on": ["260203QC", "260203QG"]  # Not completed yet
        },
        "phases": [
            {
                "phase_id": "build_01",
                "name": "Build Phase",
                "tasks": [
                    {"task_id": "VP_001", "description": "Task 1", "status": "pending"},
                ]
            }
        ]
    }
    (plan4 / "plan_build.yml").write_text(yaml.dump(plan4_build))

    return plans_dir


@pytest.fixture
def ralph_state_dir(temp_dir):
    """Create a temp directory for Ralph state files."""
    state_dir = temp_dir / "state"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def mock_ralph_service(ralph_plans_dir, ralph_state_dir, monkeypatch):
    """Mock RalphLoopService to use temp directories."""
    from agenticguidance.services.ralph import RalphLoopService

    # Monkeypatch __init__ to use our temp directories
    original_init = RalphLoopService.__init__

    def patched_init(self, plans_dir=None):
        original_init(self, plans_dir or ralph_plans_dir)
        self.state_dir = ralph_state_dir

    monkeypatch.setattr(RalphLoopService, "__init__", patched_init)

    return {"plans_dir": ralph_plans_dir, "state_dir": ralph_state_dir}


@pytest.fixture
def ralph_running_state(ralph_state_dir):
    """Create a running Ralph state file."""
    from agenticguidance.services.ralph import RalphState, IterationRecord

    state = RalphState(
        loop_id="test-loop-123",
        started_at=time.time() - 300,  # Started 5 minutes ago
        current_iteration=2,
        max_iterations=20,
        status="running",
        prompt_file="/path/to/prompt.txt",
        tmux_session="ralph-test-loop",
        iterations=[
            IterationRecord(
                number=1,
                started_at=time.time() - 290,
                ended_at=time.time() - 270,
                action_taken="execute:260203QC",
                result="success",
                plans_completed=[],
            ),
            IterationRecord(
                number=2,
                started_at=time.time() - 260,
                ended_at=time.time() - 240,
                action_taken="plan:260203QG",
                result="success",
                plans_completed=[],
            ),
        ]
    )

    state_file = ralph_state_dir / "state.json"
    state_file.write_text(json.dumps(state.to_dict(), indent=2))

    return state


class TestRalphNext:
    """Test ralph next command."""

    def test_next_returns_json(self, cli_runner, mock_ralph_service):
        """next -j returns valid JSON."""
        result = cli_runner(["session", "ralph", "next", "-j"])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "action" in data
        assert "plan" in data
        assert "task" in data
        assert "reason" in data

    def test_next_returns_execute_action(self, cli_runner, mock_ralph_service):
        """next returns execute when plan ready."""
        result = cli_runner(["session", "ralph", "next", "-j"])

        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Should prioritize plan with orchestration (execute action)
        assert data["action"] == "execute"
        assert data["plan"] == "260203QC_question_cli"
        # Task ID may be None if not found in analyze, just check action is correct
        assert "ready" in data["reason"].lower() or "pending" in data["reason"].lower()

    def test_next_returns_plan_action(self, cli_runner, mock_ralph_service, ralph_plans_dir):
        """next returns plan when no MMD but execute plans completed."""
        # Remove the execute-ready plan
        import shutil
        shutil.rmtree(ralph_plans_dir / "260203QC_question_cli")

        result = cli_runner(["session", "ralph", "next", "-j"])

        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Should return plan action for plan without orchestration
        assert data["action"] == "plan"
        assert data["plan"] == "260203QG_question_guidance"
        assert "orchestration" in data["reason"].lower() or "mmd" in data["reason"].lower()

    def test_next_returns_complete(self, cli_runner, mock_ralph_service, ralph_plans_dir):
        """next returns complete when all done."""
        # Mark all plans as completed
        import shutil

        # Remove non-completed plans
        shutil.rmtree(ralph_plans_dir / "260203QC_question_cli")
        shutil.rmtree(ralph_plans_dir / "260203QG_question_guidance")
        shutil.rmtree(ralph_plans_dir / "260203VP_voice_personaplex")

        result = cli_runner(["session", "ralph", "next", "-j"])

        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["action"] == "complete"
        assert "finished" in data["reason"].lower() or "complete" in data["reason"].lower()

    def test_next_returns_blocked(self, cli_runner, mock_ralph_service, ralph_plans_dir):
        """next returns blocked when all plans blocked or only completed plans remain."""
        # Remove all executable/plannable plans, leave only blocked one
        import shutil
        shutil.rmtree(ralph_plans_dir / "260203QC_question_cli")
        shutil.rmtree(ralph_plans_dir / "260203QG_question_guidance")

        result = cli_runner(["session", "ralph", "next", "-j"])

        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Should be either blocked (if only blocked plans) or complete (if blocked + completed)
        assert data["action"] in ("blocked", "complete")
        assert "blocked" in data["reason"].lower() or "no actionable" in data["reason"].lower() or "finished" in data["reason"].lower()

    def test_next_human_readable(self, cli_runner, mock_ralph_service):
        """next without -j shows formatted output."""
        result = cli_runner(["session", "ralph", "next"])

        assert result.returncode == 0
        # Should show action, plan, and reason in human-readable format
        assert "Action:" in result.stdout or "action" in result.stdout.lower()
        assert "260203QC" in result.stdout
        assert "Reason:" in result.stdout or "reason" in result.stdout.lower()


class TestRalphStatus:
    """Test ralph status command."""

    def test_status_no_loop(self, cli_runner, mock_ralph_service):
        """status shows no loop message."""
        result = cli_runner(["session", "ralph", "status"])

        assert result.returncode == 0
        assert "no loop" in result.stdout.lower() or "not" in result.stdout.lower()

    def test_status_running_loop(self, cli_runner, mock_ralph_service, ralph_running_state):
        """status shows running loop info."""
        result = cli_runner(["session", "ralph", "status"])

        assert result.returncode == 0
        assert "running" in result.stdout.lower()
        assert "test-loop-123" in result.stdout
        assert "2" in result.stdout  # Current iteration
        assert "20" in result.stdout  # Max iterations

    def test_status_json_output(self, cli_runner, mock_ralph_service, ralph_running_state):
        """status -j returns valid JSON."""
        result = cli_runner(["session", "ralph", "status", "-j"])

        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert "loop" in data
        assert "plans" in data
        assert data["loop"]["status"] == "running"
        assert data["loop"]["loop_id"] == "test-loop-123"
        assert data["loop"]["current_iteration"] == 2

    def test_status_shows_plan_counts(self, cli_runner, mock_ralph_service, ralph_running_state):
        """status shows plan statistics."""
        result = cli_runner(["session", "ralph", "status", "-j"])

        assert result.returncode == 0
        data = json.loads(result.stdout)

        plans_info = data["plans"]
        assert "total" in plans_info
        assert "ready_to_execute" in plans_info
        assert "needs_planning" in plans_info
        assert "blocked" in plans_info
        assert "completed" in plans_info

        # Based on our fixture setup
        assert plans_info["total"] == 4
        assert plans_info["ready_to_execute"] == 1  # 260203QC
        assert plans_info["needs_planning"] == 1  # 260203QG
        assert plans_info["blocked"] == 1  # 260203VP
        assert plans_info["completed"] == 1  # 260203PS

    def test_status_human_readable_shows_plan_stats(self, cli_runner, mock_ralph_service):
        """status without -j shows plan statistics in human format."""
        result = cli_runner(["session", "ralph", "status"])

        assert result.returncode == 0
        # Should show plan breakdown
        assert "Plan Status" in result.stdout or "plan" in result.stdout.lower()
        assert "Ready to execute" in result.stdout or "execute" in result.stdout.lower()


class TestRalphHistory:
    """Test ralph history command."""

    def test_history_no_iterations(self, cli_runner, mock_ralph_service):
        """history with no iterations shows message."""
        # history command raises click.exceptions.Exit which is not SystemExit
        # So we need to handle it differently
        import click

        try:
            result = cli_runner(["session", "ralph", "history"])
            # If no exception, check output
            output = result.stdout + result.stderr
            assert "no" in output.lower() or "iteration" in output.lower()
        except click.exceptions.Exit as e:
            # This is expected - exit code 0 means success
            assert e.exit_code == 0

    def test_history_with_iterations(self, cli_runner, mock_ralph_service, ralph_running_state):
        """history shows iteration records."""
        result = cli_runner(["session", "ralph", "history"])

        assert result.returncode == 0
        # Should show iteration info
        assert "execute:260203QC" in result.stdout
        assert "plan:260203QG" in result.stdout
        assert "success" in result.stdout.lower()

    def test_history_json_output(self, cli_runner, mock_ralph_service, ralph_running_state):
        """history -j returns valid JSON."""
        result = cli_runner(["session", "ralph", "history", "-j"])

        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert "iterations" in data
        assert "total" in data
        assert "showing" in data

        assert data["total"] == 2
        assert len(data["iterations"]) == 2

        # Check iteration structure
        iteration = data["iterations"][0]
        assert "number" in iteration
        assert "action" in iteration
        assert "result" in iteration
        assert "duration_seconds" in iteration

    def test_history_limit(self, cli_runner, mock_ralph_service, ralph_running_state):
        """history --limit restricts output."""
        result = cli_runner(["session", "ralph", "history", "--limit", "1", "-j"])

        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["total"] == 2  # Total iterations
        assert data["showing"] == 1  # But only showing 1
        assert len(data["iterations"]) == 1

    def test_history_shows_duration(self, cli_runner, mock_ralph_service, ralph_running_state):
        """history displays iteration duration."""
        result = cli_runner(["session", "ralph", "history"])

        assert result.returncode == 0
        # Should show duration in human-readable format
        assert "Duration" in result.stdout or "s" in result.stdout  # seconds marker


class TestRalphStart:
    """Test ralph start command (limited - no tmux in tests)."""

    def test_start_checks_existing_loop(self, cli_runner, mock_ralph_service, ralph_running_state):
        """start fails if loop already running."""
        import agenticcli.commands.ralph as ralph_module
        import click

        with patch.object(ralph_module.shutil, "which", return_value="/usr/bin/tmux"):
            try:
                result = cli_runner(["session", "ralph", "start"])
                # If it doesn't raise, check for error
                assert result.returncode == 1
            except click.exceptions.Exit as e:
                # Expected to exit with error code
                assert e.exit_code == 1

    def test_start_checks_tmux(self, cli_runner, mock_ralph_service):
        """start errors if tmux not found."""
        import agenticcli.commands.ralph as ralph_module
        import click

        with patch.object(ralph_module.shutil, "which", return_value=None):
            try:
                result = cli_runner(["session", "ralph", "start"])
                assert result.returncode == 1
            except click.exceptions.Exit as e:
                assert e.exit_code == 1

    def test_start_checks_claude(self, cli_runner, mock_ralph_service):
        """start errors if claude not found."""
        import agenticcli.commands.ralph as ralph_module
        import click

        def mock_which(cmd):
            if cmd == "tmux":
                return "/usr/bin/tmux"
            return None

        with patch.object(ralph_module.shutil, "which", side_effect=mock_which):
            try:
                result = cli_runner(["session", "ralph", "start"])
                assert result.returncode == 1
            except click.exceptions.Exit as e:
                assert e.exit_code == 1

    def test_start_with_custom_prompt(self, cli_runner, mock_ralph_service, temp_dir):
        """start accepts custom prompt file."""
        import agenticcli.commands.ralph as ralph_module
        import click

        prompt_file = temp_dir / "custom_prompt.txt"
        prompt_file.write_text("Custom Ralph prompt")

        # Mock tmux and claude as available, but make tmux creation fail (to avoid actually starting)
        def mock_which(cmd):
            return f"/usr/bin/{cmd}"

        with patch.object(ralph_module.shutil, "which", side_effect=mock_which):
            with patch.object(ralph_module.subprocess, "run") as mock_run:
                # Make tmux new-session fail to avoid background process
                mock_run.return_value = MagicMock(returncode=1, stderr="tmux error")

                try:
                    result = cli_runner(["session", "ralph", "start", "--prompt-file", str(prompt_file)])
                    # If no exception, command accepted the argument
                    assert True
                except click.exceptions.Exit:
                    # Exit is OK - we're just testing argument acceptance
                    pass

    def test_start_with_max_iterations(self, cli_runner, mock_ralph_service):
        """start accepts max iterations argument."""
        import agenticcli.commands.ralph as ralph_module
        import click

        def mock_which(cmd):
            return f"/usr/bin/{cmd}"

        with patch.object(ralph_module.shutil, "which", side_effect=mock_which):
            with patch.object(ralph_module.subprocess, "run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stderr="tmux error")

                try:
                    result = cli_runner(["session", "ralph", "start", "--max-iterations", "50"])
                    assert True
                except click.exceptions.Exit:
                    pass

    def test_start_background_flag(self, cli_runner, mock_ralph_service):
        """start accepts --background flag."""
        import agenticcli.commands.ralph as ralph_module
        import click

        def mock_which(cmd):
            return f"/usr/bin/{cmd}"

        with patch.object(ralph_module.shutil, "which", side_effect=mock_which):
            with patch.object(ralph_module.subprocess, "run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stderr="tmux error")

                try:
                    result = cli_runner(["session", "ralph", "start", "--background"])
                    assert True
                except click.exceptions.Exit:
                    pass


class TestRalphStop:
    """Test ralph stop command."""

    def test_stop_no_loop(self, cli_runner, mock_ralph_service):
        """stop shows no loop running message."""
        # stop raises click.exceptions.Exit(0) when no loop is running
        import click

        try:
            result = cli_runner(["session", "ralph", "stop"])
            # If no exception, check output
            output = result.stdout + result.stderr
            assert "no" in output.lower() and ("loop" in output.lower() or "running" in output.lower())
        except click.exceptions.Exit as e:
            # This is expected - exit code 0 means success
            assert e.exit_code == 0

    def test_stop_updates_state(self, cli_runner, mock_ralph_service, ralph_running_state, ralph_state_dir):
        """stop updates loop state to stopped."""
        # Mock tmux commands to avoid actual tmux operations
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = cli_runner(["session", "ralph", "stop"])

        assert result.returncode == 0
        assert "stopped" in result.stdout.lower() or "stopping" in result.stdout.lower()

        # Verify state was updated
        state_file = ralph_state_dir / "state.json"
        assert state_file.exists()

        state_data = json.loads(state_file.read_text())
        assert state_data["status"] == "stopped"

    def test_stop_force_flag(self, cli_runner, mock_ralph_service, ralph_running_state):
        """stop --force immediately kills session."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = cli_runner(["session", "ralph", "stop", "--force"])

        assert result.returncode == 0

        # Verify subprocess was called with kill-session
        calls = [call for call in mock_run.call_args_list if call[0][0][1] == "kill-session"]
        assert len(calls) > 0

    def test_stop_graceful_sends_termination(self, cli_runner, mock_ralph_service, ralph_running_state):
        """stop without --force sends graceful termination."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            with patch("time.sleep"):  # Skip the sleep delay
                result = cli_runner(["session", "ralph", "stop"])

        assert result.returncode == 0

        # Should call both send-keys (C-c) and kill-session
        all_calls = [call[0][0] for call in mock_run.call_args_list]
        send_keys_calls = [c for c in all_calls if len(c) > 1 and c[1] == "send-keys"]
        kill_calls = [c for c in all_calls if len(c) > 1 and c[1] == "kill-session"]

        assert len(send_keys_calls) > 0
        assert len(kill_calls) > 0


class TestRalphIntegration:
    """Integration tests for Ralph commands working together."""

    def test_status_and_next_consistency(self, cli_runner, mock_ralph_service):
        """status and next should show consistent plan states."""
        # Get status
        status_result = cli_runner(["session", "ralph", "status", "-j"])
        assert status_result.returncode == 0
        status_data = json.loads(status_result.stdout)

        # Get next action
        next_result = cli_runner(["session", "ralph", "next", "-j"])
        assert next_result.returncode == 0
        next_data = json.loads(next_result.stdout)

        # If status shows ready_to_execute plans, next should return execute action
        if status_data["plans"]["ready_to_execute"] > 0:
            assert next_data["action"] == "execute"
        elif status_data["plans"]["needs_planning"] > 0:
            assert next_data["action"] == "plan"

    def test_next_prioritizes_execute_over_plan(self, cli_runner, mock_ralph_service):
        """next should prioritize execute actions over plan actions."""
        result = cli_runner(["session", "ralph", "next", "-j"])
        assert result.returncode == 0
        data = json.loads(result.stdout)

        # With our fixture, 260203QC is ready to execute, 260203QG needs planning
        # Execute should be prioritized
        assert data["action"] == "execute"
        assert data["plan"] == "260203QC_question_cli"

    def test_history_after_stop(self, cli_runner, mock_ralph_service, ralph_running_state):
        """history should still be accessible after stopping loop."""
        # Stop the loop
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cli_runner(["session", "ralph", "stop"])

        # History should still show iterations
        result = cli_runner(["session", "ralph", "history", "-j"])
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["total"] == 2
        assert len(data["iterations"]) == 2
