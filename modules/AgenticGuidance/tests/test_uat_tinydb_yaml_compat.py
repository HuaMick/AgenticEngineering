"""UAT tests for TinyDB/YAML compatibility user stories.

Covers acceptance criteria for:
  US-GD-202 - YAML Import/Export
  US-GD-205 - Database Location
  US-GD-206 - Backward Compatibility

Each test class maps directly to a user story criterion.  Tests use isolated
tmp_path fixtures and real (non-mocked) EpicRepository and EpicService instances
wherever possible to avoid reward-hacking patterns.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _write_ticket_yaml(folder: Path, data: dict) -> Path:
    """Write a ticket_build.yml into folder and return the file path."""
    folder.mkdir(parents=True, exist_ok=True)
    ticket_file = folder / "ticket_build.yml"
    with open(ticket_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return ticket_file


def _write_plan_yaml(folder: Path, data: dict) -> Path:
    """Write a plan_build.yml into folder and return the file path.

    Used for EpicService tests that delegate to PlanRepository internally.
    """
    folder.mkdir(parents=True, exist_ok=True)
    plan_file = folder / "plan_build.yml"
    with open(plan_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return plan_file


def _minimal_epic_data(folder_name: str, status: str = "pending") -> dict:
    """Return a complete epic dict suitable for round-trip tests."""
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
                "tickets": [
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
                "tickets": [
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
    """Provide a tmp directory structured like a git repo with epics layout."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "docs" / "epics" / "live").mkdir(parents=True)
    (repo / "docs" / "epics" / "completed").mkdir(parents=True)
    (repo / "docs" / "epics" / "deferred").mkdir(parents=True)
    return repo


@pytest.fixture
def repo_db(isolated_repo):
    """Return an isolated EpicRepository backed by the isolated_repo tmp dir."""
    from agenticguidance.services.epic_repository import EpicRepository

    db_path = isolated_repo / ".agentic" / "epics.db"
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    yield repo
    repo.close()


# ===========================================================================
# US-GD-202: YAML Import/Export
# ===========================================================================


class TestUS_GD_202_SyncToYaml:
    """US-GD-202 - Criterion 1: sync_to_yaml() writes epic data back to YAML."""

    def test_sync_to_yaml_creates_ticket_build_yml(self, tmp_path):
        """sync_to_yaml() writes a ticket_build.yml with current DB state."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_sync_test"
        epic_dir = tmp_path / "epics" / "live" / epic_name
        _write_ticket_yaml(epic_dir, _minimal_epic_data(epic_name))

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.import_from_yaml(epic_dir)

        # Remove ticket_build.yml so we can confirm sync recreates it
        (epic_dir / "ticket_build.yml").unlink()
        assert not (epic_dir / "ticket_build.yml").exists()

        result = repo.sync_to_yaml(epic_name)
        repo.close()

        assert result is True, "sync_to_yaml should return True on success"
        assert (epic_dir / "ticket_build.yml").exists(), "ticket_build.yml should be recreated"

    def test_sync_to_yaml_content_matches_db_state(self, tmp_path):
        """sync_to_yaml() writes epic fields that match what is stored in TinyDB."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_content_check"
        epic_dir = tmp_path / "epics" / "live" / epic_name
        original_data = _minimal_epic_data(epic_name)
        _write_ticket_yaml(epic_dir, original_data)

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.import_from_yaml(epic_dir)

        # Mutate status in TinyDB
        repo.update_epic(epic_name, {"status": "active"})

        # Sync back to YAML
        repo.sync_to_yaml(epic_name)
        repo.close()

        with open(epic_dir / "ticket_build.yml") as f:
            written = yaml.safe_load(f)

        assert written["status"] == "active", "sync_to_yaml should reflect DB status update"
        assert written["name"] == original_data["name"]
        assert written["objective"] == original_data["objective"]
        assert written["priority"] == original_data["priority"]

    def test_sync_to_yaml_returns_false_for_unknown_epic(self, tmp_path):
        """sync_to_yaml() returns False when the epic does not exist in DB."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        result = repo.sync_to_yaml("nonexistent_epic_xyz")
        repo.close()

        assert result is False

    def test_sync_to_yaml_returns_false_when_folder_missing(self, tmp_path):
        """sync_to_yaml() returns False when the stored epic_folder doesn't exist."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_missing_dir"
        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

        # Insert epic pointing to a non-existent directory
        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(tmp_path / "does_not_exist" / epic_name),
            "status": "pending",
            "objective": "Test",
        })

        result = repo.sync_to_yaml(epic_name)
        repo.close()

        assert result is False


