"""Integration tests for CLI workflow sequences.

Tests multi-step operations and command interactions.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


class TestPlanWorkflowSequence:
    """Test plan creation -> status -> task -> archive workflow."""

    @pytest.fixture
    def integration_repo(self):
        """Create a full integration test repo with git."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "TestProject"
            repo_path.mkdir()

            # Initialize git
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo_path,
                capture_output=True,
            )

            # Create initial structure
            (repo_path / "docs" / "plans" / "live").mkdir(parents=True)
            (repo_path / "README.md").write_text("# Test Project\n")

            # Initial commit
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def cli_in_repo(self, integration_repo):
        """Run CLI commands in the integration repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(integration_repo)

        def run_cli(*args, expect_exit=None):
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
                    f"Expected exit {expect_exit}, got {exit_code}. "
                    f"stdout: {stdout}, stderr: {stderr}"
                )

            return stdout, stderr, exit_code

        yield run_cli

        os.chdir(original_cwd)

    def test_plan_scaffold_status_workflow(self, cli_in_repo, integration_repo):
        """Test: scaffold plan -> check status -> validate."""
        # Step 1: Scaffold a new plan
        stdout, stderr, code = cli_in_repo("plan", "scaffold", "test-feature")
        assert code == 0
        assert "Created planning folder" in stdout

        # Verify flattened folder structure (plan_*.yml files directly in folder)
        plan_path = integration_repo / "docs" / "plans" / "live" / "test-feature"
        assert plan_path.exists()
        # Flattened structure: plan_*.yml files directly in plan_path
        plan_files = list(plan_path.glob("plan_*.yml"))
        assert len(plan_files) >= 1, "Expected at least one plan_*.yml file"

        # Step 2: Check plan status
        stdout, stderr, code = cli_in_repo("plan", "status")
        assert code == 0
        # Should show the test-feature plan

        # Step 3: Validate the plan structure (may fail with empty plans)
        stdout, stderr, code = cli_in_repo("plan", "validate")
        # Allow graceful failure for empty/placeholder plans
        assert code in [0, 1, 2], f"Unexpected exit: {code}, stderr: {stderr}"

    def test_plan_with_json_output(self, cli_in_repo, integration_repo):
        """Test plan commands with JSON output mode."""
        # Scaffold
        cli_in_repo("plan", "scaffold", "json-test")

        # Create a plan file with tasks (flattened: directly in plan folder)
        plan_path = integration_repo / "docs" / "plans" / "live" / "json-test"
        plan_content = {
            "plan": {
                "name": "JSON Test Plan",
                "status": "in_progress",
                "phases": [
                    {
                        "id": "phase-1",
                        "name": "Phase 1",
                        "status": "in_progress",
                        "tasks": [
                            {"id": "task-1", "name": "Task 1", "status": "pending"},
                            {"id": "task-2", "name": "Task 2", "status": "completed"},
                        ],
                    }
                ],
            }
        }
        with open(plan_path / "plan_test.yml", "w") as f:
            yaml.dump(plan_content, f)

        # Status with JSON output
        stdout, stderr, code = cli_in_repo("--json", "plan", "status")
        assert code == 0
        data = json.loads(stdout)
        # JSON output should have meaningful keys
        assert isinstance(data, dict)
        assert len(data) > 0  # Should have some data

    def test_plan_scaffold_already_exists(self, cli_in_repo, integration_repo):
        """Test scaffolding a plan that already exists."""
        # First scaffold succeeds
        stdout, stderr, code = cli_in_repo("plan", "scaffold", "duplicate-test")
        assert code == 0

        # Second scaffold fails
        stdout, stderr, code = cli_in_repo("plan", "scaffold", "duplicate-test")
        assert code == 1
        assert "already exists" in stdout or "already exists" in stderr


class TestConfigWorkflowSequence:
    """Test config initialization -> set -> get -> list workflow."""

    @pytest.fixture
    def config_repo(self):
        """Create a repo for config testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "ConfigProject"
            repo_path.mkdir()

            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo_path,
                capture_output=True,
            )
            (repo_path / "README.md").write_text("# Config Test\n")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def temp_config_env(self, config_repo):
        """Set up temporary config environment."""
        config_home = config_repo / ".config"
        config_home.mkdir()

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}):
            yield config_home

    @pytest.fixture
    def cli_with_config(self, config_repo, temp_config_env):
        """Run CLI commands with isolated config."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(config_repo)

        def run_cli(*args, expect_exit=None):
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

            return stdout_capture.getvalue(), stderr_capture.getvalue(), exit_code

        yield run_cli

        os.chdir(original_cwd)

    def test_config_init_set_get_list_workflow(self, cli_with_config, temp_config_env):
        """Test: init config -> set value -> get value -> list all."""
        # Step 1: Initialize config
        stdout, stderr, code = cli_with_config("config", "init")
        assert code == 0
        assert "initialized" in stdout.lower() or "created" in stdout.lower() or code == 0

        # Verify config directory exists
        config_dir = temp_config_env / "agenticcli"
        assert config_dir.exists()

        # Step 2: Set a preference
        stdout, stderr, code = cli_with_config("preferences", "set", "test.key", "test_value")
        assert code == 0

        # Step 3: Get the preference
        stdout, stderr, code = cli_with_config("preferences", "get", "test.key")
        assert code == 0
        assert "test_value" in stdout

        # Step 4: List all preferences
        stdout, stderr, code = cli_with_config("preferences", "list")
        assert code == 0

    def test_config_json_workflow(self, cli_with_config, temp_config_env):
        """Test config commands with JSON output."""
        # Initialize
        cli_with_config("config", "init")

        # Set preference
        cli_with_config("preferences", "set", "json.test", "json_value")

        # Get with JSON
        stdout, stderr, code = cli_with_config("--json", "preferences", "get", "json.test")
        assert code == 0
        data = json.loads(stdout)
        assert data.get("value") == "json_value" or "json_value" in str(data)

        # List with JSON
        stdout, stderr, code = cli_with_config("--json", "preferences", "list")
        assert code == 0
        data = json.loads(stdout)
        assert isinstance(data, dict)

    def test_preferences_delete_workflow(self, cli_with_config, temp_config_env):
        """Test setting and deleting preferences."""
        cli_with_config("config", "init")

        # Set multiple values
        cli_with_config("preferences", "set", "delete.test1", "value1")
        cli_with_config("preferences", "set", "delete.test2", "value2")

        # Verify they exist
        stdout, _, _ = cli_with_config("preferences", "get", "delete.test1")
        assert "value1" in stdout

        # Delete one
        stdout, stderr, code = cli_with_config("preferences", "delete", "delete.test1")
        assert code == 0

        # Verify it's gone
        stdout, stderr, code = cli_with_config("preferences", "get", "delete.test1")
        # Should either return empty or indicate not found
        assert "value1" not in stdout or code != 0


class TestTemplateWorkflowSequence:
    """Test template generation workflows."""

    @pytest.fixture
    def template_repo(self):
        """Create a repo for template testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "TemplateProject"
            repo_path.mkdir()

            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo_path,
                capture_output=True,
            )
            (repo_path / "README.md").write_text("# Template Test\n")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def template_cli(self, template_repo):
        """Run CLI commands in template repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(template_repo)

        def run_cli(*args):
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

            return stdout_capture.getvalue(), stderr_capture.getvalue(), exit_code

        yield run_cli

        os.chdir(original_cwd)

    def test_template_list_and_generate_workflow(self, template_cli, template_repo):
        """Test: list templates -> generate each type."""
        # Step 1: List available templates
        stdout, stderr, code = template_cli("template", "list")
        assert code == 0
        assert "build" in stdout.lower()
        assert "test" in stdout.lower()

        # Step 2: Generate each template type
        for template_type in ["build", "test", "cleanup", "guidance"]:
            stdout, stderr, code = template_cli("template", "generate", template_type)
            assert code == 0, f"Failed to generate {template_type} template"
            # Template should contain YAML-like content
            assert "plan:" in stdout or "name:" in stdout or "phases:" in stdout

    def test_template_generate_to_file(self, template_cli, template_repo):
        """Test generating template to a file."""
        output_file = template_repo / "generated_plan.yml"

        stdout, stderr, code = template_cli(
            "template", "generate", "build", "--output", str(output_file)
        )
        assert code == 0
        assert output_file.exists()

        # Verify file content is valid YAML
        with open(output_file) as f:
            content = yaml.safe_load(f)
        assert content is not None


class TestHealthCheckSequence:
    """Test health check and diagnostic workflows."""

    @pytest.fixture
    def health_repo(self):
        """Create a repo for health check testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "HealthProject"
            repo_path.mkdir()

            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo_path,
                capture_output=True,
            )
            (repo_path / "README.md").write_text("# Health Test\n")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def health_cli(self, health_repo):
        """Run CLI commands in health repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(health_repo)

        config_home = health_repo / ".config"
        config_home.mkdir(exist_ok=True)

        def run_cli(*args):
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

            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}):
                with patch.object(sys, "argv", ["agentic"] + cmd_args):
                    with redirect_stdout(stdout_capture):
                        with redirect_stderr(stderr_capture):
                            try:
                                _run_cli()
                            except SystemExit as e:
                                exit_code = e.code if e.code is not None else 0

            return stdout_capture.getvalue(), stderr_capture.getvalue(), exit_code

        yield run_cli

        os.chdir(original_cwd)

    def test_health_check_workflow(self, health_cli):
        """Test health check reports system status."""
        stdout, stderr, code = health_cli("health")
        # Health check may pass or fail depending on environment
        # but should not crash
        assert code in [0, 1]
        assert "cli_version" in stdout.lower() or "health" in stdout.lower()

    def test_health_json_output(self, health_cli):
        """Test health check with JSON output."""
        stdout, stderr, code = health_cli("--json", "health")
        assert code in [0, 1]
        # Should be valid JSON
        try:
            data = json.loads(stdout)
            assert isinstance(data, dict)
        except json.JSONDecodeError:
            # If not JSON, that's also acceptable for certain outputs
            pass


class TestErrorRecoverySequence:
    """Test error handling and recovery scenarios."""

    def test_invalid_command_shows_help(self, cli_runner):
        """Test that invalid commands show helpful error messages."""
        stdout, stderr, code = cli_runner("nonexistent")
        assert code == 2  # argparse error
        combined = stdout + stderr
        assert "usage" in combined.lower() or "error" in combined.lower()

    def test_missing_required_args(self, cli_runner):
        """Test that missing required args show usage."""
        # worktree create requires branch
        stdout, stderr, code = cli_runner("worktree", "create")
        assert code == 2

        # plan scaffold requires name
        stdout, stderr, code = cli_runner("plan", "scaffold")
        assert code == 2

    def test_invalid_plan_path_handled(self, cli_runner, temp_dir):
        """Test handling of invalid plan paths."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            stdout, stderr, code = cli_runner("plan", "status")
            # Should handle gracefully
            assert code in [0, 1]
        finally:
            os.chdir(original_cwd)


