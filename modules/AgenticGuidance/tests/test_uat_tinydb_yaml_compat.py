"""UAT tests for TinyDB/YAML compatibility user stories.

Covers acceptance criteria for:
  US-GD-202 - YAML Import/Export
  US-GD-205 - Database Location
  US-GD-206 - Backward Compatibility

Each test class maps directly to a user story criterion.  Tests use isolated
tmp_path fixtures and real (non-mocked) PlanRepository instances wherever
possible to avoid reward-hacking patterns.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _write_plan_yaml(folder: Path, data: dict) -> Path:
    """Write a plan_build.yml into folder and return the file path."""
    folder.mkdir(parents=True, exist_ok=True)
    plan_file = folder / "plan_build.yml"
    with open(plan_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return plan_file


def _minimal_plan_data(folder_name: str, status: str = "pending") -> dict:
    """Return a complete plan dict suitable for round-trip tests."""
    return {
        "name": folder_name,
        "status": status,
        "priority": "high",
        "objective": f"Objective for {folder_name}",
        "created": "2026-02-24",
        "branch": "main",
        "worktree_path": "/tmp/repo",
        "context": "Test context value",
        "phases": [
            {
                "name": "Alpha Phase",
                "description": "First phase",
                "execution": "sequential",
                "tasks": [
                    {
                        "id": "A001",
                        "name": "Task Alpha",
                        "description": "Do alpha work",
                        "status": "pending",
                        "agent": "builder",
                        "success_criteria": "Alpha done",
                    },
                    {
                        "id": "A002",
                        "name": "Task Beta",
                        "description": "Do beta work",
                        "status": "completed",
                        "agent": "runner",
                        "completed_date": "2026-02-20",
                    },
                ],
            },
            {
                "name": "Beta Phase",
                "description": "Second phase",
                "tasks": [
                    {
                        "id": "B001",
                        "name": "Task Gamma",
                        "description": "Do gamma work",
                        "status": "in_progress",
                    },
                ],
            },
        ],
    }


@pytest.fixture
def isolated_repo(tmp_path):
    """Provide a tmp directory structured like a git repo with plans layout."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "docs" / "plans" / "live").mkdir(parents=True)
    (repo / "docs" / "plans" / "completed").mkdir(parents=True)
    (repo / "docs" / "plans" / "deferred").mkdir(parents=True)
    return repo


@pytest.fixture
def repo_db(isolated_repo):
    """Return an isolated PlanRepository backed by the isolated_repo tmp dir."""
    from agenticguidance.services.plan_repository import PlanRepository

    db_path = isolated_repo / ".agentic" / "plans.db"
    repo = PlanRepository(db_path=db_path, auto_bootstrap=False)
    yield repo
    repo.close()


# ===========================================================================
# US-GD-202: YAML Import/Export
# ===========================================================================


