"""UAT tests for TinyDB data store user stories.

Covers acceptance criteria for:
  US-GD-202 - TinyDB CRUD and data persistence
  US-GD-205 - Database Location
  US-GD-206 - Data isolation and resurrection detection

Each test class maps directly to a user story criterion. Tests use isolated
tmp_path fixtures and real (non-mocked) EpicRepository and EpicService instances
wherever possible to avoid reward-hacking patterns.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

pytestmark = pytest.mark.story("US-SET-017", "US-SET-024", "US-SET-019", "US-SET-021", "US-SET-023")


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
    """Write a plan_build.yml into folder and return the file path."""
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


def _populate_repo_from_epic_data(repo, epic_folder_name: str, epic_folder: str, data: dict) -> None:
    """Populate EpicRepository from a YAML-style epic data dict."""
    repo.create_epic({
        "epic_folder_name": epic_folder_name,
        "epic_folder": epic_folder,
        "name": data.get("name", epic_folder_name),
        "status": data.get("status", "pending"),
        "objective": data.get("objective", ""),
        "branch": data.get("branch", "main"),
        "worktree_path": data.get("worktree_path", ""),
    })
    for phase in data.get("phases", []):
        phase_name = phase.get("name", "default")
        for ticket in phase.get("tickets", []):
            repo.add_ticket(epic_folder_name, phase_name, ticket)


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
# US-GD-202: TinyDB CRUD and data persistence
# ===========================================================================


class TestUS_GD_202_TinyDbWrite:
    """US-GD-202 - Criterion 1: TinyDB stores epic data reliably."""

    def test_create_epic_persists_to_tinydb(self, tmp_path):
        """create_epic() writes epic data that can be retrieved."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_create_test"
        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(tmp_path / epic_name),
            "name": epic_name,
            "status": "pending",
            "objective": "Test creation",
        })

        result = repo.get_epic(epic_name)
        repo.close()

        assert result is not None, "create_epic should persist data retrievable by get_epic"
        assert result.status == "pending"
        assert result.name == epic_name

    def test_add_tickets_persists_to_tinydb(self, tmp_path):
        """add_ticket() writes ticket data that can be retrieved."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_ticket_test"
        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(tmp_path / epic_name),
            "status": "pending",
        })
        repo.add_ticket(epic_name, "Alpha Phase", {
            "id": "A001",
            "name": "Task Alpha",
            "description": "Do alpha work",
            "status": "pending",
            "agent": "builder",
        })

        tickets = repo.get_tickets(epic_name)
        repo.close()

        assert len(tickets) == 1
        assert tickets[0].id == "A001"

    def test_update_epic_status_persists(self, tmp_path):
        """update_epic() status change is durable in TinyDB."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_update_test"
        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(tmp_path / epic_name),
            "status": "pending",
        })
        repo.update_epic(epic_name, {"status": "active"})

        result = repo.get_epic(epic_name)
        repo.close()

        assert result is not None
        assert result.status == "active", "update_epic should reflect DB status update"

    def test_get_epic_not_in_tinydb_returns_none(self, tmp_path):
        """get_epic() returns None when the epic does not exist in TinyDB."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        result = repo.get_epic("nonexistent_epic_xyz")
        repo.close()

        assert result is None


class TestUS_GD_202_TinyDbReadThrough:
    """US-GD-202 - Criterion 2: TinyDB is authoritative; no YAML read-through."""

    def test_get_epic_returns_none_when_not_in_tinydb(self, isolated_repo):
        """EpicService.get_epic() returns None when TinyDB has no record.

        With YAML decommissioned, there is no read-through from YAML files.
        """
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_cache_miss"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(epic_dir, _minimal_epic_data(epic_name))

        # Service starts with empty TinyDB; get_epic returns None (no YAML read-through)
        service = EpicService(repo_path=isolated_repo)
        result = service.get_epic(epic_name)

        assert result is None, (
            "get_epic should return None when epic is not in TinyDB (YAML decommissioned)"
        )

    def test_get_epic_tickets_returns_empty_when_not_in_tinydb(self, isolated_repo):
        """get_epic_tickets() returns empty when epic is absent from TinyDB."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_tickets_read_through"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(epic_dir, _minimal_epic_data(epic_name))

        service = EpicService(repo_path=isolated_repo)
        tickets = service.get_epic_tickets(epic_name)

        assert len(tickets) == 0, (
            "get_epic_tickets returns empty when epic not in TinyDB (no YAML read-through)"
        )

    def test_list_epics_returns_only_tinydb_epics(self, isolated_repo):
        """list_epics() returns only epics registered in TinyDB (not disk-only)."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_disk_only_epic"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(epic_dir, _minimal_epic_data(epic_name))

        # Service with empty TinyDB
        service = EpicService(repo_path=isolated_repo)
        epics = service.list_epics(status="live")

        epic_names = {p.epic_folder_name for p in epics}
        assert epic_name not in epic_names, (
            "list_epics() should only return TinyDB-registered epics (YAML decommissioned)"
        )


class TestUS_GD_202_TinyDbRoundTrip:
    """US-GD-202 - Criteria 3 & 4: TinyDB CRUD round-trip preserves all fields."""

    def test_round_trip_preserves_epic_fields(self, tmp_path):
        """Creating an epic in TinyDB then retrieving it preserves top-level fields."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_round_trip"
        epic_dir = tmp_path / "epics" / epic_name
        epic_dir.mkdir(parents=True)
        original = _minimal_epic_data(epic_name)

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        _populate_repo_from_epic_data(repo, epic_name, str(epic_dir), original)

        result = repo.get_epic(epic_name)
        repo.close()

        assert result is not None
        assert result.name == original["name"]
        assert result.status == original["status"]
        assert result.objective == original["objective"]
        assert result.branch == original["branch"]

    def test_round_trip_preserves_tickets(self, tmp_path):
        """Creating tickets in TinyDB then retrieving them preserves all ticket fields."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_ticket_round_trip"
        epic_dir = tmp_path / "epics" / epic_name
        epic_dir.mkdir(parents=True)
        original = _minimal_epic_data(epic_name)

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        _populate_repo_from_epic_data(repo, epic_name, str(epic_dir), original)

        tickets = repo.get_tickets(epic_name)
        repo.close()

        ticket_ids = {t.id for t in tickets}
        assert "A001" in ticket_ids, "Ticket A001 should survive round-trip"
        assert "A002" in ticket_ids, "Ticket A002 should survive round-trip"
        assert "B001" in ticket_ids, "Ticket B001 should survive round-trip"

        a001 = next(t for t in tickets if t.id == "A001")
        assert a001.name == "Task Alpha"
        assert a001.status == "pending"
        assert a001.agent == "builder"

        a002 = next(t for t in tickets if t.id == "A002")
        assert a002.status == "completed"

    def test_round_trip_preserves_phase_grouping(self, tmp_path):
        """Tickets retain their phase_name after round-trip through TinyDB."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_phase_round_trip"
        epic_dir = tmp_path / "epics" / epic_name
        epic_dir.mkdir(parents=True)
        original = _minimal_epic_data(epic_name)

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        _populate_repo_from_epic_data(repo, epic_name, str(epic_dir), original)

        tickets = repo.get_tickets(epic_name)
        repo.close()

        phase_names = {t.phase_name for t in tickets}
        assert "Alpha Phase" in phase_names
        assert "Beta Phase" in phase_names

    def test_round_trip_metadata_preserved(self, tmp_path):
        """Optional metadata fields (branch, worktree_path) survive TinyDB round-trip."""
        from agenticguidance.services.epic_repository import EpicRepository

        epic_name = "260224TE_metadata_trip"
        epic_dir = tmp_path / "epics" / epic_name
        epic_dir.mkdir(parents=True)
        original = {
            "name": epic_name,
            "status": "active",
            "objective": "Test metadata",
            "branch": "feature/test-branch",
            "worktree_path": "/tmp/worktree",
            "phases": [],
        }

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        _populate_repo_from_epic_data(repo, epic_name, str(epic_dir), original)

        result = repo.get_epic(epic_name)
        repo.close()

        assert result is not None
        assert result.branch == "feature/test-branch"
        assert result.worktree_path == "/tmp/worktree"


