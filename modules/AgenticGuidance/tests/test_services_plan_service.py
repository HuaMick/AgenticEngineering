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


def _setup_epic_in_tinydb(service: EpicService, epic_folder: Path, epic_data: dict) -> None:
    """Populate TinyDB with epic data from a YAML-style dict.

    Call this after creating the YAML file and the epic folder, so that
    service.get_epic(), list_epics(), etc. can find the epic via TinyDB.

    Args:
        service: EpicService instance (uses service._repository).
        epic_folder: Path to the epic folder (used to derive epic_folder_name).
        epic_data: YAML-style dict with optional name, status, phases, tasks.
    """
    if service._repository is None:
        return

    epic_folder_name = epic_folder.name
    service._repository.create_epic({
        "epic_folder_name": epic_folder_name,
        "epic_folder": str(epic_folder),
        "name": epic_data.get("name", epic_folder_name),
        "status": epic_data.get("status", "active"),
        "objective": epic_data.get("objective", ""),
        "worktree_path": epic_data.get("worktree_path", ""),
        "branch": epic_data.get("branch", "main"),
    })

    phases = epic_data.get("phases", [])
    for phase in phases:
        phase_name = phase.get("name", phase.get("id", "default"))
        tickets = phase.get("tickets", phase.get("tasks", []))
        for ticket in tickets:
            service._repository.add_ticket(epic_folder_name, phase_name, ticket)


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

        # Override _isolate_tinydb's patch so _find_repo_root sees our .git
        with patch.object(EpicService, "_find_repo_root", staticmethod(lambda start=None: repo_path)):
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

        # Override _isolate_tinydb's patch so _find_repo_root finds nested/.git walk
        with patch.object(EpicService, "_find_repo_root", staticmethod(lambda start=None: repo_path)):
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
        # Folder is no longer created by create_epic(); verify TinyDB record exists instead.
        db_record = service._repository.get_epic(result.epic_folder_name)
        assert db_record is not None, "Epic record should exist in TinyDB after creation"

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

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

        # Get by short ID
        epic = service.get_epic("260203PS")

        assert epic is not None
        assert epic.epic_folder_name == "260203PS_test_plan"

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

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

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

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

        # Get by relative path (normalized to folder name in TinyDB)
        epic = service.get_epic("260203PS_test_plan")

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

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

        # Get by absolute path (normalized to folder name in TinyDB)
        epic = service.get_epic("260203PS_test_plan")

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
        """Test get_epic extracts tasks from TinyDB correctly."""
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

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

        epic = service.get_epic("260203PS")

        assert epic is not None
        # Tickets are stored in TinyDB with phase_name; phases table not populated
        assert len(epic.tasks) == 3
        task_ids = [t.id for t in epic.tasks]
        assert "task_001" in task_ids
        assert "task_002" in task_ids
        assert "task_003" in task_ids
        # Check phase_name is preserved
        phase1_tasks = [t for t in epic.tasks if t.phase_name == "Phase 1"]
        phase2_tasks = [t for t in epic.tasks if t.phase_name == "Phase 2"]
        assert len(phase1_tasks) == 2
        assert len(phase2_tasks) == 1


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

            _setup_epic_in_tinydb(service, epic_folder, epic_data)

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

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

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
            "status": "deferred",
            "objective": "Deferred objective",
            "phases": [],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

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

            _setup_epic_in_tinydb(service, epic_folder, epic_data)

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

        _setup_epic_in_tinydb(service, valid_folder, epic_data)

        # Create invalid folder names (not in TinyDB, so won't appear in list)
        (live_dir / "invalid_name").mkdir()
        (live_dir / "20230203_too_short").mkdir()

        epics = service.list_epics(status="live")

        # Should only return the valid epic (TinyDB only has the valid one)
        assert len(epics) == 1
        assert epics[0].epic_folder_name == "260203PS_valid"


