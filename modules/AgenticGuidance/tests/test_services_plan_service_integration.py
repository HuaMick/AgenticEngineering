"""Integration tests for PlanService with real plan folders in the repo."""

import os
from pathlib import Path

import pytest

from agenticguidance.services.plan import PlanService


class TestPlanServiceIntegration:
    """Integration tests using real plan folders in the repository."""

    @pytest.fixture
    def repo_root(self):
        """Get the repository root directory."""
        # Find repo root by looking for .git directory
        current = Path(__file__).resolve()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        pytest.skip("Not in a git repository")

    @pytest.fixture
    def service(self, repo_root):
        """Create PlanService instance with real repo path."""
        return PlanService(repo_path=repo_root)

    def test_list_plans_returns_existing_live_plans(self, service, repo_root):
        """Test list_plans returns existing live plans from the repo."""
        plans_dir = repo_root / "docs" / "plans" / "live"

        if not plans_dir.exists():
            pytest.skip("No docs/plans/live directory in repository")

        # Get actual plan folders
        actual_folders = [
            d.name for d in plans_dir.iterdir()
            if d.is_dir() and "_" in d.name and len(d.name.split("_")[0]) == 8
        ]

        if not actual_folders:
            pytest.skip("No live plans in repository")

        # List plans via service
        plans = service.list_plans(status="live")

        # Verify we got results
        assert len(plans) > 0, "PlanService should return live plans"

        # Verify returned plan folder names match actual folders
        returned_names = {p.plan_folder_name for p in plans}
        for folder in actual_folders:
            assert folder in returned_names, f"Plan {folder} should be in results"

    def test_get_plan_on_real_plan_returns_valid_data(self, service, repo_root):
        """Test get_plan on a real plan returns valid data."""
        plans_dir = repo_root / "docs" / "plans" / "live"

        if not plans_dir.exists():
            pytest.skip("No docs/plans/live directory in repository")

        # Find first valid plan folder
        plan_folder = None
        for d in plans_dir.iterdir():
            if d.is_dir() and "_" in d.name and len(d.name.split("_")[0]) == 8:
                # Check if it has plan files
                if list(d.glob("plan_*.yml")):
                    plan_folder = d
                    break

        if not plan_folder:
            pytest.skip("No valid plan with plan_*.yml files found")

        # Get plan by short ID
        plan_id = plan_folder.name.split("_")[0]
        plan = service.get_plan(plan_id)

        # Verify we got valid plan data
        assert plan is not None, f"Should retrieve plan {plan_id}"
        assert plan.plan_folder_name == plan_folder.name
        assert plan.plan_folder == plan_folder
        assert isinstance(plan.phases, list)
        assert isinstance(plan.tasks, list)

    def test_validate_real_plan_structure_passes(self, service, repo_root):
        """Test validate on real plan structure passes."""
        plans_dir = repo_root / "docs" / "plans" / "live"

        if not plans_dir.exists():
            pytest.skip("No docs/plans/live directory in repository")

        # Find first valid plan folder
        plan_folder = None
        for d in plans_dir.iterdir():
            if d.is_dir() and "_" in d.name and len(d.name.split("_")[0]) == 8:
                # Check if it has plan files
                if list(d.glob("plan_*.yml")):
                    plan_folder = d
                    break

        if not plan_folder:
            pytest.skip("No valid plan with plan_*.yml files found")

        # Validate structure
        result = service.validate_plan_structure(plan_folder)

        # Real plans should be valid (or have only warnings, not errors)
        if not result.valid:
            # Show errors for debugging
            error_msg = f"Plan {plan_folder.name} validation failed:\n"
            error_msg += "\n".join(f"  - {e}" for e in result.errors)
            pytest.fail(error_msg)

    def test_list_completed_plans(self, service, repo_root):
        """Test list_plans returns completed plans if they exist."""
        completed_dir = repo_root / "docs" / "plans" / "completed"

        if not completed_dir.exists():
            pytest.skip("No docs/plans/completed directory in repository")

        plans = service.list_plans(status="completed")

        # If there are completed folders, we should get results
        actual_folders = [
            d.name for d in completed_dir.iterdir()
            if d.is_dir() and "_" in d.name
        ]

        if actual_folders:
            assert len(plans) > 0, "Should return completed plans"

    def test_list_deferred_plans(self, service, repo_root):
        """Test list_plans returns deferred plans if they exist."""
        deferred_dir = repo_root / "docs" / "plans" / "deferred"

        if not deferred_dir.exists():
            pytest.skip("No docs/plans/deferred directory in repository")

        plans = service.list_plans(status="deferred")

        # If there are deferred folders, we should get results
        actual_folders = [
            d.name for d in deferred_dir.iterdir()
            if d.is_dir() and "_" in d.name
        ]

        if actual_folders:
            assert len(plans) > 0, "Should return deferred plans"

    def test_get_plan_tasks_from_real_plan(self, service, repo_root):
        """Test get_plan_tasks extracts tasks from a real plan."""
        plans_dir = repo_root / "docs" / "plans" / "live"

        if not plans_dir.exists():
            pytest.skip("No docs/plans/live directory in repository")

        # Find first plan with tasks
        plan_id = None
        for d in plans_dir.iterdir():
            if d.is_dir() and "_" in d.name and len(d.name.split("_")[0]) == 8:
                if list(d.glob("plan_*.yml")):
                    # Quick check if plan has tasks
                    plan_data = service.get_plan(d.name.split("_")[0])
                    if plan_data and plan_data.tasks:
                        plan_id = d.name.split("_")[0]
                        break

        if not plan_id:
            pytest.skip("No plan with tasks found")

        # Get tasks
        tasks = service.get_plan_tasks(plan_id)

        assert len(tasks) > 0, "Should extract tasks from plan"
        assert all(hasattr(t, "id") for t in tasks), "All tasks should have IDs"
        assert all(hasattr(t, "name") for t in tasks), "All tasks should have names"

    def test_resolve_plan_by_multiple_methods(self, service, repo_root):
        """Test plan can be resolved by ID, folder name, and path."""
        plans_dir = repo_root / "docs" / "plans" / "live"

        if not plans_dir.exists():
            pytest.skip("No docs/plans/live directory in repository")

        # Find first valid plan
        plan_folder = None
        for d in plans_dir.iterdir():
            if d.is_dir() and "_" in d.name and len(d.name.split("_")[0]) == 8:
                if list(d.glob("plan_*.yml")):
                    plan_folder = d
                    break

        if not plan_folder:
            pytest.skip("No valid plan found")

        plan_id = plan_folder.name.split("_")[0]
        folder_name = plan_folder.name

        # Test all resolution methods
        by_id = service.get_plan(plan_id)
        by_folder = service.get_plan(folder_name)
        by_rel_path = service.get_plan(f"docs/plans/live/{folder_name}")
        by_abs_path = service.get_plan(str(plan_folder))

        # All should resolve to the same plan
        assert by_id is not None
        assert by_folder is not None
        assert by_rel_path is not None
        assert by_abs_path is not None

        assert by_id.plan_folder_name == folder_name
        assert by_folder.plan_folder_name == folder_name
        assert by_rel_path.plan_folder_name == folder_name
        assert by_abs_path.plan_folder_name == folder_name
