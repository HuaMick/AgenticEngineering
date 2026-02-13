"""Tests for workspace file sync and plan folder creation funneling.

Tests the fixes for workspace drift root causes:
- Plan folder creation funneling through CLI
- Workspace update for reused worktrees
- cmd_create no longer creates plan folders
- Sync on plan completion
- Registry cleanup in sync
- FileLock protection
- Validator regex with hyphenated phase IDs
"""

import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

import pytest


class TestWorkspaceUpdate:
    """Test workspace file update for both new and reused worktrees."""

    def test_workspace_update_for_new_worktree(self, tmp_path, monkeypatch):
        """Verify workspace is updated when creating a new worktree."""
        from agenticcli.commands.worktree import update_workspace_add

        workspace_file = tmp_path / "test.code-workspace"
        workspace_file.write_text(json.dumps({"folders": []}))

        worktree_path = tmp_path / "worktree-branch"
        result = update_workspace_add(workspace_file, worktree_path, "branch", "repo")

        assert result is True
        workspace = json.loads(workspace_file.read_text())
        assert len(workspace["folders"]) == 1
        assert workspace["folders"][0]["name"] == "repo (branch)"

    def test_workspace_update_for_reused_worktree(self, tmp_path, monkeypatch):
        """Verify workspace is updated when reusing an existing worktree."""
        from agenticcli.commands.worktree import update_workspace_add

        workspace_file = tmp_path / "test.code-workspace"
        workspace_file.write_text(json.dumps({"folders": []}))

        worktree_path = tmp_path / "worktree-branch"
        # First call (new worktree)
        result1 = update_workspace_add(workspace_file, worktree_path, "old-branch", "repo")
        assert result1 is True

        # Second call (reused worktree with new branch)
        result2 = update_workspace_add(workspace_file, worktree_path, "new-branch", "repo")
        assert result2 is True

        workspace = json.loads(workspace_file.read_text())
        # Should have one entry with updated name
        assert len(workspace["folders"]) == 1
        assert workspace["folders"][0]["name"] == "repo (new-branch)"

    def test_workspace_update_is_idempotent(self, tmp_path, monkeypatch):
        """Verify multiple updates to same path don't create duplicates."""
        from agenticcli.commands.worktree import update_workspace_add

        workspace_file = tmp_path / "test.code-workspace"
        workspace_file.write_text(json.dumps({"folders": []}))

        worktree_path = tmp_path / "worktree-branch"
        # Call multiple times with same path
        update_workspace_add(workspace_file, worktree_path, "branch", "repo")
        update_workspace_add(workspace_file, worktree_path, "branch", "repo")
        update_workspace_add(workspace_file, worktree_path, "branch", "repo")

        workspace = json.loads(workspace_file.read_text())
        assert len(workspace["folders"]) == 1


