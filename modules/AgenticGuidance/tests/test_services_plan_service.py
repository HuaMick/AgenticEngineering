"""Tests for PlanService - plan management CRUD operations."""

import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agenticguidance.services.plan import (
    PhaseData,
    PlanCreateResult,
    PlanData,
    PlanMetadata,
    PlanService,
    PlanUpdateResult,
    TaskData,
    ValidationResult,
)


class TestPlanServiceInit:
    """Tests for PlanService initialization."""

    def test_init_with_repo_path(self, tmp_path):
        """Test initialization with explicit repo_path."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        assert service.repo_path == repo_path
        assert service.plans_base == repo_path / "docs" / "plans"

    def test_init_auto_detect_repo(self, tmp_path):
        """Test initialization auto-detects repo root from cwd."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        with patch("agenticguidance.services.plan.Path.cwd", return_value=repo_path):
            service = PlanService()

        assert service.repo_path == repo_path
        assert service.plans_base == repo_path / "docs" / "plans"

    def test_init_nested_directory(self, tmp_path):
        """Test initialization from nested directory finds repo root."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        nested = repo_path / "modules" / "AgenticGuidance"
        nested.mkdir(parents=True)

        with patch("agenticguidance.services.plan.Path.cwd", return_value=nested):
            service = PlanService()

        assert service.repo_path == repo_path


class TestCreatePlan:
    """Tests for create_plan() method."""

    def test_create_plan_success(self, tmp_path):
        """Test create_plan creates folder and scaffold files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        with patch("agenticguidance.services.plan.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.strftime.side_effect = lambda fmt: "260203" if fmt == "%y%m%d" else "2026-02-03"
            mock_dt.now.return_value = mock_now

            result = service.create_plan(
                objective="Test plan objective",
                branch="main",
                description="test_plan",
            )

        assert result.success is True
        assert result.plan_folder_name == "260203MA_test_plan"
        assert result.plan_folder.exists()
        assert (result.plan_folder / "README.md").exists()
        assert (result.plan_folder / "plan_build.yml").exists()

    def test_create_plan_naming_convention(self, tmp_path):
        """Test create_plan follows YYMMDDXX_description convention."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        with patch("agenticguidance.services.plan.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.strftime.side_effect = lambda fmt: "260203" if fmt == "%y%m%d" else "2026-02-03"
            mock_dt.now.return_value = mock_now

            result = service.create_plan(
                objective="Test objective",
                branch="feature-branch",
                description="my_feature",
            )

        assert result.plan_folder_name == "260203FE_my_feature"

    def test_create_plan_dry_run(self, tmp_path):
        """Test create_plan with dry_run=True creates no files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        with patch("agenticguidance.services.plan.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.strftime.side_effect = lambda fmt: "260203" if fmt == "%y%m%d" else "2026-02-03"
            mock_dt.now.return_value = mock_now

            result = service.create_plan(
                objective="Test objective",
                branch="main",
                description="test",
                dry_run=True,
            )

        assert result.success is True
        assert "[dry-run]" in result.message
        assert not result.plan_folder.exists()

    def test_create_plan_already_exists(self, tmp_path):
        """Test create_plan fails when folder already exists."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        with patch("agenticguidance.services.plan.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.strftime.side_effect = lambda fmt: "260203" if fmt == "%y%m%d" else "2026-02-03"
            mock_dt.now.return_value = mock_now

            # Create first plan
            result1 = service.create_plan(
                objective="Test objective",
                branch="main",
                description="test",
            )

            # Try to create duplicate
            result2 = service.create_plan(
                objective="Test objective",
                branch="main",
                description="test",
            )

        assert result1.success is True
        assert result2.success is False
        assert "already exists" in result2.message

    def test_create_plan_sanitizes_description(self, tmp_path):
        """Test create_plan sanitizes description for folder name."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        with patch("agenticguidance.services.plan.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.strftime.side_effect = lambda fmt: "260203" if fmt == "%y%m%d" else "2026-02-03"
            mock_dt.now.return_value = mock_now

            result = service.create_plan(
                objective="Test objective",
                branch="main",
                description="Test Feature! @#$ With Spaces",
            )

        # Should convert to lowercase, replace special chars with underscores
        assert "_" in result.plan_folder_name
        assert result.plan_folder_name.split("_")[1].isalnum() or "_" in result.plan_folder_name.split("_")[1]


class TestGetPlan:
    """Tests for get_plan() method."""

    def test_get_plan_by_id(self, tmp_path):
        """Test get_plan retrieves plan by short ID."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create a plan
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "branch": "main",
            "status": "active",
            "objective": "Test objective",
            "phases": [
                {
                    "name": "Phase 1",
                    "description": "Test phase",
                    "tasks": [
                        {
                            "id": "task_001",
                            "name": "Test task",
                            "description": "Task description",
                            "status": "pending",
                        }
                    ],
                }
            ],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        # Get by short ID
        plan = service.get_plan("260203PS")

        assert plan is not None
        assert plan.plan_folder_name == "260203PS_test_plan"
        assert plan.objective == "Test objective"
        assert len(plan.phases) == 1
        assert len(plan.tasks) == 1

    def test_get_plan_by_folder_name(self, tmp_path):
        """Test get_plan retrieves plan by full folder name."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create a plan
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "branch": "main",
            "status": "active",
            "objective": "Test objective",
            "phases": [],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        # Get by full folder name
        plan = service.get_plan("260203PS_test_plan")

        assert plan is not None
        assert plan.plan_folder_name == "260203PS_test_plan"

    def test_get_plan_by_relative_path(self, tmp_path):
        """Test get_plan retrieves plan by relative path."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create a plan
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "branch": "main",
            "status": "active",
            "objective": "Test objective",
            "phases": [],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        # Get by relative path
        plan = service.get_plan("docs/plans/live/260203PS_test_plan")

        assert plan is not None
        assert plan.plan_folder_name == "260203PS_test_plan"

    def test_get_plan_by_absolute_path(self, tmp_path):
        """Test get_plan retrieves plan by absolute path."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create a plan
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "branch": "main",
            "status": "active",
            "objective": "Test objective",
            "phases": [],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        # Get by absolute path
        plan = service.get_plan(str(plan_folder))

        assert plan is not None
        assert plan.plan_folder_name == "260203PS_test_plan"

    def test_get_plan_not_found(self, tmp_path):
        """Test get_plan returns None when plan not found."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        plan = service.get_plan("260203XX")

        assert plan is None

    def test_get_plan_extracts_tasks(self, tmp_path):
        """Test get_plan extracts tasks from phases correctly."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create a plan with multiple phases and tasks
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "branch": "main",
            "status": "active",
            "objective": "Test objective",
            "phases": [
                {
                    "name": "Phase 1",
                    "description": "First phase",
                    "tasks": [
                        {
                            "id": "task_001",
                            "name": "Task 1",
                            "status": "pending",
                            "agent": "build-python",
                        },
                        {
                            "id": "task_002",
                            "name": "Task 2",
                            "status": "completed",
                            "agent": "test-python",
                        },
                    ],
                },
                {
                    "name": "Phase 2",
                    "description": "Second phase",
                    "tasks": [
                        {
                            "id": "task_003",
                            "name": "Task 3",
                            "status": "in_progress",
                            "agent": "build-python",
                        },
                    ],
                },
            ],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        plan = service.get_plan("260203PS")

        assert plan is not None
        assert len(plan.phases) == 2
        assert len(plan.tasks) == 3
        assert plan.tasks[0].id == "task_001"
        assert plan.tasks[0].phase_name == "Phase 1"
        assert plan.tasks[1].id == "task_002"
        assert plan.tasks[2].id == "task_003"
        assert plan.tasks[2].phase_name == "Phase 2"


class TestListPlans:
    """Tests for list_plans() method."""

    def test_list_plans_live(self, tmp_path):
        """Test list_plans returns live plans."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create multiple live plans
        live_dir = repo_path / "docs" / "plans" / "live"
        live_dir.mkdir(parents=True)

        for i in range(3):
            plan_folder = live_dir / f"26020{i}PS_plan_{i}"
            plan_folder.mkdir()

            plan_data = {
                "name": f"plan-{i}",
                "worktree_path": str(repo_path),
                "status": "active",
                "objective": f"Objective {i}",
                "phases": [],
            }

            with open(plan_folder / "plan_build.yml", "w") as f:
                yaml.dump(plan_data, f)

        plans = service.list_plans(status="live")

        assert len(plans) == 3
        assert all(isinstance(p, PlanMetadata) for p in plans)

    def test_list_plans_completed(self, tmp_path):
        """Test list_plans returns completed plans."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create completed plan
        completed_dir = repo_path / "docs" / "plans" / "completed"
        completed_dir.mkdir(parents=True)

        plan_folder = completed_dir / "260203PS_completed_plan"
        plan_folder.mkdir()

        plan_data = {
            "name": "completed-plan",
            "worktree_path": str(repo_path),
            "status": "fully_completed",
            "objective": "Completed objective",
            "phases": [],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        plans = service.list_plans(status="completed")

        assert len(plans) == 1
        assert plans[0].status == "fully_completed"

    def test_list_plans_deferred(self, tmp_path):
        """Test list_plans returns deferred plans."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create deferred plan
        deferred_dir = repo_path / "docs" / "plans" / "deferred"
        deferred_dir.mkdir(parents=True)

        plan_folder = deferred_dir / "260203PS_deferred_plan"
        plan_folder.mkdir()

        plan_data = {
            "name": "deferred-plan",
            "worktree_path": str(repo_path),
            "status": "blocked",
            "objective": "Deferred objective",
            "phases": [],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        plans = service.list_plans(status="deferred")

        assert len(plans) == 1

    def test_list_plans_empty(self, tmp_path):
        """Test list_plans returns empty list when no plans exist."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        plans = service.list_plans(status="live")

        assert plans == []

    def test_list_plans_sorted_newest_first(self, tmp_path):
        """Test list_plans returns plans sorted by folder name (newest first)."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        live_dir = repo_path / "docs" / "plans" / "live"
        live_dir.mkdir(parents=True)

        # Create plans with different dates
        folder_names = ["260201PS_old", "260203PS_new", "260202PS_mid"]

        for name in folder_names:
            plan_folder = live_dir / name
            plan_folder.mkdir()

            plan_data = {
                "name": name,
                "worktree_path": str(repo_path),
                "status": "active",
                "objective": "Test",
                "phases": [],
            }

            with open(plan_folder / "plan_build.yml", "w") as f:
                yaml.dump(plan_data, f)

        plans = service.list_plans(status="live")

        # Should be sorted newest first
        assert plans[0].plan_folder_name == "260203PS_new"
        assert plans[1].plan_folder_name == "260202PS_mid"
        assert plans[2].plan_folder_name == "260201PS_old"

    def test_list_plans_skips_invalid_names(self, tmp_path):
        """Test list_plans skips folders with invalid naming convention."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        live_dir = repo_path / "docs" / "plans" / "live"
        live_dir.mkdir(parents=True)

        # Create valid plan
        valid_folder = live_dir / "260203PS_valid"
        valid_folder.mkdir()

        plan_data = {
            "name": "valid",
            "worktree_path": str(repo_path),
            "status": "active",
            "objective": "Test",
            "phases": [],
        }

        with open(valid_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        # Create invalid folder names
        (live_dir / "invalid_name").mkdir()
        (live_dir / "20230203_too_short").mkdir()

        plans = service.list_plans(status="live")

        # Should only return the valid plan
        assert len(plans) == 1
        assert plans[0].plan_folder_name == "260203PS_valid"


class TestUpdatePlanStatus:
    """Tests for update_plan_status() method."""

    def test_update_plan_status_success(self, tmp_path):
        """Test update_plan_status updates status successfully."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create a plan
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "pending",
            "phases": [],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        result = service.update_plan_status("260203PS", "active")

        assert result.success is True
        assert result.old_status == "pending"
        assert result.new_status == "active"

        # Verify file was updated
        with open(plan_folder / "plan_build.yml") as f:
            updated_data = yaml.safe_load(f)
        assert updated_data["status"] == "active"

    def test_update_plan_status_invalid_status(self, tmp_path):
        """Test update_plan_status rejects invalid status values."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        result = service.update_plan_status("260203PS", "invalid_status")

        assert result.success is False
        assert "Invalid status" in result.message

    def test_update_plan_status_plan_not_found(self, tmp_path):
        """Test update_plan_status fails when plan not found."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        result = service.update_plan_status("260203XX", "active")

        assert result.success is False
        assert "not found" in result.message

    def test_update_plan_status_dry_run(self, tmp_path):
        """Test update_plan_status with dry_run=True modifies nothing."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create a plan
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "pending",
            "phases": [],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        result = service.update_plan_status("260203PS", "active", dry_run=True)

        assert result.success is True
        assert "[dry-run]" in result.message
        assert result.old_status == "pending"
        assert result.new_status == "active"

        # Verify file was NOT updated
        with open(plan_folder / "plan_build.yml") as f:
            updated_data = yaml.safe_load(f)
        assert updated_data["status"] == "pending"

    def test_update_plan_status_multiple_files(self, tmp_path):
        """Test update_plan_status updates all plan_*.yml files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create a plan with multiple YAML files
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_build = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "pending",
            "phases": [],
        }

        plan_test = {
            "status": "pending",
            "test_strategy": "unit",
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_build, f)

        with open(plan_folder / "plan_test.yml", "w") as f:
            yaml.dump(plan_test, f)

        result = service.update_plan_status("260203PS", "active")

        assert result.success is True
        assert result.old_status == "pending"
        assert result.new_status == "active"

        # Verify both YAML files were updated (via yaml_sync)
        with open(plan_folder / "plan_build.yml") as f:
            build_data = yaml.safe_load(f)
        assert build_data["status"] == "active"

        with open(plan_folder / "plan_test.yml") as f:
            test_data = yaml.safe_load(f)
        assert test_data["status"] == "active"


class TestGetPlanTasks:
    """Tests for get_plan_tasks() method."""

    def test_get_plan_tasks_all(self, tmp_path):
        """Test get_plan_tasks returns all tasks."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create a plan with tasks
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tasks": [
                        {"id": "task_001", "name": "Task 1", "status": "pending"},
                        {"id": "task_002", "name": "Task 2", "status": "completed"},
                        {"id": "task_003", "name": "Task 3", "status": "in_progress"},
                    ],
                },
            ],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        tasks = service.get_plan_tasks("260203PS")

        assert len(tasks) == 3
        assert all(isinstance(t, TaskData) for t in tasks)

    def test_get_plan_tasks_filtered_by_status(self, tmp_path):
        """Test get_plan_tasks filters by status."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create a plan with tasks
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tasks": [
                        {"id": "task_001", "name": "Task 1", "status": "pending"},
                        {"id": "task_002", "name": "Task 2", "status": "completed"},
                        {"id": "task_003", "name": "Task 3", "status": "pending"},
                    ],
                },
            ],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        pending_tasks = service.get_plan_tasks("260203PS", status_filter="pending")

        assert len(pending_tasks) == 2
        assert all(t.status == "pending" for t in pending_tasks)

    def test_get_plan_tasks_plan_not_found(self, tmp_path):
        """Test get_plan_tasks returns empty list when plan not found."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        tasks = service.get_plan_tasks("260203XX")

        assert tasks == []


class TestValidatePlanStructure:
    """Tests for validate_plan_structure() method."""

    def test_validate_plan_structure_valid(self, tmp_path):
        """Test validate_plan_structure passes for valid plan."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create a valid plan
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "active",
            "phases": [
                {
                    "id": "phase_001",
                    "name": "Phase 1",
                    "tasks": [
                        {
                            "id": "task_001",
                            "name": "Task 1",
                            "description": "Task description",
                            "success_criteria": ["Criterion 1"],
                        },
                    ],
                },
            ],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_plan_structure_invalid_folder_name(self, tmp_path):
        """Test validate_plan_structure fails for invalid folder naming."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create plan with invalid folder name
        plan_folder = repo_path / "docs" / "plans" / "live" / "invalid_folder_name"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "active",
            "phases": [],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is False
        assert any("YYMMDDXX_description" in e for e in result.errors)

    def test_validate_plan_structure_missing_required_fields(self, tmp_path):
        """Test validate_plan_structure fails when required fields missing."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create plan missing required fields
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            # Missing: worktree_path, status, phases
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is False
        assert any("status" in e for e in result.errors)
        assert any("phases" in e for e in result.errors)
        # worktree_path is optional - generates a warning, not an error
        assert any("worktree_path" in w for w in result.warnings)

    def test_validate_plan_structure_invalid_status(self, tmp_path):
        """Test validate_plan_structure fails for invalid status value."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create plan with invalid status
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "invalid_status",
            "phases": [],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is False
        assert any("Invalid status" in e for e in result.errors)

    def test_validate_plan_structure_duplicate_task_ids(self, tmp_path):
        """Test validate_plan_structure fails for duplicate task IDs."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create plan with duplicate task IDs
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tasks": [
                        {"id": "task_001", "name": "Task 1"},
                        {"id": "task_001", "name": "Task 2"},  # Duplicate ID
                    ],
                },
            ],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is False
        assert any("Duplicate task ID" in e for e in result.errors)

    def test_validate_plan_structure_warnings(self, tmp_path):
        """Test validate_plan_structure generates warnings for quality issues."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create plan with quality issues
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tasks": [
                        {
                            "id": "task_001",
                            "name": "Task 1",
                            "description": "",  # Empty description
                            # Missing success_criteria
                        },
                    ],
                },
            ],
        }

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f)

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is True  # Valid, but with warnings
        assert len(result.warnings) > 0
        assert any("empty description" in w for w in result.warnings)
        assert any("no success criteria" in w for w in result.warnings)

    def test_validate_plan_structure_folder_not_exists(self, tmp_path):
        """Test validate_plan_structure fails when folder doesn't exist."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        non_existent = repo_path / "docs" / "plans" / "live" / "260203XX_nonexistent"

        result = service.validate_plan_structure(non_existent)

        assert result.valid is False
        assert any("does not exist" in e for e in result.errors)

    def test_validate_plan_structure_no_plan_files(self, tmp_path):
        """Test validate_plan_structure fails when no plan_*.yml files found."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create empty plan folder
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is False
        assert any("No plan_*.yml files" in e for e in result.errors)


