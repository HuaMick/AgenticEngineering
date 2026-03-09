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

    # Create docs/epics/live structure with an epic folder (flattened structure)
    epic_folder = repo_dir / "docs" / "epics" / "live" / "260123CL_test_plan"
    epic_folder.mkdir(parents=True)

    # Create README.md
    readme = epic_folder / "README.md"
    readme.write_text(
        """# Test Plan

## Status: ACTIVE
**Branch**: main

## Overview
This is a test plan for integration testing.
"""
    )

    # Populate TinyDB - MainFirstEpicResolver uses git rev-parse to find repo root
    # which returns repo_dir, so DB is at repo_dir/.agentic/epics.db
    from agenticguidance.services.epic_repository import EpicRepository

    db_path = repo_dir / ".agentic" / "epics.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    epic_folder_name = "260123CL_test_plan"
    db_repo.create_epic({
        "epic_folder_name": epic_folder_name,
        "epic_folder": str(epic_folder),
        "name": "test-build-plan",
        "status": "active",
        "context": "Test build plan for JIT context validation",
    })
    db_repo.add_phase(epic_folder_name, {"name": "Phase 1"})
    db_repo.add_ticket(epic_folder_name, "Phase 1", {
        "task_id": "01.1",
        "name": "First task",
        "description": "This is the first task",
        "status": "in_progress",
    })
    db_repo.add_ticket(epic_folder_name, "Phase 1", {
        "task_id": "01.2",
        "name": "Second task",
        "description": "This is the second task",
        "status": "pending",
    })
    db_repo.close()

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
        stdout, stderr, code = cli_runner(["agent", "context", "--help"])
        assert code == 0
        assert "bootstrap" in stdout
        assert "role" in stdout
        assert "task" in stdout
        assert "inputs" in stdout

    def test_context_alias_ctx(self, cli_runner):
        """Test 'ctx' alias is deprecated and points to 'agent context'."""
        result = cli_runner(["ctx", "--help"])
        # ctx is now a deprecated alias - shows deprecation message
        assert "moved" in result.stderr or "agent context" in result.stderr or "Deprecated" in result.stdout


class TestContextBootstrap:
    """Tests for context bootstrap command."""

    def test_bootstrap_returns_json(self, plan_cli_runner):
        """Test bootstrap with -j returns valid JSON."""
        stdout, stderr, code = plan_cli_runner(["-j", "agent", "context", "bootstrap"])
        assert code == 0

        # Should return valid JSON
        data = json.loads(stdout)
        assert "role" in data
        assert "cli_commands" in data

    def test_bootstrap_with_role(self, plan_cli_runner):
        """Test bootstrap with explicit --role argument."""
        stdout, stderr, code = plan_cli_runner(
            ["-j", "agent", "context", "bootstrap", "--role", "planner-build"]
        )
        assert code == 0

        data = json.loads(stdout)
        assert data["role"] == "planner-build"

    def test_bootstrap_human_readable(self, plan_cli_runner):
        """Test bootstrap without -j returns human-readable output."""
        stdout, stderr, code = plan_cli_runner(["agent", "context", "bootstrap"])
        assert code == 0
        # Should contain human-readable elements
        assert "Bootstrap Context" in stdout or "Role:" in stdout or "CLI Commands" in stdout

    def test_bootstrap_output_structure_complete(self, plan_cli_runner):
        """Test bootstrap output contains all 7 required fields with correct types."""
        stdout, stderr, code = plan_cli_runner(["-j", "agent", "context", "bootstrap"])
        assert code == 0

        data = json.loads(stdout)
        # All 7 fields must be present
        assert "role" in data, "Must include 'role'"
        assert "objective" in data, "Must include 'objective'"
        assert "epic_folder" in data, "Must include 'epic_folder'"
        assert "epic_path" in data, "Must include 'epic_path'"
        assert "current_task" in data, "Must include 'current_task'"
        assert "process" in data, "Must include 'process'"
        assert "essential_inputs" in data, "Must include 'essential_inputs'"
        assert "cli_commands" in data, "Must include 'cli_commands'"

        # Type checks
        assert isinstance(data["role"], str)
        assert data["epic_folder"] == "260123CL_test_plan"
        assert isinstance(data["epic_path"], str)
        assert isinstance(data["essential_inputs"], list)
        assert isinstance(data["cli_commands"], dict)

        # CLI commands should all start with 'agentic'
        for cmd_name, cmd_val in data["cli_commands"].items():
            assert cmd_val.startswith("agentic"), f"CLI command '{cmd_name}' should start with 'agentic'"

    def test_bootstrap_no_active_plan(self, cli_runner):
        """Test bootstrap works when no active plan exists (defaults to 'build' role)."""
        stdout, stderr, code = cli_runner(["-j", "agent", "context", "bootstrap"])
        assert code == 0

        data = json.loads(stdout)
        assert data["role"] == "build", "Should default to 'build' role"
        assert data["current_task"] is None, "No task when no plan"
        assert data["epic_folder"] is None, "No epic_folder when no plan"
        assert isinstance(data["cli_commands"], dict)

    def test_bootstrap_with_role_override(self, plan_cli_runner):
        """Test bootstrap with --role overrides any inferred role."""
        stdout, stderr, code = plan_cli_runner(
            ["-j", "agent", "context", "bootstrap", "--role", "custom-role"]
        )
        assert code == 0

        data = json.loads(stdout)
        assert data["role"] == "custom-role", "Explicit --role should override inferred role"


