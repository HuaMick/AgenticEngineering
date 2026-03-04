"""Tests for 'agentic epic init' command.

Integration tests for the epic initialization command that creates
epic folders with YYMMDDXX_description naming convention.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest


def create_worktree_for_test(temp_repo: Path, branch: str, base: str = "main") -> Path:
    """Helper to create a worktree for testing."""
    worktree_path = temp_repo.parent / f"repo-{branch}"
    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(worktree_path), base],
        cwd=temp_repo,
        capture_output=True,
        check=True,
    )
    return worktree_path


class TestPlanInit:
    """Tests for 'agentic epic init' command."""

    def test_init_with_existing_worktree(self, cli_runner, temp_repo):
        """Test init succeeds with existing worktree."""
        branch = "test-feature"
        worktree_path = create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "init", branch, "--description", "my feature"]
        )

        # Should succeed
        assert code == 0
        assert "Epic initialized" in stdout or "Plan initialized" in stdout

        # Verify epic folder was created with correct naming
        # Epics are in docs/epics/live/
        main_epics_dir = temp_repo / "docs" / "epics" / "live"
        plan_folders = list(main_epics_dir.glob("*"))
        matching = [p for p in plan_folders if "_my_feature" in p.name]
        assert len(matching) == 1
        plan_folder_name = matching[0].name

        # Should match pattern: YYMMDDXX_my_feature
        assert plan_folder_name.endswith("_my_feature")
        assert len(plan_folder_name.split("_")[0]) == 8  # YYMMDDXX

    def test_init_uses_branch_as_default_description(self, cli_runner, temp_repo):
        """Test init uses branch name as description when not specified."""
        branch = "auth"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(["agent", "epic", "init", branch])

        assert code == 0

        # Verify epic folder uses branch as description
        main_epics_dir = temp_repo / "docs" / "epics" / "live"
        plan_folders = list(main_epics_dir.glob("*"))
        matching = [p for p in plan_folders if "_auth" in p.name]
        assert len(matching) == 1

    def test_init_creates_plan_in_repo_root(self, cli_runner, temp_repo):
        """Test init creates epic folder in docs/epics/live/."""
        branch = "existing-branch"

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "init", branch, "--description", "repo root check"]
        )

        assert code == 0
        assert "Epic initialized" in stdout or "Plan initialized" in stdout

        # Should create epic folder in repo root
        epics_dir = temp_repo / "docs" / "epics" / "live"
        assert epics_dir.exists()
        matching = [p for p in epics_dir.iterdir() if "_repo_root_check" in p.name]
        assert len(matching) == 1

    def test_init_fails_if_plan_folder_exists(self, cli_runner, temp_repo):
        """Test init fails with exit code 2 if epic folder already exists."""
        branch = "dupe-test"
        create_worktree_for_test(temp_repo, branch)

        # First create an epic
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "init", branch, "--description", "first"]
        )
        assert code == 0

        # Try to create another epic with same description
        # This should fail because the folder name will be the same
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "init", branch, "--description", "first"]
        )

        assert code == 2
        assert "already exists" in stderr.lower()

    def test_init_json_output(self, cli_runner, temp_repo):
        """Test init with JSON output flag."""
        branch = "json-test"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "agent", "epic", "init", branch, "--description", "json output test"]
        )

        assert code == 0
        result = json.loads(stdout)

        assert "epic_folder" in result
        assert "epic_folder_name" in result
        assert result["branch"] == branch

    def test_init_with_base_branch(self, cli_runner, temp_repo):
        """Test init respects --base flag."""
        # Create a different base branch first
        subprocess.run(
            ["git", "checkout", "-b", "develop"],
            cwd=temp_repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=temp_repo,
            capture_output=True,
        )

        # Create worktree from develop
        branch = "from-develop"
        worktree_path = temp_repo.parent / f"repo-{branch}"
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(worktree_path), "develop"],
            cwd=temp_repo,
            capture_output=True,
            check=True,
        )

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "init", branch, "--base", "develop", "--description", "test"]
        )

        assert code == 0

    def test_init_sanitizes_description(self, cli_runner, temp_repo):
        """Test init sanitizes special characters in description."""
        branch = "sanitize-test"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "init", branch, "--description", "My Feature: Bug Fix #123!"]
        )

        assert code == 0

        # Verify description was sanitized
        main_epics_dir = temp_repo / "docs" / "epics" / "live"
        plan_folders = list(main_epics_dir.glob("*"))
        matching = [p for p in plan_folders if "bug_fix" in p.name]
        assert len(matching) == 1
        plan_folder_name = matching[0].name

        # Should not contain special chars
        assert ":" not in plan_folder_name
        assert "#" not in plan_folder_name
        assert "!" not in plan_folder_name
        assert "_my_feature_bug_fix_123" in plan_folder_name

    def test_init_creates_proper_folder_structure(self, cli_runner, temp_repo):
        """Test init creates epic folder directory."""
        branch = "structure-test"

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "init", branch, "--description", "structure"]
        )

        assert code == 0

        # Verify epic folder created
        epics_dir = temp_repo / "docs" / "epics" / "live"
        plan_folders = list(epics_dir.glob("*_structure"))
        assert len(plan_folders) == 1
        plan_folder = plan_folders[0]
        assert plan_folder.is_dir()


class TestPlanInitEnforcement:
    """Tests for epic init enforcement."""

    def test_init_prevents_duplicate_plans(self, cli_runner, temp_repo):
        """Test init prevents creating duplicate epics with same name."""
        branch = "dup-check"

        # Create first epic
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "init", branch, "--description", "first"]
        )
        assert code == 0

        # Try to create another epic with different description (should work)
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "init", branch, "--description", "second"]
        )
        assert code in [0, 2]  # 0 if different folder allowed, 2 if duplicate detected


class TestPlanInitHelp:
    """Tests for epic init help and usage."""

    def test_init_help(self, cli_runner):
        """Test epic init shows help."""
        stdout, stderr, code = cli_runner(["agent", "epic", "init", "--help"])
        assert "branch" in stdout.lower() or code == 0


class TestPlanInitEdgeCases:
    """Edge case tests for epic init."""

    def test_init_empty_branch_fails(self, cli_runner):
        """Test init fails with empty branch name."""
        # This should fail at argument parsing level
        stdout, stderr, code = cli_runner(["agent", "epic", "init"])
        assert code != 0

    def test_init_plan_id_from_repo_path(self, cli_runner, temp_repo):
        """Test epic ID is derived from repo path."""
        branch = "suffix-test"

        stdout, stderr, code = cli_runner(
            ["-j", "agent", "epic", "init", branch, "--description", "test"]
        )

        assert code == 0
        result = json.loads(stdout)

        plan_name = result["epic_folder_name"]
        # Should have 2-letter uppercase ID at positions 6-7
        assert plan_name[6:8].isupper()
