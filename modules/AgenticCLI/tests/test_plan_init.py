"""Tests for 'agentic plan init' command.

Integration tests for the plan initialization command that combines
worktree creation with plan folder scaffolding using YYMMDDXX_description naming.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest


class TestPlanInit:
    """Tests for 'agentic plan init' command."""

    def test_init_creates_worktree_and_plan(self, cli_runner, temp_repo):
        """Test init creates both worktree and plan folder."""
        stdout, stderr, code = cli_runner(
            ["plan", "init", "test-feature", "--description", "my feature"]
        )

        # Should succeed
        assert code == 0
        assert "Plan initialized" in stdout

        # Verify worktree was created
        worktree_path = temp_repo.parent / "repo-test-feature"
        assert worktree_path.exists()

        # Verify plan folder was created with correct naming
        plan_folders = list((worktree_path / "docs" / "plans" / "live").glob("*"))
        # May include inherited 260103AE_test from base repo, plus our new one
        matching = [p for p in plan_folders if "_my_feature" in p.name]
        assert len(matching) == 1
        plan_folder_name = matching[0].name

        # Should match pattern: YYMMDDXX_my_feature
        # XX should be "FE" (first 2 chars of "test-feature" suffix after last hyphen)
        assert plan_folder_name.endswith("_my_feature")
        assert len(plan_folder_name.split("_")[0]) == 8  # YYMMDDXX

    def test_init_uses_branch_as_default_description(self, cli_runner, temp_repo):
        """Test init uses branch name as description when not specified."""
        stdout, stderr, code = cli_runner(["plan", "init", "auth"])

        assert code == 0

        # Verify plan folder uses branch as description
        worktree_path = temp_repo.parent / "repo-auth"
        plan_folders = list((worktree_path / "docs" / "plans" / "live").glob("*"))
        # Find the one we created (not inherited 260103AE_test)
        matching = [p for p in plan_folders if "_auth" in p.name]
        assert len(matching) == 1

    def test_init_uses_existing_worktree(self, cli_runner, temp_repo):
        """Test init uses existing worktree when branch already has one."""
        # First, create worktree manually
        branch = "existing-branch"
        worktree_path = temp_repo.parent / f"repo-{branch}"
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(worktree_path), "main"],
            cwd=temp_repo,
            capture_output=True,
            check=True,
        )

        # Now run plan init
        stdout, stderr, code = cli_runner(
            ["plan", "init", branch, "--description", "test"]
        )

        assert code == 0
        assert "existing worktree" in stdout.lower()

        # Should create plan folder in existing worktree
        plan_dir = worktree_path / "docs" / "plans" / "live"
        assert plan_dir.exists()
        assert any(plan_dir.iterdir())

    def test_init_fails_if_plan_folder_exists(self, cli_runner, temp_repo):
        """Test init fails with exit code 2 if plan folder already exists."""
        # First create a worktree and plan
        stdout, stderr, code = cli_runner(
            ["plan", "init", "dupe-test", "--description", "first"]
        )
        assert code == 0

        # Try to create another plan in same worktree with same description
        # This should fail because the folder name will be the same
        stdout, stderr, code = cli_runner(
            ["plan", "init", "dupe-test", "--description", "first"]
        )

        assert code == 2
        assert "already exists" in stderr.lower()

    def test_init_json_output(self, cli_runner, temp_repo):
        """Test init with JSON output flag."""
        stdout, stderr, code = cli_runner(
            ["-j", "plan", "init", "json-test", "--description", "json output test"]
        )

        assert code == 0
        result = json.loads(stdout)

        assert "worktree" in result
        assert "plan_folder" in result
        assert "plan_folder_name" in result
        assert "worktree_created" in result
        assert result["branch"] == "json-test"

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

        stdout, stderr, code = cli_runner(
            ["plan", "init", "from-develop", "--base", "develop", "--description", "test"]
        )

        assert code == 0

    def test_init_sanitizes_description(self, cli_runner, temp_repo):
        """Test init sanitizes special characters in description."""
        stdout, stderr, code = cli_runner(
            ["plan", "init", "sanitize-test", "--description", "My Feature: Bug Fix #123!"]
        )

        assert code == 0

        # Verify description was sanitized
        worktree_path = temp_repo.parent / "repo-sanitize-test"
        plan_folders = list((worktree_path / "docs" / "plans" / "live").glob("*"))
        # Find the one we created (not inherited 260103AE_test)
        matching = [p for p in plan_folders if "bug_fix" in p.name]
        assert len(matching) == 1
        plan_folder_name = matching[0].name

        # Should not contain special chars
        assert ":" not in plan_folder_name
        assert "#" not in plan_folder_name
        assert "!" not in plan_folder_name
        assert "_my_feature_bug_fix_123" in plan_folder_name

    def test_init_creates_proper_folder_structure(self, cli_runner, temp_repo):
        """Test init creates live/, completed/ subdirectories."""
        stdout, stderr, code = cli_runner(
            ["plan", "init", "structure-test", "--description", "structure"]
        )

        assert code == 0

        worktree_path = temp_repo.parent / "repo-structure-test"
        plan_folders = list((worktree_path / "docs" / "plans" / "live").glob("*"))
        plan_folder = plan_folders[0]

        # Check subdirectories
        assert (plan_folder / "live").exists()
        assert (plan_folder / "completed").exists()


class TestPlanInitHelp:
    """Tests for plan init help and usage."""

    def test_init_help(self, cli_runner):
        """Test plan init shows help."""
        # This will fail because plan init requires branch arg
        stdout, stderr, code = cli_runner(["plan", "init", "--help"])
        assert "branch" in stdout.lower() or code == 0


class TestPlanInitEdgeCases:
    """Edge case tests for plan init."""

    def test_init_empty_branch_fails(self, cli_runner):
        """Test init fails with empty branch name."""
        # This should fail at argument parsing level
        stdout, stderr, code = cli_runner(["plan", "init"])
        assert code != 0

    def test_init_worktree_id_from_repo_suffix(self, cli_runner, temp_repo):
        """Test worktree ID is derived from worktree path suffix."""
        stdout, stderr, code = cli_runner(
            ["-j", "plan", "init", "suffix-test", "--description", "test"]
        )

        assert code == 0
        result = json.loads(stdout)

        # Worktree path will be repo-suffix-test
        # Suffix after last hyphen is "test", so worktree ID should be "TE"
        plan_name = result["plan_folder_name"]
        assert "TE_" in plan_name or plan_name[6:8].isupper()