class TestContextRole:
    """Tests for context role command."""

    def test_role_returns_json(self, plan_cli_runner):
        """Test role command returns valid JSON with role process data."""
        mock_process = {
            "name": "build-python",
            "description": "Build Python projects",
            "steps": ["analyze", "implement", "test"],
        }
        with patch(
            "agenticguidance.services.get_role_process",
            return_value=mock_process,
        ):
            stdout, stderr, code = plan_cli_runner(
                ["-j", "agent", "context", "role", "build-python"]
            )

        assert code == 0
        data = json.loads(stdout)
        assert data["name"] == "build-python"
        assert data["description"] == "Build Python projects"
        assert isinstance(data["steps"], list)
        assert len(data["steps"]) == 3

    def test_role_not_found_error(self, plan_cli_runner):
        """Test role command fails with error when role not found."""
        with patch(
            "agenticguidance.services.get_role_process",
            return_value=None,
        ):
            stdout, stderr, code = plan_cli_runner(
                ["-j", "agent", "context", "role", "nonexistent-role"]
            )

        assert code == 1
        assert "not found" in stderr.lower() or "role" in stderr.lower()

    def test_role_requires_role_id(self, cli_runner):
        """Test role command requires role_id argument."""
        stdout, stderr, code = cli_runner(["agent", "context", "role"])
        # Should fail without role_id
        assert code != 0 or "required" in stderr.lower() or "error" in stderr.lower()