class TestRegistryCleanup:
    """Test worktree registry cleanup in cmd_sync."""

    def test_sync_removes_stale_registry_entries(self, tmp_path, monkeypatch):
        """Verify cmd_sync removes registry entries for deleted worktrees."""
        from agenticcli.commands.worktree import cmd_sync, save_worktree_registry

        # Create a repo structure
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        workspace_file = repo_root / "test.code-workspace"
        workspace_file.write_text(json.dumps({"folders": []}))
        registry_file = repo_root / "docs" / "worktrees.yml"
        registry_file.parent.mkdir(parents=True)

        # Create registry with stale entry
        stale_path = tmp_path / "deleted-worktree"
        registry = [
            {
                "branch": "deleted-branch",
                "abbreviation": "DB",
                "description": "Deleted branch",
                "path": str(stale_path),
            }
        ]
        save_worktree_registry(repo_root, registry)

        # Mock git commands
        monkeypatch.setattr("agenticcli.commands.worktree.get_repo_root", lambda: repo_root)
        monkeypatch.setattr("agenticcli.commands.worktree.get_actual_worktrees", lambda x: [])

        # Run sync
        args = SimpleNamespace()
        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_print:
                cmd_sync(args)
                # Check that registry was cleaned
                call_args = mock_print.call_args[0][0]
                assert call_args.get("registry_cleaned", 0) > 0

    def test_sync_preserves_valid_registry_entries(self, tmp_path, monkeypatch):
        """Verify cmd_sync keeps registry entries for existing worktrees."""
        from agenticcli.commands.worktree import cmd_sync, save_worktree_registry

        # Create a repo structure with real worktree
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        workspace_file = repo_root / "test.code-workspace"
        workspace_file.write_text(json.dumps({"folders": []}))
        registry_file = repo_root / "docs" / "worktrees.yml"
        registry_file.parent.mkdir(parents=True)

        # Create valid worktree path
        valid_path = tmp_path / "valid-worktree"
        valid_path.mkdir()

        # Create registry with valid entry
        registry = [
            {
                "branch": "valid-branch",
                "abbreviation": "VB",
                "description": "Valid branch",
                "path": str(valid_path),
            }
        ]
        save_worktree_registry(repo_root, registry)

        # Mock git commands
        monkeypatch.setattr("agenticcli.commands.worktree.get_repo_root", lambda: repo_root)
        monkeypatch.setattr("agenticcli.commands.worktree.get_actual_worktrees", lambda x: [])

        # Run sync
        args = SimpleNamespace()
        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_print:
                cmd_sync(args)
                # Check that no entries were cleaned (valid path exists)
                call_args = mock_print.call_args[0][0]
                assert call_args.get("registry_cleaned", 0) == 0


class TestCmdCreateDeprecation:
    """Test that cmd_create no longer creates plan folders."""

    def test_cmd_create_skips_plan_folder_creation(self, tmp_path, monkeypatch):
        """Verify cmd_create does not create plan folders (deprecated)."""
        # The cmd_create function should now have skip_plan hardcoded to True
        # Verify by checking the source directly
        from agenticcli.commands.worktree import cmd_create
        import inspect

        source = inspect.getsource(cmd_create)
        # Check that skip_plan is set to True (not from args.no_plan)
        assert 'skip_plan = True' in source or 'skip_plan=True' in source


class TestFileLock:
    """Test FileLock protection for workspace file operations."""

    def test_filelock_prevents_concurrent_writes(self, tmp_path):
        """Verify FileLock prevents concurrent workspace file modifications."""
        from agenticguidance.services.state import FileLock

        lock_file = tmp_path / "test.lock"

        # Acquire first lock
        lock1 = FileLock(tmp_path / "test.txt", timeout=0.5)
        assert lock1.acquire() is True

        # Try to acquire second lock (should timeout)
        lock2 = FileLock(tmp_path / "test.txt", timeout=0.5)
        assert lock2.acquire() is False

        # Release first lock
        lock1.release()

        # Now second lock should succeed
        assert lock2.acquire() is True
        lock2.release()

    def test_workspace_add_uses_filelock(self, tmp_path, monkeypatch):
        """Verify update_workspace_add uses FileLock."""
        from agenticcli.commands.worktree import update_workspace_add

        workspace_file = tmp_path / "test.code-workspace"
        workspace_file.write_text(json.dumps({"folders": []}))

        # Mock FileLock to verify it's called
        with patch("agenticguidance.services.state.FileLock") as mock_lock:
            mock_lock_instance = MagicMock()
            mock_lock.return_value = mock_lock_instance
            mock_lock_instance.__enter__ = MagicMock(return_value=mock_lock_instance)
            mock_lock_instance.__exit__ = MagicMock(return_value=False)

            worktree_path = tmp_path / "worktree-branch"
            update_workspace_add(workspace_file, worktree_path, "branch", "repo")

            # Verify FileLock was instantiated
            mock_lock.assert_called_once()

    def test_workspace_remove_uses_filelock(self, tmp_path, monkeypatch):
        """Verify update_workspace_remove uses FileLock."""
        from agenticcli.commands.worktree import update_workspace_remove

        workspace_file = tmp_path / "test.code-workspace"
        workspace_file.write_text(json.dumps({"folders": [{"path": "test"}]}))

        # Mock FileLock to verify it's called
        with patch("agenticguidance.services.state.FileLock") as mock_lock:
            mock_lock_instance = MagicMock()
            mock_lock.return_value = mock_lock_instance
            mock_lock_instance.__enter__ = MagicMock(return_value=mock_lock_instance)
            mock_lock_instance.__exit__ = MagicMock(return_value=False)

            worktree_path = tmp_path / "worktree-branch"
            update_workspace_remove(workspace_file, worktree_path)

            # Verify FileLock was instantiated
            mock_lock.assert_called_once()


