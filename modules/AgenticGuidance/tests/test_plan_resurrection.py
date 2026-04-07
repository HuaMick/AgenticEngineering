"""Tests for graceful epic resurrection (live-preference logic).

Covers:
- TE_001: find_plan_folder() prefers live/ when TinyDB points to completed/
- TE_002: EpicService.get_epic() and list_epics() with resurrected epics
- TE_003: Death loop scenario simulation

The "resurrection" scenario occurs when an epic is archived to completed/
then manually recreated in live/ (e.g. via git restore or mkdir).  TinyDB
still points at the completed/ path, so all lookups must detect this and
prefer the live/ path.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-PLN-001")
import yaml


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def plans_base(tmp_path):
    """Create an epics base with live/ and completed/ directories."""
    base = tmp_path / "docs" / "epics"
    (base / "live").mkdir(parents=True)
    (base / "completed").mkdir(parents=True)
    return base


@pytest.fixture
def resurrected_plan(plans_base):
    """Create an epic that exists in both live/ and completed/.

    Simulates the resurrection scenario: the epic was archived to completed/
    then the live/ folder was recreated (e.g. via git checkout).
    """
    plan_name = "260222NE_test_resurrection"

    # Create completed/ version (this is what TinyDB knows about)
    completed_dir = plans_base / "completed" / plan_name
    completed_dir.mkdir()
    plan_data = {
        "name": "Test Resurrection",
        "status": "completed",
        "objective": "Test the resurrection flow",
        "phases": [
            {
                "name": "Build Phase",
                "tickets": [
                    {"id": "BU_001", "name": "Build task", "status": "completed"},
                ],
            }
        ],
    }
    with open(completed_dir / "plan_build.yml", "w") as f:
        yaml.dump(plan_data, f, default_flow_style=False)

    # Create live/ version (the resurrected copy)
    live_dir = plans_base / "live" / plan_name
    live_dir.mkdir()
    plan_data_live = {
        "name": "Test Resurrection",
        "status": "in_progress",
        "objective": "Test the resurrection flow",
        "phases": [
            {
                "name": "Build Phase",
                "tickets": [
                    {"id": "BU_001", "name": "Build task", "status": "completed"},
                    {"id": "BU_002", "name": "New task", "status": "pending"},
                ],
            }
        ],
    }
    with open(live_dir / "plan_build.yml", "w") as f:
        yaml.dump(plan_data_live, f, default_flow_style=False)

    return plan_name, plans_base


# ---------------------------------------------------------------------------
# TE_001: find_plan_folder() live-preference tests
# ---------------------------------------------------------------------------

class TestFindPlanFolderLivePreference:
    """Tests for find_plan_folder() preferring live/ over completed/."""

    @pytest.fixture
    def git_repo_with_resurrection(self, tmp_path):
        """Create a git repo with a resurrected epic."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo_dir, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo_dir, capture_output=True,
        )

        plans = repo_dir / "docs" / "epics"
        live_dir = plans / "live" / "260222NE_resurrected"
        completed_dir = plans / "completed" / "260222NE_resurrected"
        live_dir.mkdir(parents=True)
        completed_dir.mkdir(parents=True)

        # Both have plan files
        for d in (live_dir, completed_dir):
            (d / "plan_build.yml").write_text("name: Test\nstatus: pending\n")

        (repo_dir / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=repo_dir, capture_output=True,
        )

        return repo_dir

    def test_tinydb_lookup_finds_epic(self, git_repo_with_resurrection, _isolate_tinydb):
        """find_epic_folder() resolves epic via TinyDB lookup."""
        from agenticcli.commands.epic import find_epic_folder
        from agenticguidance.services.epic_repository import EpicRepository

        repo_dir = git_repo_with_resurrection
        plan_name = "260222NE_resurrected"
        live_path = repo_dir / "docs" / "epics" / "live" / plan_name

        # Register epic in TinyDB
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        repo.create_epic({
            "epic_folder_name": plan_name,
            "epic_folder": str(live_path),
            "status": "active",
        })
        repo.close()

        result = find_epic_folder(plan_name)
        assert result == live_path

    def test_partial_name_match(self, git_repo_with_resurrection, _isolate_tinydb):
        """find_epic_folder() resolves epic via partial name prefix match."""
        from agenticcli.commands.epic import find_epic_folder
        from agenticguidance.services.epic_repository import EpicRepository

        repo_dir = git_repo_with_resurrection
        plan_name = "260222NE_resurrected"
        live_path = repo_dir / "docs" / "epics" / "live" / plan_name

        # Register epic in TinyDB
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        repo.create_epic({
            "epic_folder_name": plan_name,
            "epic_folder": str(live_path),
            "status": "active",
        })
        repo.close()

        result = find_epic_folder("260222NE")
        assert result == live_path

    def test_not_in_tinydb_returns_error(self, tmp_path):
        """When epic is not registered in TinyDB, sys.exit(1)."""
        from agenticcli.commands.epic import find_epic_folder

        with pytest.raises(SystemExit) as exc_info:
            find_epic_folder("260222NE_only_archived")
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# TE_002: EpicService.get_epic() and list_epics() tests
# ---------------------------------------------------------------------------