class TestContextTask:
    """Tests for context task command."""

    def test_task_returns_json(self, plan_cli_runner):
        """Test task command returns valid JSON with epic_folder and task fields."""
        stdout, stderr, code = plan_cli_runner(["-j", "agent", "context", "task"])
        assert code == 0
        assert stdout.strip(), "Task output must not be empty"

        data = json.loads(stdout)
        assert isinstance(data, dict), "Response must be a dict"
        assert "epic_folder" in data, "Response must include 'epic_folder'"
        assert "task" in data, "Response must include 'task'"

        task = data["task"]
        if task is not None:
            assert "id" in task, "Task must have 'id'"
            assert "name" in task, "Task must have 'name'"
            assert "status" in task, "Task must have 'status'"

    def test_task_resolves_from_plan(self, plan_cli_runner, plan_repo):
        """Test task command finds the in_progress task from Main-First plan."""
        stdout, stderr, code = plan_cli_runner(["-j", "agent", "context", "task"])
        assert code == 0
        assert stdout.strip(), "Task output must not be empty"

        data = json.loads(stdout)
        assert isinstance(data, dict)
        assert data.get("epic_folder") == "260123CL_test_plan"

        task = data.get("task")
        assert task is not None, "Expected a task from the plan_repo fixture"
        # plan_repo creates task 01.1 (in_progress) and 01.2 (pending)
        # extract_current_ticket should return the in_progress one
        assert "id" in task, "Task must have 'id'"
        assert "name" in task, "Task must have 'name'"
        assert "status" in task, "Task must have 'status'"
        assert task["id"] == "01.1", "Should return the in_progress task (01.1)"
        assert task["status"] == "in_progress"

    def test_task_with_all_flag(self, plan_cli_runner, plan_repo):
        """Test task --all returns all tasks from the plan."""
        stdout, stderr, code = plan_cli_runner(
            ["-j", "agent", "context", "task", "--all"]
        )
        assert code == 0
        assert stdout.strip(), "Output must not be empty"

        data = json.loads(stdout)
        assert isinstance(data, dict)
        assert "task_count" in data, "Response must include 'task_count'"
        assert "tasks" in data, "Response must include 'tasks'"
        assert data["task_count"] == 2, "plan_repo has 2 tasks"

        tasks = data["tasks"]
        assert len(tasks) == 2
        task_ids = [t["id"] for t in tasks]
        assert "01.1" in task_ids, "Should include task 01.1"
        assert "01.2" in task_ids, "Should include task 01.2"

        # Validate structure of each task
        for task in tasks:
            assert "id" in task, "Each task must have 'id'"
            assert "name" in task, "Each task must have 'name'"
            assert "status" in task, "Each task must have 'status'"

    def test_task_no_active_epic(self, cli_runner):
        """Test task command with no active epic returns error JSON."""
        stdout, stderr, code = cli_runner(
            ["-j", "agent", "context", "task"]
        )
        # Source uses sys.exit(0) for no-epic case
        assert code == 0

        if stdout.strip():
            data = json.loads(stdout)
            assert "error" in data, "No-epic response must include 'error' key"
            assert "no active epic" in data["error"].lower()


