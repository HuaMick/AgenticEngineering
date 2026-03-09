"""Pytest configuration and fixtures for AgenticGuidance tests."""

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _isolate_tinydb(tmp_path):
    """Redirect all TinyDB writes to a per-test temp directory."""
    isolated_db_path = tmp_path / ".agentic" / "epics.db"
    isolated_db_path.parent.mkdir(parents=True, exist_ok=True)

    from agenticguidance.services.epic import EpicService

    def _isolated_find_repo_root(start=None):
        return tmp_path

    with patch.object(EpicService, "_find_repo_root", staticmethod(_isolated_find_repo_root)):
        yield isolated_db_path


def populate_tinydb_from_yaml(db_path, epic_folder_name, epic_folder, yaml_data):
    """Populate TinyDB with epic/ticket data from a YAML-style dict.

    Args:
        db_path: Path to the TinyDB database file.
        epic_folder_name: Epic folder name.
        epic_folder: Path to the epic folder on disk.
        yaml_data: Dict with optional keys: name, status, phases, tasks.
    """
    from agenticguidance.services.epic_repository import EpicRepository

    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    repo.create_epic({
        "epic_folder_name": epic_folder_name,
        "epic_folder": str(epic_folder),
        "name": yaml_data.get("name", epic_folder_name),
        "status": yaml_data.get("status", "active"),
    })

    phases = yaml_data.get("phases", [])
    for phase in phases:
        phase_name = phase.get("name", phase.get("id", "default"))
        tickets = phase.get("tickets", phase.get("tasks", []))
        for ticket in tickets:
            repo.add_ticket(epic_folder_name, phase_name, ticket)

    flat_tasks = yaml_data.get("tasks", [])
    for ticket in flat_tasks:
        repo.add_ticket(epic_folder_name, "default", ticket)

    repo.close()
    return repo


@pytest.fixture
def tinydb_populator(_isolate_tinydb):
    """Fixture providing a function to populate the isolated TinyDB."""
    db_path = _isolate_tinydb

    def _populate(epic_folder_name, epic_folder, yaml_data):
        return populate_tinydb_from_yaml(db_path, epic_folder_name, epic_folder, yaml_data)

    return _populate


@pytest.fixture
def isolated_repo(_isolate_tinydb, tmp_path):
    """Provide a pre-configured EpicRepository pointing at the isolated DB."""
    from agenticguidance.services.epic_repository import EpicRepository
    repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
    yield repo
    repo.close()