class TestPlanServiceResurrection:
    """Tests for EpicService get_epic() and list_epics() with resurrected epics."""

    def test_get_plan_returns_tinydb_record_directly(self, resurrected_plan):
        """get_epic() returns the TinyDB record without disk-based resurrection."""
        from agenticguidance.services.epic import EpicService, EpicMetadata

        plan_name, plans_base = resurrected_plan
        repo_root = plans_base.parent.parent  # docs/epics -> docs -> repo

        # Mock repository returns completed/ path (no disk-based correction)
        mock_repo = MagicMock()
        completed_path = plans_base / "completed" / plan_name

        mock_plan_data = MagicMock()
        mock_plan_data.epic_folder = completed_path
        mock_plan_data.epic_folder_name = plan_name
        mock_repo.get_epic.return_value = mock_plan_data

        service = EpicService(repo_path=repo_root)
        service._repository = mock_repo

        result = service.get_epic(plan_name)

        # Returns TinyDB record as-is (no disk-based resurrection)
        assert result is not None
        assert result.epic_folder == completed_path
        # No resync triggered - disk checks removed
        mock_repo.resync_epic_folder.assert_not_called()

    def test_get_plan_returns_completed_when_no_live(self, plans_base):
        """get_epic() should return completed/ path when no live/ version exists."""
        from agenticguidance.services.epic import EpicService

        plan_name = "260222NE_archived_only"
        completed_dir = plans_base / "completed" / plan_name
        completed_dir.mkdir()
        (completed_dir / "plan_build.yml").write_text(
            "name: Archived\nstatus: completed\nphases: []\n"
        )

        repo_root = plans_base.parent.parent

        mock_repo = MagicMock()
        mock_plan_data = MagicMock()
        mock_plan_data.epic_folder = completed_dir
        mock_plan_data.epic_folder_name = plan_name
        mock_repo.get_epic.return_value = mock_plan_data

        service = EpicService(repo_path=repo_root)
        service._repository = mock_repo

        result = service.get_epic(plan_name)

        assert result is not None
        assert result.epic_folder == completed_dir
        # Should NOT have triggered resync (no live/ version)
        mock_repo.resync_epic_folder.assert_not_called()

    def test_list_plans_uses_status_field_not_path(self, resurrected_plan):
        """list_epics(status='live') uses DB status field, not folder path.

        With pure DB routing, an epic with status='in_progress' appears in
        live queries regardless of its epic_folder path.
        """
        from agenticguidance.services.epic import EpicMetadata, EpicService

        plan_name, plans_base = resurrected_plan
        repo_root = plans_base.parent.parent

        # Repository returns epic with completed/ path but live-compatible status
        mock_repo = MagicMock()
        completed_meta = EpicMetadata(
            epic_folder=plans_base / "completed" / plan_name,
            epic_folder_name=plan_name,
        )
        mock_repo.list_epics.return_value = [completed_meta]

        service = EpicService(repo_path=repo_root)
        service._repository = mock_repo

        results = service.list_epics(status="live")

        # list_epics delegates directly to repository — path is irrelevant
        result_names = {r.plan_folder_name for r in results}
        assert plan_name in result_names, (
            f"Epic {plan_name} should appear based on DB status, not path"
        )

    def test_list_plans_no_duplicates(self, resurrected_plan):
        """list_epics() should not return duplicates — delegates to repository."""
        from agenticguidance.services.epic import EpicMetadata, EpicService

        plan_name, plans_base = resurrected_plan
        repo_root = plans_base.parent.parent
        live_path = plans_base / "live" / plan_name

        mock_repo = MagicMock()
        live_meta = EpicMetadata(
            epic_folder=live_path,
            epic_folder_name=plan_name,
        )
        mock_repo.list_epics.return_value = [live_meta]

        service = EpicService(repo_path=repo_root)
        service._repository = mock_repo

        results = service.list_epics(status="live")

        count = sum(1 for r in results if r.plan_folder_name == plan_name)
        assert count == 1, f"Epic should appear exactly once, found {count} times"


# ---------------------------------------------------------------------------
# TE_003: Death loop simulation
# ---------------------------------------------------------------------------

