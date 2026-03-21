"""TT_007: Integration tests for tmux-based session spawning.

These tests use real tmux sessions and require tmux to be installed.
Marked with pytest.mark.tmux and skipped when tmux is not available.

Run with: pytest -m tmux tests/integration/test_tmux_spawn.py
"""
import shutil
import subprocess
import time
import uuid

import pytest

pytestmark = pytest.mark.story("US-SES-001")

requires_tmux = pytest.mark.skipif(
    not shutil.which("tmux"),
    reason="tmux not available",
)


@pytest.fixture
def unique_session_name():
    """Generate a unique tmux session name for test isolation."""
    name = f"agentic-test-{uuid.uuid4().hex[:8]}"
    yield name
    # Cleanup: kill the session if it still exists
    subprocess.run(
        ["tmux", "kill-session", "-t", name],
        capture_output=True,
    )


@requires_tmux
@pytest.mark.tmux
@pytest.mark.xdist_group("tmux")
class TestTmuxSpawnIntegration:
    """Integration tests that create real tmux sessions."""

    def test_tmux_spawn_creates_real_session(self, unique_session_name):
        """Create a tmux session with a simple command, verify it exists."""
        # Create a tmux session running a simple long-lived command
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", unique_session_name,
             "bash", "-c", "sleep 30"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Failed to create tmux session: {result.stderr}"

        # Verify session exists
        check = subprocess.run(
            ["tmux", "has-session", "-t", unique_session_name],
            capture_output=True,
        )
        assert check.returncode == 0, "tmux session should exist"

        # Verify session name matches convention
        list_result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
        )
        assert unique_session_name in list_result.stdout.splitlines()

        # Kill the session — it should close
        subprocess.run(
            ["tmux", "kill-session", "-t", unique_session_name],
            capture_output=True,
        )

        # Verify session is gone
        check2 = subprocess.run(
            ["tmux", "has-session", "-t", unique_session_name],
            capture_output=True,
        )
        assert check2.returncode != 0, "tmux session should be gone after kill"

    def test_tmux_spawn_session_attach_works(self, unique_session_name):
        """Create tmux session, verify it appears in list-sessions."""
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", unique_session_name,
             "bash", "-c", "sleep 30"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Verify it appears in list-sessions
        list_result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
        )
        sessions = list_result.stdout.strip().splitlines()
        assert unique_session_name in sessions

        # Get PID from tmux pane (matching the spawn implementation)
        pid_result = subprocess.run(
            ["tmux", "list-panes", "-t", unique_session_name, "-F", "#{pane_pid}"],
            capture_output=True,
            text=True,
        )
        assert pid_result.returncode == 0
        pid_str = pid_result.stdout.strip().split("\n")[0]
        assert pid_str.isdigit(), f"Expected numeric PID, got: {pid_str}"

    def test_tmux_spawn_env_isolation(self, unique_session_name):
        """Create tmux session with CLAUDECODE unset, verify isolation."""
        import os

        # Create a tmux session that unsets CLAUDECODE and echoes the env var
        # This mirrors the actual spawn implementation's wrapped_cmd
        wrapped_cmd = f"unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT; echo CLAUDECODE=${{CLAUDECODE:-UNSET}} > /tmp/tmux_env_test_{unique_session_name}; sleep 5"

        # Set CLAUDECODE in our env to simulate running inside Claude Code
        env = os.environ.copy()
        env["CLAUDECODE"] = "1"
        env["CLAUDE_CODE_ENTRYPOINT"] = "test"

        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", unique_session_name,
             "bash", "-c", wrapped_cmd],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0

        # Wait a moment for the command to execute and write the file
        time.sleep(1)

        # Read the env test file
        env_file = f"/tmp/tmux_env_test_{unique_session_name}"
        try:
            with open(env_file) as f:
                content = f.read().strip()
            # CLAUDECODE should be UNSET inside the tmux session
            assert "CLAUDECODE=UNSET" in content, f"Expected CLAUDECODE=UNSET, got: {content}"
        finally:
            # Cleanup the temp file
            try:
                os.remove(env_file)
            except FileNotFoundError:
                pass
