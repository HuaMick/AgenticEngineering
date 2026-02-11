"""Tests for worktree reuse and auto-cleanup functionality.

Tests the enforcement of the error-driven-planning-protocol rules:
- Rule 3: Only create new worktree if ALL existing have active sessions
- Auto-cleanup: Remove worktrees when their last plan archives
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


class TestFindIdleWorktrees:
    """Tests for find_idle_worktrees function."""

    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    @patch("agenticcli.commands.session._list_all_sessions")
    @patch("agenticcli.commands.session._is_process_running")
    def test_returns_idle_non_main_worktrees(
        self, mock_running, mock_sessions, mock_worktrees
    ):
        """Idle worktrees (no active sessions) are returned."""
        from agenticcli.commands.worktree import find_idle_worktrees

        mock_worktrees.return_value = [
            {"path": "/home/code/Repo", "branch": "main"},
            {"path": "/home/code/Repo-feat-a", "branch": "feat-a"},
            {"path": "/home/code/Repo-feat-b", "branch": "feat-b"},
        ]
        mock_sessions.return_value = []
        mock_running.return_value = False

        result = find_idle_worktrees(Path("/home/code/Repo"))

        # Should return feat-a and feat-b (main excluded)
        assert len(result) == 2
        branches = {wt["branch"] for wt in result}
        assert branches == {"feat-a", "feat-b"}

    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    @patch("agenticcli.commands.session._list_all_sessions")
    @patch("agenticcli.commands.session._is_process_running")
    def test_excludes_worktrees_with_active_sessions(
        self, mock_running, mock_sessions, mock_worktrees
    ):
        """Worktrees with running sessions are excluded."""
        from agenticcli.commands.worktree import find_idle_worktrees

        mock_worktrees.return_value = [
            {"path": "/home/code/Repo", "branch": "main"},
            {"path": "/home/code/Repo-feat-a", "branch": "feat-a"},
            {"path": "/home/code/Repo-feat-b", "branch": "feat-b"},
        ]
        mock_sessions.return_value = [
            {
                "session_id": "abc",
                "status": "running",
                "pid": 12345,
                "working_dir": "/home/code/Repo-feat-a",
            }
        ]
        mock_running.return_value = True

        result = find_idle_worktrees(Path("/home/code/Repo"))

        # Only feat-b should be idle
        assert len(result) == 1
        assert result[0]["branch"] == "feat-b"

    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    @patch("agenticcli.commands.session._list_all_sessions")
    @patch("agenticcli.commands.session._is_process_running")
    def test_all_busy_returns_empty(
        self, mock_running, mock_sessions, mock_worktrees
    ):
        """When all worktrees have active sessions, returns empty list."""
        from agenticcli.commands.worktree import find_idle_worktrees

        mock_worktrees.return_value = [
            {"path": "/home/code/Repo", "branch": "main"},
            {"path": "/home/code/Repo-feat-a", "branch": "feat-a"},
        ]
        mock_sessions.return_value = [
            {
                "session_id": "abc",
                "status": "running",
                "pid": 12345,
                "working_dir": "/home/code/Repo-feat-a",
            }
        ]
        mock_running.return_value = True

        result = find_idle_worktrees(Path("/home/code/Repo"))
        assert len(result) == 0

    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    @patch("agenticcli.commands.session._list_all_sessions")
    def test_dead_session_not_considered_active(
        self, mock_sessions, mock_worktrees
    ):
        """Sessions with dead PIDs are not considered active."""
        from agenticcli.commands.worktree import find_idle_worktrees

        mock_worktrees.return_value = [
            {"path": "/home/code/Repo", "branch": "main"},
            {"path": "/home/code/Repo-feat-a", "branch": "feat-a"},
        ]
        mock_sessions.return_value = [
            {
                "session_id": "abc",
                "status": "running",
                "pid": 99999,
                "working_dir": "/home/code/Repo-feat-a",
            }
        ]

        # PID is dead
        with patch("agenticcli.commands.session._is_process_running", return_value=False):
            result = find_idle_worktrees(Path("/home/code/Repo"))

        assert len(result) == 1
        assert result[0]["branch"] == "feat-a"

    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    @patch("agenticcli.commands.session._list_all_sessions")
    def test_excludes_main_and_master(self, mock_sessions, mock_worktrees):
        """Main and master worktrees are always excluded."""
        from agenticcli.commands.worktree import find_idle_worktrees

        mock_worktrees.return_value = [
            {"path": "/home/code/Repo", "branch": "main"},
            {"path": "/home/code/Repo-master", "branch": "master"},
        ]
        mock_sessions.return_value = []

        result = find_idle_worktrees(Path("/home/code/Repo"))
        assert len(result) == 0


class TestWorktreeHasLivePlans:
    """Tests for worktree_has_live_plans function."""

    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    @patch("agenticcli.commands.worktree.get_live_plan_folders")
    @patch("agenticcli.commands.worktree._match_plans_to_branch")
    def test_returns_true_when_plans_exist(
        self, mock_match, mock_plans, mock_worktrees
    ):
        """Returns True when matching live plans are found."""
        from agenticcli.commands.worktree import worktree_has_live_plans

        mock_worktrees.return_value = [
            {"path": "/home/code/Repo-feat-a", "branch": "feat-a"},
        ]
        mock_plans.return_value = ["260208FA_feature_auth"]
        mock_match.return_value = ["260208FA_feature_auth"]

        result = worktree_has_live_plans(
            Path("/home/code/Repo-feat-a"),
            Path("/home/code/Repo"),
            [],
        )
        assert result is True

    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    @patch("agenticcli.commands.worktree.get_live_plan_folders")
    @patch("agenticcli.commands.worktree._match_plans_to_branch")
    def test_returns_false_when_no_plans(
        self, mock_match, mock_plans, mock_worktrees
    ):
        """Returns False when no matching live plans are found."""
        from agenticcli.commands.worktree import worktree_has_live_plans

        mock_worktrees.return_value = [
            {"path": "/home/code/Repo-feat-a", "branch": "feat-a"},
        ]
        mock_plans.return_value = ["260208FB_other_feature"]
        mock_match.return_value = []

        result = worktree_has_live_plans(
            Path("/home/code/Repo-feat-a"),
            Path("/home/code/Repo"),
            [],
        )
        assert result is False

    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    def test_main_always_returns_true(self, mock_worktrees):
        """Main/master worktrees always report as having plans."""
        from agenticcli.commands.worktree import worktree_has_live_plans

        mock_worktrees.return_value = [
            {"path": "/home/code/Repo", "branch": "main"},
        ]

        result = worktree_has_live_plans(
            Path("/home/code/Repo"),
            Path("/home/code/Repo"),
            [],
        )
        assert result is True


class TestCleanupWorktreeIfIdle:
    """Tests for cleanup_worktree_if_idle function."""

    def test_protects_main_branch(self):
        """Main/master branches are never cleaned up."""
        from agenticcli.commands.worktree import cleanup_worktree_if_idle

        result = cleanup_worktree_if_idle(
            "main",
            Path("/home/code/Repo"),
            Path("/home/code/Repo"),
        )
        assert result["cleaned"] is False
        assert "protected" in result["reason"]

    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    def test_no_worktree_found(self, mock_worktrees):
        """Returns not cleaned when no worktree for branch."""
        from agenticcli.commands.worktree import cleanup_worktree_if_idle

        mock_worktrees.return_value = []

        result = cleanup_worktree_if_idle(
            "nonexistent",
            Path("/home/code/Repo"),
            Path("/home/code/Repo"),
        )
        assert result["cleaned"] is False
        assert "no worktree found" in result["reason"]

    @patch("agenticcli.commands.worktree.worktree_has_live_plans")
    @patch("agenticcli.commands.worktree.load_worktree_registry")
    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    def test_skips_when_live_plans_remain(
        self, mock_worktrees, mock_registry, mock_has_plans
    ):
        """Does not clean up worktree that still has live plans."""
        from agenticcli.commands.worktree import cleanup_worktree_if_idle

        mock_worktrees.return_value = [
            {"path": "/home/code/Repo-feat", "branch": "feat"},
        ]
        mock_registry.return_value = []
        mock_has_plans.return_value = True

        result = cleanup_worktree_if_idle(
            "feat",
            Path("/home/code/Repo"),
            Path("/home/code/Repo"),
        )
        assert result["cleaned"] is False
        assert "live plans" in result["reason"]

    @patch("agenticcli.commands.worktree.update_workspace_remove")
    @patch("agenticcli.commands.worktree.find_workspace_file")
    @patch("subprocess.run")
    @patch("agenticcli.commands.session._is_process_running")
    @patch("agenticcli.commands.session._list_all_sessions")
    @patch("agenticcli.commands.worktree.worktree_has_live_plans")
    @patch("agenticcli.commands.worktree.load_worktree_registry")
    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    def test_cleans_up_idle_worktree(
        self,
        mock_worktrees,
        mock_registry,
        mock_has_plans,
        mock_sessions,
        mock_running,
        mock_subprocess,
        mock_workspace_file,
        mock_workspace_remove,
    ):
        """Removes worktree when no plans and no active sessions."""
        from agenticcli.commands.worktree import cleanup_worktree_if_idle

        mock_worktrees.return_value = [
            {"path": "/home/code/Repo-feat", "branch": "feat"},
        ]
        mock_registry.return_value = []
        mock_has_plans.return_value = False
        mock_sessions.return_value = []
        mock_running.return_value = False
        mock_subprocess.return_value = MagicMock(returncode=0)
        mock_workspace_file.return_value = None

        result = cleanup_worktree_if_idle(
            "feat",
            Path("/home/code/Repo"),
            Path("/home/code/Repo"),
        )
        assert result["cleaned"] is True
        assert result["path"] == "/home/code/Repo-feat"

    @patch("agenticcli.commands.session._is_process_running")
    @patch("agenticcli.commands.session._list_all_sessions")
    @patch("agenticcli.commands.worktree.worktree_has_live_plans")
    @patch("agenticcli.commands.worktree.load_worktree_registry")
    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    def test_skips_when_session_active(
        self,
        mock_worktrees,
        mock_registry,
        mock_has_plans,
        mock_sessions,
        mock_running,
    ):
        """Does not clean up worktree with active session."""
        from agenticcli.commands.worktree import cleanup_worktree_if_idle

        mock_worktrees.return_value = [
            {"path": "/home/code/Repo-feat", "branch": "feat"},
        ]
        mock_registry.return_value = []
        mock_has_plans.return_value = False
        mock_sessions.return_value = [
            {
                "session_id": "abc",
                "status": "running",
                "pid": 12345,
                "working_dir": "/home/code/Repo-feat",
            }
        ]
        mock_running.return_value = True

        result = cleanup_worktree_if_idle(
            "feat",
            Path("/home/code/Repo"),
            Path("/home/code/Repo"),
        )
        assert result["cleaned"] is False
        assert "active session" in result["reason"]


class TestGetPlanBranch:
    """Tests for _get_plan_branch helper function."""

    def test_extracts_branch_from_plan_build(self, tmp_path):
        """Extracts branch from plan_build.yml root-level field."""
        from agenticcli.commands.plan import _get_plan_branch

        plan_dir = tmp_path / "260208FA_feature_auth"
        plan_dir.mkdir()
        (plan_dir / "plan_build.yml").write_text(
            'name: "Feature Auth"\nbranch: "feat-auth"\nstatus: "active"\n'
        )

        result = _get_plan_branch(plan_dir)
        assert result == "feat-auth"

    def test_extracts_branch_from_nested_plan(self, tmp_path):
        """Extracts branch from nested plan: structure."""
        from agenticcli.commands.plan import _get_plan_branch

        plan_dir = tmp_path / "260208FA_feature_auth"
        plan_dir.mkdir()
        plan_content = {
            "plan": {
                "name": "Feature Auth",
                "branch": "feat-auth",
                "status": "active",
            }
        }
        with open(plan_dir / "plan_teach.yml", "w") as f:
            yaml.dump(plan_content, f)

        result = _get_plan_branch(plan_dir)
        assert result == "feat-auth"

    def test_extracts_branch_from_worktree_path(self, tmp_path):
        """Extracts branch from worktree_path field."""
        from agenticcli.commands.plan import _get_plan_branch

        plan_dir = tmp_path / "260208FA_feature_auth"
        plan_dir.mkdir()
        (plan_dir / "plan_build.yml").write_text(
            'name: "Feature Auth"\n'
            'worktree_path: "/home/code/AgenticEngineering-feat-auth"\n'
            'status: "active"\n'
        )

        result = _get_plan_branch(plan_dir)
        assert result == "feat-auth"

    def test_returns_none_for_empty_plan(self, tmp_path):
        """Returns None when no branch info is available."""
        from agenticcli.commands.plan import _get_plan_branch

        plan_dir = tmp_path / "260208XX_unknown"
        plan_dir.mkdir()
        # No plan files at all
        result = _get_plan_branch(plan_dir)
        assert result is None

    def test_ignores_main_branch(self, tmp_path):
        """Skips branch='main' as it's not a feature branch."""
        from agenticcli.commands.plan import _get_plan_branch

        plan_dir = tmp_path / "260208MA_main_plan"
        plan_dir.mkdir()
        (plan_dir / "plan_build.yml").write_text(
            'name: "Main Plan"\nbranch: "main"\nstatus: "active"\n'
        )

        result = _get_plan_branch(plan_dir)
        # Should not return "main" - falls through to other methods
        assert result != "main" or result is None

    def test_handles_yaml_parse_errors(self, tmp_path):
        """Gracefully handles malformed YAML."""
        from agenticcli.commands.plan import _get_plan_branch

        plan_dir = tmp_path / "260208XX_broken"
        plan_dir.mkdir()
        (plan_dir / "plan_build.yml").write_text(
            "invalid: yaml: [unclosed\n"
        )

        result = _get_plan_branch(plan_dir)
        # Should not raise, should return None
        assert result is None