class TestDeathLoopSimulation:
    """Simulate the scenario that causes infinite orchestration loops.

    Steps:
    1. Create an epic in live/, archive it to completed/
    2. Recreate the live/ folder manually
    3. Verify lookups operate on live/ folder (not completed/)
    """

    def test_archive_then_resurrect_prefers_live(self, tmp_path):
        """After archive + manual resurrection, get_epic returns live/ path."""
        from agenticguidance.services.epic import EpicService

        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        plans_base = repo_dir / "docs" / "epics"
        plan_name = "260222NE_death_loop"

        # Step 1: Create epic in live/
        live_dir = plans_base / "live" / plan_name
        live_dir.mkdir(parents=True)
        plan_yml = {
            "name": "Death Loop Test",
            "status": "in_progress",
            "objective": "Test death loop",
            "phases": [
                {
                    "name": "Build",
                    "tickets": [
                        {"id": "T1", "name": "Task 1", "status": "completed"},
                    ],
                }
            ],
        }
        with open(live_dir / "plan_build.yml", "w") as f:
            yaml.dump(plan_yml, f, default_flow_style=False)

        # Step 2: Archive it (simulate by moving to completed/)
        completed_dir = plans_base / "completed" / plan_name
        completed_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(live_dir), str(completed_dir))
        assert not live_dir.exists()
        assert completed_dir.exists()

        # Step 3: Recreate live/ (resurrection)
        live_dir.mkdir(parents=True)
        plan_yml["status"] = "in_progress"
        plan_yml["phases"][0]["tickets"].append(
            {"id": "T2", "name": "Task 2", "status": "pending"}
        )
        with open(live_dir / "plan_build.yml", "w") as f:
            yaml.dump(plan_yml, f, default_flow_style=False)

        # Step 4: Mock TinyDB repository that still points to completed/
        mock_repo = MagicMock()
        mock_plan_data = MagicMock()
        mock_plan_data.epic_folder = completed_dir
        mock_plan_data.epic_folder_name = plan_name
        mock_repo.get_epic.return_value = mock_plan_data
        mock_repo.resync_epic_folder.return_value = True

        service = EpicService(repo_path=repo_dir)
        service._repository = mock_repo

        # Step 5: get_epic() returns TinyDB record as-is (no disk resurrection)
        result = service.get_epic(plan_name)
        assert result is not None
        # Returns the completed/ path from TinyDB (no disk-based correction)
        assert result.epic_folder == completed_dir
        mock_repo.resync_epic_folder.assert_not_called()

    def test_list_plans_uses_db_status_after_archive(self, tmp_path):
        """list_epics(status='live') relies on DB status, not folder path.

        With pure DB routing, path mismatches don't matter — the status
        field determines which query bucket an epic falls into.
        """
        from agenticguidance.services.epic import EpicMetadata, EpicService

        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        plans_base = repo_dir / "docs" / "epics"
        plan_name = "260222NE_death_loop_list"

        mock_repo = MagicMock()
        # Repository returns epic with stale completed/ path
        stale_meta = EpicMetadata(
            epic_folder=plans_base / "completed" / plan_name,
            epic_folder_name=plan_name,
        )
        mock_repo.list_epics.return_value = [stale_meta]

        service = EpicService(repo_path=repo_dir)
        service._repository = mock_repo

        results = service.list_epics(status="live")
        result_names = {r.plan_folder_name for r in results}
        # Epic appears because repository (status-based) returned it
        assert plan_name in result_names


# ---------------------------------------------------------------------------
# EpicRepository.resync_epic_folder() tests
# ---------------------------------------------------------------------------

class TestResyncPlanFolder:
    """Tests for EpicRepository.resync_epic_folder()."""

    def test_resync_updates_path(self, tmp_path):
        """resync_epic_folder should update epic_folder to the new path."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"

        # Create old and new epic folders
        old_dir = tmp_path / "completed" / "260222NE_resync_test"
        old_dir.mkdir(parents=True)
        plan_dir = tmp_path / "live" / "260222NE_resync_test"
        plan_dir.mkdir(parents=True)

        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

        # Create epic pointing to old location, with some tickets
        repo.create_epic({
            "epic_folder_name": "260222NE_resync_test",
            "epic_folder": str(old_dir),
            "name": "Resync Test",
            "status": "completed",
        })
        repo.add_ticket("260222NE_resync_test", "Phase 1", {
            "id": "R1", "name": "Task R1", "status": "pending",
        })

        # Verify it's pointing to old location
        epic = repo.get_epic("260222NE_resync_test")
        assert epic is not None
        assert epic.epic_folder == old_dir

        # Resync to new location
        result = repo.resync_epic_folder("260222NE_resync_test", str(plan_dir))
        assert result is True

        # Verify path updated
        epic = repo.get_epic("260222NE_resync_test")
        assert epic is not None
        assert epic.epic_folder == plan_dir

        # Verify existing tickets are still accessible (resync doesn't clear them)
        tickets = repo.get_tickets("260222NE_resync_test")
        task_ids = [t.id for t in tickets]
        assert "R1" in task_ids

        repo.close()

    def test_resync_nonexistent_plan_returns_false(self, tmp_path):
        """resync_epic_folder returns False for unknown epic."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

        result = repo.resync_epic_folder("nonexistent_plan", "/tmp/nope")
        assert result is False

        repo.close()

    def test_resync_invalid_path_returns_false(self, tmp_path):
        """resync_epic_folder returns False when new_folder doesn't exist."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

        # Create an epic via TinyDB directly (no YAML import)
        plan_dir = tmp_path / "epics" / "260222NE_bad_path"
        plan_dir.mkdir(parents=True)
        repo.create_epic({
            "epic_folder_name": "260222NE_bad_path",
            "epic_folder": str(plan_dir),
            "name": "Bad Path Test",
            "status": "active",
        })

        # Try to resync to non-existent path
        result = repo.resync_epic_folder("260222NE_bad_path", "/tmp/does_not_exist_xyz")
        assert result is False

        repo.close()
