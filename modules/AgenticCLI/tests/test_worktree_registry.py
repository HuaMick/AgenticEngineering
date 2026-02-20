"""Tests for worktree registry, naming fixes, and CLI flag updates.

Covers:
- WC_001: Registry loading from docs/worktrees.yml
- WC_002: Naming algorithm uses registry lookup with fallback
- WC_003: --abbreviation flag on worktree create saves to registry
- WC_004: worktree list shows plans from main worktree
- WC_005: plan init --objective writes objective to plan_build.yml
- WC_006: Comprehensive unit tests
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Registry loading tests (WC_001, WC_002)
# ---------------------------------------------------------------------------

class TestLoadWorktreeRegistry:
    """Tests for load_worktree_registry()."""

    def test_loads_registry_from_docs(self, tmp_path):
        """Registry loads correctly from docs/worktrees.yml."""
        from agenticcli.commands.worktree import load_worktree_registry

        registry_file = tmp_path / "docs" / "worktrees.yml"
        registry_file.parent.mkdir(parents=True)
        registry_file.write_text(yaml.dump({
            "worktrees": [
                {"branch": "agentic-cli", "abbreviation": "AC", "description": "CLI dev", "path": "/tmp/cli"},
                {"branch": "main", "abbreviation": "AE", "description": "Main", "path": "/tmp/main"},
            ]
        }))

        entries = load_worktree_registry(tmp_path)
        assert len(entries) == 2
        assert entries[0]["branch"] == "agentic-cli"
        assert entries[0]["abbreviation"] == "AC"

    def test_returns_empty_list_if_no_file(self, tmp_path):
        """Returns empty list when docs/worktrees.yml doesn't exist."""
        from agenticcli.commands.worktree import load_worktree_registry

        entries = load_worktree_registry(tmp_path)
        assert entries == []

    def test_returns_empty_list_on_invalid_yaml(self, tmp_path):
        """Returns empty list when YAML is invalid."""
        from agenticcli.commands.worktree import load_worktree_registry

        registry_file = tmp_path / "docs" / "worktrees.yml"
        registry_file.parent.mkdir(parents=True)
        registry_file.write_text(": invalid: yaml: [[[")

        entries = load_worktree_registry(tmp_path)
        assert entries == []

    def test_returns_empty_list_on_missing_key(self, tmp_path):
        """Returns empty list when YAML has no worktrees key."""
        from agenticcli.commands.worktree import load_worktree_registry

        registry_file = tmp_path / "docs" / "worktrees.yml"
        registry_file.parent.mkdir(parents=True)
        registry_file.write_text(yaml.dump({"other_key": "value"}))

        entries = load_worktree_registry(tmp_path)
        assert entries == []


class TestLookupAbbreviation:
    """Tests for lookup_abbreviation()."""

    def test_returns_abbreviation_for_known_branch(self):
        """Registry lookup returns correct abbreviation for known branch."""
        from agenticcli.commands.worktree import lookup_abbreviation

        registry = [
            {"branch": "agentic-cli", "abbreviation": "AC"},
            {"branch": "agenticguidance", "abbreviation": "AG"},
        ]
        assert lookup_abbreviation(registry, "agentic-cli") == "AC"
        assert lookup_abbreviation(registry, "agenticguidance") == "AG"

    def test_returns_none_for_unknown_branch(self):
        """Registry lookup returns None for unknown branch."""
        from agenticcli.commands.worktree import lookup_abbreviation

        registry = [{"branch": "agentic-cli", "abbreviation": "AC"}]
        assert lookup_abbreviation(registry, "unknown-branch") is None

    def test_returns_none_for_empty_registry(self):
        """Registry lookup returns None for empty registry."""
        from agenticcli.commands.worktree import lookup_abbreviation

        assert lookup_abbreviation([], "any-branch") is None


# ---------------------------------------------------------------------------
# Naming algorithm tests (WC_002)
# ---------------------------------------------------------------------------

class TestGeneratePlanFolderNameWithRegistry:
    """Tests for generate_plan_folder_name() with registry integration."""

    def test_uses_registry_abbreviation(self, tmp_path):
        """Uses abbreviation from registry when branch is found."""
        from agenticcli.utils.naming import generate_plan_folder_name

        # Set up registry
        registry_file = tmp_path / "docs" / "worktrees.yml"
        registry_file.parent.mkdir(parents=True)
        registry_file.write_text(yaml.dump({
            "worktrees": [
                {"branch": "my-feature", "abbreviation": "MF", "description": "My Feature"},
            ]
        }))

        name = generate_plan_folder_name(tmp_path, "my-feature", branch="my-feature")
        # Should use MF from registry, not fallback
        assert "MF_" in name
        assert name.endswith("_my_feature")

    def test_falls_back_to_capital_extraction(self, tmp_path):
        """Falls back to capital-letter extraction for unknown branch."""
        from agenticcli.utils.naming import generate_plan_folder_name

        # No registry file - should fall back
        name = generate_plan_folder_name(tmp_path, "unknown-branch")
        # tmp_path name is random, so just check the pattern
        assert name.endswith("_unknown_branch")
        assert len(name.split("_")[0]) == 8  # YYMMDDXX