class TestUS_GD_202_ReadThrough:
    """US-GD-202 - Criterion 2: Auto-import from YAML on TinyDB cache miss."""

    def test_get_epic_imports_yaml_on_cache_miss(self, isolated_repo):
        """EpicService.get_epic() imports from YAML when TinyDB has no record."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_cache_miss"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(epic_dir, _minimal_epic_data(epic_name))

        # Service starts with empty TinyDB (auto_bootstrap not triggered
        # because the live/ directory didn't exist at PlanRepository init time
        # - we use a fresh service pointed at isolated_repo)
        service = EpicService(repo_path=isolated_repo)

        # DB is empty; get_epic should trigger YAML import (read-through)
        result = service.get_epic(epic_name)

        assert result is not None, "get_epic should return data via read-through import"
        assert result.epic_folder_name == epic_name
        assert result.objective is not None

    def test_get_epic_tickets_read_through_imports_yaml(self, isolated_repo):
        """get_epic_tickets() triggers YAML import when epic is absent from TinyDB."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_tickets_read_through"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(epic_dir, _minimal_epic_data(epic_name))

        service = EpicService(repo_path=isolated_repo)
        tickets = service.get_epic_tickets(epic_name)

        assert len(tickets) > 0, "Should import tickets from YAML on cache miss"
        ticket_ids = {t.id for t in tickets}
        assert "A001" in ticket_ids
        assert "A002" in ticket_ids
        assert "B001" in ticket_ids

    def test_list_epics_imports_disk_epics_not_in_tinydb(self, isolated_repo):
        """list_epics() reconciles disk epics that TinyDB doesn't know about."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_disk_only_epic"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(epic_dir, _minimal_epic_data(epic_name))

        service = EpicService(repo_path=isolated_repo)
        epics = service.list_epics(status="live")

        epic_names = {p.epic_folder_name for p in epics}
        assert epic_name in epic_names, (
            "list_epics() should discover epics on disk and import them into TinyDB"
        )


class TestUS_GD_202_RoundTrip:
    """US-GD-202 - Criteria 3 & 4: YAML -> TinyDB -> YAML round-trip."""

    def test_round_trip_preserves_epic_fields(self, tmp_path):
        """Importing YAML then exporting back preserves top-level epic fields."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_round_trip"
        epic_dir = tmp_path / "epics" / epic_name
        original = _minimal_epic_data(epic_name)
        _write_ticket_yaml(epic_dir, original)

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        assert repo.import_from_yaml(epic_dir) is True

        # Export to a new folder to isolate the round-trip output
        out_dir = tmp_path / "out" / epic_name
        out_dir.mkdir(parents=True)
        assert repo.export_to_yaml(epic_name, out_dir) is True
        repo.close()

        with open(out_dir / "ticket_build.yml") as f:
            exported = yaml.safe_load(f)

        assert exported["name"] == original["name"]
        assert exported["status"] == original["status"]
        assert exported["priority"] == original["priority"]
        assert exported["objective"] == original["objective"]
        assert exported["created"] == original["created"]
        assert exported["branch"] == original["branch"]

    def test_round_trip_preserves_phases(self, tmp_path):
        """Importing YAML then exporting back preserves phase structure."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_phase_round_trip"
        epic_dir = tmp_path / "epics" / epic_name
        original = _minimal_epic_data(epic_name)
        _write_ticket_yaml(epic_dir, original)

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.import_from_yaml(epic_dir)

        out_dir = tmp_path / "out" / epic_name
        out_dir.mkdir(parents=True)
        repo.export_to_yaml(epic_name, out_dir)
        repo.close()

        with open(out_dir / "ticket_build.yml") as f:
            exported = yaml.safe_load(f)

        assert len(exported["phases"]) == 2, "Both phases should survive round-trip"
        phase_names = [p["name"] for p in exported["phases"]]
        assert "Alpha Phase" in phase_names
        assert "Beta Phase" in phase_names

    def test_round_trip_preserves_tickets(self, tmp_path):
        """Importing YAML then exporting back preserves all ticket fields."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_ticket_round_trip"
        epic_dir = tmp_path / "epics" / epic_name
        original = _minimal_epic_data(epic_name)
        _write_ticket_yaml(epic_dir, original)

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.import_from_yaml(epic_dir)

        out_dir = tmp_path / "out" / epic_name
        out_dir.mkdir(parents=True)
        repo.export_to_yaml(epic_name, out_dir)
        repo.close()

        with open(out_dir / "ticket_build.yml") as f:
            exported = yaml.safe_load(f)

        all_tickets = []
        for phase in exported["phases"]:
            all_tickets.extend(phase.get("tickets", []))

        ticket_ids = {t["id"] for t in all_tickets}
        assert "A001" in ticket_ids, "Ticket A001 should survive round-trip"
        assert "A002" in ticket_ids, "Ticket A002 should survive round-trip"
        assert "B001" in ticket_ids, "Ticket B001 should survive round-trip"

        # Verify key ticket fields
        a001 = next(t for t in all_tickets if t["id"] == "A001")
        assert a001["name"] == "Task Alpha"
        assert a001["status"] == "pending"
        assert a001["agent"] == "builder"

        a002 = next(t for t in all_tickets if t["id"] == "A002")
        assert a002["status"] == "completed"

    def test_round_trip_metadata_preserved_with_context(self, tmp_path):
        """Optional metadata fields (context, branch, worktree_path) survive round-trip."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_metadata_trip"
        epic_dir = tmp_path / "epics" / epic_name
        original = {
            "name": epic_name,
            "status": "active",
            "objective": "Test metadata",
            "created": "2026-02-24",
            "branch": "feature/test-branch",
            "worktree_path": "/tmp/worktree",
            "context": "Important context here",
            "priority": "low",
            "phases": [],
        }
        _write_ticket_yaml(epic_dir, original)

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.import_from_yaml(epic_dir)

        out_dir = tmp_path / "out" / epic_name
        out_dir.mkdir(parents=True)
        repo.export_to_yaml(epic_name, out_dir)
        repo.close()

        with open(out_dir / "ticket_build.yml") as f:
            exported = yaml.safe_load(f)

        assert exported["branch"] == "feature/test-branch"
        assert exported["worktree_path"] == "/tmp/worktree"
        assert exported["priority"] == "low"


# ===========================================================================
# US-GD-205: Database Location
# ===========================================================================


class TestUS_GD_205_DatabaseLocation:
    """US-GD-205 - Criterion 1: EpicRepository creates DB at .agentic/epics.db."""

    def test_epic_service_creates_db_in_repo_local_agentic_dir(self, isolated_repo):
        """EpicService creates DB at <repo>/.agentic/epics.db, not ~/.agentic/."""
        from agenticguidance.services.epic import EpicService

        service = EpicService(repo_path=isolated_repo)

        # The repository attribute holds the PlanRepository instance
        assert service._repository is not None, "EpicService should have a repository"

        db_path = service._repository.db_path
        expected_db = isolated_repo / ".agentic" / "epics.db"

        assert db_path == expected_db, (
            f"DB should be at {expected_db}, got {db_path}"
        )

        # Confirm it is NOT in the home directory
        home_db = Path.home() / ".agentic" / "epics.db"
        assert db_path != home_db, "DB must not be created in the home directory"

    def test_epic_service_db_file_is_created_on_disk(self, isolated_repo):
        """The .agentic/epics.db file actually exists after EpicService init."""
        from agenticguidance.services.epic import EpicService

        EpicService(repo_path=isolated_repo)

        expected_db = isolated_repo / ".agentic" / "epics.db"
        assert expected_db.exists(), ".agentic/epics.db should exist after EpicService init"

    def test_ticket_service_derives_db_from_epic_path(self, isolated_repo):
        """TicketService derives the DB path from the epic folder's repo root."""
        from agenticguidance.services.ticket import TicketService

        epic_name = "260224TE_ticket_db_loc"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_ticket_yaml(epic_dir, _minimal_epic_data(epic_name))

        service = TicketService(epic_path=epic_dir)

        assert service._repository is not None
        db_path = service._repository.db_path
        expected_db = isolated_repo / ".agentic" / "epics.db"
        assert db_path == expected_db, (
            f"TicketService DB should be at {expected_db}, got {db_path}"
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
            "The epics.db file will be committed to git. "
            "Add '.agentic/' to .gitignore."
        )