class TestUS_GD_202_SyncToYaml:
    """US-GD-202 - Criterion 1: sync_to_yaml() writes plan data back to YAML."""

    def test_sync_to_yaml_creates_plan_build_yml(self, tmp_path):
        """sync_to_yaml() writes a plan_build.yml with current DB state."""
        from agenticguidance.services.plan_repository import PlanRepository

        plan_name = "260224TE_sync_test"
        plan_dir = tmp_path / "plans" / "live" / plan_name
        _write_plan_yaml(plan_dir, _minimal_plan_data(plan_name))

        db_path = tmp_path / "plans.db"
        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)
        repo.import_from_yaml(plan_dir)

        # Remove plan_build.yml so we can confirm sync recreates it
        (plan_dir / "plan_build.yml").unlink()
        assert not (plan_dir / "plan_build.yml").exists()

        result = repo.sync_to_yaml(plan_name)
        repo.close()

        assert result is True, "sync_to_yaml should return True on success"
        assert (plan_dir / "plan_build.yml").exists(), "plan_build.yml should be recreated"

    def test_sync_to_yaml_content_matches_db_state(self, tmp_path):
        """sync_to_yaml() writes plan fields that match what is stored in TinyDB."""
        from agenticguidance.services.plan_repository import PlanRepository

        plan_name = "260224TE_content_check"
        plan_dir = tmp_path / "plans" / "live" / plan_name
        original_data = _minimal_plan_data(plan_name)
        _write_plan_yaml(plan_dir, original_data)

        db_path = tmp_path / "plans.db"
        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)
        repo.import_from_yaml(plan_dir)

        # Mutate status in TinyDB
        repo.update_plan(plan_name, {"status": "active"})

        # Sync back to YAML
        repo.sync_to_yaml(plan_name)
        repo.close()

        with open(plan_dir / "plan_build.yml") as f:
            written = yaml.safe_load(f)

        assert written["status"] == "active", "sync_to_yaml should reflect DB status update"
        assert written["name"] == original_data["name"]
        assert written["objective"] == original_data["objective"]
        assert written["priority"] == original_data["priority"]

    def test_sync_to_yaml_returns_false_for_unknown_plan(self, tmp_path):
        """sync_to_yaml() returns False when the plan does not exist in DB."""
        from agenticguidance.services.plan_repository import PlanRepository

        db_path = tmp_path / "plans.db"
        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)
        result = repo.sync_to_yaml("nonexistent_plan_xyz")
        repo.close()

        assert result is False

    def test_sync_to_yaml_returns_false_when_folder_missing(self, tmp_path):
        """sync_to_yaml() returns False when the stored plan_folder doesn't exist."""
        from agenticguidance.services.plan_repository import PlanRepository

        plan_name = "260224TE_missing_dir"
        db_path = tmp_path / "plans.db"
        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)

        # Insert plan pointing to a non-existent directory
        repo.create_plan({
            "plan_folder_name": plan_name,
            "plan_folder": str(tmp_path / "does_not_exist" / plan_name),
            "status": "pending",
            "objective": "Test",
        })

        result = repo.sync_to_yaml(plan_name)
        repo.close()

        assert result is False


class TestUS_GD_202_ReadThrough:
    """US-GD-202 - Criterion 2: Auto-import from YAML on TinyDB cache miss."""

    def test_get_plan_imports_yaml_on_cache_miss(self, isolated_repo):
        """PlanService.get_plan() imports from YAML when TinyDB has no record."""
        from agenticguidance.services.plan import PlanService

        plan_name = "260224TE_cache_miss"
        plan_dir = isolated_repo / "docs" / "plans" / "live" / plan_name
        _write_plan_yaml(plan_dir, _minimal_plan_data(plan_name))

        # Service starts with empty TinyDB (auto_bootstrap not triggered
        # because the live/ directory didn't exist at PlanRepository init time
        # - we use a fresh service pointed at isolated_repo)
        service = PlanService(repo_path=isolated_repo)

        # DB is empty; get_plan should trigger YAML import (read-through)
        result = service.get_plan(plan_name)

        assert result is not None, "get_plan should return data via read-through import"
        assert result.plan_folder_name == plan_name
        assert result.objective is not None

    def test_get_plan_tasks_read_through_imports_yaml(self, isolated_repo):
        """get_plan_tasks() triggers YAML import when plan is absent from TinyDB."""
        from agenticguidance.services.plan import PlanService

        plan_name = "260224TE_tasks_read_through"
        plan_dir = isolated_repo / "docs" / "plans" / "live" / plan_name
        _write_plan_yaml(plan_dir, _minimal_plan_data(plan_name))

        service = PlanService(repo_path=isolated_repo)
        tasks = service.get_plan_tasks(plan_name)

        assert len(tasks) > 0, "Should import tasks from YAML on cache miss"
        task_ids = {t.id for t in tasks}
        assert "A001" in task_ids
        assert "A002" in task_ids
        assert "B001" in task_ids

    def test_list_plans_imports_disk_plans_not_in_tinydb(self, isolated_repo):
        """list_plans() reconciles disk plans that TinyDB doesn't know about."""
        from agenticguidance.services.plan import PlanService

        plan_name = "260224TE_disk_only_plan"
        plan_dir = isolated_repo / "docs" / "plans" / "live" / plan_name
        _write_plan_yaml(plan_dir, _minimal_plan_data(plan_name))

        service = PlanService(repo_path=isolated_repo)
        plans = service.list_plans(status="live")

        plan_names = {p.plan_folder_name for p in plans}
        assert plan_name in plan_names, (
            "list_plans() should discover plans on disk and import them into TinyDB"
        )