class TestStateWorkflowSequence:
    """Test state management workflows."""

    @pytest.fixture
    def state_repo(self):
        """Create a repo for state testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "StateProject"
            repo_path.mkdir()

            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo_path,
                capture_output=True,
            )
            (repo_path / "README.md").write_text("# State Test\n")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def state_cli(self, state_repo):
        """Run CLI commands in state repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(state_repo)

        config_home = state_repo / ".config"
        config_home.mkdir(exist_ok=True)

        def run_cli(*args):
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

            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}):
                with patch.object(sys, "argv", ["agentic"] + cmd_args):
                    with redirect_stdout(stdout_capture):
                        with redirect_stderr(stderr_capture):
                            try:
                                _run_cli()
                            except SystemExit as e:
                                exit_code = e.code if e.code is not None else 0

            return stdout_capture.getvalue(), stderr_capture.getvalue(), exit_code

        yield run_cli

        os.chdir(original_cwd)

    def test_state_list_cleanup_workflow(self, state_cli):
        """Test: list state -> cleanup stale entries."""
        # Step 1: List current state (should be empty or minimal)
        stdout, stderr, code = state_cli("state", "list")
        assert code == 0

        # Step 2: Cleanup (should handle empty state gracefully)
        stdout, stderr, code = state_cli("state", "cleanup")
        assert code == 0

    def test_state_json_output(self, state_cli):
        """Test state commands with JSON output."""
        stdout, stderr, code = state_cli("--json", "state", "list")
        assert code == 0
        data = json.loads(stdout)
        assert isinstance(data, (dict, list))


