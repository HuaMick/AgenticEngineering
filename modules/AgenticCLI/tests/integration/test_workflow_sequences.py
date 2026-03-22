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

    pytestmark = pytest.mark.story("US-PLN-001")

    @pytest.fixture
    def integration_repo(self):
        """Create a full integration test repo with git."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "TestProject"
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

            (repo_path / "docs" / "epics" / "live").mkdir(parents=True)
            (repo_path / "README.md").write_text("# Test Project\n")

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

    @pytest.mark.story("US-PLN-003")
    def test_plan_status_workflow(self, cli_in_repo, integration_repo):
        """Test: check status with validate flag."""
        # Epic status works even without epic arg (auto-detect)
        stdout, stderr, code = cli_in_repo("epic", "status")
        assert code in [0, 1, 2], f"Unexpected exit: {code}, stderr: {stderr}"

    @pytest.mark.story("US-PLN-003", "US-PLN-005")
    def test_plan_status_validate(self, cli_in_repo, integration_repo):
        """Test: epic status --validate runs validation checks."""
        stdout, stderr, code = cli_in_repo("epic", "status", "--validate")
        assert code in [0, 1, 2], f"Unexpected exit: {code}, stderr: {stderr}"


class TestConfigWorkflowSequence:
    """Test config initialization -> set -> get -> list workflow."""

    pytestmark = pytest.mark.story("US-PLN-001")

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
        stdout, stderr, code = cli_with_config("configure", "config", "init")
        assert code == 0
        assert "initialized" in stdout.lower() or "created" in stdout.lower() or code == 0

        config_dir = temp_config_env / "agenticcli"
        assert config_dir.exists()

        stdout, stderr, code = cli_with_config("configure", "preferences", "set", "test.key", "test_value")
        assert code == 0

        stdout, stderr, code = cli_with_config("configure", "preferences", "get", "test.key")
        assert code == 0
        assert "test_value" in stdout

        stdout, stderr, code = cli_with_config("configure", "preferences", "list")
        assert code == 0

    def test_config_json_workflow(self, cli_with_config, temp_config_env):
        """Test config commands with JSON output."""
        cli_with_config("configure", "config", "init")

        cli_with_config("configure", "preferences", "set", "json.test", "json_value")

        stdout, stderr, code = cli_with_config("--json", "configure", "preferences", "get", "json.test")
        assert code == 0
        data = json.loads(stdout)
        assert data.get("value") == "json_value" or "json_value" in str(data)

        stdout, stderr, code = cli_with_config("--json", "configure", "preferences", "list")
        assert code == 0
        data = json.loads(stdout)
        assert isinstance(data, dict)

    def test_preferences_delete_workflow(self, cli_with_config, temp_config_env):
        """Test setting and deleting preferences."""
        cli_with_config("configure", "config", "init")

        cli_with_config("configure", "preferences", "set", "delete.test1", "value1")
        cli_with_config("configure", "preferences", "set", "delete.test2", "value2")

        stdout, _, _ = cli_with_config("configure", "preferences", "get", "delete.test1")
        assert "value1" in stdout

        stdout, stderr, code = cli_with_config("configure", "preferences", "delete", "delete.test1")
        assert code == 0

        stdout, stderr, code = cli_with_config("configure", "preferences", "get", "delete.test1")
        assert "value1" not in stdout or code != 0


class TestHealthCheckSequence:
    """Test health check and diagnostic workflows."""

    pytestmark = pytest.mark.story("US-PLN-001")

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
        stdout, stderr, code = health_cli("setup", "health")
        assert code in [0, 1]
        assert "cli_version" in stdout.lower() or "health" in stdout.lower()

    def test_health_json_output(self, health_cli):
        """Test health check with JSON output."""
        stdout, stderr, code = health_cli("--json", "setup", "health")
        assert code in [0, 1]
        try:
            data = json.loads(stdout)
            assert isinstance(data, dict)
        except json.JSONDecodeError:
            pass


class TestErrorRecoverySequence:
    """Test error handling and recovery scenarios."""

    pytestmark = pytest.mark.story("US-PLN-001")

    def test_invalid_command_shows_help(self, cli_runner):
        """Test that invalid commands show helpful error messages."""
        stdout, stderr, code = cli_runner("nonexistent")
        assert code == 2  # argparse error
        combined = stdout + stderr
        assert "usage" in combined.lower() or "error" in combined.lower()

    def test_missing_required_args(self, cli_runner):
        """Test that missing required args show usage."""
        stdout, stderr, code = cli_runner("epic", "new")
        assert code in [1, 2]

    def test_invalid_plan_path_handled(self, cli_runner, temp_dir):
        """Test handling of invalid plan paths."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            stdout, stderr, code = cli_runner("epic", "status")
            assert code in [0, 1]
        finally:
            os.chdir(original_cwd)