class TestUS_GD_202_RoundTrip:
    """US-GD-202 - Criteria 3 & 4: YAML -> TinyDB -> YAML round-trip."""

    def test_round_trip_preserves_plan_fields(self, tmp_path):
        """Importing YAML then exporting back preserves top-level plan fields."""
        from agenticguidance.services.plan_repository import PlanRepository

        plan_name = "260224TE_round_trip"
        plan_dir = tmp_path / "plans" / plan_name
        original = _minimal_plan_data(plan_name)
        _write_plan_yaml(plan_dir, original)

        db_path = tmp_path / "plans.db"
        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)
        assert repo.import_from_yaml(plan_dir) is True

        # Export to a new folder to isolate the round-trip output
        out_dir = tmp_path / "out" / plan_name
        out_dir.mkdir(parents=True)
        assert repo.export_to_yaml(plan_name, out_dir) is True
        repo.close()

        with open(out_dir / "plan_build.yml") as f:
            exported = yaml.safe_load(f)

        assert exported["name"] == original["name"]
        assert exported["status"] == original["status"]
        assert exported["priority"] == original["priority"]
        assert exported["objective"] == original["objective"]
        assert exported["created"] == original["created"]
        assert exported["branch"] == original["branch"]

    def test_round_trip_preserves_phases(self, tmp_path):
        """Importing YAML then exporting back preserves phase structure."""
        from agenticguidance.services.plan_repository import PlanRepository

        plan_name = "260224TE_phase_round_trip"
        plan_dir = tmp_path / "plans" / plan_name
        original = _minimal_plan_data(plan_name)
        _write_plan_yaml(plan_dir, original)

        db_path = tmp_path / "plans.db"
        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)
        repo.import_from_yaml(plan_dir)

        out_dir = tmp_path / "out" / plan_name
        out_dir.mkdir(parents=True)
        repo.export_to_yaml(plan_name, out_dir)
        repo.close()

        with open(out_dir / "plan_build.yml") as f:
            exported = yaml.safe_load(f)

        assert len(exported["phases"]) == 2, "Both phases should survive round-trip"
        phase_names = [p["name"] for p in exported["phases"]]
        assert "Alpha Phase" in phase_names
        assert "Beta Phase" in phase_names

    def test_round_trip_preserves_tasks(self, tmp_path):
        """Importing YAML then exporting back preserves all task fields."""
        from agenticguidance.services.plan_repository import PlanRepository

        plan_name = "260224TE_task_round_trip"
        plan_dir = tmp_path / "plans" / plan_name
        original = _minimal_plan_data(plan_name)
        _write_plan_yaml(plan_dir, original)

        db_path = tmp_path / "plans.db"
        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)
        repo.import_from_yaml(plan_dir)

        out_dir = tmp_path / "out" / plan_name
        out_dir.mkdir(parents=True)
        repo.export_to_yaml(plan_name, out_dir)
        repo.close()

        with open(out_dir / "plan_build.yml") as f:
            exported = yaml.safe_load(f)

        all_tasks = []
        for phase in exported["phases"]:
            all_tasks.extend(phase.get("tasks", []))

        task_ids = {t["id"] for t in all_tasks}
        assert "A001" in task_ids, "Task A001 should survive round-trip"
        assert "A002" in task_ids, "Task A002 should survive round-trip"
        assert "B001" in task_ids, "Task B001 should survive round-trip"

        # Verify key task fields
        a001 = next(t for t in all_tasks if t["id"] == "A001")
        assert a001["name"] == "Task Alpha"
        assert a001["status"] == "pending"
        assert a001["agent"] == "builder"

        a002 = next(t for t in all_tasks if t["id"] == "A002")
        assert a002["status"] == "completed"

    def test_round_trip_metadata_preserved_with_context(self, tmp_path):
        """Optional metadata fields (context, branch, worktree_path) survive round-trip."""
        from agenticguidance.services.plan_repository import PlanRepository

        plan_name = "260224TE_metadata_trip"
        plan_dir = tmp_path / "plans" / plan_name
        original = {
            "name": plan_name,
            "status": "active",
            "objective": "Test metadata",
            "created": "2026-02-24",
            "branch": "feature/test-branch",
            "worktree_path": "/tmp/worktree",
            "context": "Important context here",
            "priority": "low",
            "phases": [],
        }
        _write_plan_yaml(plan_dir, original)

        db_path = tmp_path / "plans.db"
        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)
        repo.import_from_yaml(plan_dir)

        out_dir = tmp_path / "out" / plan_name
        out_dir.mkdir(parents=True)
        repo.export_to_yaml(plan_name, out_dir)
        repo.close()

        with open(out_dir / "plan_build.yml") as f:
            exported = yaml.safe_load(f)

        assert exported["branch"] == "feature/test-branch"
        assert exported["worktree_path"] == "/tmp/worktree"
        assert exported["priority"] == "low"