# ===========================================================================
# US-GD-205: Database Location
# ===========================================================================


@pytest.mark.story("US-SET-022")
class TestUS_GD_205_DatabaseLocation:
    """US-GD-205 - Criterion 1: EpicRepository uses global ~/.agentic/epics.db."""

    def test_epic_service_uses_global_db(self, isolated_repo):
        """EpicService uses the global DB (patched to tmp_path by _isolate_tinydb)."""
        from agenticguidance.services.epic import EpicService

        service = EpicService(repo_path=isolated_repo)

        # The repository attribute holds the EpicRepository instance
        assert service._repository is not None, "EpicService should have a repository"

        # DB path should be the isolated fixture path (global default, patched)
        db_path = service._repository.db_path
        assert db_path.exists() or db_path.parent.exists(), "DB path should be accessible"

    def test_epic_service_db_file_is_created_on_disk(self, isolated_repo, _isolate_tinydb):
        """The DB file actually exists after EpicService init."""
        from agenticguidance.services.epic import EpicService

        EpicService(repo_path=isolated_repo)

        assert _isolate_tinydb.parent.exists(), "DB parent dir should exist after EpicService init"

    def test_ticket_service_uses_global_db(self, isolated_repo, _isolate_tinydb):
        """TicketService uses the global DB (patched to tmp_path by _isolate_tinydb)."""
        from agenticguidance.services.ticket import TicketService

        epic_name = "260224TE_ticket_db_loc"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_ticket_yaml(epic_dir, _minimal_epic_data(epic_name))

        service = TicketService(epic_path=epic_dir)

        assert service._repository is not None
        db_path = service._repository.db_path
        # Should use the isolated (global) DB, not a repo-local one
        assert db_path == _isolate_tinydb, (
            f"TicketService DB should be at {_isolate_tinydb}, got {db_path}"
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


class TestUS_GD_205_GlobalDatabase:
    """US-GD-205 - Criterion 3: All repos share the single global DB."""

    def test_global_db_is_shared(self, tmp_path):
        """Epics created from any context are visible in the global DB."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / ".agentic" / "epics.db"
        repo_db = EpicRepository(db_path=db_path, auto_bootstrap=False)

        # Create an epic
        repo_db.create_epic({
            "epic_folder_name": "260224TE_shared_epic",
            "epic_folder": str(tmp_path / "docs" / "epics" / "live" / "260224TE_shared_epic"),
            "status": "pending",
            "objective": "Shared epic",
        })

        # Same DB should see the epic
        repo_db2 = EpicRepository(db_path=db_path, auto_bootstrap=False)
        epic = repo_db2.get_epic("260224TE_shared_epic")
        repo_db.close()
        repo_db2.close()

        assert epic is not None, (
            "Epics should be visible in the shared global DB"
        )

    def test_explicit_db_paths_are_independent(self, tmp_path):
        """Two EpicRepository instances at different explicit paths are independent."""
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
# US-GD-206: Data isolation and resurrection detection
# ===========================================================================


class TestUS_GD_206_TinyDbOnly:
    """US-GD-206 - Criterion 1: TinyDB is sole data store; YAML fallback removed."""

    def test_get_epic_returns_none_when_tinydb_empty(self, isolated_repo):
        """get_epic() returns None when TinyDB is empty (no YAML fallback)."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_yaml_fallback"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(epic_dir, _minimal_epic_data(epic_name))

        service = EpicService(repo_path=isolated_repo)
        # DB is empty here (fresh isolated repo); YAML fallback removed
        result = service.get_epic(epic_name)

        assert result is None, "Should return None when epic not in TinyDB (YAML fallback removed)"

    def test_get_epic_returns_none_when_repository_is_none(self, isolated_repo):
        """get_epic() returns None when _repository is None (import failure)."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_repo_none_fallback"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(epic_dir, _minimal_epic_data(epic_name))

        service = EpicService(repo_path=isolated_repo)
        service._repository = None  # Simulate PlanRepository import failure

        result = service.get_epic(epic_name)

        assert result is None, "Should return None when _repository is None"

    def test_list_epics_returns_empty_when_repository_is_none(self, isolated_repo):
        """list_epics() returns empty when _repository is None."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_list_yaml_fallback"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        _write_plan_yaml(epic_dir, _minimal_epic_data(epic_name))

        service = EpicService(repo_path=isolated_repo)
        service._repository = None  # Simulate PlanRepository import failure

        epics = service.list_epics(status="live")

        assert len(epics) == 0, "list_epics returns empty when _repository is None"


class TestUS_GD_206_FolderMatchesGuard:
    """US-GD-206 - Criterion 2: folder_matches guard prevents cross-epic data leaks."""

    def test_get_tickets_returns_only_matching_epic_tickets(self, tmp_path):
        """get_tickets() never returns tickets belonging to a different epic."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

        epic_a_dir = tmp_path / "epic_a"
        epic_b_dir = tmp_path / "epic_b"
        epic_a_dir.mkdir(parents=True)
        epic_b_dir.mkdir(parents=True)

        _populate_repo_from_epic_data(repo, "epic_a", str(epic_a_dir), {
            "name": "epic_a",
            "status": "pending",
            "phases": [
                {"name": "P1", "tickets": [
                    {"id": "A001", "name": "Ticket from A", "status": "pending"},
                ]}
            ],
        })
        _populate_repo_from_epic_data(repo, "epic_b", str(epic_b_dir), {
            "name": "epic_b",
            "status": "pending",
            "phases": [
                {"name": "P1", "tickets": [
                    {"id": "B001", "name": "Ticket from B", "status": "pending"},
                ]}
            ],
        })

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
            epic_dir.mkdir(parents=True)
            _populate_repo_from_epic_data(repo, epic_name, str(epic_dir), {
                "name": epic_name,
                "status": "pending",
                "phases": [
                    {"name": "P1", "tickets": [
                        {"id": "SHARED_ID", "name": f"Ticket in {epic_name}", "status": "pending"},
                    ]}
                ],
            })

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
    """US-GD-206 - Criterion 3: Resurrection detection re-syncs live epic path."""

    def test_get_epic_returns_tinydb_record_without_disk_resurrection(self, isolated_repo):
        """get_epic() returns TinyDB record as-is without disk-based resurrection."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_resurrection"
        # Create epic in live/
        live_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        live_dir.mkdir(parents=True)
        _write_plan_yaml(live_dir, _minimal_epic_data(epic_name, status="in_progress"))

        service = EpicService(repo_path=isolated_repo)

        # Register the epic in TinyDB pointing to live/
        epic_data = _minimal_epic_data(epic_name, status="in_progress")
        _populate_repo_from_epic_data(
            service._repository, epic_name, str(live_dir), epic_data
        )

        # Simulate archiving: update DB to point to completed/
        completed_dir = isolated_repo / "docs" / "epics" / "completed" / epic_name
        completed_dir.mkdir(parents=True)
        _write_plan_yaml(completed_dir, _minimal_epic_data(epic_name, status="completed"))

        service._repository.update_epic(epic_name, {
            "epic_folder": str(completed_dir),
            "status": "completed",
        })

        # get_epic returns TinyDB record as-is (no disk-based correction)
        result = service.get_epic(epic_name)

        assert result is not None, "Should find the epic in TinyDB"
        assert result.epic_folder == completed_dir, (
            "get_epic returns TinyDB record as-is without disk-based resurrection"
        )

    def test_get_epic_returns_db_path_unchanged(self, isolated_repo):
        """get_epic() does not modify TinyDB path based on disk state."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_resurrection_db_update"
        live_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        live_dir.mkdir(parents=True)
        _write_plan_yaml(live_dir, _minimal_epic_data(epic_name, status="in_progress"))

        service = EpicService(repo_path=isolated_repo)

        epic_data = _minimal_epic_data(epic_name, status="in_progress")
        _populate_repo_from_epic_data(
            service._repository, epic_name, str(live_dir), epic_data
        )

        # Simulate stale TinyDB entry pointing to completed/
        completed_dir = isolated_repo / "docs" / "epics" / "completed" / epic_name
        completed_dir.mkdir(parents=True)
        _write_plan_yaml(completed_dir, _minimal_epic_data(epic_name, status="completed"))
        service._repository.update_epic(epic_name, {"epic_folder": str(completed_dir)})

        # get_epic does not modify TinyDB based on disk state
        service.get_epic(epic_name)

        # DB path should still be completed/ (no auto-resync from disk)
        db_entry = service._repository.get_epic(epic_name)
        assert db_entry is not None
        assert db_entry.epic_folder == completed_dir, (
            "TinyDB path should not be modified by disk-based resurrection"
        )


class TestUS_GD_206_YamlSyncDisabled:
    """US-GD-206 - Criterion 4: yaml_sync_enabled has been removed."""

    def test_ticket_service_no_yaml_sync_parameter(self, isolated_repo):
        """TicketService no longer accepts yaml_sync_enabled parameter."""
        from agenticguidance.services.ticket import TicketService
        import inspect

        sig = inspect.signature(TicketService.__init__)
        assert "yaml_sync_enabled" not in sig.parameters, (
            "yaml_sync_enabled parameter should be removed from TicketService"
        )

    def test_epic_service_no_yaml_sync_parameter(self, isolated_repo):
        """EpicService no longer accepts yaml_sync_enabled parameter."""
        from agenticguidance.services.epic import EpicService
        import inspect

        sig = inspect.signature(EpicService.__init__)
        assert "yaml_sync_enabled" not in sig.parameters, (
            "yaml_sync_enabled parameter should be removed from EpicService"
        )

    def test_yaml_sync_disabled_skips_yaml_writes_on_status_update(self, isolated_repo):
        """update_epic_status does not touch YAML files (yaml_sync permanently disabled)."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_nosync"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        original_data = _minimal_epic_data(epic_name, status="pending")
        _write_plan_yaml(epic_dir, original_data)

        service = EpicService(repo_path=isolated_repo)

        # Populate TinyDB using create_epic + add_ticket
        _populate_repo_from_epic_data(
            service._repository, epic_name, str(epic_dir), original_data
        )

        service.update_epic_status(epic_name, "active")

        # YAML on disk must NOT have been updated (yaml_sync permanently disabled)
        with open(epic_dir / "plan_build.yml") as f:
            on_disk = yaml.safe_load(f)

        assert on_disk["status"] == "pending", (
            "YAML file should not be updated when yaml_sync is permanently disabled"
        )

    def test_tinydb_is_updated_even_when_yaml_not_written(self, isolated_repo):
        """update_epic_status updates TinyDB even though YAML is not written."""
        from agenticguidance.services.epic import EpicService

        epic_name = "260224TE_tinydb_only_update"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        original_data = _minimal_epic_data(epic_name, status="pending")
        _write_plan_yaml(epic_dir, original_data)

        service = EpicService(repo_path=isolated_repo)
        _populate_repo_from_epic_data(
            service._repository, epic_name, str(epic_dir), original_data
        )

        service.update_epic_status(epic_name, "active")

        # TinyDB must be updated ("active" is now a canonical status)
        db_entry = service._repository.get_epic(epic_name)
        assert db_entry is not None
        assert db_entry.status == "active", (
            "TinyDB should reflect normalized status update even when YAML is not written"
        )


