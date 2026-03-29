"""Tests for phase list display using actual phase_id values."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _make_phase(name, phase_id=None, status="pending", tasks=None):
    """Create a mock PhaseData."""
    p = MagicMock()
    p.name = name
    p.phase_id = phase_id
    p.status = status
    p.tasks = tasks or []
    return p


def _make_epic(phases):
    """Create a mock EpicData with phases."""
    epic = MagicMock()
    epic.epic_folder_name = "test_epic"
    epic.phases = phases
    return epic


@pytest.fixture
def mock_repo():
    """Mock _get_repo to return a controlled repository."""
    repo = MagicMock()
    with patch("agenticcli.commands.epic._get_repo", return_value=repo):
        yield repo


@pytest.fixture
def mock_find_epic():
    """Mock find_epic_folder to return a predictable path."""
    from pathlib import Path
    with patch("agenticcli.commands.epic.find_epic_folder", return_value=Path("/tmp/test_epic")):
        yield


def test_phase_list_shows_stored_phase_id(mock_repo, mock_find_epic, capsys):
    """Display uses actual phase_id from TinyDB, not auto-numbered P{i+1}."""
    phases = [
        _make_phase("Build", phase_id="BUILD_01", tasks=[MagicMock()]),
        _make_phase("Test", phase_id="TEST_01"),
    ]
    epic = _make_epic(phases)
    mock_repo.get_epic.return_value = epic

    from agenticcli.commands.epic import cmd_phase_list

    args = SimpleNamespace(plan=None, json=False)

    with patch("agenticcli.console.is_json_output", return_value=True), \
         patch("agenticcli.console.print_json") as mock_print_json:
        cmd_phase_list(args)
        call_data = mock_print_json.call_args[0][0]
        assert call_data["phases"][0]["id"] == "BUILD_01"
        assert call_data["phases"][1]["id"] == "TEST_01"


def test_phase_list_fallback_for_missing_phase_id(mock_repo, mock_find_epic, capsys):
    """P{i+1} fallback used when phase_id is None (legacy data)."""
    phases = [
        _make_phase("Build", phase_id=None, tasks=[]),
        _make_phase("Test", phase_id="", tasks=[]),
    ]
    epic = _make_epic(phases)
    mock_repo.get_epic.return_value = epic

    from agenticcli.commands.epic import cmd_phase_list

    args = SimpleNamespace(plan=None, json=False)

    with patch("agenticcli.console.is_json_output", return_value=True), \
         patch("agenticcli.console.print_json") as mock_print_json:
        cmd_phase_list(args)
        call_data = mock_print_json.call_args[0][0]
        assert call_data["phases"][0]["id"] == "P1"
        assert call_data["phases"][1]["id"] == "P2"