# ===========================================================================
# US-GD-205: Database Location
# ===========================================================================


class TestUS_GD_205_DatabaseLocation:
    """US-GD-205 - Criterion 1: PlanRepository creates DB at .agentic/plans.db."""

    def test_plan_service_creates_db_in_repo_local_agentic_dir(self, isolated_repo):
        """PlanService creates DB at <repo>/.agentic/plans.db, not ~/.agentic/."""
        from agenticguidance.services.plan import PlanService

        service = PlanService(repo_path=isolated_repo)

        # The repository attribute holds the PlanRepository instance
        assert service._repository is not None, "PlanService should have a repository"

        db_path = service._repository.db_path
        expected_db = isolated_repo / ".agentic" / "plans.db"

        assert db_path == expected_db, (
            f"DB should be at {expected_db}, got {db_path}"
        )

        # Confirm it is NOT in the home directory
        home_db = Path.home() / ".agentic" / "plans.db"
        assert db_path != home_db, "DB must not be created in the home directory"

    def test_plan_service_db_file_is_created_on_disk(self, isolated_repo):
        """The .agentic/plans.db file actually exists after PlanService init."""
        from agenticguidance.services.plan import PlanService

        PlanService(repo_path=isolated_repo)

        expected_db = isolated_repo / ".agentic" / "plans.db"
        assert expected_db.exists(), ".agentic/plans.db should exist after PlanService init"

    def test_task_service_derives_db_from_plan_path(self, isolated_repo):
        """TaskService derives the DB path from the plan folder's repo root."""
        from agenticguidance.services.task import TaskService

        plan_name = "260224TE_task_db_loc"
        plan_dir = isolated_repo / "docs" / "plans" / "live" / plan_name
        _write_plan_yaml(plan_dir, _minimal_plan_data(plan_name))

        service = TaskService(plan_path=plan_dir)

        assert service._repository is not None
        db_path = service._repository.db_path
        expected_db = isolated_repo / ".agentic" / "plans.db"
        assert db_path == expected_db, (
            f"TaskService DB should be at {expected_db}, got {db_path}"
        )


class TestUS_GD_205_GitIgnore:
    """US-GD-205 - Criterion 2: .agentic/ is in .gitignore."""

    def test_agentic_dir_in_gitignore(self):
        """The repo .gitignore must contain an entry for .agentic/."""
        repo_root = Path(__file__)
        while repo_root != repo_root.parent:
            if (repo_root / ".git").exists():
                break
            repo_root = repo_root.parent

        gitignore = repo_root / ".gitignore"
        # This test surfaces a defect if .agentic/ is not in .gitignore
        assert gitignore.exists(), ".gitignore must exist at repo root"

        content = gitignore.read_text()
        has_entry = ".agentic/" in content or ".agentic" in content

        assert has_entry, (
            "DEFECT US-GD-205: .agentic/ is NOT in .gitignore. "
            "The plans.db file will be committed to git. "
            "Add '.agentic/' to .gitignore."
        )


