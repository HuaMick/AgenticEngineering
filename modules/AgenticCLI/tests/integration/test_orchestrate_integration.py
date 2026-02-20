"""Integration tests for agentic session orchestrate command.

These tests run the ACTUAL installed CLI binary, not mocked subprocess calls.
This is the only way to catch bugs like the command-too-long error that
slipped through UAT in plans 260214PF, 260214TG, 260214US.
"""
import subprocess

import pytest


@pytest.mark.integration
class TestOrchestrateNoTmux:
    """Test orchestrate command without tmux (CI-compatible)."""

    def test_planning_mode_starts_without_error(self):
        """agentic session orchestrate --mode planning --no-tmux starts without command-too-long error."""
        result = subprocess.run(
            ["agentic", "session", "orchestrate", "--mode", "planning", "--no-tmux"],
            capture_output=True,
            text=True,
            timeout=15,
            input="/exit\n",
        )
        assert "argument list too long" not in result.stderr.lower(), (
            f"Command too long error: {result.stderr[:500]}"
        )
        assert "command too long" not in result.stderr.lower(), (
            f"Command too long error: {result.stderr[:500]}"
        )

    def test_executor_mode_starts_without_error(self):
        """agentic session orchestrate --mode executor --no-tmux starts without command-too-long error."""
        result = subprocess.run(
            ["agentic", "session", "orchestrate", "--mode", "executor", "--no-tmux"],
            capture_output=True,
            text=True,
            timeout=15,
            input="/exit\n",
        )
        assert "argument list too long" not in result.stderr.lower()
        assert "command too long" not in result.stderr.lower()

    def test_loop_mode_starts_without_error(self):
        """agentic session orchestrate --mode loop --no-tmux starts without command-too-long error."""
        result = subprocess.run(
            ["agentic", "session", "orchestrate", "--mode", "loop", "--no-tmux"],
            capture_output=True,
            text=True,
            timeout=15,
            input="/exit\n",
        )
        assert "argument list too long" not in result.stderr.lower()
        assert "command too long" not in result.stderr.lower()

    def test_invalid_mode_gives_clear_error(self):
        """agentic session orchestrate --mode bogus gives a clear error, not a crash."""
        result = subprocess.run(
            ["agentic", "session", "orchestrate", "--mode", "bogus", "--no-tmux"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0


@pytest.mark.integration
class TestOrchestratePromptFile:
    """Verify system prompt is written to temp file."""

    def test_temp_file_created_for_planning(self):
        """Planning mode creates a temp file for the system prompt."""
        import glob
        import os

        # Clean up any existing temp files
        for f in glob.glob("/tmp/agentic_prompt_*.md"):
            os.unlink(f)

        result = subprocess.run(
            ["agentic", "session", "orchestrate", "--mode", "planning", "--no-tmux"],
            capture_output=True,
            text=True,
            timeout=15,
            input="/exit\n",
        )

        # A temp file should have been created
        temp_files = glob.glob("/tmp/agentic_prompt_*.md")
        assert len(temp_files) >= 1, (
            f"No temp prompt file created. stderr: {result.stderr[:300]}"
        )

        # The file should contain the process content
        content = open(temp_files[0]).read()
        assert "BOOTSTRAP CONTEXT" in content
        assert len(content) > 100

        # Cleanup
        for f in temp_files:
            os.unlink(f)