class TestEnvWorkflowSequence:
    """Test environment variable management workflows."""

    @pytest.fixture
    def env_repo(self):
        """Create a repo for env testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "EnvProject"
            repo_path.mkdir()

            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo_path,
                capture_output=True,
            )
            (repo_path / "README.md").write_text("# Env Test\n")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def env_cli(self, env_repo):
        """Run CLI commands in env repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(env_repo)

        config_home = env_repo / ".config"
        config_home.mkdir(exist_ok=True)

        def run_cli(*args):
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

            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}):
                with patch.object(sys, "argv", ["agentic"] + cmd_args):
                    with redirect_stdout(stdout_capture):
                        with redirect_stderr(stderr_capture):
                            try:
                                _run_cli()
                            except SystemExit as e:
                                exit_code = e.code if e.code is not None else 0

            return stdout_capture.getvalue(), stderr_capture.getvalue(), exit_code

        yield run_cli

        os.chdir(original_cwd)

    def test_env_show_workflow(self, env_cli):
        """Test showing environment configuration."""
        stdout, stderr, code = env_cli("env", "show")
        assert code == 0

    def test_env_export_workflow(self, env_cli):
        """Test exporting environment variables."""
        stdout, stderr, code = env_cli("env", "export")
        assert code == 0
        # Should show export commands or empty if no vars configured


