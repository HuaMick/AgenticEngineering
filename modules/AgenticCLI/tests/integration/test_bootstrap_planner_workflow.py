"""Integration test for bootstrap to planner workflow.

Tests the end-to-end workflow:
1. Bootstrap a new plan with 'agentic plan bootstrap'
2. Load planner context
3. Verify planner can access the plan files
"""

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # Create initial commit
    (repo_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # Create docs/epics/live directory structure
    plans_dir = repo_path / "docs" / "epics" / "live"
    plans_dir.mkdir(parents=True, exist_ok=True)

    return repo_path


@pytest.fixture
def mock_git_context(temp_git_repo, monkeypatch):
    """Mock git utility functions and subprocess to use temp repo.

    Patches both the utility functions AND the subprocess calls used
    by cmd_init so all operations target the temp repo.
    """
    from agenticcli.utils import git

    monkeypatch.setattr(git, "get_project_root", lambda: temp_git_repo)

    # Wrap subprocess.run to redirect git rev-parse to the temp repo
    real_subprocess_run = subprocess.run

    def patched_subprocess_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and cmd[:2] == ["git", "rev-parse"]:
            # Override --show-toplevel to return temp repo
            if "--show-toplevel" in cmd:
                result = MagicMock()
                result.stdout = str(temp_git_repo) + "\n"
                result.stderr = ""
                result.returncode = 0
                return result
        return real_subprocess_run(cmd, *args, **kwargs)

    monkeypatch.setattr("agenticcli.commands.epic.subprocess.run", patched_subprocess_run)

    return temp_git_repo


class TestBootstrapPlannerWorkflow:
    """Integration tests for bootstrap to planner workflow."""

    def test_bootstrap_creates_planner_readable_plan(self, mock_git_context):
        """Test that bootstrap creates a plan that planner can read."""
        from agenticcli.commands import epic as plan

        # Bootstrap a plan
        args = SimpleNamespace(
            branch="test-feature",
            objective="Implement test feature for workflow",
            description="workflow test",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        # Find the created plan
        plans_dir = mock_git_context / "docs" / "epics" / "live"
        plan_folders = list(plans_dir.glob("*_workflow_test"))
        assert len(plan_folders) == 1
        plan_folder = plan_folders[0]

        # Flattened structure: plan_build.yml directly in plan folder
        plan_build_file = plan_folder / "plan_build.yml"
        assert plan_build_file.exists()

        with open(plan_build_file) as f:
            plan_data = yaml.safe_load(f)

        # Verify planner can access expected fields
        assert "context" in plan_data
        assert "phases" in plan_data
        assert plan_data["context"].strip() == "Implement test feature for workflow"

    def test_bootstrap_plan_has_initial_tasks(self, mock_git_context):
        """Test that bootstrapped plan has initial tasks for planner."""
        from agenticcli.commands import epic as plan

        args = SimpleNamespace(
            branch="tasks-test",
            objective="Test initial tasks",
            description="tasks test",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        plans_dir = mock_git_context / "docs" / "epics" / "live"
        plan_folders = list(plans_dir.glob("*_tasks_test"))
        plan_folder = plan_folders[0]

        # Flattened structure
        plan_build_file = plan_folder / "plan_build.yml"
        with open(plan_build_file) as f:
            plan_data = yaml.safe_load(f)

        # Planner needs initial tasks to start planning
        assert "phases" in plan_data
        assert len(plan_data["phases"]) > 0
        assert "tickets" in plan_data["phases"][0]
        assert len(plan_data["phases"][0]["tickets"]) > 0

        # Verify task structure
        first_task = plan_data["phases"][0]["tickets"][0]
        assert "id" in first_task
        assert "name" in first_task
        assert "status" in first_task

    def test_bootstrap_provides_planner_spawn_hint(self, mock_git_context, capsys):
        """Test that bootstrap output includes hint for spawning planner."""
        from agenticcli.commands import epic as plan

        args = SimpleNamespace(
            branch="hint-test",
            objective="Test planner hint",
            description="hint test",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            plan.cmd_bootstrap(args)

        captured = capsys.readouterr()
        # Should suggest how to spawn planner agent
        assert "planner" in captured.out.lower() or "agent" in captured.out.lower()

    def test_bootstrap_plan_folder_structure_valid(self, mock_git_context):
        """Test that bootstrapped plan folder structure is valid for planner."""
        from agenticcli.commands import epic as plan

        args = SimpleNamespace(
            branch="structure-test",
            objective="Test folder structure",
            description="structure valid",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        plans_dir = mock_git_context / "docs" / "epics" / "live"
        plan_folders = list(plans_dir.glob("*_structure_valid"))
        plan_folder = plan_folders[0]

        # Verify expected flattened structure
        assert plan_folder.is_dir()
        assert (plan_folder / "plan_build.yml").is_file()

    def test_multiple_bootstrap_plans_coexist(self, mock_git_context):
        """Test that multiple bootstrapped plans can coexist for planner."""
        from agenticcli.commands import epic as plan

        # Bootstrap first plan
        args1 = SimpleNamespace(
            branch="plan1",
            objective="First plan",
            description="plan one",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args1)

        # Bootstrap second plan (different branch)
        args2 = SimpleNamespace(
            branch="plan2",
            objective="Second plan",
            description="plan two",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args2)

        # Both plans should exist
        plans_dir = mock_git_context / "docs" / "epics" / "live"
        plan1_folders = list(plans_dir.glob("*_plan_one"))
        plan2_folders = list(plans_dir.glob("*_plan_two"))

        assert len(plan1_folders) == 1
        assert len(plan2_folders) == 1

        # Planner should be able to work with either plan

    def test_bootstrap_plan_metadata_complete(self, mock_git_context):
        """Test that bootstrapped plan has complete metadata for planner."""
        from agenticcli.commands import epic as plan

        args = SimpleNamespace(
            branch="metadata-test",
            objective="Test metadata completeness",
            description="metadata test",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        plans_dir = mock_git_context / "docs" / "epics" / "live"
        plan_folders = list(plans_dir.glob("*_metadata_test"))
        plan_folder = plan_folders[0]

        # Flattened structure
        plan_build_file = plan_folder / "plan_build.yml"
        with open(plan_build_file) as f:
            plan_data = yaml.safe_load(f)

        # Planner needs these metadata fields
        required_fields = ["name", "branch", "status", "context"]
        for field in required_fields:
            assert field in plan_data, f"Missing required field: {field}"

        # Verify values are not empty
        assert plan_data["name"]
        assert plan_data["branch"] == "metadata-test"
        assert plan_data["status"] in ["active", "pending", "in_progress"]
        assert plan_data["context"]


class TestPlannerContextAccess:
    """Tests for planner accessing bootstrapped plan context."""

    def test_planner_can_find_plan_by_folder_name(self, mock_git_context):
        """Test that planner can find plan by folder name."""
        from agenticcli.commands import epic as plan

        args = SimpleNamespace(
            branch="findable",
            objective="Test findability",
            description="findable plan",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        # Planner would search for plans
        plans_dir = mock_git_context / "docs" / "epics" / "live"
        all_plans = list(plans_dir.iterdir())

        # Should be able to find by partial match
        matching = [p for p in all_plans if "findable_plan" in p.name]
        assert len(matching) == 1

    def test_planner_can_read_plan_objective(self, mock_git_context):
        """Test that planner can read plan objective."""
        from agenticcli.commands import epic as plan

        objective_text = "This is a specific objective for the planner to read"
        args = SimpleNamespace(
            branch="objective-test",
            objective=objective_text,
            description="objective read",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        plans_dir = mock_git_context / "docs" / "epics" / "live"
        plan_folders = list(plans_dir.glob("*_objective_read"))
        plan_folder = plan_folders[0]

        # Flattened structure
        plan_build_file = plan_folder / "plan_build.yml"
        with open(plan_build_file) as f:
            plan_data = yaml.safe_load(f)

        # Planner reads context (objective) to understand what to plan
        assert plan_data["context"].strip() == objective_text