class TestValidateTaskNesting:
    """Tests for task nesting validation in validate_plan_structure().

    Validates that:
    - Root-level tasks: key is rejected (tasks must be nested under phases[].tasks[])
    - Phases without tasks: key generate warnings
    - Blocking conditions (root tasks + no phases) are detected
    - Valid plans with proper nesting still pass
    """

    def _make_plan(self, tmp_path, plan_data: dict) -> tuple:
        """Helper to create a plan folder with given YAML data."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        plan_folder = repo_path / "docs" / "plans" / "live" / "260223TU_test_nesting"
        plan_folder.mkdir(parents=True)

        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_data, f, default_flow_style=False)

        return service, plan_folder

    # --- TU_001: Root-level tasks detection ---

    def test_root_level_tasks_returns_error(self, tmp_path):
        """Plan with root-level tasks: key must return validation error."""
        service, plan_folder = self._make_plan(tmp_path, {
            "name": "bad-plan",
            "status": "active",
            "tasks": [
                {"id": "T1", "name": "orphan task", "status": "pending"},
            ],
        })

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is False
        root_level_errors = [e for e in result.errors if "root" in e.lower() and "task" in e.lower()]
        assert len(root_level_errors) > 0, f"Expected root-level tasks error, got: {result.errors}"

    def test_root_level_tasks_error_mentions_phases(self, tmp_path):
        """Error message for root-level tasks must mention phases nesting."""
        service, plan_folder = self._make_plan(tmp_path, {
            "name": "bad-plan",
            "status": "active",
            "tasks": [
                {"id": "T1", "name": "orphan task", "status": "pending"},
            ],
        })

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is False
        all_errors = " ".join(result.errors).lower()
        assert "nested" in all_errors or "phases" in all_errors, (
            f"Error should mention nesting under phases, got: {result.errors}"
        )

    def test_root_level_tasks_with_phases_returns_error(self, tmp_path):
        """Plan with BOTH root-level tasks: AND phases: must return error."""
        service, plan_folder = self._make_plan(tmp_path, {
            "name": "bad-plan",
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tasks": [
                        {"id": "T2", "name": "nested task", "status": "pending"},
                    ],
                },
            ],
            "tasks": [
                {"id": "T1", "name": "orphan task", "status": "pending"},
            ],
        })

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is False
        root_level_errors = [e for e in result.errors if "root" in e.lower() and "task" in e.lower()]
        assert len(root_level_errors) > 0, (
            f"Expected root-level tasks error even with phases present, got: {result.errors}"
        )

    # --- TU_002: Phase without tasks detection ---

    def test_phase_without_tasks_returns_warning(self, tmp_path):
        """Plan with a phase that has no tasks: key must return warning."""
        service, plan_folder = self._make_plan(tmp_path, {
            "name": "partial-plan",
            "status": "active",
            "phases": [
                {
                    "name": "Phase with tasks",
                    "tasks": [
                        {"id": "T1", "name": "a task", "status": "pending"},
                    ],
                },
                {
                    "name": "Empty phase",
                },
            ],
        })

        result = service.validate_plan_structure(plan_folder)

        empty_phase_warnings = [
            w for w in result.warnings if "Empty phase" in w and "task" in w.lower()
        ]
        assert len(empty_phase_warnings) > 0, (
            f"Expected warning about 'Empty phase' having no tasks, got warnings: {result.warnings}"
        )

    def test_phase_with_tasks_no_warning(self, tmp_path):
        """Phase with tasks should NOT trigger a missing-tasks warning."""
        service, plan_folder = self._make_plan(tmp_path, {
            "name": "good-plan",
            "status": "active",
            "phases": [
                {
                    "name": "Phase with tasks",
                    "tasks": [
                        {"id": "T1", "name": "a task", "status": "pending",
                         "description": "desc", "success_criteria": ["ok"]},
                    ],
                },
            ],
        })

        result = service.validate_plan_structure(plan_folder)

        no_tasks_warnings = [
            w for w in result.warnings if "no tasks" in w.lower() or "has no task" in w.lower()
        ]
        assert len(no_tasks_warnings) == 0, (
            f"Phase with tasks should not trigger warning, got: {no_tasks_warnings}"
        )

    def test_multiple_phases_mixed_tasks(self, tmp_path):
        """Only phases without tasks should trigger warnings."""
        service, plan_folder = self._make_plan(tmp_path, {
            "name": "mixed-plan",
            "status": "active",
            "phases": [
                {
                    "name": "Good Phase",
                    "tasks": [
                        {"id": "T1", "name": "task", "status": "pending"},
                    ],
                },
                {"name": "Empty Phase A"},
                {
                    "name": "Another Good Phase",
                    "tasks": [
                        {"id": "T2", "name": "task 2", "status": "pending"},
                    ],
                },
                {"name": "Empty Phase B"},
            ],
        })

        result = service.validate_plan_structure(plan_folder)

        empty_warnings = [
            w for w in result.warnings if "no tasks" in w.lower() or "has no task" in w.lower()
        ]
        assert len(empty_warnings) == 2, (
            f"Expected 2 warnings for 2 empty phases, got {len(empty_warnings)}: {empty_warnings}"
        )

    # --- TU_003: Blocking condition (root tasks + no phases) ---

    def test_root_tasks_no_phases_is_blocking(self, tmp_path):
        """Plan with root-level tasks and NO phases key must be a blocking error."""
        service, plan_folder = self._make_plan(tmp_path, {
            "name": "flat-plan",
            "status": "active",
            "tasks": [
                {"id": "T1", "name": "orphan", "status": "pending"},
            ],
        })

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is False
        all_errors = " ".join(result.errors).lower()
        assert "task" in all_errors, f"Expected task-related error, got: {result.errors}"

    def test_root_tasks_no_phases_valid_false(self, tmp_path):
        """ValidationResult.valid must be False for flat plan with root tasks."""
        service, plan_folder = self._make_plan(tmp_path, {
            "name": "flat-plan",
            "status": "active",
            "tasks": [
                {"id": "T1", "name": "orphan", "status": "pending"},
            ],
        })

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is False, "Plan with root tasks and no phases must be invalid"
        assert len(result.errors) > 0, "Must have at least one error"

    # --- TU_004: Valid plans still pass (regression) ---

    def test_valid_nested_tasks_pass(self, tmp_path):
        """Plan with proper phases[].tasks[] nesting must pass validation."""
        service, plan_folder = self._make_plan(tmp_path, {
            "name": "good-plan",
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tasks": [
                        {
                            "id": "T1",
                            "name": "proper task",
                            "description": "Well-formed task",
                            "status": "pending",
                            "success_criteria": ["It works"],
                        },
                    ],
                },
            ],
        })

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is True, f"Valid plan should pass, errors: {result.errors}"
        assert len(result.errors) == 0

    def test_multiple_phases_with_tasks_pass(self, tmp_path):
        """Plan with multiple phases each containing tasks must pass."""
        service, plan_folder = self._make_plan(tmp_path, {
            "name": "multi-phase-plan",
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tasks": [
                        {"id": "T1", "name": "task 1", "description": "d1",
                         "status": "pending", "success_criteria": ["ok"]},
                        {"id": "T2", "name": "task 2", "description": "d2",
                         "status": "pending", "success_criteria": ["ok"]},
                    ],
                },
                {
                    "name": "Phase 2",
                    "tasks": [
                        {"id": "T3", "name": "task 3", "description": "d3",
                         "status": "pending", "success_criteria": ["ok"]},
                    ],
                },
            ],
        })

        result = service.validate_plan_structure(plan_folder)

        assert result.valid is True, f"Valid multi-phase plan should pass, errors: {result.errors}"
        assert len(result.errors) == 0

    def test_stub_templates_skipped(self, tmp_path):
        """Stub templates with _template_status: stub should be skipped."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        plan_folder = repo_path / "docs" / "plans" / "live" / "260223TU_test_stub"
        plan_folder.mkdir(parents=True)

        # Write a valid build plan
        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump({
                "name": "stub-plan",
                "status": "active",
                "phases": [
                    {
                        "name": "Phase 1",
                        "tasks": [
                            {"id": "T1", "name": "task", "description": "d",
                             "status": "pending", "success_criteria": ["ok"]},
                        ],
                    },
                ],
            }, f, default_flow_style=False)

        # Write a stub template that has root-level tasks (should be skipped)
        with open(plan_folder / "plan_test.yml", "w") as f:
            yaml.dump({
                "_template_status": "stub",
                "name": "test-stub",
                "status": "pending",
                "tasks": [
                    {"id": "T99", "name": "stub task"},
                ],
            }, f, default_flow_style=False)

        result = service.validate_plan_structure(plan_folder)

        root_errors = [e for e in result.errors if "root" in e.lower() and "task" in e.lower()]
        assert len(root_errors) == 0, (
            f"Stub template should be skipped, but got root-task errors: {root_errors}"
        )


