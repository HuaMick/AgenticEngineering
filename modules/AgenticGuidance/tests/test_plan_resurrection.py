"""Tests for graceful plan resurrection (live-preference logic).

Covers:
- TE_001: find_plan_folder() prefers live/ when TinyDB points to completed/
- TE_002: PlanService.get_plan() and list_plans() with resurrected plans
- TE_003: Death loop scenario simulation

The "resurrection" scenario occurs when a plan is archived to completed/
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
import yaml


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def plans_base(tmp_path):
    """Create a plans base with live/ and completed/ directories."""
    base = tmp_path / "docs" / "plans"
    (base / "live").mkdir(parents=True)
    (base / "completed").mkdir(parents=True)
    return base


@pytest.fixture
def resurrected_plan(plans_base):
    """Create a plan that exists in both live/ and completed/.

    Simulates the resurrection scenario: the plan was archived to completed/
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
                "tasks": [
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
                "tasks": [
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
        """Create a git repo with a resurrected plan."""
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

        plans = repo_dir / "docs" / "plans"
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

    def test_tinydb_completed_path_resolved_to_live(self, git_repo_with_resurrection):
        """When TinyDB points to completed/ but live/ exists, return live/.

        find_plan_folder() imports PlanRepository locally; when TinyDB lookup
        fails (or isn't available), it falls through to the filesystem scan
        which correctly returns the live/ path.
        """
        from agenticcli.commands.plan import find_plan_folder

        repo_dir = git_repo_with_resurrection
        plan_name = "260222NE_resurrected"
        live_path = repo_dir / "docs" / "plans" / "live" / plan_name

        with patch("agenticcli.commands.plan.subprocess.run") as mock_run:
            mock_run.return_value.stdout = str(repo_dir) + "\n"
            mock_run.return_value.returncode = 0

            # The TinyDB import will fail (no DB), falling through to
            # filesystem scan which should find the live/ folder.
            result = find_plan_folder(plan_name)
            assert result == live_path

    def test_only_live_exists_returns_live(self, git_repo_with_resurrection):
        """When plan exists only in live/ (no TinyDB entry), return live/."""
        from agenticcli.commands.plan import find_plan_folder

        repo_dir = git_repo_with_resurrection
        live_path = repo_dir / "docs" / "plans" / "live" / "260222NE_resurrected"

        with patch("agenticcli.commands.plan.subprocess.run") as mock_run:
            mock_run.return_value.stdout = str(repo_dir) + "\n"
            mock_run.return_value.returncode = 0

            result = find_plan_folder("260222NE_resurrected")
            assert result == live_path

    def test_only_completed_returns_nothing(self, tmp_path):
        """When plan exists only in completed/ (normal archived plan), sys.exit(1)."""
        from agenticcli.commands.plan import find_plan_folder

        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=repo_dir, capture_output=True)

        completed_dir = repo_dir / "docs" / "plans" / "completed" / "260222NE_only_archived"
        completed_dir.mkdir(parents=True)
        (completed_dir / "plan_build.yml").write_text("name: Test\n")
        (repo_dir / "docs" / "plans" / "live").mkdir(parents=True)
        (repo_dir / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, capture_output=True)

        with patch("agenticcli.commands.plan.subprocess.run") as mock_run:
            mock_run.return_value.stdout = str(repo_dir) + "\n"
            mock_run.return_value.returncode = 0

            # No live/ folder for this plan -> should exit
            with pytest.raises(SystemExit) as exc_info:
                find_plan_folder("260222NE_only_archived")
            assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# TE_002: PlanService.get_plan() and list_plans() tests
# ---------------------------------------------------------------------------

class TestPlanServiceResurrection:
    """Tests for PlanService get_plan() and list_plans() with resurrected plans."""

    def test_get_plan_prefers_live_over_completed(self, resurrected_plan):
        """get_plan() should return the live/ version when both exist."""
        from agenticguidance.services.plan import PlanService

        plan_name, plans_base = resurrected_plan
        repo_root = plans_base.parent.parent  # docs/plans -> docs -> repo

        # Create a mock repository that returns completed/ path
        mock_repo = MagicMock()
        completed_path = plans_base / "completed" / plan_name
        live_path = plans_base / "live" / plan_name

        mock_plan_data = MagicMock()
        mock_plan_data.plan_folder = completed_path
        mock_plan_data.plan_folder_name = plan_name
        mock_repo.get_plan.return_value = mock_plan_data
        mock_repo.update_plan.return_value = MagicMock(success=True)
        mock_repo.resync_plan_folder.return_value = True

        service = PlanService(repo_path=repo_root)
        service._repository = mock_repo

        result = service.get_plan(plan_name)

        # Should have corrected to live/ path
        assert result is not None
        assert result.plan_folder == live_path
        # Should have triggered resync
        mock_repo.resync_plan_folder.assert_called_once_with(
            plan_name, str(live_path)
        )

    def test_get_plan_returns_completed_when_no_live(self, plans_base):
        """get_plan() should return completed/ path when no live/ version exists."""
        from agenticguidance.services.plan import PlanService

        plan_name = "260222NE_archived_only"
        completed_dir = plans_base / "completed" / plan_name
        completed_dir.mkdir()
        (completed_dir / "plan_build.yml").write_text(
            "name: Archived\nstatus: completed\nphases: []\n"
        )

        repo_root = plans_base.parent.parent

        mock_repo = MagicMock()
        mock_plan_data = MagicMock()
        mock_plan_data.plan_folder = completed_dir
        mock_plan_data.plan_folder_name = plan_name
        mock_repo.get_plan.return_value = mock_plan_data

        service = PlanService(repo_path=repo_root)
        service._repository = mock_repo

        result = service.get_plan(plan_name)

        assert result is not None
        assert result.plan_folder == completed_dir
        # Should NOT have triggered resync (no live/ version)
        mock_repo.resync_plan_folder.assert_not_called()

    def test_list_plans_includes_resurrected(self, resurrected_plan):
        """list_plans(status='live') should include plans found on filesystem
        even if TinyDB doesn't know about them."""
        from agenticguidance.services.plan import PlanMetadata, PlanService

        plan_name, plans_base = resurrected_plan
        repo_root = plans_base.parent.parent

        # Mock repository that returns NO live plans (because it only knows completed/)
        mock_repo = MagicMock()
        # Return a result that points to completed/ (not live/)
        completed_meta = PlanMetadata(
            plan_folder=plans_base / "completed" / plan_name,
            plan_folder_name=plan_name,
        )
        mock_repo.list_plans.return_value = [completed_meta]
        mock_repo.resync_plan_folder.return_value = True

        service = PlanService(repo_path=repo_root)
        service._repository = mock_repo

        results = service.list_plans(status="live")

        # Should find the resurrected plan via filesystem scan
        result_names = {r.plan_folder_name for r in results}
        assert plan_name in result_names, (
            f"Resurrected plan {plan_name} should appear in live list"
        )

        # The live/ version should be the one returned
        for r in results:
            if r.plan_folder_name == plan_name:
                assert "live" in str(r.plan_folder)
                break

    def test_list_plans_no_duplicates(self, resurrected_plan):
        """list_plans() should not return duplicates when TinyDB and filesystem
        both find the same plan."""
        from agenticguidance.services.plan import PlanMetadata, PlanService

        plan_name, plans_base = resurrected_plan
        repo_root = plans_base.parent.parent
        live_path = plans_base / "live" / plan_name

        # Mock repository that already returns the live/ path
        mock_repo = MagicMock()
        live_meta = PlanMetadata(
            plan_folder=live_path,
            plan_folder_name=plan_name,
        )
        mock_repo.list_plans.return_value = [live_meta]

        service = PlanService(repo_path=repo_root)
        service._repository = mock_repo

        results = service.list_plans(status="live")

        # Count occurrences of our plan
        count = sum(1 for r in results if r.plan_folder_name == plan_name)
        assert count == 1, f"Plan should appear exactly once, found {count} times"


# ---------------------------------------------------------------------------
# TE_003: Death loop simulation
# ---------------------------------------------------------------------------

class TestDeathLoopSimulation:
    """Simulate the scenario that causes infinite orchestration loops.

    Steps:
    1. Create a plan in live/, archive it to completed/
    2. Recreate the live/ folder manually
    3. Verify lookups operate on live/ folder (not completed/)
    """

    def test_archive_then_resurrect_prefers_live(self, tmp_path):
        """After archive + manual resurrection, get_plan returns live/ path."""
        from agenticguidance.services.plan import PlanService

        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        plans_base = repo_dir / "docs" / "plans"
        plan_name = "260222NE_death_loop"

        # Step 1: Create plan in live/
        live_dir = plans_base / "live" / plan_name
        live_dir.mkdir(parents=True)
        plan_yml = {
            "name": "Death Loop Test",
            "status": "in_progress",
            "objective": "Test death loop",
            "phases": [
                {
                    "name": "Build",
                    "tasks": [
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
        plan_yml["phases"][0]["tasks"].append(
            {"id": "T2", "name": "Task 2", "status": "pending"}
        )
        with open(live_dir / "plan_build.yml", "w") as f:
            yaml.dump(plan_yml, f, default_flow_style=False)

        # Step 4: Mock TinyDB repository that still points to completed/
        mock_repo = MagicMock()
        mock_plan_data = MagicMock()
        mock_plan_data.plan_folder = completed_dir
        mock_plan_data.plan_folder_name = plan_name
        mock_repo.get_plan.return_value = mock_plan_data
        mock_repo.resync_plan_folder.return_value = True

        service = PlanService(repo_path=repo_dir)
        service._repository = mock_repo

        # Step 5: Verify get_plan returns live/ path
        result = service.get_plan(plan_name)
        assert result is not None
        assert result.plan_folder == live_dir
        mock_repo.resync_plan_folder.assert_called_once()

    def test_list_plans_finds_resurrected_after_archive(self, tmp_path):
        """list_plans(status='live') finds resurrected plan even when
        TinyDB returns empty for live status."""
        from agenticguidance.services.plan import PlanService

        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        plans_base = repo_dir / "docs" / "plans"
        plan_name = "260222NE_death_loop_list"

        # Create live/ plan
        live_dir = plans_base / "live" / plan_name
        live_dir.mkdir(parents=True)
        (live_dir / "plan_build.yml").write_text(
            "name: Death Loop List\nstatus: in_progress\nobjective: Test\nphases: []\n"
        )
        (plans_base / "completed").mkdir(exist_ok=True)

        # Mock TinyDB that returns nothing for "live" status
        mock_repo = MagicMock()
        mock_repo.list_plans.return_value = []

        service = PlanService(repo_path=repo_dir)
        service._repository = mock_repo

        # Even though TinyDB returns nothing, filesystem scan should find it
        # Note: when tinydb_results is empty (falsy), the code falls through
        # to the YAML scan path which DOES scan the filesystem.
        results = service.list_plans(status="live")
        result_names = {r.plan_folder_name for r in results}
        assert plan_name in result_names


# ---------------------------------------------------------------------------
# PlanRepository.resync_plan_folder() tests
# ---------------------------------------------------------------------------

class TestResyncPlanFolder:
    """Tests for PlanRepository.resync_plan_folder()."""

    def test_resync_updates_path_and_reimports(self, tmp_path):
        """resync_plan_folder should update plan_folder and re-import YAML."""
        from agenticguidance.services.plan_repository import PlanRepository

        db_path = tmp_path / "test.db"

        # Create a plan folder
        plan_dir = tmp_path / "live" / "260222NE_resync_test"
        plan_dir.mkdir(parents=True)
        (plan_dir / "plan_build.yml").write_text(
            yaml.dump({
                "name": "Resync Test",
                "status": "in_progress",
                "phases": [
                    {
                        "name": "Phase 1",
                        "tasks": [
                            {"id": "R1", "name": "Task R1", "status": "pending"},
                        ],
                    }
                ],
            })
        )

        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)

        # First import from an old location
        old_dir = tmp_path / "completed" / "260222NE_resync_test"
        old_dir.mkdir(parents=True)
        (old_dir / "plan_build.yml").write_text(
            yaml.dump({
                "name": "Resync Test",
                "status": "completed",
                "phases": [],
            })
        )
        repo.import_from_yaml(old_dir)

        # Verify it's pointing to old location
        plan = repo.get_plan("260222NE_resync_test")
        assert plan is not None
        assert plan.plan_folder == old_dir

        # Resync to new location
        result = repo.resync_plan_folder("260222NE_resync_test", str(plan_dir))
        assert result is True

        # Verify path updated
        plan = repo.get_plan("260222NE_resync_test")
        assert plan is not None
        assert plan.plan_folder == plan_dir

        # Verify tasks were re-imported from new location
        tasks = repo.get_tasks("260222NE_resync_test")
        task_ids = [t.id for t in tasks]
        assert "R1" in task_ids

        repo.close()

    def test_resync_nonexistent_plan_returns_false(self, tmp_path):
        """resync_plan_folder returns False for unknown plan."""
        from agenticguidance.services.plan_repository import PlanRepository

        db_path = tmp_path / "test.db"
        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)

        result = repo.resync_plan_folder("nonexistent_plan", "/tmp/nope")
        assert result is False

        repo.close()

    def test_resync_invalid_path_returns_false(self, tmp_path):
        """resync_plan_folder returns False when new_folder doesn't exist."""
        from agenticguidance.services.plan_repository import PlanRepository

        db_path = tmp_path / "test.db"
        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)

        # Create a plan
        plan_dir = tmp_path / "plans" / "260222NE_bad_path"
        plan_dir.mkdir(parents=True)
        (plan_dir / "plan_build.yml").write_text("name: Test\nstatus: pending\nphases: []\n")
        repo.import_from_yaml(plan_dir)

        # Try to resync to non-existent path
        result = repo.resync_plan_folder("260222NE_bad_path", "/tmp/does_not_exist_xyz")
        assert result is False

        repo.close()
