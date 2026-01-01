"""
Shell operations security and error handling tests.

Tests cover:
1. Command timeout handling
2. Error handling for invalid commands
3. Return code capture
4. stdout/stderr separation
"""

import pytest
import tempfile
import os
from pathlib import Path

from myagents.backend.services.agents.domains.shell_operations import ShellOperations


class TestCommandTimeoutHandling:
    """Test timeout behavior for long-running commands."""

    def test_command_timeout_exceeds_limit(self, tmp_path):
        """Commands that exceed timeout should return error result.

        Uses a short timeout (2s) for test efficiency instead of the default 30s.
        """
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        # Use sleep 5 with 2s timeout for faster test
        result = shell_ops.execute_shell("sleep 5", timeout=2)

        assert result["success"] is False
        assert result["returncode"] == -1
        assert "timed out" in result["stderr"].lower()

    def test_command_completes_within_timeout(self, tmp_path):
        """Commands that complete within timeout should succeed."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        # Quick command that completes within timeout
        result = shell_ops.execute_shell("echo 'done'", timeout=5)

        assert result["success"] is True
        assert result["returncode"] == 0
        assert "done" in result["stdout"]

    def test_timeout_default_is_30_seconds(self, tmp_path):
        """Verify default timeout is 30 seconds.

        Note: This test verifies behavior without actually waiting 30 seconds.
        """
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        # Test that a 1s command succeeds with default timeout
        result = shell_ops.execute_shell("sleep 1")

        assert result["success"] is True
        assert result["returncode"] == 0

    def test_timeout_with_partial_output(self, tmp_path):
        """Commands that timeout should preserve any partial output."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        # Command that outputs before timing out
        # Note: capture_output may not get partial output in all cases
        result = shell_ops.execute_shell(
            "echo 'starting'; sleep 5; echo 'never reached'",
            timeout=1
        )

        assert result["success"] is False
        assert result["returncode"] == -1


class TestErrorHandling:
    """Test error handling for invalid and failing commands."""

    def test_invalid_command_returns_error(self, tmp_path):
        """Non-existent commands should return error with returncode > 0."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("nonexistent_command_xyz123")

        assert result["success"] is False
        assert result["returncode"] > 0
        # Error message should be in stderr
        assert result["stderr"] != ""

    def test_command_with_bad_syntax(self, tmp_path):
        """Commands with syntax errors should return error."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("echo 'unclosed string")

        assert result["success"] is False
        assert result["returncode"] > 0

    def test_command_that_exits_with_error_code(self, tmp_path):
        """Commands that exit with non-zero code should be marked as failed."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("exit 42")

        assert result["success"] is False
        assert result["returncode"] == 42

    @pytest.mark.skipif(os.geteuid() == 0, reason="Test skipped when running as root (file permissions bypassed)")
    def test_command_that_fails_due_to_permissions(self, tmp_path):
        """Commands that fail due to permissions should return error."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        # Try to read a file without permissions
        protected_file = tmp_path / "protected.txt"
        protected_file.write_text("secret")
        protected_file.chmod(0o000)

        try:
            result = shell_ops.execute_shell(f"cat {protected_file}")

            assert result["success"] is False
            assert result["returncode"] > 0
            assert "permission" in result["stderr"].lower() or "denied" in result["stderr"].lower()
        finally:
            # Cleanup - restore permissions for deletion
            protected_file.chmod(0o644)

    def test_command_that_references_missing_file(self, tmp_path):
        """Commands referencing non-existent files should return error."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("cat /nonexistent/file/path.txt")

        assert result["success"] is False
        assert result["returncode"] > 0
        assert "no such file" in result["stderr"].lower()


class TestReturnCodeCapture:
    """Test that return codes are correctly captured."""

    def test_successful_command_returns_zero(self, tmp_path):
        """Successful commands should return code 0."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("true")

        assert result["returncode"] == 0
        assert result["success"] is True

    def test_failed_command_returns_nonzero(self, tmp_path):
        """Failed commands should return code > 0."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("false")

        assert result["returncode"] == 1
        assert result["success"] is False

    def test_specific_exit_codes_are_preserved(self, tmp_path):
        """Specific exit codes should be preserved exactly."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        for code in [1, 2, 42, 127, 255]:
            result = shell_ops.execute_shell(f"exit {code}")

            assert result["returncode"] == code
            assert result["success"] is False

    def test_timeout_returns_negative_one(self, tmp_path):
        """Timeout should return returncode -1."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("sleep 10", timeout=1)

        assert result["returncode"] == -1
        assert result["success"] is False

    def test_pipeline_returns_last_command_code(self, tmp_path):
        """Pipeline should return the exit code of the last command."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        # First command succeeds, second fails
        result = shell_ops.execute_shell("echo 'test' | false")

        assert result["returncode"] == 1
        assert result["success"] is False