# ---------------------------------------------------------------------------
# Save registry tests (WC_003)
# ---------------------------------------------------------------------------

class TestSaveWorktreeRegistry:
    """Tests for save_worktree_registry()."""

    def test_saves_registry(self, tmp_path):
        """Saves entries to docs/worktrees.yml."""
        from agenticcli.commands.worktree import save_worktree_registry, load_worktree_registry

        entries = [
            {"branch": "test-branch", "abbreviation": "TB", "description": "Test", "path": "/tmp/test"},
        ]
        result = save_worktree_registry(tmp_path, entries)
        assert result is True

        # Verify it was saved correctly
        loaded = load_worktree_registry(tmp_path)
        assert len(loaded) == 1
        assert loaded[0]["branch"] == "test-branch"
        assert loaded[0]["abbreviation"] == "TB"

    def test_creates_docs_directory_if_missing(self, tmp_path):
        """Creates docs/ directory if it doesn't exist."""
        from agenticcli.commands.worktree import save_worktree_registry

        entries = [{"branch": "b", "abbreviation": "BB"}]
        result = save_worktree_registry(tmp_path, entries)
        assert result is True
        assert (tmp_path / "docs" / "worktrees.yml").exists()


# ---------------------------------------------------------------------------
# Main-First Planning list tests (WC_004)
# ---------------------------------------------------------------------------

class TestMatchPlansToBranch:
    """Tests for _match_plans_to_branch()."""

    def test_matches_by_abbreviation(self):
        """Matches plan folders by abbreviation in positions 6-8."""
        from agenticcli.commands.worktree import _match_plans_to_branch

        plan_folders = ["260207AC_some_plan", "260207AG_other_plan", "260207XX_unrelated"]
        registry = [{"branch": "agentic-cli", "abbreviation": "AC"}]

        matches = _match_plans_to_branch(plan_folders, "agentic-cli", registry)
        assert matches == ["260207AC_some_plan"]

    def test_matches_by_branch_name(self):
        """Matches plan folders by branch name after underscore."""
        from agenticcli.commands.worktree import _match_plans_to_branch

        plan_folders = ["260207XX_my_feature", "260207YY_other"]
        registry = []

        matches = _match_plans_to_branch(plan_folders, "my_feature", registry)
        assert "260207XX_my_feature" in matches

    def test_no_matches_returns_empty(self):
        """Returns empty list when no plans match."""
        from agenticcli.commands.worktree import _match_plans_to_branch

        plan_folders = ["260207AC_some_plan"]
        registry = [{"branch": "unrelated", "abbreviation": "ZZ"}]

        matches = _match_plans_to_branch(plan_folders, "unrelated", registry)
        assert matches == []


class TestFindMainWorktreePath:
    """Tests for _find_main_worktree_path()."""

    def test_finds_main_branch(self):
        """Finds worktree with branch 'main'."""
        from agenticcli.commands.worktree import _find_main_worktree_path

        worktrees = [
            {"path": "/home/code/Repo", "branch": "main"},
            {"path": "/home/code/Repo-feature", "branch": "feature"},
        ]
        assert _find_main_worktree_path(worktrees) == "/home/code/Repo"

    def test_finds_master_branch(self):
        """Finds worktree with branch 'master'."""
        from agenticcli.commands.worktree import _find_main_worktree_path

        worktrees = [
            {"path": "/home/code/Repo", "branch": "master"},
        ]
        assert _find_main_worktree_path(worktrees) == "/home/code/Repo"

    def test_returns_none_when_no_main(self):
        """Returns None when no main/master branch found."""
        from agenticcli.commands.worktree import _find_main_worktree_path

        worktrees = [
            {"path": "/home/code/Repo-feat", "branch": "feat"},
        ]
        assert _find_main_worktree_path(worktrees) is None


# ---------------------------------------------------------------------------
# Plan init --objective tests (WC_005)
# ---------------------------------------------------------------------------

