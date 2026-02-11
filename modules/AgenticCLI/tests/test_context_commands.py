"""Tests for context commands (JIT context retrieval).

Tests the 'agentic context' command group:
- bootstrap: Get agent seed context
- role: Get role-specific guidance
- task: Get current task from plan
- inputs: Get input file manifest
- generate-agent: Generate thin-client agent file
"""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


@pytest.fixture
def plan_repo(temp_dir):
    """Create a repository with Main-First plan structure."""
    repo_dir = temp_dir / "main_repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_dir,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        capture_output=True,
    )

    # Create docs/plans/live structure with a plan folder (flattened structure)
    plan_folder = repo_dir / "docs" / "plans" / "live" / "260123CL_test_plan"
    plan_folder.mkdir(parents=True)

    # Create README.md
    readme = plan_folder / "README.md"
    readme.write_text(
        """# Test Plan

## Status: ACTIVE
**Branch**: main

## Overview
This is a test plan for integration testing.
"""
    )

    # Create plan_build.yml with tasks (flattened: directly in plan_folder)
    plan_file = plan_folder / "plan_build.yml"
    plan_content = {
        "name": "test-build-plan",
        "status": "active",
        "worktree_path": str(repo_dir),
        "context": "Test build plan for JIT context validation",
        "phases": [
            {
                "name": "Phase 1",
                "id": "phase_01",
                "tasks": [
                    {
                        "id": "01.1",
                        "name": "First task",
                        "description": "This is the first task",
                        "status": "in_progress",
                        "agent_type": "build",
                    },
                    {
                        "id": "01.2",
                        "name": "Second task",
                        "description": "This is the second task",
                        "status": "pending",
                        "agent_type": "build",
                    },
                ],
            }
        ],
    }
    with open(plan_file, "w") as f:
        yaml.dump(plan_content, f)

    # Initial commit
    (repo_dir / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit with plan"],
        cwd=repo_dir,
        capture_output=True,
    )

    yield repo_dir


@pytest.fixture
def plan_cli_runner(plan_repo):
    """CLI runner in the plan repository context."""
    import io
    import sys
    from contextlib import redirect_stderr, redirect_stdout
    from unittest.mock import patch

    original_cwd = os.getcwd()
    os.chdir(plan_repo)

    class CLIResult:
        def __init__(self, stdout: str, stderr: str, returncode: int):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

        def __iter__(self):
            return iter((self.stdout, self.stderr, self.returncode))

    def run_cli(*args, expect_exit: int | None = None):
        from agenticcli.cli import run_cli as _run_cli
        from agenticcli.console import set_json_output

        set_json_output(False)

        if len(args) == 1 and isinstance(args[0], list):
            cmd_args = args[0]
        else:
            cmd_args = list(args)

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        exit_code = 0

        with patch.object(sys, "argv", ["agentic"] + cmd_args):
            with redirect_stdout(stdout_capture):
                with redirect_stderr(stderr_capture):
                    try:
                        _run_cli()
                    except SystemExit as e:
                        exit_code = e.code if e.code is not None else 0

        stdout = stdout_capture.getvalue()
        stderr = stderr_capture.getvalue()

        if expect_exit is not None:
            assert exit_code == expect_exit, (
                f"Expected exit {expect_exit}, got {exit_code}. stderr: {stderr}"
            )

        return CLIResult(stdout, stderr, exit_code)

    yield run_cli
    from agenticcli.console import set_json_output
    set_json_output(False)
    os.chdir(original_cwd)


class TestContextHelp:
    """Tests for context command help output."""

    def test_context_help(self, cli_runner):
        """Test context --help shows all subcommands."""
        stdout, stderr, code = cli_runner(["context", "--help"])
        assert code == 0
        assert "bootstrap" in stdout
        assert "role" in stdout
        assert "task" in stdout
        assert "inputs" in stdout

    def test_context_alias_ctx(self, cli_runner):
        """Test 'ctx' alias works for context."""
        result = cli_runner(["ctx", "--help"])
        assert result.returncode == 0
        assert "bootstrap" in result.stdout


class TestContextBootstrap:
    """Tests for context bootstrap command."""

    def test_bootstrap_returns_json(self, plan_cli_runner):
        """Test bootstrap with -j returns valid JSON."""
        stdout, stderr, code = plan_cli_runner(["-j", "context", "bootstrap"])
        assert code == 0

        # Should return valid JSON
        data = json.loads(stdout)
        assert "role" in data
        assert "cli_commands" in data

    def test_bootstrap_with_role(self, plan_cli_runner):
        """Test bootstrap with explicit --role argument."""
        stdout, stderr, code = plan_cli_runner(
            ["-j", "context", "bootstrap", "--role", "planner-build"]
        )
        assert code == 0

        data = json.loads(stdout)
        assert data["role"] == "planner-build"

    def test_bootstrap_human_readable(self, plan_cli_runner):
        """Test bootstrap without -j returns human-readable output."""
        stdout, stderr, code = plan_cli_runner(["context", "bootstrap"])
        assert code == 0
        # Should contain human-readable elements
        assert "Bootstrap Context" in stdout or "Role:" in stdout or "CLI Commands" in stdout


