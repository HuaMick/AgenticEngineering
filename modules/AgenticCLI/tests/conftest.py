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


@pytest.fixture(autouse=True)
def _block_real_ntfy():
    """Safety net: prevent any test from sending real ntfy notifications.

    Patches _get_ntfy_config to return None so ntfy code paths are skipped.
    Tests that intentionally test ntfy should override this fixture in their
    module by defining their own _block_real_ntfy that yields without patching.
    """
    with patch("agenticcli.commands.question._get_ntfy_config", return_value=None):
        yield


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

    # Create a sample plan folder (flattened structure: plan files directly in folder)
    plan_folder = plans_live / "260103AE_test"
    plan_folder.mkdir(parents=True)

    # Create sample plan file (flattened: directly in plan_folder)
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
    with open(plan_folder / "plan_test.yml", "w") as f:
        yaml.dump(sample_plan, f)

    # Create a minimal orchestration MMD file (EN-006 requires it for task start)
    (plan_folder / "orchestration_test.mmd").write_text(
        "flowchart TD\n  P01[Phase 1] --> P02[Phase 2]\n"
    )

    yield repo_dir


@pytest.fixture
def mock_cwd(temp_repo):
    """Mock os.getcwd to return temp_repo."""
    original_cwd = os.getcwd()
    os.chdir(temp_repo)
    yield temp_repo
    os.chdir(original_cwd)


@pytest.fixture
def cli_runner(temp_repo):
    """Fixture to run CLI commands and capture output.

    Runs in a temp repo directory to satisfy project requirement.
    Initializes a real git repository for git commands to work.
    """
    import io
    import subprocess
    from contextlib import redirect_stderr, redirect_stdout

    # Initialize a real git repository
    subprocess.run(
        ["git", "init"],
        cwd=temp_repo,
        capture_output=True,
        check=True,
    )
    # Configure git user for the repo
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=temp_repo,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_repo,
        capture_output=True,
    )
    # Create an initial commit so we have a branch
    (temp_repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(
        ["git", "add", "."],
        cwd=temp_repo,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_repo,
        capture_output=True,
    )

    # Change to temp repo directory
    original_cwd = os.getcwd()
    os.chdir(temp_repo)

    class CLIResult:
        """Result from CLI run. Supports both attribute and tuple unpacking access."""

        def __init__(self, stdout: str, stderr: str, returncode: int):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

        def __iter__(self):
            """Support tuple unpacking: stdout, stderr, code = result."""
            return iter((self.stdout, self.stderr, self.returncode))

    def run_cli(*args, expect_exit: int | None = None):
        """Run CLI with args and return CLIResult."""
        from agenticcli.cli import run_cli as _run_cli
        from agenticcli.console import set_json_output

        # Reset JSON output mode before each run
        set_json_output(False)

        # Support both run_cli("a", "b") and run_cli(["a", "b"])
        if len(args) == 1 and isinstance(args[0], list):
            cmd_args = args[0]
        else:
            cmd_args = list(args)

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        exit_code = 0

        # Patch sys.argv
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

    # Reset global state that may have been set by --json flag
    from agenticcli.console import set_json_output
    set_json_output(False)

    # Restore cwd
    os.chdir(original_cwd)


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
        },
    }
    prefs_file = temp_config_dir / "preferences.yml"
    with open(prefs_file, "w") as f:
        yaml.dump(prefs, f)
    return prefs_file