class TestUS_GD_205_IsolatedDatabases:
    """US-GD-205 - Criterion 3: Each repo gets its own independent DB."""

    def test_two_repos_have_independent_databases(self, tmp_path):
        """Epics created in repo A do not appear in repo B's database."""
        from agenticguidance.services.epic_repository import EpicRepository

        repo_a = tmp_path / "repo_a"
        repo_b = tmp_path / "repo_b"
        repo_a.mkdir()
        repo_b.mkdir()

        db_a = repo_a / ".agentic" / "epics.db"
        db_b = repo_b / ".agentic" / "epics.db"

        repo_a_db = EpicRepository(db_path=db_a, auto_bootstrap=False)
        repo_b_db = EpicRepository(db_path=db_b, auto_bootstrap=False)

        # Create an epic in repo A
        repo_a_db.create_epic({
            "epic_folder_name": "260224TE_repo_a_epic",
            "epic_folder": str(repo_a / "docs" / "epics" / "live" / "260224TE_repo_a_epic"),
            "status": "pending",
            "objective": "Repo A epic",
        })

        # Repo B should have no knowledge of repo A's epic
        epic_in_b = repo_b_db.get_epic("260224TE_repo_a_epic")
        repo_a_db.close()
        repo_b_db.close()

        assert epic_in_b is None, (
            "Epics from repo A must not appear in repo B's database"
        )

    def test_databases_at_different_paths(self, tmp_path):
        """Two EpicRepository instances at different paths are truly independent."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_1 = tmp_path / "proj1" / ".agentic" / "epics.db"
        db_2 = tmp_path / "proj2" / ".agentic" / "epics.db"

        r1 = EpicRepository(db_path=db_1, auto_bootstrap=False)
        r2 = EpicRepository(db_path=db_2, auto_bootstrap=False)

        r1.create_epic({"epic_folder_name": "unique_to_proj1", "epic_folder": "/tmp/e1", "status": "pending"})
        r2.create_epic({"epic_folder_name": "unique_to_proj2", "epic_folder": "/tmp/e2", "status": "pending"})

        # Cross-check: neither should see the other's epics
        assert r1.get_epic("unique_to_proj2") is None
        assert r2.get_epic("unique_to_proj1") is None

        r1.close()
        r2.close()


# ===========================================================================
# US-GD-206: Backward Compatibility
# ===========================================================================


class TestUS_GD_206_YamlFallback:
    """US-GD-206 - Criterion 1: System falls back to YAML when TinyDB has no record."""

    def test_get_epic_falls_through_to_yaml_when_tinydb_empty(self, isolated_repo):
        """get_epic() reads from YAML when TinyDB has no record for the epic."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_yaml_fallback"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(epic_dir, _minimal_epic_data(epic_name))

        service = EpicService(repo_path=isolated_repo)
        # DB is empty here (fresh isolated repo); read-through should kick in
        result = service.get_epic(epic_name)

        assert result is not None, "Should fall through to YAML import when DB is empty"
        assert result.epic_folder_name == epic_name

    def test_get_epic_yaml_only_mode_when_repository_is_none(self, isolated_repo):
        """get_epic() uses pure YAML when _repository is None (import failure)."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_repo_none_fallback"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(epic_dir, _minimal_epic_data(epic_name))

        service = EpicService(repo_path=isolated_repo)
        service._repository = None  # Simulate PlanRepository import failure

        result = service.get_epic(epic_name)

        assert result is not None, "YAML fallback must work when _repository is None"
        assert result.epic_folder_name == epic_name
        assert result.objective is not None

    def test_list_epics_yaml_only_mode_when_repository_is_none(self, isolated_repo):
        """list_epics() uses YAML scan when _repository is None."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_list_yaml_fallback"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(epic_dir, _minimal_epic_data(epic_name))

        service = EpicService(repo_path=isolated_repo)
        service._repository = None  # Simulate PlanRepository import failure

        epics = service.list_epics(status="live")
        epic_names = {p.epic_folder_name for p in epics}

        assert epic_name in epic_names, "YAML fallback list_epics should find epic on disk"