class TestUS_GD_205_IsolatedDatabases:
    """US-GD-205 - Criterion 3: Each repo gets its own independent DB."""

    def test_two_repos_have_independent_databases(self, tmp_path):
        """Plans created in repo A do not appear in repo B's database."""
        from agenticguidance.services.plan_repository import PlanRepository

        repo_a = tmp_path / "repo_a"
        repo_b = tmp_path / "repo_b"
        repo_a.mkdir()
        repo_b.mkdir()

        db_a = repo_a / ".agentic" / "plans.db"
        db_b = repo_b / ".agentic" / "plans.db"

        repo_a_db = PlanRepository(db_path=db_a, auto_bootstrap=False)
        repo_b_db = PlanRepository(db_path=db_b, auto_bootstrap=False)

        # Create a plan in repo A
        repo_a_db.create_plan({
            "plan_folder_name": "260224TE_repo_a_plan",
            "plan_folder": str(repo_a / "docs" / "plans" / "live" / "260224TE_repo_a_plan"),
            "status": "pending",
            "objective": "Repo A plan",
        })

        # Repo B should have no knowledge of repo A's plan
        plan_in_b = repo_b_db.get_plan("260224TE_repo_a_plan")
        repo_a_db.close()
        repo_b_db.close()

        assert plan_in_b is None, (
            "Plans from repo A must not appear in repo B's database"
        )

    def test_databases_at_different_paths(self, tmp_path):
        """Two PlanRepository instances at different paths are truly independent."""
        from agenticguidance.services.plan_repository import PlanRepository

        db_1 = tmp_path / "proj1" / ".agentic" / "plans.db"
        db_2 = tmp_path / "proj2" / ".agentic" / "plans.db"

        r1 = PlanRepository(db_path=db_1, auto_bootstrap=False)
        r2 = PlanRepository(db_path=db_2, auto_bootstrap=False)

        r1.create_plan({"plan_folder_name": "unique_to_proj1", "plan_folder": "/tmp/p1", "status": "pending"})
        r2.create_plan({"plan_folder_name": "unique_to_proj2", "plan_folder": "/tmp/p2", "status": "pending"})

        # Cross-check: neither should see the other's plans
        assert r1.get_plan("unique_to_proj2") is None
        assert r2.get_plan("unique_to_proj1") is None

        r1.close()
        r2.close()


# ===========================================================================
# US-GD-206: Backward Compatibility
# ===========================================================================


class TestUS_GD_206_YamlFallback:
    """US-GD-206 - Criterion 1: System falls back to YAML when TinyDB has no record."""

    def test_get_plan_falls_through_to_yaml_when_tinydb_empty(self, isolated_repo):
        """get_plan() reads from YAML when TinyDB has no record for the plan."""
        from agenticguidance.services.plan import PlanService

        plan_name = "260224TE_yaml_fallback"
        plan_dir = isolated_repo / "docs" / "plans" / "live" / plan_name
        _write_plan_yaml(plan_dir, _minimal_plan_data(plan_name))

        service = PlanService(repo_path=isolated_repo)
        # DB is empty here (fresh isolated repo); read-through should kick in
        result = service.get_plan(plan_name)

        assert result is not None, "Should fall through to YAML import when DB is empty"
        assert result.plan_folder_name == plan_name

    def test_get_plan_yaml_only_mode_when_repository_is_none(self, isolated_repo):
        """get_plan() uses pure YAML when _repository is None (import failure)."""
        from agenticguidance.services.plan import PlanService

        plan_name = "260224TE_repo_none_fallback"
        plan_dir = isolated_repo / "docs" / "plans" / "live" / plan_name
        _write_plan_yaml(plan_dir, _minimal_plan_data(plan_name))

        service = PlanService(repo_path=isolated_repo)
        service._repository = None  # Simulate PlanRepository import failure

        result = service.get_plan(plan_name)

        assert result is not None, "YAML fallback must work when _repository is None"
        assert result.plan_folder_name == plan_name
        assert result.objective is not None

    def test_list_plans_yaml_only_mode_when_repository_is_none(self, isolated_repo):
        """list_plans() uses YAML scan when _repository is None."""
        from agenticguidance.services.plan import PlanService

        plan_name = "260224TE_list_yaml_fallback"
        plan_dir = isolated_repo / "docs" / "plans" / "live" / plan_name
        _write_plan_yaml(plan_dir, _minimal_plan_data(plan_name))

        service = PlanService(repo_path=isolated_repo)
        service._repository = None  # Simulate PlanRepository import failure

        plans = service.list_plans(status="live")
        plan_names = {p.plan_folder_name for p in plans}

        assert plan_name in plan_names, "YAML fallback list_plans should find plan on disk"