class TestPlanInitObjective:
    """Tests for plan init --objective writing plan_build.yml."""

    def test_init_with_objective_writes_plan_build(self, cli_runner, temp_repo):
        """plan init --objective writes objective to plan_build.yml."""
        import subprocess

        branch = "obj-test"
        # Create worktree first
        worktree_path = temp_repo.parent / f"repo-{branch}"
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(worktree_path), "main"],
            cwd=temp_repo, capture_output=True, check=True,
        )

        stdout, stderr, code = cli_runner(
            ["plan", "init", branch, "--description", "test objective", "--objective", "Build a better widget"]
        )

        assert code == 0

        # Find the plan folder in main worktree
        main_plans_dir = temp_repo / "docs" / "plans" / "live"
        matching = [p for p in main_plans_dir.iterdir() if "_test_objective" in p.name]
        assert len(matching) == 1

        plan_build = matching[0] / "plan_build.yml"
        assert plan_build.exists()

        content = plan_build.read_text()
        assert "Build a better widget" in content
        assert "active" in content

    def test_init_without_objective_no_plan_build_override(self, cli_runner, temp_repo):
        """plan init without --objective creates scaffolded plan_build.yml template (not custom one)."""
        import subprocess

        branch = "no-obj-test"
        worktree_path = temp_repo.parent / f"repo-{branch}"
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(worktree_path), "main"],
            cwd=temp_repo, capture_output=True, check=True,
        )

        stdout, stderr, code = cli_runner(
            ["plan", "init", branch, "--description", "no objective"]
        )

        assert code == 0

        # The plan_build.yml should NOT exist (only template files from create_planning_folder)
        main_plans_dir = temp_repo / "docs" / "plans" / "live"
        matching = [p for p in main_plans_dir.iterdir() if "_no_objective" in p.name]
        assert len(matching) == 1

        # plan_teach.yml should exist (from template), but plan_build.yml should be
        # either the template or not contain custom objective
        plan_folder = matching[0]
        plan_build = plan_folder / "plan_build.yml"
        if plan_build.exists():
            content = plan_build.read_text()
            # Should NOT contain a custom objective
            assert "Build a better widget" not in content

    def test_init_objective_in_json_output(self, cli_runner, temp_repo):
        """plan init --objective includes objective in JSON output."""
        import json
        import subprocess

        branch = "json-obj-test"
        worktree_path = temp_repo.parent / f"repo-{branch}"
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(worktree_path), "main"],
            cwd=temp_repo, capture_output=True, check=True,
        )

        stdout, stderr, code = cli_runner(
            ["-j", "plan", "init", branch, "--description", "json obj", "--objective", "Test objective"]
        )

        assert code == 0
        result = json.loads(stdout)
        assert result.get("objective") == "Test objective"


# ---------------------------------------------------------------------------
# get_worktree_id with registry support tests (naming.py)
# ---------------------------------------------------------------------------

class TestGetWorktreeIdWithRegistry:
    """Tests for get_worktree_id() in naming.py with registry support."""

    def test_path_based_fallback_still_works(self):
        """Original path-based ID extraction still works without branch."""
        from agenticcli.utils.naming import get_worktree_id

        assert get_worktree_id(Path("/home/code/AgenticEngineering-agenticguidance")) == "AG"
        assert get_worktree_id(Path("/home/code/AgenticEngineering-agentic-cli")) == "CL"
        assert get_worktree_id(Path("/home/code/MyProject")) == "MY"

    def test_registry_lookup_with_branch(self, tmp_path):
        """Uses registry abbreviation when branch is provided."""
        from agenticcli.utils.naming import get_worktree_id

        # Set up registry in tmp_path
        registry_file = tmp_path / "docs" / "worktrees.yml"
        registry_file.parent.mkdir(parents=True)
        registry_file.write_text(yaml.dump({
            "worktrees": [
                {"branch": "my-feature", "abbreviation": "MF"},
            ]
        }))

        result = get_worktree_id(tmp_path, branch="my-feature")
        assert result == "MF"

    def test_falls_back_to_path_when_branch_not_in_registry(self, tmp_path):
        """Falls back to path-based ID when branch not in registry."""
        from agenticcli.utils.naming import get_worktree_id

        # Set up registry without the target branch
        registry_file = tmp_path / "docs" / "worktrees.yml"
        registry_file.parent.mkdir(parents=True)
        registry_file.write_text(yaml.dump({
            "worktrees": [
                {"branch": "other", "abbreviation": "OT"},
            ]
        }))

        # tmp_path name varies, just verify it's a 2-char string
        result = get_worktree_id(tmp_path, branch="unknown")
        assert len(result) == 2
        assert result.isupper()