class TestDryRunOperations:
    """Tests for dry-run functionality across operations."""

    def test_create_plan_dry_run_creates_no_files(self, tmp_path):
        """Test create_plan with dry_run=True creates no files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        with patch("agenticguidance.services.plan.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.strftime.side_effect = lambda fmt: "260203" if fmt == "%y%m%d" else "2026-02-03"
            mock_dt.now.return_value = mock_now

            result = service.create_plan(
                objective="Test objective",
                branch="main",
                description="test",
                dry_run=True,
            )

        assert result.success is True
        assert "[dry-run]" in result.message

        # Verify no files created
        live_dir = repo_path / "docs" / "plans" / "live"
        if live_dir.exists():
            assert len(list(live_dir.iterdir())) == 0

    def test_update_plan_status_dry_run_modifies_nothing(self, tmp_path):
        """Test update_plan_status with dry_run=True modifies nothing."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = PlanService(repo_path=repo_path)

        # Create a plan
        plan_folder = repo_path / "docs" / "plans" / "live" / "260203PS_test_plan"
        plan_folder.mkdir(parents=True)

        plan_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "pending",
            "phases": [],
        }

        plan_file = plan_folder / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_data, f)

        # Get original modification time
        original_mtime = plan_file.stat().st_mtime

        result = service.update_plan_status("260203PS", "active", dry_run=True)

        assert result.success is True
        assert "[dry-run]" in result.message

        # Verify file not modified
        with open(plan_file) as f:
            data = yaml.safe_load(f)
        assert data["status"] == "pending"

        # Verify modification time unchanged
        assert plan_file.stat().st_mtime == original_mtime