class TestUS_GD_206_FolderMatchesGuard:
    """US-GD-206 - Criterion 2: folder_matches guard prevents cross-epic data leaks."""

    def test_get_tickets_returns_only_matching_epic_tickets(self, tmp_path):
        """get_tickets() never returns tickets belonging to a different epic."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

        epic_a_dir = tmp_path / "epic_a"
        epic_b_dir = tmp_path / "epic_b"

        _write_ticket_yaml(epic_a_dir, {
            "name": "epic_a",
            "status": "pending",
            "phases": [
                {"name": "P1", "tickets": [
                    {"id": "A001", "name": "Ticket from A", "status": "pending"},
                ]}
            ],
        })
        _write_ticket_yaml(epic_b_dir, {
            "name": "epic_b",
            "status": "pending",
            "phases": [
                {"name": "P1", "tickets": [
                    {"id": "B001", "name": "Ticket from B", "status": "pending"},
                ]}
            ],
        })

        repo.import_from_yaml(epic_a_dir)
        repo.import_from_yaml(epic_b_dir)

        tickets_a = repo.get_tickets("epic_a")
        tickets_b = repo.get_tickets("epic_b")

        ids_a = {t.id for t in tickets_a}
        ids_b = {t.id for t in tickets_b}

        # Strict isolation: epic A tickets must not appear in epic B and vice versa
        assert "A001" in ids_a
        assert "B001" not in ids_a, "Ticket from epic_b leaked into epic_a query"
        assert "B001" in ids_b
        assert "A001" not in ids_b, "Ticket from epic_a leaked into epic_b query"

        repo.close()

    def test_update_ticket_status_only_affects_correct_epic(self, tmp_path):
        """update_ticket_status() only updates tickets in the specified epic."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

        for epic_name in ("epic_x", "epic_y"):
            epic_dir = tmp_path / epic_name
            _write_ticket_yaml(epic_dir, {
                "name": epic_name,
                "status": "pending",
                "phases": [
                    {"name": "P1", "tickets": [
                        {"id": "SHARED_ID", "name": f"Ticket in {epic_name}", "status": "pending"},
                    ]}
                ],
            })
            repo.import_from_yaml(epic_dir)

        # Update the ticket in epic_x only
        ok = repo.update_ticket_status("epic_x", "SHARED_ID", "completed")
        assert ok is True

        ticket_x = repo.get_ticket("epic_x", "SHARED_ID")
        ticket_y = repo.get_ticket("epic_y", "SHARED_ID")

        assert ticket_x is not None and ticket_x.status == "completed"
        assert ticket_y is not None and ticket_y.status == "pending", (
            "Updating ticket in epic_x must not affect epic_y's ticket with same ID"
        )

        repo.close()


