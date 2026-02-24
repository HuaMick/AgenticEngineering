"""Real tmux layout integration tests.

These tests create ACTUAL tmux sessions and verify the 3-pane
orchestration layout. NO mocking. NO --no-tmux bypass.

Every test uses real tmux binaries, real sessions, real pane counts.
"""
import json
import os
import subprocess
import tempfile
import time

import pytest

from agenticcli.utils.tmux_layout import (
    _create_new_session_layout,
    cleanup_orchestration_sessions,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.tmux,
    pytest.mark.skipif(
        not subprocess.run(["which", "tmux"], capture_output=True).returncode == 0,
        reason="tmux not available",
    ),
]


def _kill_session(name):
    subprocess.run(["tmux", "kill-session", "-t", name], capture_output=True)


def _session_exists(name):
    result = subprocess.run(
        ["tmux", "has-session", "-t", name], capture_output=True
    )
    return result.returncode == 0


def _get_panes(session_name, fmt="#{pane_id} #{pane_title}"):
    result = subprocess.run(
        ["tmux", "list-panes", "-t", session_name, "-F", fmt],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    return result.stdout.strip().splitlines()


class TestNewSessionCreatesThreePanes:
    def test_new_session_creates_three_panes(self, tmux_session_cleanup):
        session = f"agentic-orch-test-3pane-{os.getpid()}"
        try:
            layout = _create_new_session_layout(
                session_name=session,
                claude_cmd_str="echo test",
                dashboard_refresh=5,
                question_refresh=10,
                skip_commands=True,
            )
            panes = _get_panes(session)
            assert len(panes) == 3, f"Expected 3 panes, got {len(panes)}: {panes}"

            # Verify pane titles
            titles = []
            for line in panes:
                parts = line.split(None, 1)
                if len(parts) > 1:
                    titles.append(parts[1])
            assert "orchestrator" in titles
            assert "sessions" in titles
            assert "questions" in titles
        finally:
            _kill_session(session)


class TestPaneDimensionsAreReasonable:
    def test_pane_dimensions_are_reasonable(self, tmux_session_cleanup):
        session = f"agentic-orch-test-dims-{os.getpid()}"
        try:
            _create_new_session_layout(
                session_name=session,
                claude_cmd_str="echo test",
                dashboard_refresh=5,
                question_refresh=10,
                skip_commands=True,
            )
            panes = _get_panes(session, "#{pane_id} #{pane_width} #{pane_height}")
            assert len(panes) == 3

            dims = []
            for line in panes:
                parts = line.split()
                dims.append({
                    "pane_id": parts[0],
                    "width": int(parts[1]),
                    "height": int(parts[2]),
                })

            # Main pane (first) should be wider than status pane (second)
            # Main gets ~70% (140 cols), status gets ~30% (60 cols)
            assert dims[0]["width"] > dims[1]["width"], (
                f"Main pane width {dims[0]['width']} should be > "
                f"status pane width {dims[1]['width']}"
            )

            # Status pane (second) should be taller than questions pane (third)
            # Status gets ~60% height, questions gets ~40%
            assert dims[1]["height"] > dims[2]["height"], (
                f"Status pane height {dims[1]['height']} should be > "
                f"questions pane height {dims[2]['height']}"
            )
        finally:
            _kill_session(session)


class TestSessionNameContainsPid:
    def test_session_name_contains_pid(self, tmux_session_cleanup):
        session = f"agentic-orch-{os.getpid()}"
        try:
            layout = _create_new_session_layout(
                session_name=session,
                claude_cmd_str="echo test",
                dashboard_refresh=5,
                question_refresh=10,
                skip_commands=True,
            )
            assert layout.session_name.startswith("agentic-orch-")
            # Session name should contain a number (pid)
            suffix = layout.session_name.replace("agentic-orch-", "")
            assert suffix.isdigit()
            assert _session_exists(session)
        finally:
            _kill_session(session)


class TestCleanupKillsOrphanedSessions:
    def test_cleanup_kills_orphaned_sessions(self, tmux_session_cleanup):
        zombies = [
            "agentic-orch-zombie-1",
            "agentic-orch-zombie-2",
            "agentic-orch-zombie-3",
        ]
        safe_session = "non-agentic-test-session"
        try:
            # Create zombie sessions
            for z in zombies:
                subprocess.run(
                    ["tmux", "new-session", "-d", "-s", z],
                    capture_output=True, check=True,
                )
            # Create a non-agentic session that should survive
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", safe_session],
                capture_output=True, check=True,
            )

            # Verify all exist
            for z in zombies:
                assert _session_exists(z), f"Zombie {z} should exist before cleanup"
            assert _session_exists(safe_session)

            # Run cleanup
            killed = cleanup_orchestration_sessions()

            # Verify zombies are dead
            for z in zombies:
                assert not _session_exists(z), f"Zombie {z} should be killed"
            assert len(killed) >= 3

            # Verify safe session survived
            assert _session_exists(safe_session), "Non-agentic session should survive"
        finally:
            for z in zombies:
                _kill_session(z)
            _kill_session(safe_session)