class TestUS_GD_206_FolderMatchesGuard:
    """US-GD-206 - Criterion 2: folder_matches guard prevents cross-plan data leaks."""

    def test_get_tasks_returns_only_matching_plan_tasks(self, tmp_path):
        """get_tasks() never returns tasks belonging to a different plan."""
        from agenticguidance.services.plan_repository import PlanRepository

        db_path = tmp_path / "plans.db"
        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)

        plan_a_dir = tmp_path / "plan_a"
        plan_b_dir = tmp_path / "plan_b"

        _write_plan_yaml(plan_a_dir, {
            "name": "plan_a",
            "status": "pending",
            "phases": [
                {"name": "P1", "tasks": [
                    {"id": "A001", "name": "Task from A", "status": "pending"},
                ]}
            ],
        })
        _write_plan_yaml(plan_b_dir, {
            "name": "plan_b",
            "status": "pending",
            "phases": [
                {"name": "P1", "tasks": [
                    {"id": "B001", "name": "Task from B", "status": "pending"},
                ]}
            ],
        })

        repo.import_from_yaml(plan_a_dir)
        repo.import_from_yaml(plan_b_dir)

        tasks_a = repo.get_tasks("plan_a")
        tasks_b = repo.get_tasks("plan_b")

        ids_a = {t.id for t in tasks_a}
        ids_b = {t.id for t in tasks_b}

        # Strict isolation: plan A tasks must not appear in plan B and vice versa
        assert "A001" in ids_a
        assert "B001" not in ids_a, "Task from plan_b leaked into plan_a query"
        assert "B001" in ids_b
        assert "A001" not in ids_b, "Task from plan_a leaked into plan_b query"

        repo.close()

    def test_update_task_status_only_affects_correct_plan(self, tmp_path):
        """update_task_status() only updates tasks in the specified plan."""
        from agenticguidance.services.plan_repository import PlanRepository

        db_path = tmp_path / "plans.db"
        repo = PlanRepository(db_path=db_path, auto_bootstrap=False)

        for plan_name in ("plan_x", "plan_y"):
            plan_dir = tmp_path / plan_name
            _write_plan_yaml(plan_dir, {
                "name": plan_name,
                "status": "pending",
                "phases": [
                    {"name": "P1", "tasks": [
                        {"id": "SHARED_ID", "name": f"Task in {plan_name}", "status": "pending"},
                    ]}
                ],
            })
            repo.import_from_yaml(plan_dir)

        # Update the task in plan_x only
        ok = repo.update_task_status("plan_x", "SHARED_ID", "completed")
        assert ok is True

        task_x = repo.get_task("plan_x", "SHARED_ID")
        task_y = repo.get_task("plan_y", "SHARED_ID")

        assert task_x is not None and task_x.status == "completed"
        assert task_y is not None and task_y.status == "pending", (
            "Updating task in plan_x must not affect plan_y's task with same ID"
        )

        repo.close()


class TestUS_GD_206_ResurrectionDetection:
    """US-GD-206 - Criterion 3: Resurrection detection re-imports live plan."""

    def test_get_plan_detects_resurrection_and_resyncs(self, isolated_repo):
        """When TinyDB says completed/ but live/ exists, get_plan resyncs to live."""
        from agenticguidance.services.plan import PlanService

        plan_name = "260224TE_resurrection"
        # Create plan in live/
        live_dir = isolated_repo / "docs" / "plans" / "live" / plan_name
        _write_plan_yaml(live_dir, _minimal_plan_data(plan_name, status="in_progress"))

        service = PlanService(repo_path=isolated_repo)
        # Import plan so TinyDB knows about it
        service._repository.import_from_yaml(live_dir)

        # Simulate archiving: update DB to point to completed/ (stale path)
        completed_dir = isolated_repo / "docs" / "plans" / "completed" / plan_name
        completed_dir.mkdir(parents=True)
        _write_plan_yaml(completed_dir, _minimal_plan_data(plan_name, status="completed"))

        service._repository.update_plan(plan_name, {
            "plan_folder": str(completed_dir),
            "status": "completed",
        })

        # Plan still exists in live/ (resurrection scenario)
        assert live_dir.exists()

        # get_plan should detect stale completed/ path and resync to live/
        result = service.get_plan(plan_name)

        assert result is not None, "Should find the plan after resurrection detection"
        assert result.plan_folder == live_dir, (
            f"Plan folder should be the live/ path {live_dir}, got {result.plan_folder}"
        )

    def test_resurrection_detection_updates_tinydb_path(self, isolated_repo):
        """After resurrection detection, TinyDB stores the live/ path."""
        from agenticguidance.services.plan import PlanService

        plan_name = "260224TE_resurrection_db_update"
        live_dir = isolated_repo / "docs" / "plans" / "live" / plan_name
        _write_plan_yaml(live_dir, _minimal_plan_data(plan_name, status="in_progress"))

        service = PlanService(repo_path=isolated_repo)
        service._repository.import_from_yaml(live_dir)

        # Simulate stale TinyDB entry pointing to completed/
        completed_dir = isolated_repo / "docs" / "plans" / "completed" / plan_name
        completed_dir.mkdir(parents=True)
        _write_plan_yaml(completed_dir, _minimal_plan_data(plan_name, status="completed"))
        service._repository.update_plan(plan_name, {"plan_folder": str(completed_dir)})

        # Trigger resurrection detection via get_plan
        service.get_plan(plan_name)

        # After detection, re-read from DB directly to confirm path was updated
        db_entry = service._repository.get_plan(plan_name)
        assert db_entry is not None
        assert db_entry.plan_folder == live_dir, (
            "TinyDB should be updated to live/ path after resurrection detection"
        )