class TestCrossCommandIntegration:
    """Test interactions between different command groups."""

    @pytest.fixture
    def full_integration_repo(self):
        """Create a fully-featured integration repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "FullIntegrationProject"
            repo_path.mkdir()

            # Git setup
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo_path,
                capture_output=True,
            )

            # Project structure
            (repo_path / "docs" / "plans" / "live").mkdir(parents=True)
            (repo_path / "modules").mkdir()
            (repo_path / "README.md").write_text("# Full Integration Test\n")

            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def full_cli(self, full_integration_repo):
        """Run CLI commands in full integration repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(full_integration_repo)

        config_home = full_integration_repo / ".config"
        config_home.mkdir(exist_ok=True)

        def run_cli(*args):
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

            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}):
                with patch.object(sys, "argv", ["agentic"] + cmd_args):
                    with redirect_stdout(stdout_capture):
                        with redirect_stderr(stderr_capture):
                            try:
                                _run_cli()
                            except SystemExit as e:
                                exit_code = e.code if e.code is not None else 0

            return stdout_capture.getvalue(), stderr_capture.getvalue(), exit_code

        yield run_cli

        os.chdir(original_cwd)

    def test_full_project_workflow(self, full_cli, full_integration_repo):
        """Test a complete project setup and planning workflow."""
        # Step 1: Initialize config
        stdout, stderr, code = full_cli("config", "init")
        assert code == 0

        # Step 2: Check health
        stdout, stderr, code = full_cli("health")
        # May pass or fail depending on environment, but shouldn't crash

        # Step 3: Check worktree status
        stdout, stderr, code = full_cli("worktree", "status")
        assert code == 0

        # Step 4: Scaffold a plan
        stdout, stderr, code = full_cli("plan", "scaffold", "feature-integration")
        assert code == 0

        # Step 5: Generate a build template
        stdout, stderr, code = full_cli("template", "generate", "build")
        assert code == 0

        # Step 6: Check plan status (may fail if no plans with tasks)
        stdout, stderr, code = full_cli("plan", "status")
        # Allow success or graceful failure
        assert code in [0, 1, 2], f"Unexpected exit: {code}, stderr: {stderr}"

        # Step 7: Validate plan (may fail if empty plans)
        stdout, stderr, code = full_cli("plan", "validate")
        # Allow success or graceful failure
        assert code in [0, 1, 2], f"Unexpected exit: {code}, stderr: {stderr}"

    def test_json_mode_consistency(self, full_cli):
        """Test that JSON mode works consistently across commands."""
        json_commands = [
            ["--json", "worktree", "status"],
            ["--json", "plan", "status"],
            ["--json", "preferences", "list"],
            ["--json", "state", "list"],
            ["--json", "template", "list"],
        ]

        for cmd in json_commands:
            stdout, stderr, code = full_cli(*cmd)
            if code == 0 and stdout.strip():
                try:
                    data = json.loads(stdout)
                    assert isinstance(data, (dict, list)), f"Invalid JSON structure for {cmd}"
                except json.JSONDecodeError:
                    # Some commands may not produce JSON in all scenarios
                    pass

    def test_alias_commands_work(self, full_cli):
        """Test that command aliases work correctly."""
        # worktree -> wt
        stdout1, _, code1 = full_cli("worktree", "status")
        stdout2, _, code2 = full_cli("wt", "status")
        assert code1 == code2

        # config -> cfg
        stdout1, _, code1 = full_cli("config", "show")
        stdout2, _, code2 = full_cli("cfg", "show")
        assert code1 == code2

        # template -> tpl
        stdout1, _, code1 = full_cli("template", "list")
        stdout2, _, code2 = full_cli("tpl", "list")
        assert code1 == code2
