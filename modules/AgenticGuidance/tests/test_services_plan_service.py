"""Tests for EpicService - epic management CRUD operations."""

import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agenticguidance.services.epic import (
    PhaseData,
    EpicCreateResult,
    EpicData,
    EpicMetadata,
    EpicService,
    EpicUpdateResult,
    TicketData,
    ValidationResult,
)


class TestEpicServiceInit:
    """Tests for EpicService initialization."""

    def test_init_with_repo_path(self, tmp_path):
        """Test initialization with explicit repo_path."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        assert service.repo_path == repo_path
        assert service.epics_base == repo_path / "docs" / "epics"

    def test_init_auto_detect_repo(self, tmp_path):
        """Test initialization auto-detects repo root from cwd."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        with patch("agenticguidance.services.epic.Path.cwd", return_value=repo_path):
            service = EpicService()

        assert service.repo_path == repo_path
        assert service.epics_base == repo_path / "docs" / "epics"

    def test_init_nested_directory(self, tmp_path):
        """Test initialization from nested directory finds repo root."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        nested = repo_path / "modules" / "AgenticGuidance"
        nested.mkdir(parents=True)

        with patch("agenticguidance.services.epic.Path.cwd", return_value=nested):
            service = EpicService()

        assert service.repo_path == repo_path


class TestCreateEpic:
    """Tests for create_epic() method."""

    def test_create_epic_success(self, tmp_path):
        """Test create_epic creates folder and scaffold files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        with patch("agenticguidance.services.epic.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.strftime.side_effect = lambda fmt: "260203" if fmt == "%y%m%d" else "2026-02-03"
            mock_dt.now.return_value = mock_now

            result = service.create_epic(
                objective="Test epic objective",
                branch="main",
                description="test_plan",
            )

        assert result.success is True
        assert result.epic_folder_name == "260203MA_test_plan"
        assert result.epic_folder.exists()
        assert (result.epic_folder / "README.md").exists()
        assert (result.epic_folder / "plan_build.yml").exists()

    def test_create_epic_naming_convention(self, tmp_path):
        """Test create_epic follows YYMMDDXX_description convention."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        with patch("agenticguidance.services.epic.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.strftime.side_effect = lambda fmt: "260203" if fmt == "%y%m%d" else "2026-02-03"
            mock_dt.now.return_value = mock_now

            result = service.create_epic(
                objective="Test objective",
                branch="feature-branch",
                description="my_feature",
            )

        assert result.epic_folder_name == "260203FE_my_feature"

    def test_create_epic_dry_run(self, tmp_path):
        """Test create_epic with dry_run=True creates no files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        with patch("agenticguidance.services.epic.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.strftime.side_effect = lambda fmt: "260203" if fmt == "%y%m%d" else "2026-02-03"
            mock_dt.now.return_value = mock_now

            result = service.create_epic(
                objective="Test objective",
                branch="main",
                description="test",
                dry_run=True,
            )

        assert result.success is True
        assert "[dry-run]" in result.message
        assert not result.epic_folder.exists()

    def test_create_epic_already_exists(self, tmp_path):
        """Test create_epic fails when folder already exists."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        with patch("agenticguidance.services.epic.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.strftime.side_effect = lambda fmt: "260203" if fmt == "%y%m%d" else "2026-02-03"
            mock_dt.now.return_value = mock_now

            # Create first epic
            result1 = service.create_epic(
                objective="Test objective",
                branch="main",
                description="test",
            )

            # Try to create duplicate
            result2 = service.create_epic(
                objective="Test objective",
                branch="main",
                description="test",
            )

        assert result1.success is True
        assert result2.success is False
        assert "already exists" in result2.message

    def test_create_epic_sanitizes_description(self, tmp_path):
        """Test create_epic sanitizes description for folder name."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        with patch("agenticguidance.services.epic.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.strftime.side_effect = lambda fmt: "260203" if fmt == "%y%m%d" else "2026-02-03"
            mock_dt.now.return_value = mock_now

            result = service.create_epic(
                objective="Test objective",
                branch="main",
                description="Test Feature! @#$ With Spaces",
            )

        # Should convert to lowercase, replace special chars with underscores
        assert "_" in result.epic_folder_name
        assert result.epic_folder_name.split("_")[1].isalnum() or "_" in result.epic_folder_name.split("_")[1]


class TestGetEpic:
    """Tests for get_epic() method."""

    def test_get_epic_by_id(self, tmp_path):
        """Test get_epic retrieves epic by short ID."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create an epic
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "branch": "main",
            "status": "active",
            "objective": "Test objective",
            "phases": [
                {
                    "name": "Phase 1",
                    "description": "Test phase",
                    "tickets": [
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

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        # Get by short ID
        epic = service.get_epic("260203PS")

        assert epic is not None
        assert epic.epic_folder_name == "260203PS_test_plan"
        assert epic.objective == "Test objective"
        assert len(epic.phases) == 1
        assert len(epic.tasks) == 1

    def test_get_epic_by_folder_name(self, tmp_path):
        """Test get_epic retrieves epic by full folder name."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create an epic
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "branch": "main",
            "status": "active",
            "objective": "Test objective",
            "phases": [],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        # Get by full folder name
        epic = service.get_epic("260203PS_test_plan")

        assert epic is not None
        assert epic.epic_folder_name == "260203PS_test_plan"

    def test_get_epic_by_relative_path(self, tmp_path):
        """Test get_epic retrieves epic by relative path."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create an epic
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "branch": "main",
            "status": "active",
            "objective": "Test objective",
            "phases": [],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        # Get by relative path
        epic = service.get_epic("docs/epics/live/260203PS_test_plan")

        assert epic is not None
        assert epic.epic_folder_name == "260203PS_test_plan"

    def test_get_epic_by_absolute_path(self, tmp_path):
        """Test get_epic retrieves epic by absolute path."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create an epic
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "branch": "main",
            "status": "active",
            "objective": "Test objective",
            "phases": [],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        # Get by absolute path
        epic = service.get_epic(str(epic_folder))

        assert epic is not None
        assert epic.epic_folder_name == "260203PS_test_plan"

    def test_get_epic_not_found(self, tmp_path):
        """Test get_epic returns None when epic not found."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        epic = service.get_epic("260203XX")

        assert epic is None

    def test_get_epic_extracts_tasks(self, tmp_path):
        """Test get_epic extracts tasks from phases correctly."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create an epic with multiple phases and tasks
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "branch": "main",
            "status": "active",
            "objective": "Test objective",
            "phases": [
                {
                    "name": "Phase 1",
                    "description": "First phase",
                    "tickets": [
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
                    "tickets": [
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

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        epic = service.get_epic("260203PS")

        assert epic is not None
        assert len(epic.phases) == 2
        assert len(epic.tasks) == 3
        assert epic.tasks[0].id == "task_001"
        assert epic.tasks[0].phase_name == "Phase 1"
        assert epic.tasks[1].id == "task_002"
        assert epic.tasks[2].id == "task_003"
        assert epic.tasks[2].phase_name == "Phase 2"


class TestListEpics:
    """Tests for list_epics() method."""

    def test_list_epics_live(self, tmp_path):
        """Test list_epics returns live epics."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create multiple live epics
        live_dir = repo_path / "docs" / "epics" / "live"
        live_dir.mkdir(parents=True)

        for i in range(3):
            epic_folder = live_dir / f"26020{i}PS_plan_{i}"
            epic_folder.mkdir()

            epic_data = {
                "name": f"plan-{i}",
                "worktree_path": str(repo_path),
                "status": "active",
                "objective": f"Objective {i}",
                "phases": [],
            }

            with open(epic_folder / "plan_build.yml", "w") as f:
                yaml.dump(epic_data, f)

        epics = service.list_epics(status="live")

        assert len(epics) == 3
        assert all(isinstance(p, EpicMetadata) for p in epics)

    def test_list_epics_completed(self, tmp_path):
        """Test list_epics returns completed epics."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create completed epic
        completed_dir = repo_path / "docs" / "epics" / "completed"
        completed_dir.mkdir(parents=True)

        epic_folder = completed_dir / "260203PS_completed_plan"
        epic_folder.mkdir()

        epic_data = {
            "name": "completed-plan",
            "worktree_path": str(repo_path),
            "status": "fully_completed",
            "objective": "Completed objective",
            "phases": [],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        epics = service.list_epics(status="completed")

        assert len(epics) == 1
        assert epics[0].status == "fully_completed"

    def test_list_epics_deferred(self, tmp_path):
        """Test list_epics returns deferred epics."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create deferred epic
        deferred_dir = repo_path / "docs" / "epics" / "deferred"
        deferred_dir.mkdir(parents=True)

        epic_folder = deferred_dir / "260203PS_deferred_plan"
        epic_folder.mkdir()

        epic_data = {
            "name": "deferred-plan",
            "worktree_path": str(repo_path),
            "status": "blocked",
            "objective": "Deferred objective",
            "phases": [],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        epics = service.list_epics(status="deferred")

        assert len(epics) == 1

    def test_list_epics_empty(self, tmp_path):
        """Test list_epics returns empty list when no epics exist."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        epics = service.list_epics(status="live")

        assert epics == []

    def test_list_epics_sorted_newest_first(self, tmp_path):
        """Test list_epics returns epics sorted by folder name (newest first)."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        live_dir = repo_path / "docs" / "epics" / "live"
        live_dir.mkdir(parents=True)

        # Create epics with different dates
        folder_names = ["260201PS_old", "260203PS_new", "260202PS_mid"]

        for name in folder_names:
            epic_folder = live_dir / name
            epic_folder.mkdir()

            epic_data = {
                "name": name,
                "worktree_path": str(repo_path),
                "status": "active",
                "objective": "Test",
                "phases": [],
            }

            with open(epic_folder / "plan_build.yml", "w") as f:
                yaml.dump(epic_data, f)

        epics = service.list_epics(status="live")

        # Should be sorted newest first
        assert epics[0].epic_folder_name == "260203PS_new"
        assert epics[1].epic_folder_name == "260202PS_mid"
        assert epics[2].epic_folder_name == "260201PS_old"

    def test_list_epics_skips_invalid_names(self, tmp_path):
        """Test list_epics skips folders with invalid naming convention."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        live_dir = repo_path / "docs" / "epics" / "live"
        live_dir.mkdir(parents=True)

        # Create valid epic
        valid_folder = live_dir / "260203PS_valid"
        valid_folder.mkdir()

        epic_data = {
            "name": "valid",
            "worktree_path": str(repo_path),
            "status": "active",
            "objective": "Test",
            "phases": [],
        }

        with open(valid_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        # Create invalid folder names
        (live_dir / "invalid_name").mkdir()
        (live_dir / "20230203_too_short").mkdir()

        epics = service.list_epics(status="live")

        # Should only return the valid epic
        assert len(epics) == 1
        assert epics[0].epic_folder_name == "260203PS_valid"


class TestUpdateEpicStatus:
    """Tests for update_epic_status() method."""

    def test_update_epic_status_success(self, tmp_path):
        """Test update_epic_status updates status successfully."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create an epic
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "pending",
            "phases": [],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        result = service.update_epic_status("260203PS", "active")

        assert result.success is True
        assert result.old_status == "pending"
        assert result.new_status == "active"

        # Verify file was updated
        with open(epic_folder / "plan_build.yml") as f:
            updated_data = yaml.safe_load(f)
        assert updated_data["status"] == "active"

    def test_update_epic_status_invalid_status(self, tmp_path):
        """Test update_epic_status rejects invalid status values."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        result = service.update_epic_status("260203PS", "invalid_status")

        assert result.success is False
        assert "Invalid status" in result.message

    def test_update_epic_status_epic_not_found(self, tmp_path):
        """Test update_epic_status fails when epic not found."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        result = service.update_epic_status("260203XX", "active")

        assert result.success is False
        assert "not found" in result.message

    def test_update_epic_status_dry_run(self, tmp_path):
        """Test update_epic_status with dry_run=True modifies nothing."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create an epic
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "pending",
            "phases": [],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        result = service.update_epic_status("260203PS", "active", dry_run=True)

        assert result.success is True
        assert "[dry-run]" in result.message
        assert result.old_status == "pending"
        assert result.new_status == "active"

        # Verify file was NOT updated
        with open(epic_folder / "plan_build.yml") as f:
            updated_data = yaml.safe_load(f)
        assert updated_data["status"] == "pending"

    def test_update_epic_status_multiple_files(self, tmp_path):
        """Test update_epic_status updates all plan_*.yml files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create an epic with multiple YAML files
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

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

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_build, f)

        with open(epic_folder / "plan_test.yml", "w") as f:
            yaml.dump(plan_test, f)

        result = service.update_epic_status("260203PS", "active")

        assert result.success is True
        assert result.old_status == "pending"
        assert result.new_status == "active"

        # Verify both YAML files were updated (via yaml_sync)
        with open(epic_folder / "plan_build.yml") as f:
            build_data = yaml.safe_load(f)
        assert build_data["status"] == "active"

        with open(epic_folder / "plan_test.yml") as f:
            test_data = yaml.safe_load(f)
        assert test_data["status"] == "active"


class TestGetEpicTickets:
    """Tests for get_epic_tickets() method."""

    def test_get_epic_tickets_all(self, tmp_path):
        """Test get_epic_tickets returns all tickets."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create an epic with tasks
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tickets": [
                        {"id": "task_001", "name": "Task 1", "status": "pending"},
                        {"id": "task_002", "name": "Task 2", "status": "completed"},
                        {"id": "task_003", "name": "Task 3", "status": "in_progress"},
                    ],
                },
            ],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        tasks = service.get_epic_tickets("260203PS")

        assert len(tasks) == 3
        assert all(isinstance(t, TicketData) for t in tasks)

    def test_get_epic_tickets_filtered_by_status(self, tmp_path):
        """Test get_epic_tickets filters by status."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create an epic with tasks
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tickets": [
                        {"id": "task_001", "name": "Task 1", "status": "pending"},
                        {"id": "task_002", "name": "Task 2", "status": "completed"},
                        {"id": "task_003", "name": "Task 3", "status": "pending"},
                    ],
                },
            ],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        pending_tasks = service.get_epic_tickets("260203PS", status_filter="pending")

        assert len(pending_tasks) == 2
        assert all(t.status == "pending" for t in pending_tasks)

    def test_get_epic_tickets_epic_not_found(self, tmp_path):
        """Test get_epic_tickets returns empty list when epic not found."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        tasks = service.get_epic_tickets("260203XX")

        assert tasks == []


class TestValidateEpicStructure:
    """Tests for validate_epic_structure() method."""

    def test_validate_epic_structure_valid(self, tmp_path):
        """Test validate_epic_structure passes for valid epic."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create a valid epic
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "active",
            "phases": [
                {
                    "id": "phase_001",
                    "name": "Phase 1",
                    "tickets": [
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

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_epic_structure_invalid_folder_name(self, tmp_path):
        """Test validate_epic_structure fails for invalid folder naming."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create epic with invalid folder name
        epic_folder = repo_path / "docs" / "epics" / "live" / "invalid_folder_name"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "active",
            "phases": [],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        assert any("YYMMDDXX_description" in e for e in result.errors)

    def test_validate_epic_structure_missing_required_fields(self, tmp_path):
        """Test validate_epic_structure fails when required fields missing."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create epic missing required fields
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            # Missing: worktree_path, status, phases
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        assert any("status" in e for e in result.errors)
        assert any("phases" in e for e in result.errors)
        # worktree_path is optional - generates a warning, not an error
        assert any("worktree_path" in w for w in result.warnings)

    def test_validate_epic_structure_invalid_status(self, tmp_path):
        """Test validate_epic_structure fails for invalid status value."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create epic with invalid status
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "invalid_status",
            "phases": [],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        assert any("Invalid status" in e for e in result.errors)

    def test_validate_epic_structure_duplicate_task_ids(self, tmp_path):
        """Test validate_epic_structure fails for duplicate ticket IDs."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create epic with duplicate task IDs
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tickets": [
                        {"id": "task_001", "name": "Task 1"},
                        {"id": "task_001", "name": "Task 2"},  # Duplicate ID
                    ],
                },
            ],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        assert any("Duplicate ticket ID" in e for e in result.errors)

    def test_validate_epic_structure_warnings(self, tmp_path):
        """Test validate_epic_structure generates warnings for quality issues."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create epic with quality issues
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tickets": [
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

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is True  # Valid, but with warnings
        assert len(result.warnings) > 0
        assert any("empty description" in w for w in result.warnings)
        assert any("no success criteria" in w for w in result.warnings)

    def test_validate_epic_structure_folder_not_exists(self, tmp_path):
        """Test validate_epic_structure fails when folder doesn't exist."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        non_existent = repo_path / "docs" / "epics" / "live" / "260203XX_nonexistent"

        result = service.validate_epic_structure(non_existent)

        assert result.valid is False
        assert any("does not exist" in e for e in result.errors)

    def test_validate_epic_structure_no_plan_files(self, tmp_path):
        """Test validate_epic_structure fails when no plan_*.yml files found."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create empty epic folder
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        assert any("No plan_*.yml files" in e for e in result.errors)


class TestValidateTicketNesting:
    """Tests for ticket nesting validation in validate_epic_structure().

    Validates that:
    - Root-level tasks: key is rejected (tickets must be nested under phases[].tasks[])
    - Phases without tickets: key generate warnings
    - Blocking conditions (root tasks + no phases) are detected
    - Valid epics with proper nesting still pass
    """

    def _make_epic(self, tmp_path, epic_data: dict) -> tuple:
        """Helper to create an epic folder with given YAML data."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        epic_folder = repo_path / "docs" / "epics" / "live" / "260223TU_test_nesting"
        epic_folder.mkdir(parents=True)

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f, default_flow_style=False)

        return service, epic_folder

    # --- TU_001: Root-level tasks detection ---

    def test_root_level_tasks_returns_error(self, tmp_path):
        """Epic with root-level tasks: key must return validation error."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "bad-epic",
            "status": "active",
            "tasks": [
                {"id": "T1", "name": "orphan task", "status": "pending"},
            ],
        })

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        root_level_errors = [e for e in result.errors if "root" in e.lower() and "task" in e.lower()]
        assert len(root_level_errors) > 0, f"Expected root-level tasks error, got: {result.errors}"

    def test_root_level_tasks_error_mentions_phases(self, tmp_path):
        """Error message for root-level tasks must mention phases nesting."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "bad-epic",
            "status": "active",
            "tasks": [
                {"id": "T1", "name": "orphan task", "status": "pending"},
            ],
        })

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        all_errors = " ".join(result.errors).lower()
        assert "nested" in all_errors or "phases" in all_errors, (
            f"Error should mention nesting under phases, got: {result.errors}"
        )

    def test_root_level_tasks_with_phases_returns_error(self, tmp_path):
        """Epic with BOTH root-level tasks: AND phases: must return error."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "bad-epic",
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tickets": [
                        {"id": "T2", "name": "nested task", "status": "pending"},
                    ],
                },
            ],
            "tasks": [
                {"id": "T1", "name": "orphan task", "status": "pending"},
            ],
        })

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        root_level_errors = [e for e in result.errors if "root" in e.lower() and "task" in e.lower()]
        assert len(root_level_errors) > 0, (
            f"Expected root-level tasks error even with phases present, got: {result.errors}"
        )

    # --- TU_002: Phase without tickets detection ---

    def test_phase_without_tasks_returns_warning(self, tmp_path):
        """Epic with a phase that has no tickets must return warning."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "partial-epic",
            "status": "active",
            "phases": [
                {
                    "name": "Phase with tasks",
                    "tickets": [
                        {"id": "T1", "name": "a task", "status": "pending"},
                    ],
                },
                {
                    "name": "Empty phase",
                },
            ],
        })

        result = service.validate_epic_structure(epic_folder)

        empty_phase_warnings = [
            w for w in result.warnings if "Empty phase" in w and "ticket" in w.lower()
        ]
        assert len(empty_phase_warnings) > 0, (
            f"Expected warning about 'Empty phase' having no tickets, got warnings: {result.warnings}"
        )

    def test_phase_with_tasks_no_warning(self, tmp_path):
        """Phase with tickets should NOT trigger a missing-tickets warning."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "good-epic",
            "status": "active",
            "phases": [
                {
                    "name": "Phase with tasks",
                    "tickets": [
                        {"id": "T1", "name": "a task", "status": "pending",
                         "description": "desc", "success_criteria": ["ok"]},
                    ],
                },
            ],
        })

        result = service.validate_epic_structure(epic_folder)

        no_tickets_warnings = [
            w for w in result.warnings if "no tickets" in w.lower() or "has no ticket" in w.lower()
        ]
        assert len(no_tickets_warnings) == 0, (
            f"Phase with tickets should not trigger warning, got: {no_tickets_warnings}"
        )

    def test_multiple_phases_mixed_tasks(self, tmp_path):
        """Only phases without tickets should trigger warnings."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "mixed-epic",
            "status": "active",
            "phases": [
                {
                    "name": "Good Phase",
                    "tickets": [
                        {"id": "T1", "name": "task", "status": "pending"},
                    ],
                },
                {"name": "Empty Phase A"},
                {
                    "name": "Another Good Phase",
                    "tickets": [
                        {"id": "T2", "name": "task 2", "status": "pending"},
                    ],
                },
                {"name": "Empty Phase B"},
            ],
        })

        result = service.validate_epic_structure(epic_folder)

        empty_warnings = [
            w for w in result.warnings if "no tickets" in w.lower() or "has no ticket" in w.lower()
        ]
        assert len(empty_warnings) == 2, (
            f"Expected 2 warnings for 2 empty phases, got {len(empty_warnings)}: {empty_warnings}"
        )

    # --- TU_003: Blocking condition (root tasks + no phases) ---

    def test_root_tasks_no_phases_is_blocking(self, tmp_path):
        """Epic with root-level tasks and NO phases key must be a blocking error."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "flat-epic",
            "status": "active",
            "tasks": [
                {"id": "T1", "name": "orphan", "status": "pending"},
            ],
        })

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        all_errors = " ".join(result.errors).lower()
        assert "task" in all_errors, f"Expected task-related error, got: {result.errors}"

    def test_root_tasks_no_phases_valid_false(self, tmp_path):
        """ValidationResult.valid must be False for flat epic with root tasks."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "flat-epic",
            "status": "active",
            "tasks": [
                {"id": "T1", "name": "orphan", "status": "pending"},
            ],
        })

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False, "Epic with root tasks and no phases must be invalid"
        assert len(result.errors) > 0, "Must have at least one error"

    # --- TU_004: Valid epics still pass (regression) ---

    def test_valid_nested_tasks_pass(self, tmp_path):
        """Epic with proper phases[].tasks[] nesting must pass validation."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "good-epic",
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tickets": [
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

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is True, f"Valid epic should pass, errors: {result.errors}"
        assert len(result.errors) == 0

    def test_multiple_phases_with_tasks_pass(self, tmp_path):
        """Epic with multiple phases each containing tickets must pass."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "multi-phase-epic",
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tickets": [
                        {"id": "T1", "name": "task 1", "description": "d1",
                         "status": "pending", "success_criteria": ["ok"]},
                        {"id": "T2", "name": "task 2", "description": "d2",
                         "status": "pending", "success_criteria": ["ok"]},
                    ],
                },
                {
                    "name": "Phase 2",
                    "tickets": [
                        {"id": "T3", "name": "task 3", "description": "d3",
                         "status": "pending", "success_criteria": ["ok"]},
                    ],
                },
            ],
        })

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is True, f"Valid multi-phase epic should pass, errors: {result.errors}"
        assert len(result.errors) == 0

    def test_stub_templates_skipped(self, tmp_path):
        """Stub templates with _template_status: stub should be skipped."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        epic_folder = repo_path / "docs" / "epics" / "live" / "260223TU_test_stub"
        epic_folder.mkdir(parents=True)

        # Write a valid build epic
        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump({
                "name": "stub-epic",
                "status": "active",
                "phases": [
                    {
                        "name": "Phase 1",
                        "tickets": [
                            {"id": "T1", "name": "task", "description": "d",
                             "status": "pending", "success_criteria": ["ok"]},
                        ],
                    },
                ],
            }, f, default_flow_style=False)

        # Write a stub template that has root-level tasks (should be skipped)
        with open(epic_folder / "plan_test.yml", "w") as f:
            yaml.dump({
                "_template_status": "stub",
                "name": "test-stub",
                "status": "pending",
                "tasks": [
                    {"id": "T99", "name": "stub task"},
                ],
            }, f, default_flow_style=False)

        result = service.validate_epic_structure(epic_folder)

        root_errors = [e for e in result.errors if "root" in e.lower() and "task" in e.lower()]
        assert len(root_errors) == 0, (
            f"Stub template should be skipped, but got root-task errors: {root_errors}"
        )