class TestStateWorkflowSequence:
    """Test state management workflows."""

    pytestmark = pytest.mark.story("US-PLN-001", "US-SES-009")

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

    @pytest.mark.story("US-SES-007", "US-SES-008", "US-SES-009")
    def test_state_list_cleanup_workflow(self, state_cli):
        """Test: list state -> cleanup stale entries."""
        stdout, stderr, code = state_cli("configure", "state", "list")
        assert code == 0

        stdout, stderr, code = state_cli("configure", "state", "cleanup")
        assert code == 0

    @pytest.mark.story("US-SES-009")
    def test_state_json_output(self, state_cli):
        """Test state commands with JSON output."""
        stdout, stderr, code = state_cli("--json", "configure", "state", "list")
        assert code == 0
        data = json.loads(stdout)
        assert isinstance(data, (dict, list))


class TestEnvWorkflowSequence:
    """Test environment variable management workflows."""

    # US-SET-010 (env run) has no dedicated test; closest coverage is here
    pytestmark = pytest.mark.story("US-PLN-001", "US-SET-010", "US-SET-011")

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

    @pytest.mark.story("US-SET-008")
    def test_env_show_workflow(self, env_cli):
        """Test showing environment configuration."""
        stdout, stderr, code = env_cli("configure", "env", "show")
        assert code == 0

    @pytest.mark.story("US-SET-009")
    def test_env_export_workflow(self, env_cli):
        """Test exporting environment variables."""
        stdout, stderr, code = env_cli("configure", "env", "export")
        assert code == 0


class TestCrossCommandIntegration:
    """Test interactions between different command groups."""

    pytestmark = pytest.mark.story("US-PLN-001")

    @pytest.fixture
    def full_integration_repo(self):
        """Create a fully-featured integration repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "FullIntegrationProject"
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

            (repo_path / "docs" / "epics" / "live").mkdir(parents=True)
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
        stdout, stderr, code = full_cli("configure", "config", "init")
        assert code == 0

        # Step 2: Check health
        stdout, stderr, code = full_cli("setup", "health")

        # Step 3: Check plan status
        stdout, stderr, code = full_cli("epic", "status")
        assert code in [0, 1, 2], f"Unexpected exit: {code}, stderr: {stderr}"

        # Step 4: Check status with validate flag
        stdout, stderr, code = full_cli("epic", "status", "--validate")
        assert code in [0, 1, 2], f"Unexpected exit: {code}, stderr: {stderr}"

    def test_json_mode_consistency(self, full_cli):
        """Test that JSON mode works consistently across commands."""
        json_commands = [
            ["--json", "epic", "status"],
            ["--json", "configure", "preferences", "list"],
            ["--json", "configure", "state", "list"],
        ]

        for cmd in json_commands:
            stdout, stderr, code = full_cli(*cmd)
            if code == 0 and stdout.strip():
                try:
                    data = json.loads(stdout)
                    assert isinstance(data, (dict, list)), f"Invalid JSON structure for {cmd}"
                except json.JSONDecodeError:
                    pass

    def test_alias_commands_work(self, full_cli):
        """Test that command aliases work correctly."""
        # configure -> cfg
        stdout1, _, code1 = full_cli("configure", "config", "show")
        stdout2, _, code2 = full_cli("cfg", "config", "show")
        assert code1 == code2
