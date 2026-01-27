"""Tests for context service."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agenticguidance.services.context import (
    MainFirstPlanResolver,
    get_role_process,
    get_role_inputs_manifest,
    generate_agent_bootstrap,
    _find_agents_directory,
)


class TestMainFirstPlanResolver:
    """Tests for MainFirstPlanResolver class."""

    def test_init_defaults_to_cwd(self):
        """Test resolver defaults to current working directory."""
        resolver = MainFirstPlanResolver()
        assert resolver.cwd == Path.cwd()

    def test_init_accepts_custom_cwd(self, tmp_path):
        """Test resolver accepts custom working directory."""
        resolver = MainFirstPlanResolver(cwd=tmp_path)
        assert resolver.cwd == tmp_path

    @patch("subprocess.run")
    def test_find_main_worktree_caches_result(self, mock_run):
        """Test main worktree is cached after first lookup."""
        mock_run.return_value = MagicMock(
            stdout="worktree /home/test/project\nHEAD abc123\nbranch refs/heads/main\n",
            returncode=0,
        )

        resolver = MainFirstPlanResolver()
        result1 = resolver.find_main_worktree()
        result2 = resolver.find_main_worktree()

        assert result1 == result2
        assert mock_run.call_count == 1  # Only called once due to caching

    @patch("subprocess.run")
    def test_find_main_worktree_returns_path_for_main(self, mock_run):
        """Test returns path when main branch worktree found."""
        mock_run.return_value = MagicMock(
            stdout="worktree /home/test/project\nHEAD abc123\nbranch refs/heads/main\n",
            returncode=0,
        )

        resolver = MainFirstPlanResolver()
        result = resolver.find_main_worktree()

        assert result == Path("/home/test/project")

    @patch("subprocess.run")
    def test_find_main_worktree_returns_path_for_master(self, mock_run):
        """Test returns path when master branch worktree found."""
        mock_run.return_value = MagicMock(
            stdout="worktree /home/test/project\nHEAD abc123\nbranch refs/heads/master\n",
            returncode=0,
        )

        resolver = MainFirstPlanResolver()
        result = resolver.find_main_worktree()

        assert result == Path("/home/test/project")

    @patch("subprocess.run")
    def test_find_main_worktree_returns_none_when_not_found(self, mock_run):
        """Test returns None when no main/master worktree."""
        mock_run.return_value = MagicMock(
            stdout="worktree /home/test/feature\nHEAD abc123\nbranch refs/heads/feature\n",
            returncode=0,
        )

        resolver = MainFirstPlanResolver()
        result = resolver.find_main_worktree()

        assert result is None

    @patch("subprocess.run")
    def test_find_main_worktree_handles_git_error(self, mock_run):
        """Test handles git command failure gracefully."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        resolver = MainFirstPlanResolver()
        result = resolver.find_main_worktree()

        assert result is None

    @patch("subprocess.run")
    def test_get_current_branch_returns_branch_name(self, mock_run):
        """Test returns current branch name."""
        mock_run.return_value = MagicMock(stdout="feature-branch\n", returncode=0)

        resolver = MainFirstPlanResolver()
        result = resolver.get_current_branch()

        assert result == "feature-branch"

    @patch("subprocess.run")
    def test_get_current_branch_caches_result(self, mock_run):
        """Test branch name is cached."""
        mock_run.return_value = MagicMock(stdout="main\n", returncode=0)

        resolver = MainFirstPlanResolver()
        result1 = resolver.get_current_branch()
        result2 = resolver.get_current_branch()

        assert result1 == result2
        assert mock_run.call_count == 1

    @patch("subprocess.run")
    def test_get_current_branch_handles_error(self, mock_run):
        """Test handles git error gracefully."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        resolver = MainFirstPlanResolver()
        result = resolver.get_current_branch()

        assert result is None

    def test_extract_all_tasks_returns_empty_for_missing_folder(self, tmp_path):
        """Test returns empty list when live folder doesn't exist."""
        resolver = MainFirstPlanResolver()
        result = resolver.extract_all_tasks(tmp_path)

        assert result == []

    def test_extract_all_tasks_parses_plan_file(self, tmp_path):
        """Test extracts tasks from plan YAML files (flattened structure)."""
        # Flattened: plan files directly in tmp_path
        plan_content = """
phases:
  - name: "Build Phase"
    id: "phase_1"
    tasks:
      - id: "task_001"
        name: "First task"
        description: "Do something"
        status: "pending"
"""
        (tmp_path / "plan_build.yml").write_text(plan_content)

        resolver = MainFirstPlanResolver()
        tasks = resolver.extract_all_tasks(tmp_path)

        assert len(tasks) == 1
        assert tasks[0]["id"] == "task_001"
        assert tasks[0]["name"] == "First task"
        assert tasks[0]["status"] == "pending"
        assert tasks[0]["phase"] == "Build Phase"

    def test_extract_current_task_returns_in_progress_first(self, tmp_path):
        """Test returns in_progress task over pending (flattened structure)."""
        # Flattened: plan files directly in tmp_path
        plan_content = """
phases:
  - name: "Build"
    tasks:
      - id: "task_001"
        name: "Pending task"
        status: "pending"
      - id: "task_002"
        name: "In progress task"
        status: "in_progress"
"""
        (tmp_path / "plan_build.yml").write_text(plan_content)

        resolver = MainFirstPlanResolver()
        task = resolver.extract_current_task(tmp_path)

        assert task["id"] == "task_002"
        assert task["status"] == "in_progress"

    def test_extract_current_task_returns_first_pending(self, tmp_path):
        """Test returns first pending when no in_progress (flattened structure)."""
        # Flattened: plan files directly in tmp_path
        plan_content = """
phases:
  - name: "Build"
    tasks:
      - id: "task_001"
        name: "First pending"
        status: "pending"
      - id: "task_002"
        name: "Second pending"
        status: "pending"
"""
        (tmp_path / "plan_build.yml").write_text(plan_content)

        resolver = MainFirstPlanResolver()
        task = resolver.extract_current_task(tmp_path)

        assert task["id"] == "task_001"


class TestGetRoleProcess:
    """Tests for get_role_process function."""

    @patch("agenticguidance.services.context._find_agents_directory")
    def test_returns_none_when_agents_dir_not_found(self, mock_find):
        """Test returns None when agents directory not found."""
        mock_find.return_value = None

        result = get_role_process("planner-build")

        assert result is None

    @patch("agenticguidance.services.context._find_agents_directory")
    def test_returns_none_when_agent_not_found(self, mock_find, tmp_path):
        """Test returns None when specific agent not found."""
        mock_find.return_value = tmp_path

        result = get_role_process("nonexistent-agent")

        assert result is None


class TestGetRoleInputsManifest:
    """Tests for get_role_inputs_manifest function."""

    @patch("agenticguidance.services.context._find_agents_directory")
    def test_returns_none_when_agents_dir_not_found(self, mock_find):
        """Test returns None when agents directory not found."""
        mock_find.return_value = None

        result = get_role_inputs_manifest("planner-build")

        assert result is None

    @patch("agenticguidance.services.context._find_agents_directory")
    def test_returns_empty_manifest_when_no_inputs_file(self, mock_find, tmp_path):
        """Test returns empty manifest when inputs.yml doesn't exist."""
        agent_dir = tmp_path / "planner" / "planner-build"
        agent_dir.mkdir(parents=True)
        mock_find.return_value = tmp_path

        result = get_role_inputs_manifest("planner-build")

        assert result == {"role": "planner-build", "inputs": [], "missing": []}