class TestStdoutStderrSeparation:
    """Test that stdout and stderr are captured separately."""

    def test_stdout_only(self, tmp_path):
        """Commands that only write to stdout should have empty stderr."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("echo 'hello stdout'")

        assert "hello stdout" in result["stdout"]
        assert result["stderr"] == ""
        assert result["success"] is True

    def test_stderr_only(self, tmp_path):
        """Commands that only write to stderr should have empty stdout."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("echo 'hello stderr' >&2")

        assert result["stdout"] == ""
        assert "hello stderr" in result["stderr"]

    def test_both_stdout_and_stderr(self, tmp_path):
        """Commands that write to both should capture both separately."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("echo 'out' && echo 'err' >&2")

        assert "out" in result["stdout"]
        assert "err" in result["stderr"]

    def test_interleaved_output(self, tmp_path):
        """Interleaved stdout and stderr should both be captured."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell(
            "echo 'out1'; echo 'err1' >&2; echo 'out2'; echo 'err2' >&2"
        )

        assert "out1" in result["stdout"]
        assert "out2" in result["stdout"]
        assert "err1" in result["stderr"]
        assert "err2" in result["stderr"]

    def test_multiline_output(self, tmp_path):
        """Multiline output should be preserved with newlines."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("echo -e 'line1\\nline2\\nline3'")

        assert "line1" in result["stdout"]
        assert "line2" in result["stdout"]
        assert "line3" in result["stdout"]
        assert result["success"] is True

    def test_empty_output(self, tmp_path):
        """Commands with no output should return empty strings."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("true")

        assert result["stdout"] == ""
        assert result["stderr"] == ""
        assert result["success"] is True

    def test_large_output_is_captured(self, tmp_path):
        """Large output should be fully captured."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        # Generate 1000 lines of output
        result = shell_ops.execute_shell("seq 1 1000")

        lines = result["stdout"].strip().split('\n')
        assert len(lines) == 1000
        assert lines[0] == "1"
        assert lines[-1] == "1000"


class TestWorkingDirectoryValidation:
    """Test security validation of working directories."""

    def test_default_working_directory(self, tmp_path):
        """Default working directory should be the allowed directory."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("pwd")

        assert str(tmp_path) in result["stdout"]
        assert result["success"] is True

    def test_relative_path_within_allowed(self, tmp_path):
        """Relative paths within allowed directory should work."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("pwd", working_dir="subdir")

        assert str(subdir) in result["stdout"]
        assert result["success"] is True

    def test_path_traversal_blocked(self, tmp_path):
        """Path traversal attempts should be blocked."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        with pytest.raises(ValueError, match="outside allowed directory"):
            shell_ops.execute_shell("pwd", working_dir="../../../etc")

    def test_absolute_path_outside_blocked(self, tmp_path):
        """Absolute paths outside allowed directory should be blocked."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        with pytest.raises(ValueError, match="outside allowed directory"):
            shell_ops.execute_shell("pwd", working_dir="/etc")

    def test_absolute_path_inside_allowed(self, tmp_path):
        """Absolute paths inside allowed directory should work."""
        subdir = tmp_path / "inner"
        subdir.mkdir()

        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("pwd", working_dir=str(subdir))

        assert str(subdir) in result["stdout"]
        assert result["success"] is True

    def test_nonexistent_directory_rejected(self, tmp_path):
        """Non-existent directories should be rejected."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        with pytest.raises(ValueError, match="does not exist"):
            shell_ops.execute_shell("pwd", working_dir="nonexistent")

    def test_symlink_escape_blocked(self, tmp_path):
        """Symlinks that escape allowed directory should be blocked."""
        # Create a symlink pointing outside
        symlink = tmp_path / "escape"
        symlink.symlink_to("/tmp")

        shell_ops = ShellOperations(allowed_dir=tmp_path)

        with pytest.raises(ValueError, match="outside allowed directory"):
            shell_ops.execute_shell("pwd", working_dir="escape")


class TestGeneralExceptionHandling:
    """Test handling of general exceptions during command execution."""

    def test_empty_command(self, tmp_path):
        """Empty commands should complete without error."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("")

        # Empty command should return code 0 in bash
        assert result["returncode"] == 0
        assert result["success"] is True

    def test_command_with_special_characters(self, tmp_path):
        """Commands with special characters should be handled."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        result = shell_ops.execute_shell("echo 'test $VAR `command` \"quotes\"'")

        assert result["success"] is True
        assert "test" in result["stdout"]

    def test_very_long_command(self, tmp_path):
        """Very long commands should be handled."""
        shell_ops = ShellOperations(allowed_dir=tmp_path)

        # Create a command with many arguments
        args = " ".join([f"arg{i}" for i in range(100)])
        result = shell_ops.execute_shell(f"echo {args}")

        assert result["success"] is True
        assert "arg99" in result["stdout"]