class TestDryRunCreatesAndDestroysLayout:
    def test_dry_run_creates_and_destroys_layout(self, tmux_session_cleanup):
        result = subprocess.run(
            ["agentic", "session", "orchestrate", "planning", "--dry-run"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"dry-run failed: {result.stderr}"

        output = json.loads(result.stdout)
        assert output["pane_count"] == 3
        assert output["session_name"].startswith("agentic-orch-")
        assert len(output["panes"]) == 3

        # Verify session was cleaned up
        assert not _session_exists(output["session_name"]), (
            f"Session {output['session_name']} should be cleaned up after dry-run"
        )


class TestSendKeysCommandReachesPane:
    def test_send_keys_command_reaches_pane(self, tmux_session_cleanup):
        session = f"agentic-orch-test-sendkeys-{os.getpid()}"
        try:
            layout = _create_new_session_layout(
                session_name=session,
                claude_cmd_str="echo test",
                dashboard_refresh=5,
                question_refresh=10,
                skip_commands=True,
            )

            # Send a test command to the main pane
            subprocess.run(
                ["tmux", "send-keys", "-t", layout.main_pane_id,
                 "echo TMUX_TEST_MARKER_12345", "Enter"],
                check=True,
            )

            # Wait for command to execute
            time.sleep(1)

            # Capture pane content
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", layout.main_pane_id, "-p"],
                capture_output=True, text=True,
            )
            assert "TMUX_TEST_MARKER_12345" in result.stdout, (
                f"Marker not found in pane output: {result.stdout[:200]}"
            )
        finally:
            _kill_session(session)


class TestPromptFileIsReadableFromPane:
    def test_prompt_file_is_readable_from_pane(self, tmux_session_cleanup):
        session = f"agentic-orch-test-catfile-{os.getpid()}"
        marker = "SMOKE_TEST_CAT_EXPANSION_67890"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", prefix="agentic_test_", delete=False
        ) as f:
            f.write(marker)
            tmpfile = f.name

        try:
            layout = _create_new_session_layout(
                session_name=session,
                claude_cmd_str="echo test",
                dashboard_refresh=5,
                question_refresh=10,
                skip_commands=True,
            )

            # Send $(cat file) expansion command
            subprocess.run(
                ["tmux", "send-keys", "-t", layout.main_pane_id,
                 f'echo "$(cat {tmpfile})"', "Enter"],
                check=True,
            )

            time.sleep(1)

            result = subprocess.run(
                ["tmux", "capture-pane", "-t", layout.main_pane_id, "-p"],
                capture_output=True, text=True,
            )
            assert marker in result.stdout, (
                f"$(cat file) expansion failed - marker not found: {result.stdout[:200]}"
            )
        finally:
            _kill_session(session)
            os.unlink(tmpfile)
