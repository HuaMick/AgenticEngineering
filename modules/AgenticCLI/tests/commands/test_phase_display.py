"""Tests for phase list display and folder-free epic resolution."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _make_phase(name, phase_id=None, status="planning", tasks=None):
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


class TestEpicFolderOrSynthetic:
    """Regression tests for _epic_folder_or_synthetic with empty epic_folder."""

    def test_empty_string_epic_folder_uses_name(self):
        """epic_folder='' (folder-free) must use epic_folder_name, not Path('')."""
        from agenticcli.commands.epic import _epic_folder_or_synthetic

        epic = MagicMock()
        epic.epic_folder = ""
        epic.epic_folder_name = "260329AG_my_epic"

        result = _epic_folder_or_synthetic(epic)
        assert result.name == "260329AG_my_epic"

    def test_none_epic_folder_uses_name(self):
        """epic_folder=None uses epic_folder_name."""
        from agenticcli.commands.epic import _epic_folder_or_synthetic

        epic = MagicMock()
        epic.epic_folder = None
        epic.epic_folder_name = "260329AG_my_epic"

        result = _epic_folder_or_synthetic(epic)
        assert result.name == "260329AG_my_epic"

    def test_real_path_epic_folder_returned(self):
        """Non-empty epic_folder is returned as-is."""
        from agenticcli.commands.epic import _epic_folder_or_synthetic

        epic = MagicMock()
        epic.epic_folder = Path("/home/user/docs/epics/live/260329AG_my_epic")
        epic.epic_folder_name = "260329AG_my_epic"

        result = _epic_folder_or_synthetic(epic)
        assert result == Path("/home/user/docs/epics/live/260329AG_my_epic")