class TestContextInputs:
    """Tests for context inputs command.

    Covers:
    - Manifest structure validation
    - --role filtering
    - Path resolution to absolute
    - Missing file detection
    - --resolve layer expansion
    - Error handling for missing --role
    """

    def test_inputs_returns_json(self, plan_cli_runner):
        """Test inputs command returns valid JSON with role and inputs fields."""
        mock_manifest = {
            "role": "build-python",
            "inputs": [
                {
                    "path": "/project/src/main.py",
                    "relative_path": "src/main.py",
                    "description": "Main entry",
                    "exists": True,
                }
            ],
            "missing": [],
            "layers": [],
        }
        with patch(
            "agenticguidance.services.get_role_inputs_manifest",
            return_value=mock_manifest,
        ):
            stdout, stderr, code = plan_cli_runner(
                ["-j", "agent", "context", "inputs", "--role", "build-python"]
            )

        assert code == 0
        assert stdout.strip(), "Output must not be empty"
        data = json.loads(stdout)
        assert isinstance(data, dict)
        assert data["role"] == "build-python"
        assert "inputs" in data
        assert len(data["inputs"]) == 1

    def test_context_inputs_returns_manifest(self, plan_cli_runner):
        """Verify manifest structure has role, inputs, missing, and layers fields."""
        # Mock get_role_inputs_manifest to return a known manifest
        mock_manifest = {
            "role": "test-agent",
            "inputs": [
                {
                    "path": "/abs/path/to/file.py",
                    "relative_path": "src/file.py",
                    "description": "Main source file",
                    "exists": True,
                },
                {
                    "path": "/abs/path/to/missing.py",
                    "relative_path": "src/missing.py",
                    "description": "Missing file",
                    "exists": False,
                },
            ],
            "missing": ["src/missing.py"],
            "layers": [
                {"type": "layer", "path": "assets/inputs/core.yml", "required": True}
            ],
        }
        with patch(
            "agenticguidance.services.get_role_inputs_manifest",
            return_value=mock_manifest,
        ):
            stdout, stderr, code = plan_cli_runner(
                ["-j", "agent", "context", "inputs", "--role", "test-agent"]
            )

        assert code == 0
        data = json.loads(stdout)

        # Verify top-level manifest structure
        assert "role" in data, "Manifest must include 'role' field"
        assert "inputs" in data, "Manifest must include 'inputs' list"
        assert "missing" in data, "Manifest must include 'missing' list"
        assert "layers" in data, "Manifest must include 'layers' list"

        # Verify types
        assert isinstance(data["inputs"], list)
        assert isinstance(data["missing"], list)
        assert isinstance(data["layers"], list)

        # Verify input item structure
        assert len(data["inputs"]) == 2
        first_input = data["inputs"][0]
        assert "path" in first_input, "Each input must have 'path'"
        assert "exists" in first_input, "Each input must have 'exists'"
        assert "description" in first_input, "Each input must have 'description'"

    def test_context_inputs_role_filter(self, plan_cli_runner):
        """Verify --role filters inputs to only the specified role."""
        # Set up two different manifests for two different roles
        manifests = {
            "role-alpha": {
                "role": "role-alpha",
                "inputs": [{"path": "/alpha.py", "relative_path": "alpha.py", "description": "Alpha file", "exists": True}],
                "missing": [],
                "layers": [],
            },
            "role-beta": {
                "role": "role-beta",
                "inputs": [{"path": "/beta.py", "relative_path": "beta.py", "description": "Beta file", "exists": True}],
                "missing": [],
                "layers": [],
            },
        }

        def mock_get_manifest(role_id, resolve_layers=False):
            return manifests.get(role_id)

        with patch(
            "agenticguidance.services.get_role_inputs_manifest",
            side_effect=mock_get_manifest,
        ):
            # Request role-alpha
            stdout_a, _, code_a = plan_cli_runner(
                ["-j", "agent", "context", "inputs", "--role", "role-alpha"]
            )
            assert code_a == 0
            data_a = json.loads(stdout_a)
            assert data_a["role"] == "role-alpha"
            assert any("alpha" in inp["path"] for inp in data_a["inputs"])
            assert not any("beta" in inp["path"] for inp in data_a["inputs"])

            # Request role-beta
            stdout_b, _, code_b = plan_cli_runner(
                ["-j", "agent", "context", "inputs", "--role", "role-beta"]
            )
            assert code_b == 0
            data_b = json.loads(stdout_b)
            assert data_b["role"] == "role-beta"
            assert any("beta" in inp["path"] for inp in data_b["inputs"])
            assert not any("alpha" in inp["path"] for inp in data_b["inputs"])

    def test_context_inputs_resolves_paths(self, plan_cli_runner):
        """Verify all input paths are resolved to absolute paths."""
        mock_manifest = {
            "role": "path-test",
            "inputs": [
                {
                    "path": "/home/project/src/module.py",
                    "relative_path": "src/module.py",
                    "description": "Module file",
                    "exists": True,
                },
                {
                    "path": "/home/project/tests/test_module.py",
                    "relative_path": "tests/test_module.py",
                    "description": "Test file",
                    "exists": False,
                },
            ],
            "missing": ["tests/test_module.py"],
            "layers": [],
        }
        with patch(
            "agenticguidance.services.get_role_inputs_manifest",
            return_value=mock_manifest,
        ):
            stdout, _, code = plan_cli_runner(
                ["-j", "agent", "context", "inputs", "--role", "path-test"]
            )

        assert code == 0
        data = json.loads(stdout)

        # Every input path must be absolute
        for inp in data["inputs"]:
            assert inp["path"].startswith("/"), (
                f"Input path must be absolute, got: {inp['path']}"
            )

    def test_context_inputs_validates_existence(self, plan_cli_runner):
        """Verify missing files are flagged in the manifest."""
        mock_manifest = {
            "role": "existence-check",
            "inputs": [
                {
                    "path": "/real/existing/file.py",
                    "relative_path": "existing/file.py",
                    "description": "File that exists",
                    "exists": True,
                },
                {
                    "path": "/missing/nonexistent.py",
                    "relative_path": "missing/nonexistent.py",
                    "description": "File that does not exist",
                    "exists": False,
                },
                {
                    "path": "/another/gone.yml",
                    "relative_path": "another/gone.yml",
                    "description": "Another missing file",
                    "exists": False,
                },
            ],
            "missing": ["missing/nonexistent.py", "another/gone.yml"],
            "layers": [],
        }
        with patch(
            "agenticguidance.services.get_role_inputs_manifest",
            return_value=mock_manifest,
        ):
            stdout, _, code = plan_cli_runner(
                ["-j", "agent", "context", "inputs", "--role", "existence-check"]
            )

        assert code == 0
        data = json.loads(stdout)

        # Verify exists flags are correct
        existing = [inp for inp in data["inputs"] if inp["exists"]]
        missing = [inp for inp in data["inputs"] if not inp["exists"]]
        assert len(existing) == 1, "Should have exactly 1 existing file"
        assert len(missing) == 2, "Should have exactly 2 missing files"

        # Verify missing list contains the right relative paths
        assert len(data["missing"]) == 2
        assert "missing/nonexistent.py" in data["missing"]
        assert "another/gone.yml" in data["missing"]

    def test_context_inputs_resolve_layers(self, plan_cli_runner):
        """Verify --resolve flag causes layer expansion."""
        # Without --resolve, layers should be references
        unresolve_manifest = {
            "role": "layer-test",
            "inputs": [],
            "missing": [],
            "layers": [
                {"type": "layer", "path": "assets/inputs/core-system.yml", "required": True},
                {"type": "layer", "path": "assets/inputs/core-guidelines.yml", "required": True},
            ],
        }

        # With --resolve, layers should be expanded into inputs
        resolved_manifest = {
            "role": "layer-test",
            "inputs": [
                {
                    "path": "/project/assets/definitions/plans.yml",
                    "relative_path": "assets/definitions/plans.yml",
                    "description": "Plan definitions (from core-system layer)",
                    "exists": True,
                },
                {
                    "path": "/project/assets/guidelines/testing.yml",
                    "relative_path": "assets/guidelines/testing.yml",
                    "description": "Testing guidelines (from core-guidelines layer)",
                    "exists": True,
                },
            ],
            "missing": [],
            "layers": [],
        }

        call_count = {"n": 0}

        def mock_get_manifest(role_id, resolve_layers=False):
            call_count["n"] += 1
            if resolve_layers:
                return resolved_manifest
            return unresolve_manifest

        with patch(
            "agenticguidance.services.get_role_inputs_manifest",
            side_effect=mock_get_manifest,
        ):
            # Without --resolve: layers present, inputs empty
            stdout_no_resolve, _, code_nr = plan_cli_runner(
                ["-j", "agent", "context", "inputs", "--role", "layer-test"]
            )
            assert code_nr == 0
            data_nr = json.loads(stdout_no_resolve)
            assert len(data_nr["layers"]) == 2, "Without --resolve, layers should be listed"
            assert len(data_nr["inputs"]) == 0, "Without --resolve, inputs from layers should not appear"

            # With --resolve: layers expanded into inputs
            stdout_resolve, _, code_r = plan_cli_runner(
                ["-j", "agent", "context", "inputs", "--role", "layer-test", "--resolve"]
            )
            assert code_r == 0
            data_r = json.loads(stdout_resolve)
            assert len(data_r["inputs"]) == 2, "With --resolve, layer contents should appear as inputs"
            assert len(data_r["layers"]) == 0, "With --resolve, layers should be empty (expanded)"

    def test_context_inputs_requires_role(self, plan_cli_runner):
        """Test that inputs command fails gracefully without --role."""
        stdout, stderr, code = plan_cli_runner(
            ["-j", "agent", "context", "inputs"]
        )
        assert code == 1, "Should exit with error when --role is missing"
        assert "role" in stderr.lower() or "required" in stderr.lower(), (
            f"Error should mention --role requirement, got: {stderr}"
        )

    def test_context_inputs_unknown_role_returns_error(self, plan_cli_runner):
        """Test that inputs command fails for an unknown/nonexistent role."""
        with patch(
            "agenticguidance.services.get_role_inputs_manifest",
            return_value=None,
        ):
            stdout, stderr, code = plan_cli_runner(
                ["-j", "agent", "context", "inputs", "--role", "nonexistent-role-xyz"]
            )
        assert code == 1, "Should exit with error for unknown role"

    def test_context_inputs_human_readable_output(self, plan_cli_runner):
        """Test inputs command produces human-readable output without -j."""
        mock_manifest = {
            "role": "human-test",
            "inputs": [
                {
                    "path": "/project/src/main.py",
                    "relative_path": "src/main.py",
                    "description": "Main entry point",
                    "exists": True,
                },
                {
                    "path": "/project/src/missing.py",
                    "relative_path": "src/missing.py",
                    "description": "Missing module",
                    "exists": False,
                },
            ],
            "missing": ["src/missing.py"],
            "layers": [],
        }
        with patch(
            "agenticguidance.services.get_role_inputs_manifest",
            return_value=mock_manifest,
        ):
            stdout, _, code = plan_cli_runner(
                ["agent", "context", "inputs", "--role", "human-test"]
            )

        assert code == 0
        # Human-readable output should mention the role and show input info
        assert "human-test" in stdout or "Input" in stdout


