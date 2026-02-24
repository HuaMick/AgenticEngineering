"""Integration tests for agentic session orchestrate command.

These tests run the ACTUAL installed CLI binary, not mocked subprocess calls.
This is the only way to catch bugs like the command-too-long error that
slipped through UAT in plans 260214PF, 260214TG, 260214US.
"""
import subprocess

import pytest


@pytest.mark.integration
class TestOrchestrateNoTmux:
    """Test orchestrate command without old --mode flag (now uses positional action)."""

    def test_planning_action_requires_positional_arg(self):
        """agentic session orchestrate without positional arg gives usage error."""
        result = subprocess.run(
            ["agentic", "session", "orchestrate"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Should fail since 'action' is a required positional arg
        assert result.returncode != 0

    def test_invalid_action_gives_clear_error(self):
        """agentic session orchestrate bogus gives a clear error, not a crash."""
        result = subprocess.run(
            ["agentic", "session", "orchestrate", "bogus"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
        # Should mention valid actions or 'Unknown action'
        output = result.stdout + result.stderr
        assert "bogus" in output or "unknown" in output.lower() or "valid" in output.lower()

    def test_planning_action_is_recognised(self):
        """agentic session orchestrate planning is recognised as a valid action."""
        # We only check it doesn't fail with 'Unknown action' immediately;
        # it may fail later if health check fails in test env, which is fine.
        result = subprocess.run(
            ["agentic", "session", "orchestrate", "planning", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # --help should always succeed
        assert result.returncode == 0