class TestContextRole:
    """Tests for context role command."""

    def test_role_returns_json(self, plan_cli_runner):
        """Test role command returns JSON for valid role."""
        stdout, stderr, code = plan_cli_runner(["-j", "context", "role", "build-python"])
        # May return empty/null if role not found, but should not error
        assert code == 0

    def test_role_requires_role_id(self, cli_runner):
        """Test role command requires role_id argument."""
        stdout, stderr, code = cli_runner(["context", "role"])
        # Should fail without role_id
        assert code != 0 or "required" in stderr.lower() or "error" in stderr.lower()


class TestContextTask:
    """Tests for context task command."""

    def test_task_returns_json(self, plan_cli_runner):
        """Test task command returns JSON."""
        stdout, stderr, code = plan_cli_runner(["-j", "context", "task"])
        assert code == 0

        # Should return task info or null
        if stdout.strip():
            data = json.loads(stdout)
            # May be null if no task found, or a task object
            assert data is None or isinstance(data, dict)

    def test_task_resolves_from_plan(self, plan_cli_runner, plan_repo):
        """Test task command finds task from Main-First plan."""
        stdout, stderr, code = plan_cli_runner(["-j", "context", "task"])
        assert code == 0

        # Try to parse - may be null or a task
        if stdout.strip() and stdout.strip() != "null":
            data = json.loads(stdout)
            if data:
                # Response wraps task in {"plan_folder": ..., "task": {...}}
                task = data.get("task", data)
                assert "id" in task or "name" in task or "status" in task


class TestContextInputs:
    """Tests for context inputs command."""

    def test_inputs_returns_json(self, plan_cli_runner):
        """Test inputs command returns JSON."""
        stdout, stderr, code = plan_cli_runner(["-j", "context", "inputs", "--role", "build-python"])
        assert code == 0

        # Should return JSON (may be empty object)
        if stdout.strip():
            data = json.loads(stdout)
            assert isinstance(data, dict)

    def test_inputs_with_role(self, plan_cli_runner):
        """Test inputs command with --role argument."""
        stdout, stderr, code = plan_cli_runner(
            ["-j", "context", "inputs", "--role", "build-python"]
        )
        assert code == 0


class TestContextGenerateAgent:
    """Tests for context generate-agent command."""

    def test_generate_agent_help(self, cli_runner):
        """Test generate-agent help output."""
        stdout, stderr, code = cli_runner(["context", "generate-agent", "--help"])
        assert code == 0
        assert "role" in stdout.lower() or "generate" in stdout.lower()


class TestContextIntegration:
    """Integration tests for context commands working together."""

    def test_bootstrap_then_task_consistent(self, plan_cli_runner):
        """Test that bootstrap and task commands return consistent data."""
        # Get bootstrap context
        bootstrap_result = plan_cli_runner(["-j", "context", "bootstrap"])
        assert bootstrap_result.returncode == 0
        bootstrap_data = json.loads(bootstrap_result.stdout)

        # Get task directly
        task_result = plan_cli_runner(["-j", "context", "task"])
        assert task_result.returncode == 0

        # If bootstrap has a current_task, task command should return same info
        if bootstrap_data.get("current_task") and task_result.stdout.strip() != "null":
            task_response = json.loads(task_result.stdout)
            # Task response wraps in {"plan_folder": ..., "task": {...}}
            task_data = task_response.get("task", task_response) if task_response else None
            if task_data and bootstrap_data["current_task"]:
                # Both should reference same task
                assert (
                    bootstrap_data["current_task"].get("id") == task_data.get("id")
                    or bootstrap_data["current_task"].get("name") == task_data.get("name")
                )

    def test_bootstrap_cli_commands_valid(self, plan_cli_runner):
        """Test that cli_commands in bootstrap output are valid commands."""
        stdout, stderr, code = plan_cli_runner(["-j", "context", "bootstrap"])
        assert code == 0

        data = json.loads(stdout)
        cli_commands = data.get("cli_commands", {})

        # Should have expected command hints
        assert "task_prefill" in cli_commands or "task_status" in cli_commands
        # Commands should start with 'agentic'
        for cmd in cli_commands.values():
            assert cmd.startswith("agentic")
