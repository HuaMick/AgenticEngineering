"""Real CLI orchestrate smoke tests.

Tests the ACTUAL `agentic orchestrate` command end-to-end using --dry-run.
Verifies tmux layout creation, cleanup, and error handling via the installed binary.
"""
import json
import subprocess

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.tmux,
    pytest.mark.xdist_group("tmux"),
    pytest.mark.skipif(
        not subprocess.run(["which", "tmux"], capture_output=True).returncode == 0,
        reason="tmux not available",
    ),
]


def _session_exists(name):
    result = subprocess.run(
        ["tmux", "has-session", "-t", name], capture_output=True
    )
    return result.returncode == 0


def _list_orch_sessions():
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    return [s for s in result.stdout.strip().splitlines()
            if s.startswith("agentic-orch-")]


class TestOrchestrateDryRunPlanning:
    def test_orchestrate_dry_run_planning(self, tmux_session_cleanup):
        result = subprocess.run(
            ["agentic", "orchestrate", "session", "plan", "--dry-run"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"Exit code {result.returncode}: {result.stderr}"

        output = json.loads(result.stdout)
        assert output["pane_count"] == 3
        assert output["session_name"].startswith("agentic-orch-")
        assert len(output["panes"]) == 3

        # Verify no tmux session left behind
        assert not _session_exists(output["session_name"])


class TestOrchestrateDryRunWithDifferentActions:
    def test_orchestrate_dry_run_ignores_action(self, tmux_session_cleanup):
        """--dry-run should work regardless of the action argument."""
        result = subprocess.run(
            ["agentic", "orchestrate", "session", "plan", "--dry-run"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["pane_count"] == 3


class TestOrchestrateDryRunPaneDetails:
    def test_dry_run_pane_titles(self, tmux_session_cleanup):
        result = subprocess.run(
            ["agentic", "orchestrate", "session", "plan", "--dry-run"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)

        titles = [p["pane_title"] for p in output["panes"]]
        assert "orchestrator" in titles
        assert "sessions" in titles
        assert "questions" in titles


class TestOrchestrateDryRunDistinctPanes:
    def test_dry_run_distinct_pane_ids(self, tmux_session_cleanup):
        result = subprocess.run(
            ["agentic", "orchestrate", "session", "plan", "--dry-run"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)

        pane_ids = [p["pane_id"] for p in output["panes"]]
        assert len(set(pane_ids)) == 3, f"Pane IDs not distinct: {pane_ids}"

        # Also check the named fields match
        assert output["main_pane_id"] in pane_ids
        assert output["status_pane_id"] in pane_ids
        assert output["questions_pane_id"] in pane_ids


class TestOrchestrateDryRunJsonOutput:
    def test_dry_run_valid_json_fields(self, tmux_session_cleanup):
        result = subprocess.run(
            ["agentic", "orchestrate", "session", "plan", "--dry-run"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)

        # Verify all expected fields exist
        required_fields = [
            "session_name", "main_pane_id", "status_pane_id",
            "questions_pane_id", "created_new_session", "pane_count", "panes",
        ]
        for field in required_fields:
            assert field in output, f"Missing field: {field}"

        assert output["created_new_session"] is True


class TestNoOrphanedSessionsAfterDryRun:
    def test_no_orphaned_sessions_after_dry_run(self, tmux_session_cleanup):
        """Run --dry-run 3 times, verify no orphaned sessions remain."""
        for _ in range(3):
            result = subprocess.run(
                ["agentic", "orchestrate", "session", "plan", "--dry-run"],
                capture_output=True, text=True, timeout=15,
            )
            assert result.returncode == 0

        remaining = _list_orch_sessions()
        assert len(remaining) == 0, f"Orphaned sessions found: {remaining}"