class TestUS_GD_206_ResurrectionDetection:
    """US-GD-206 - Criterion 3: Resurrection detection re-imports live epic."""

    def test_get_epic_detects_resurrection_and_resyncs(self, isolated_repo):
        """When TinyDB says completed/ but live/ exists, get_epic resyncs to live."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_resurrection"
        # Create epic in live/
        live_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(live_dir, _minimal_epic_data(epic_name, status="in_progress"))

        service = EpicService(repo_path=isolated_repo)
        # Import epic so TinyDB knows about it
        service._repository.import_from_yaml(live_dir)

        # Simulate archiving: update DB to point to completed/ (stale path)
        completed_dir = isolated_repo / "docs" / "epics" / "completed" / epic_name
        completed_dir.mkdir(parents=True)
        _write_plan_yaml(completed_dir, _minimal_epic_data(epic_name, status="completed"))

        service._repository.update_epic(epic_name, {
            "plan_folder": str(completed_dir),
            "status": "completed",
        })

        # Epic still exists in live/ (resurrection scenario)
        assert live_dir.exists()

        # get_epic should detect stale completed/ path and resync to live/
        result = service.get_epic(epic_name)

        assert result is not None, "Should find the epic after resurrection detection"
        assert result.epic_folder == live_dir, (
            f"Epic folder should be the live/ path {live_dir}, got {result.epic_folder}"
        )

    def test_resurrection_detection_updates_tinydb_path(self, isolated_repo):
        """After resurrection detection, TinyDB stores the live/ path."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_resurrection_db_update"
        live_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(live_dir, _minimal_epic_data(epic_name, status="in_progress"))

        service = EpicService(repo_path=isolated_repo)
        service._repository.import_from_yaml(live_dir)

        # Simulate stale TinyDB entry pointing to completed/
        completed_dir = isolated_repo / "docs" / "epics" / "completed" / epic_name
        completed_dir.mkdir(parents=True)
        _write_plan_yaml(completed_dir, _minimal_epic_data(epic_name, status="completed"))
        service._repository.update_epic(epic_name, {"plan_folder": str(completed_dir)})

        # Trigger resurrection detection via get_epic
        service.get_epic(epic_name)

        # After detection, re-read from DB directly to confirm path was updated
        db_entry = service._repository.get_epic(epic_name)
        assert db_entry is not None
        assert db_entry.epic_folder == live_dir, (
            "TinyDB should be updated to live/ path after resurrection detection"
        )