class TestUS_GD_206_YamlSyncEnabled:
    """US-GD-206 - Criterion 4: yaml_sync_enabled flag on TaskService for dual-write."""

    def test_task_service_has_yaml_sync_enabled_flag(self, isolated_repo):
        """TaskService exposes a yaml_sync_enabled attribute."""
        from agenticguidance.services.task import TaskService

        plan_name = "260224TE_yaml_sync_flag"
        plan_dir = isolated_repo / "docs" / "plans" / "live" / plan_name
        _write_plan_yaml(plan_dir, _minimal_plan_data(plan_name))

        service_on = TaskService(plan_path=plan_dir, yaml_sync_enabled=True)
        service_off = TaskService(plan_path=plan_dir, yaml_sync_enabled=False)

        assert service_on._yaml_sync_enabled is True
        assert service_off._yaml_sync_enabled is False

    def test_plan_service_has_yaml_sync_enabled_flag(self, isolated_repo):
        """PlanService exposes a yaml_sync_enabled attribute."""
        from agenticguidance.services.plan import PlanService

        service_on = PlanService(repo_path=isolated_repo, yaml_sync_enabled=True)
        service_off = PlanService(repo_path=isolated_repo, yaml_sync_enabled=False)

        assert service_on._yaml_sync_enabled is True
        assert service_off._yaml_sync_enabled is False

    def test_yaml_sync_disabled_skips_yaml_writes_on_status_update(self, isolated_repo):
        """When yaml_sync_enabled=False, update_plan_status does not touch YAML files."""
        from agenticguidance.services.plan import PlanService

        plan_name = "260224TE_nosync"
        plan_dir = isolated_repo / "docs" / "plans" / "live" / plan_name
        original_data = _minimal_plan_data(plan_name, status="pending")
        _write_plan_yaml(plan_dir, original_data)

        service = PlanService(repo_path=isolated_repo, yaml_sync_enabled=False)
        # Ensure plan is in TinyDB
        service._repository.import_from_yaml(plan_dir)

        service.update_plan_status(plan_name, "active")

        # YAML on disk must NOT have been updated (yaml_sync disabled)
        with open(plan_dir / "plan_build.yml") as f:
            on_disk = yaml.safe_load(f)

        assert on_disk["status"] == "pending", (
            "YAML file should not be updated when yaml_sync_enabled=False"
        )

    def test_yaml_sync_enabled_updates_yaml_on_status_change(self, isolated_repo):
        """When yaml_sync_enabled=True, update_plan_status also updates the YAML file."""
        from agenticguidance.services.plan import PlanService

        plan_name = "260224TE_withsync"
        plan_dir = isolated_repo / "docs" / "plans" / "live" / plan_name
        _write_plan_yaml(plan_dir, _minimal_plan_data(plan_name, status="pending"))

        service = PlanService(repo_path=isolated_repo, yaml_sync_enabled=True)
        service._repository.import_from_yaml(plan_dir)

        service.update_plan_status(plan_name, "active")

        with open(plan_dir / "plan_build.yml") as f:
            on_disk = yaml.safe_load(f)

        assert on_disk["status"] == "active", (
            "YAML file should be updated when yaml_sync_enabled=True"
        )