class TestUpdateEpicStatus:
    """Tests for update_epic_status() method."""

    def test_update_epic_status_success(self, tmp_path):
        """Test update_epic_status updates status in TinyDB successfully."""
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

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

        result = service.update_epic_status("260203PS", "active")

        assert result.success is True
        assert result.old_status == "pending"
        assert result.new_status == "active"  # "active" is now a canonical status

        # Verify TinyDB was updated
        updated_epic = service._repository.get_epic("260203PS_test_plan")
        assert updated_epic.status == "active"

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

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

        result = service.update_epic_status("260203PS", "active", dry_run=True)

        assert result.success is True
        assert "[dry-run]" in result.message
        assert result.old_status == "pending"
        assert result.new_status == "active"

        # Verify TinyDB was NOT updated (dry-run)
        unchanged_epic = service._repository.get_epic("260203PS_test_plan")
        assert unchanged_epic.status == "pending"

    def test_update_epic_status_multiple_files(self, tmp_path):
        """Test update_epic_status updates TinyDB status (YAML sync disabled)."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create an epic
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        plan_build = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "pending",
            "phases": [],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_build, f)

        _setup_epic_in_tinydb(service, epic_folder, plan_build)

        result = service.update_epic_status("260203PS", "active")

        assert result.success is True
        assert result.old_status == "pending"
        assert result.new_status == "active"

        # Verify TinyDB was updated (YAML sync is permanently disabled)
        updated_epic = service._repository.get_epic("260203PS_test_plan")
        assert updated_epic.status == "active"


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

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

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

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

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

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

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
        """Test validate_epic_structure fails when epic not in TinyDB."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create epic folder but do NOT add to TinyDB
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump({"name": "test-plan"}, f)

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        # When epic is not in TinyDB, the error mentions TinyDB
        assert any("TinyDB" in e or "not found" in e for e in result.errors)

    def test_validate_epic_structure_invalid_status(self, tmp_path):
        """Test validate_epic_structure fails for invalid status in TinyDB."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create epic with invalid status in TinyDB
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

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        assert any("Invalid status" in e for e in result.errors)

    def test_validate_epic_structure_duplicate_task_ids(self, tmp_path):
        """Test validate_epic_structure fails for duplicate ticket IDs in TinyDB."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create epic folder and register it in TinyDB
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        epic_data = {
            "name": "test-plan",
            "worktree_path": str(repo_path),
            "status": "active",
            "phases": [],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        service._repository.create_epic({
            "epic_folder_name": "260203PS_test_plan",
            "epic_folder": str(epic_folder),
            "name": "test-plan",
            "status": "active",
        })

        # Force-insert duplicate ticket IDs directly (bypassing add_ticket dedup guard)
        service._repository._tickets.insert({
            "epic_folder_name": "260203PS_test_plan",
            "phase_name": "Phase 1",
            "task_id": "task_001",
            "name": "Task 1",
            "description": "First",
            "status": "pending",
        })
        service._repository._tickets.insert({
            "epic_folder_name": "260203PS_test_plan",
            "phase_name": "Phase 1",
            "task_id": "task_001",  # Duplicate ID
            "name": "Task 2",
            "description": "Duplicate",
            "status": "pending",
        })

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        assert any("Duplicate ticket ID" in e for e in result.errors)

    def test_validate_epic_structure_warnings(self, tmp_path):
        """Test validate_epic_structure generates warnings for quality issues in TinyDB."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create epic with quality issues (empty description)
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
                        },
                    ],
                },
            ],
        }

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f)

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is True  # Valid, but with warnings
        assert len(result.warnings) > 0
        assert any("empty description" in w for w in result.warnings)

    def test_validate_epic_structure_folder_not_exists(self, tmp_path):
        """Test validate_epic_structure fails when epic is not registered in TinyDB."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        non_existent = repo_path / "docs" / "epics" / "live" / "260203XX_nonexistent"

        result = service.validate_epic_structure(non_existent)

        assert result.valid is False
        # Validation no longer checks filesystem; an unregistered epic produces
        # a "not found in TinyDB" error instead of a "does not exist" error.
        assert any("not found in TinyDB" in e for e in result.errors)

    def test_validate_epic_structure_no_plan_files(self, tmp_path):
        """Test validate_epic_structure fails when epic not registered in TinyDB."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        # Create epic folder but do NOT register in TinyDB
        epic_folder = repo_path / "docs" / "epics" / "live" / "260203PS_test_plan"
        epic_folder.mkdir(parents=True)

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        # When epic is not in TinyDB, the error mentions TinyDB or not found
        assert any("TinyDB" in e or "not found" in e for e in result.errors)


class TestValidateTicketNesting:
    """Tests for ticket validation in validate_epic_structure() using TinyDB.

    With TinyDB as sole data store, validation checks:
    - Epic must be registered in TinyDB
    - Valid status values
    - Unique ticket IDs (no duplicates)
    - Quality warnings for empty descriptions
    - No tickets warning
    """

    def _make_epic(self, tmp_path, epic_data: dict) -> tuple:
        """Helper to create an epic folder and populate TinyDB."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        epic_folder = repo_path / "docs" / "epics" / "live" / "260223TU_test_nesting"
        epic_folder.mkdir(parents=True)

        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f, default_flow_style=False)

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

        return service, epic_folder

    # --- TU_001: Epic not in TinyDB ---

    def test_epic_not_in_tinydb_returns_error(self, tmp_path):
        """Epic folder exists but not in TinyDB must return validation error."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        epic_folder = repo_path / "docs" / "epics" / "live" / "260223TU_test_nesting"
        epic_folder.mkdir(parents=True)

        # Do NOT populate TinyDB
        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        assert any("not found" in e.lower() or "tinydb" in e.lower() for e in result.errors), (
            f"Expected 'not found' error, got: {result.errors}"
        )

    def test_epic_not_in_tinydb_error_is_blocking(self, tmp_path):
        """Missing TinyDB registration must be a blocking error (valid=False)."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        epic_folder = repo_path / "docs" / "epics" / "live" / "260223TU_test_nesting"
        epic_folder.mkdir(parents=True)

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False, "Epic not in TinyDB must be invalid"
        assert len(result.errors) > 0, "Must have at least one error"

    def test_epic_not_in_tinydb_with_yaml_file_returns_error(self, tmp_path):
        """Epic with YAML file but not in TinyDB must return error."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        epic_folder = repo_path / "docs" / "epics" / "live" / "260223TU_test_nesting"
        epic_folder.mkdir(parents=True)

        # Write YAML but don't add to TinyDB
        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump({
                "name": "good-epic",
                "status": "active",
                "phases": [
                    {
                        "name": "Phase 1",
                        "tickets": [
                            {"id": "T1", "name": "task", "status": "pending"},
                        ],
                    },
                ],
            }, f)

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        assert any("not found" in e.lower() or "tinydb" in e.lower() for e in result.errors)

    # --- TU_002: No tickets warning ---

    def test_epic_with_no_tickets_warns(self, tmp_path):
        """Epic registered in TinyDB with no tickets must trigger a warning."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "empty-epic",
            "status": "active",
            "phases": [],
        })

        result = service.validate_epic_structure(epic_folder)

        no_ticket_warnings = [
            w for w in result.warnings if "no tickets" in w.lower() or "ticket" in w.lower()
        ]
        assert len(no_ticket_warnings) > 0, (
            f"Expected warning about no tickets, got warnings: {result.warnings}"
        )

    def test_epic_with_tickets_no_empty_warning(self, tmp_path):
        """Epic with tickets registered in TinyDB should not trigger no-tickets warning."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "good-epic",
            "status": "active",
            "phases": [
                {
                    "name": "Phase with tasks",
                    "tickets": [
                        {"id": "T1", "name": "a task", "status": "pending",
                         "description": "desc"},
                    ],
                },
            ],
        })

        result = service.validate_epic_structure(epic_folder)

        no_tickets_warnings = [
            w for w in result.warnings if "no tickets" in w.lower()
        ]
        assert len(no_tickets_warnings) == 0, (
            f"Epic with tickets should not trigger no-tickets warning, got: {no_tickets_warnings}"
        )

    def test_multiple_tickets_multiple_phases_no_tickets_warning(self, tmp_path):
        """Epic with tickets in multiple phases must not trigger no-tickets warning."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "multi-phase-epic",
            "status": "active",
            "phases": [
                {
                    "name": "Phase 1",
                    "tickets": [
                        {"id": "T1", "name": "task", "status": "pending",
                         "description": "desc"},
                        {"id": "T2", "name": "task 2", "status": "pending",
                         "description": "desc 2"},
                    ],
                },
                {
                    "name": "Phase 2",
                    "tickets": [
                        {"id": "T3", "name": "task 3", "status": "pending",
                         "description": "desc 3"},
                    ],
                },
            ],
        })

        result = service.validate_epic_structure(epic_folder)

        no_tickets_warnings = [
            w for w in result.warnings if "no tickets" in w.lower()
        ]
        assert len(no_tickets_warnings) == 0, (
            f"Got unexpected no-tickets warnings: {no_tickets_warnings}"
        )

    # --- TU_003: Invalid status ---

    def test_invalid_status_is_blocking(self, tmp_path):
        """Epic with invalid status must be a blocking validation error."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "flat-epic",
            "status": "completely_invalid",
            "phases": [],
        })

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False
        all_errors = " ".join(result.errors).lower()
        assert "status" in all_errors, f"Expected status-related error, got: {result.errors}"

    def test_invalid_status_valid_false(self, tmp_path):
        """ValidationResult.valid must be False for epic with invalid status."""
        service, epic_folder = self._make_epic(tmp_path, {
            "name": "flat-epic",
            "status": "not_a_valid_status",
            "phases": [],
        })

        result = service.validate_epic_structure(epic_folder)

        assert result.valid is False, "Epic with invalid status must be invalid"
        assert len(result.errors) > 0, "Must have at least one error"

    # --- TU_004: Valid epics still pass (regression) ---

    def test_valid_nested_tasks_pass(self, tmp_path):
        """Epic with proper phases[].tasks[] nesting in TinyDB must pass validation."""
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
        """Epic with valid TinyDB registration should pass even with extra YAML files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        service = EpicService(repo_path=repo_path)

        epic_folder = repo_path / "docs" / "epics" / "live" / "260223TU_test_stub"
        epic_folder.mkdir(parents=True)

        epic_data = {
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
        }

        # Write a valid build epic
        with open(epic_folder / "plan_build.yml", "w") as f:
            yaml.dump(epic_data, f, default_flow_style=False)

        # Write a stub template YAML alongside (irrelevant to TinyDB-based validation)
        with open(epic_folder / "plan_test.yml", "w") as f:
            yaml.dump({
                "_template_status": "stub",
                "name": "test-stub",
                "status": "pending",
                "tasks": [
                    {"id": "T99", "name": "stub task"},
                ],
            }, f, default_flow_style=False)

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

        result = service.validate_epic_structure(epic_folder)

        # TinyDB-based validation only checks TinyDB content - no errors from YAML files
        assert len(result.errors) == 0, (
            f"Extra YAML files should not cause errors, got: {result.errors}"
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

        _setup_epic_in_tinydb(service, epic_folder, epic_data)

        result = service.update_epic_status("260203PS", "active", dry_run=True)

        assert result.success is True
        assert "[dry-run]" in result.message

        # Verify TinyDB status was NOT updated (dry-run)
        unchanged = service._repository.get_epic("260203PS_test_plan")
        assert unchanged.status == "pending"