class TestContextGenerateAgent:
    """Tests for context generate-agent command."""

    def test_generate_agent_help(self, cli_runner):
        """Test generate-agent help output shows role parameter and output option."""
        stdout, stderr, code = cli_runner(["agent", "context", "generate-agent", "--help"])
        assert code == 0
        combined = stdout.lower()
        assert "role" in combined, "Help should mention 'role' parameter"
        assert "generate" in combined or "agent" in combined, "Help should mention 'generate' or 'agent'"

    def test_generate_agent_success_stdout(self, plan_cli_runner):
        """Test generate-agent outputs generated content to stdout."""
        mock_content = "# Generated Agent\nRole: test-role\nagentic context bootstrap --role test-role"
        with patch(
            "agenticguidance.services.generate_agent_bootstrap",
            return_value=mock_content,
        ):
            stdout, stderr, code = plan_cli_runner(
                ["agent", "context", "generate-agent", "test-role"]
            )

        assert code == 0
        assert "# Generated Agent" in stdout
        assert "test-role" in stdout

    def test_generate_agent_role_not_found(self, plan_cli_runner):
        """Test generate-agent fails with error for unknown role."""
        with patch(
            "agenticguidance.services.generate_agent_bootstrap",
            return_value=None,
        ):
            stdout, stderr, code = plan_cli_runner(
                ["agent", "context", "generate-agent", "nonexistent-role"]
            )

        assert code == 1
        assert "could not generate" in stderr.lower() or "error" in stderr.lower()


class TestContextIntegration:
    """Integration tests for context commands working together."""

    def test_bootstrap_then_task_consistent(self, plan_cli_runner):
        """Test that bootstrap and task commands return consistent data."""
        # Get bootstrap context
        bootstrap_result = plan_cli_runner(["-j", "agent", "context", "bootstrap"])
        assert bootstrap_result.returncode == 0
        bootstrap_data = json.loads(bootstrap_result.stdout)

        # Get task directly
        task_result = plan_cli_runner(["-j", "agent", "context", "task"])
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
        stdout, stderr, code = plan_cli_runner(["-j", "agent", "context", "bootstrap"])
        assert code == 0

        data = json.loads(stdout)
        cli_commands = data.get("cli_commands", {})

        # Should have expected command hints
        assert "task_prefill" in cli_commands or "task_status" in cli_commands
        # Commands should start with 'agentic'
        for cmd in cli_commands.values():
            assert cmd.startswith("agentic")