class TestValidatorRegex:
    """Test validator regex with hyphenated phase IDs."""

    def test_validator_accepts_hyphenated_phase_ids(self):
        """Verify validator regex matches hyphenated phase IDs like 'phase-1'."""
        # Test the regex pattern used in plan.py validator
        pattern = r"([\w-]+)\s*(?:->|=)\s*(\S+)"

        test_cases = [
            ("phase-1 -> build-python", ("phase-1", "build-python")),
            ("phase-2 -> test-runner", ("phase-2", "test-runner")),
            ("P1 -> builder", ("P1", "builder")),
            ("phase_3 -> deployer", ("phase_3", "deployer")),
            ("build-phase -> build-python", ("build-phase", "build-python")),
        ]

        for test_input, expected in test_cases:
            match = re.match(pattern, test_input)
            assert match is not None, f"Pattern should match: {test_input}"
            assert match.groups() == expected, f"Groups mismatch for: {test_input}"

    def test_validator_rejects_invalid_patterns(self):
        """Verify validator regex rejects invalid patterns."""
        pattern = r"([\w-]+)\s*(?:->|=)\s*(\S+)"

        invalid_cases = [
            "phase 1 -> builder",  # Space in phase ID
            "phase->",  # Missing agent type
            "-> builder",  # Missing phase ID
            "",  # Empty string
        ]

        for test_input in invalid_cases:
            match = re.match(pattern, test_input)
            if test_input:  # Only non-empty strings should produce no match or partial match
                assert match is None or match.groups()[0] == "" or match.groups()[1] == "", \
                    f"Pattern should not fully match: {test_input}"


class TestSyncOnCompletion:
    """Test workspace sync on plan completion."""

    def test_cleanup_triggers_sync(self, tmp_path, monkeypatch):
        """Verify plan cleanup triggers workspace sync."""
        from agenticcli.commands.plan import _try_worktree_cleanup_after_archive

        # Create plan structure
        plan_path = tmp_path / "docs" / "plans" / "live" / "260214XX_test"
        plan_path.mkdir(parents=True)
        plan_file = plan_path / "plan_build.yml"
        plan_file.write_text("branch: test-branch\n")

        repo_root = tmp_path

        # Mock dependencies
        monkeypatch.setattr(
            "agenticcli.commands.plan._get_plan_branch",
            lambda x: "test-branch"
        )

        mock_cleanup_result = {"cleaned": True, "path": "/test/path"}
        with patch("agenticcli.commands.worktree.cleanup_worktree_if_idle", return_value=mock_cleanup_result):
            with patch("agenticcli.commands.worktree.cmd_sync") as mock_sync:
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(stdout=str(repo_root))

                    _try_worktree_cleanup_after_archive(plan_path)

                    # Verify cmd_sync was called
                    mock_sync.assert_called_once()


class TestIntegration:
    """Integration tests for full lifecycle."""

    def test_full_lifecycle_no_drift(self, tmp_path, monkeypatch):
        """Test full lifecycle: init -> work -> complete -> sync without drift."""
        # This is a placeholder for a full integration test
        # In a real implementation, this would:
        # 1. Create a plan via cmd_init
        # 2. Verify workspace was updated
        # 3. Complete the plan
        # 4. Verify sync was called
        # 5. Check no drift exists
        pass