class TestDryRunOperations:
    """Tests for dry-run functionality across operations."""

    def test_create_epic_dry_run_creates_no_files(self, tmp_path):
        """Test create_epic with dry_run=True creates no files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        with patch("agenticguidance.services.epic.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.strftime.side_effect = lambda fmt: "260203" if fmt == "%y%m%d" else "2026-02-03"
            mock_dt.now.return_value = mock_now

            result = service.create_epic(
                objective="Test objective",
                branch="main",
                description="test",
                dry_run=True,
            )

        assert result.success is True
        assert "[dry-run]" in result.message

        # Verify no files created
        live_dir = repo_path / "docs" / "epics" / "live"
        if live_dir.exists():
            assert len(list(live_dir.iterdir())) == 0

    def test_update_epic_status_dry_run_modifies_nothing(self, tmp_path):
        """Test update_epic_status with dry_run=True modifies nothing."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create an epic
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "pending",
            "phases": [],
        }

        plan_file = epic_folder / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(epic_data, f)

        # Get original modification time
        original_mtime = plan_file.stat().st_mtime

        result = service.update_epic_status("260203PS", "active", dry_run=True)

        assert result.success is True
        assert "[dry-run]" in result.message

        # Verify file not modified
        with open(plan_file) as f:
            data = yaml.safe_load(f)
        assert data["status"] == "pending"

        # Verify modification time unchanged
        assert plan_file.stat().st_mtime == original_mtime
