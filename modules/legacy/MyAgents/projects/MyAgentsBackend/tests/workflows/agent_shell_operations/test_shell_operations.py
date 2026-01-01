"""Tests for ShellOperations domain basic functionality.

Test scope:
1. Test successful command execution (e.g., "echo hello")
2. Test working directory enforcement (defaults to allowed_dir)
3. Test return dict contains stdout, stderr, returncode, success keys
"""

import os
import pytest
from pathlib import Path

from myagents.backend.services.agents.domains.shell_operations import ShellOperations


@pytest.mark.agent_shell_operations
class TestShellOperationsBasic:
    """Test basic ShellOperations functionality."""

    def test_successful_command_execution_echo(self):
        """Test that execute_shell successfully runs echo command and returns correct output."""
        # Get the allowed directory from environment (set by conftest)
        allowed_dir = Path(os.environ.get("MYAGENTS_ALLOWED_DIR", "/home/code/myagents"))

        shell_ops = ShellOperations(allowed_dir=allowed_dir)
        result = shell_ops.execute_shell("echo hello")

        # Verify command executed successfully
        assert result["success"] is True, f"Expected success=True, got {result}"
        assert result["returncode"] == 0, f"Expected returncode=0, got {result['returncode']}"
        assert "hello" in result["stdout"], f"Expected 'hello' in stdout, got: {result['stdout']}"
        assert result["stderr"] == "", f"Expected empty stderr, got: {result['stderr']}"

    def test_successful_command_execution_pwd(self):
        """Test that execute_shell runs pwd command in correct directory."""
        allowed_dir = Path(os.environ.get("MYAGENTS_ALLOWED_DIR", "/home/code/myagents"))

        shell_ops = ShellOperations(allowed_dir=allowed_dir)
        result = shell_ops.execute_shell("pwd")

        # Verify command executed successfully
        assert result["success"] is True, f"Expected success=True, got {result}"
        assert result["returncode"] == 0, f"Expected returncode=0, got {result['returncode']}"
        # pwd should return the allowed directory
        assert str(allowed_dir) in result["stdout"], f"Expected {allowed_dir} in stdout, got: {result['stdout']}"

    def test_working_directory_defaults_to_allowed_dir(self):
        """Test that working directory defaults to allowed_dir when not specified."""
        allowed_dir = Path(os.environ.get("MYAGENTS_ALLOWED_DIR", "/home/code/myagents"))

        shell_ops = ShellOperations(allowed_dir=allowed_dir)

        # Execute pwd without specifying working_dir
        result = shell_ops.execute_shell("pwd")

        # Verify working directory is the allowed directory
        assert result["success"] is True
        pwd_output = result["stdout"].strip()
        assert pwd_output == str(allowed_dir), f"Expected pwd={allowed_dir}, got {pwd_output}"

    def test_working_directory_can_be_subdirectory(self):
        """Test that working directory can be a subdirectory of allowed_dir."""
        allowed_dir = Path(os.environ.get("MYAGENTS_ALLOWED_DIR", "/home/code/myagents"))

        shell_ops = ShellOperations(allowed_dir=allowed_dir)

        # Use tests directory as a known subdirectory
        tests_dir = allowed_dir / "tests"

        if tests_dir.exists():
            result = shell_ops.execute_shell("pwd", working_dir=str(tests_dir))

            assert result["success"] is True
            pwd_output = result["stdout"].strip()
            assert pwd_output == str(tests_dir), f"Expected pwd={tests_dir}, got {pwd_output}"
        else:
            pytest.skip(f"Tests directory not found: {tests_dir}")

    def test_return_dict_contains_required_keys(self):
        """Test that return dict contains stdout, stderr, returncode, success keys."""
        allowed_dir = Path(os.environ.get("MYAGENTS_ALLOWED_DIR", "/home/code/myagents"))

        shell_ops = ShellOperations(allowed_dir=allowed_dir)
        result = shell_ops.execute_shell("echo test")

        # Verify all required keys are present
        required_keys = ["stdout", "stderr", "returncode", "success"]
        for key in required_keys:
            assert key in result, f"Missing required key '{key}' in result: {result}"

        # Verify key types
        assert isinstance(result["stdout"], str), f"stdout should be string, got {type(result['stdout'])}"
        assert isinstance(result["stderr"], str), f"stderr should be string, got {type(result['stderr'])}"
        assert isinstance(result["returncode"], int), f"returncode should be int, got {type(result['returncode'])}"
        assert isinstance(result["success"], bool), f"success should be bool, got {type(result['success'])}"

    def test_failed_command_returns_correct_structure(self):
        """Test that failed commands return correct structure with success=False."""
        allowed_dir = Path(os.environ.get("MYAGENTS_ALLOWED_DIR", "/home/code/myagents"))

        shell_ops = ShellOperations(allowed_dir=allowed_dir)

        # Execute a command that will fail
        result = shell_ops.execute_shell("exit 1")

        # Verify failure is correctly reported
        assert result["success"] is False, f"Expected success=False for exit 1, got {result}"
        assert result["returncode"] == 1, f"Expected returncode=1, got {result['returncode']}"

        # Still should have all required keys
        required_keys = ["stdout", "stderr", "returncode", "success"]
        for key in required_keys:
            assert key in result, f"Missing required key '{key}' in failed result: {result}"

    def test_command_with_stderr_output(self):
        """Test that stderr output is captured correctly."""
        allowed_dir = Path(os.environ.get("MYAGENTS_ALLOWED_DIR", "/home/code/myagents"))

        shell_ops = ShellOperations(allowed_dir=allowed_dir)

        # Command that outputs to stderr
        result = shell_ops.execute_shell("echo error_message >&2")

        # Verify stderr is captured (command should succeed even with stderr)
        assert "error_message" in result["stderr"], f"Expected 'error_message' in stderr, got: {result['stderr']}"
        # Note: return code is still 0 since echo succeeded
        assert result["returncode"] == 0

    def test_multiline_output(self):
        """Test that multiline output is captured correctly."""
        allowed_dir = Path(os.environ.get("MYAGENTS_ALLOWED_DIR", "/home/code/myagents"))

        shell_ops = ShellOperations(allowed_dir=allowed_dir)

        # Command that outputs multiple lines
        result = shell_ops.execute_shell("echo 'line1'; echo 'line2'; echo 'line3'")

        assert result["success"] is True
        assert "line1" in result["stdout"]
        assert "line2" in result["stdout"]
        assert "line3" in result["stdout"]
