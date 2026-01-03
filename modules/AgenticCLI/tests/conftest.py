"""Pytest configuration and fixtures for AgenticCLI tests."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_dir(temp_dir):
    """Create a temporary config directory and set XDG_CONFIG_HOME."""
    config_dir = temp_dir / "config" / "agenticcli"
    config_dir.mkdir(parents=True)
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(temp_dir / "config")}):
        yield config_dir


@pytest.fixture
def temp_repo(temp_dir):
    """Create a temporary git repository structure."""
    repo_dir = temp_dir / "repo"
    repo_dir.mkdir()

    # Create docs/plans/live structure
    plans_live = repo_dir / "docs" / "plans" / "live"
    plans_live.mkdir(parents=True)

    # Create a sample plan folder
    plan_folder = plans_live / "260103AE_test"
    (plan_folder / "live").mkdir(parents=True)
    (plan_folder / "completed").mkdir(parents=True)

    # Create sample plan file
    sample_plan = {
        "plan": {
            "name": "Test Plan",
            "status": "in_progress",
            "phases": [
                {"id": "01", "name": "Phase 1", "status": "completed"},
                {"id": "02", "name": "Phase 2", "status": "pending"},
            ],
        }
    }
    with open(plan_folder / "live" / "plan_test.yml", "w") as f:
        yaml.dump(sample_plan, f)

    yield repo_dir


@pytest.fixture
def mock_cwd(temp_repo):
    """Mock os.getcwd to return temp_repo."""
    original_cwd = os.getcwd()
    os.chdir(temp_repo)
    yield temp_repo
    os.chdir(original_cwd)


@pytest.fixture
def cli_runner():
    """Fixture to run CLI commands and capture output."""
    import io
    from contextlib import redirect_stdout, redirect_stderr

    def run_cli(args: list[str], expect_exit: int | None = None):
        """Run CLI with args and return (stdout, stderr, exit_code)."""
        from agenticcli.cli import run_cli as _run_cli

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        exit_code = 0

        # Patch sys.argv
        with patch.object(sys, "argv", ["agentic"] + args):
            with redirect_stdout(stdout_capture):
                with redirect_stderr(stderr_capture):
                    try:
                        _run_cli()
                    except SystemExit as e:
                        exit_code = e.code if e.code is not None else 0

        stdout = stdout_capture.getvalue()
        stderr = stderr_capture.getvalue()

        if expect_exit is not None:
            assert exit_code == expect_exit, f"Expected exit {expect_exit}, got {exit_code}. stderr: {stderr}"

        return stdout, stderr, exit_code

    return run_cli


@pytest.fixture
def sample_prefs(temp_config_dir):
    """Create sample preferences file."""
    prefs = {
        "worktree": {
            "default_base": "main",
        },
        "plan": {
            "auto_scaffold": True,
        },
        "test": {
            "nested": {
                "value": "test_value",
            }
        }
    }
    prefs_file = temp_config_dir / "preferences.yml"
    with open(prefs_file, "w") as f:
        yaml.dump(prefs, f)
    return prefs_file
