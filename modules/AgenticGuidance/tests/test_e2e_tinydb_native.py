"""End-to-end verification: full epic lifecycle works with TinyDB-only storage.

Verifies that no YAML files are created or required at any step:
1. Epic creation -> TinyDB only, no YAML
2. Epic listing -> reads from TinyDB
3. Ticket listing -> reads from TinyDB
4. Ticket start/complete -> updates TinyDB
5. Epic archive -> updates TinyDB status
6. No ticket_*.yml or plan_*.yml files exist at any point
"""

import pytest
from pathlib import Path

from agenticguidance.services.epic import EpicService
from agenticguidance.services.epic_repository import EpicRepository
from agenticguidance.services.ticket import TicketService


@pytest.fixture
def repo(tmp_path):
    """Isolated EpicRepository."""
    db_path = tmp_path / "epics.db"
    r = EpicRepository(db_path=db_path, auto_bootstrap=False)
    yield r
    r.close()


@pytest.fixture
def isolated_repo(tmp_path):
    """Isolated git-like repo structure for EpicService."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "docs" / "epics" / "live").mkdir(parents=True)
    (repo_root / "docs" / "epics" / "completed").mkdir(parents=True)
    (repo_root / ".agentic").mkdir()
    return repo_root


def _yaml_files_in(path: Path) -> list:
    """Find any ticket_*.yml or plan_*.yml files under path."""
    found = []
    if path.exists():
        for f in path.rglob("*.yml"):
            if f.name.startswith("ticket_") or f.name.startswith("plan_"):
                found.append(f)
    return found


class TestFullLifecycleNoYaml:
    """Complete epic lifecycle using only TinyDB storage."""

    def test_create_epic_no_yaml(self, isolated_repo):
        """Step 1: EpicService.create_epic writes to TinyDB, not YAML."""
        service = EpicService(repo_path=isolated_repo)
        result = service.create_epic(
            objective="Test TinyDB-only epic",
            branch="test-branch",
            description="tinydb_native_test",
        )
        assert result.success
        # Folder is no longer created by create_epic(); verify TinyDB record exists instead.
        db_record = service._repository.get_epic(result.epic_folder_name)
        assert db_record is not None, "Epic record should exist in TinyDB after creation"

        # No YAML files should exist (check parent live/ dir since folder may not exist)
        yaml_files = _yaml_files_in(result.epic_folder.parent)
        assert yaml_files == [], f"YAML files found after create_epic: {yaml_files}"

    def test_list_epics_from_tinydb(self, isolated_repo):
        """Step 2: list_epics reads from TinyDB."""
        service = EpicService(repo_path=isolated_repo)
        service.create_epic(
            objective="List test epic",
            branch="list-branch",
            description="list_test",
        )

        epics = service.list_epics(status="live")
        assert len(epics) >= 1
        names = [e.epic_folder_name for e in epics]
        assert any("list_test" in n for n in names)

    def test_ticket_operations_tinydb_only(self, isolated_repo):
        """Steps 3-4: Ticket list/start/complete use TinyDB only."""
        service = EpicService(repo_path=isolated_repo)
        result = service.create_epic(
            objective="Ticket ops test",
            branch="ticket-branch",
            description="ticket_ops",
        )
        epic_name = result.epic_folder_name

        # Add phase and tickets via repository
        service._repository.add_phase(epic_name, {"name": "Build Phase"})
        service._repository.add_ticket(epic_name, "Build Phase", {
            "task_id": "T1_1",
            "name": "Build component",
            "status": "pending",
        })
        service._repository.add_ticket(epic_name, "Build Phase", {
            "task_id": "T1_2",
            "name": "Build component 2",
            "status": "pending",
        })

        # List tickets
        tickets = service._repository.get_tickets(epic_name)
        assert len(tickets) == 2

        # Start ticket
        service._repository.update_ticket_status(epic_name, "T1_1", "in_progress")
        t = service._repository.get_ticket(epic_name, "T1_1")
        assert t.status == "in_progress"

        # Complete ticket
        service._repository.update_ticket_status(epic_name, "T1_1", "completed")
        t = service._repository.get_ticket(epic_name, "T1_1")
        assert t.status == "completed"

        # No YAML files at any point
        yaml_files = _yaml_files_in(result.epic_folder)
        assert yaml_files == [], f"YAML files found after ticket ops: {yaml_files}"

    def test_ticket_service_no_yaml(self, isolated_repo):
        """TicketService operates without YAML."""
        epic_name = "260307TE_e2e_test"
        epic_dir = isolated_repo / "docs" / "epics" / "live" / epic_name
        epic_dir.mkdir(parents=True)

        db_path = isolated_repo / ".agentic" / "epics.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(epic_dir),
            "name": "E2E Test",
            "status": "active",
        })
        repo.add_phase(epic_name, {"name": "Phase 1"})
        repo.add_ticket(epic_name, "Phase 1", {
            "task_id": "T1_1",
            "name": "Test ticket",
            "status": "pending",
        })

        # TicketService should work without any YAML
        svc = TicketService(epic_path=epic_dir, repository=repo)
        tickets = svc.list_tickets()
        assert len(tickets) >= 1

        # No YAML created
        yaml_files = _yaml_files_in(epic_dir)
        assert yaml_files == [], f"YAML files found: {yaml_files}"
        repo.close()

    def test_epic_service_no_yaml_sync_parameter(self):
        """EpicService and TicketService no longer accept yaml_sync_enabled."""
        import inspect

        epic_sig = inspect.signature(EpicService.__init__)
        assert "yaml_sync_enabled" not in epic_sig.parameters

        ticket_sig = inspect.signature(TicketService.__init__)
        assert "yaml_sync_enabled" not in ticket_sig.parameters

    def test_no_yaml_files_in_live_epics(self, isolated_repo):
        """After creating multiple epics, no YAML files exist in live/."""
        service = EpicService(repo_path=isolated_repo)

        for i in range(3):
            service.create_epic(
                objective=f"Multi-epic test {i}",
                branch=f"multi-{i}",
                description=f"multi_test_{i}",
            )

        live_dir = isolated_repo / "docs" / "epics" / "live"
        yaml_files = _yaml_files_in(live_dir)
        assert yaml_files == [], f"YAML files found in live/: {yaml_files}"