class TestTryWorktreeCleanupAfterArchive:
    """Tests for _try_worktree_cleanup_after_archive function."""

    @patch("agenticcli.commands.plan._get_plan_branch")
    def test_skips_when_no_branch(self, mock_get_branch, tmp_path):
        """Does nothing when branch cannot be determined."""
        from agenticcli.commands.plan import _try_worktree_cleanup_after_archive

        mock_get_branch.return_value = None
        # Should not raise
        _try_worktree_cleanup_after_archive(tmp_path)

    @patch("agenticcli.commands.plan._get_plan_branch")
    def test_skips_main_branch(self, mock_get_branch, tmp_path):
        """Does nothing for main branch."""
        from agenticcli.commands.plan import _try_worktree_cleanup_after_archive

        mock_get_branch.return_value = "main"
        # Should not raise
        _try_worktree_cleanup_after_archive(tmp_path)

    @patch("agenticcli.commands.worktree.cleanup_worktree_if_idle")
    @patch("agenticcli.commands.plan.find_main_worktree")
    @patch("subprocess.run")
    @patch("agenticcli.commands.plan._get_plan_branch")
    def test_calls_cleanup_for_feature_branch(
        self, mock_get_branch, mock_subprocess, mock_find_main, mock_cleanup
    ):
        """Calls cleanup_worktree_if_idle for feature branches."""
        from agenticcli.commands.plan import _try_worktree_cleanup_after_archive

        mock_get_branch.return_value = "feat-auth"
        mock_subprocess.return_value = MagicMock(
            stdout="/home/code/Repo\n", returncode=0
        )
        mock_find_main.return_value = Path("/home/code/Repo")
        mock_cleanup.return_value = {"cleaned": False, "reason": "has plans"}

        _try_worktree_cleanup_after_archive(Path("/tmp/plan"))

        mock_cleanup.assert_called_once_with(
            "feat-auth",
            Path("/home/code/Repo"),
            Path("/home/code/Repo"),
        )