class TestUS_GD_206_YamlSyncEnabled:
    """US-GD-206 - Criterion 4: yaml_sync_enabled flag on TicketService for dual-write."""

    def test_ticket_service_has_yaml_sync_enabled_flag(self, isolated_repo):
        """TicketService exposes a yaml_sync_enabled attribute."""
        from agenticguidance.services.ticket import TicketService

        epic_name = "260224TE_yaml_sync_flag"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_ticket_yaml(epic_dir, _minimal_epic_data(epic_name))

        service_on = TicketService(epic_path=epic_dir, yaml_sync_enabled=True)
        service_off = TicketService(epic_path=epic_dir, yaml_sync_enabled=False)

        assert service_on._yaml_sync_enabled is True
        assert service_off._yaml_sync_enabled is False

    def test_epic_service_has_yaml_sync_enabled_flag(self, isolated_repo):
        """EpicService exposes a yaml_sync_enabled attribute."""
        from agenticguidance.services.epic import EpicService

        service_on = EpicService(repo_path=isolated_repo, yaml_sync_enabled=True)
        service_off = EpicService(repo_path=isolated_repo, yaml_sync_enabled=False)

        assert service_on._yaml_sync_enabled is True
        assert service_off._yaml_sync_enabled is False

    def test_yaml_sync_disabled_skips_yaml_writes_on_status_update(self, isolated_repo):
        """When yaml_sync_enabled=False, update_epic_status does not touch YAML files."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_nosync"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        original_data = _minimal_epic_data(epic_name, status="pending")
        _write_plan_yaml(epic_dir, original_data)

        service = EpicService(repo_path=isolated_repo, yaml_sync_enabled=False)
        # Ensure epic is in TinyDB
        service._repository.import_from_yaml(epic_dir)

        service.update_epic_status(epic_name, "active")

        # YAML on disk must NOT have been updated (yaml_sync disabled)
        with open(epic_dir / "plan_build.yml") as f:
            on_disk = yaml.safe_load(f)

        assert on_disk["status"] == "pending", (
            "YAML file should not be updated when yaml_sync_enabled=False"
        )

    def test_yaml_sync_enabled_updates_yaml_on_status_change(self, isolated_repo):
        """When yaml_sync_enabled=True, update_epic_status also updates the YAML file."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_withsync"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(epic_dir, _minimal_epic_data(epic_name, status="pending"))

        service = EpicService(repo_path=isolated_repo, yaml_sync_enabled=True)
        service._repository.import_from_yaml(epic_dir)

        service.update_epic_status(epic_name, "active")

        with open(epic_dir / "plan_build.yml") as f:
            on_disk = yaml.safe_load(f)

        assert on_disk["status"] == "active", (
            "YAML file should be updated when yaml_sync_enabled=True"
        )
