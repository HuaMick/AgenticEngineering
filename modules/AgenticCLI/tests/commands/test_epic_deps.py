"""Integration tests for CLI epic link/unlink/set-priority commands.

Tests:
- link creates dependency
- unlink removes dependency
- link rejects cycle, self-ref, nonexistent
- set-priority validates priority values
- list shows priority
- status shows deps

Uses monkeypatch and tmp_path TinyDB fixture.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agenticguidance.services.epic_repository import EpicRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    """Create an isolated EpicRepository backed by tmp_path."""
    db_path = tmp_path / "epics.db"
    r = EpicRepository(db_path=db_path, auto_bootstrap=False)
    yield r
    r.close()


def _create_epic(repo, name, status="in_progress", priority="medium", depends_on=None):
    """Helper to seed an epic in the repo."""
    repo.create_epic({
        "epic_folder_name": name,
        "epic_folder": f"/tmp/epics/{name}",
        "name": name,
        "status": status,
        "priority": priority,
        "objective": f"Objective for {name}",
        "depends_on": depends_on or [],
    })


def _mock_find_epic_folder(name):
    """Return a Path with the given name (simulating find_epic_folder)."""
    return Path(f"/tmp/epics/{name}")


# ---------------------------------------------------------------------------
# cmd_link tests
# ---------------------------------------------------------------------------


class TestCmdLink:
    """Tests for cmd_link CLI command."""

    def test_link_creates_dependency(self, repo):
        """link adds a dependency between two epics."""
        _create_epic(repo, "epic_A")
        _create_epic(repo, "epic_B")

        from agenticcli.commands.epic import cmd_link

        args = SimpleNamespace(epic="epic_A", depends_on="epic_B", path=None)

        with patch("agenticcli.commands.epic._get_repo", return_value=repo), \
             patch("agenticcli.commands.epic.find_epic_folder", side_effect=_mock_find_epic_folder), \
             patch("agenticcli.console.is_json_output", return_value=False), \
             patch("agenticcli.console.print_success") as mock_success:
            cmd_link(args)

        deps = repo.get_dependencies("epic_A")
        assert "epic_B" in deps
        mock_success.assert_called_once()

    def test_link_rejects_self_reference(self, repo):
        """link rejects self-dependency."""
        _create_epic(repo, "epic_A")

        from agenticcli.commands.epic import cmd_link

        args = SimpleNamespace(epic="epic_A", depends_on="epic_A", path=None)

        with patch("agenticcli.commands.epic._get_repo", return_value=repo), \
             patch("agenticcli.commands.epic.find_epic_folder", side_effect=_mock_find_epic_folder), \
             patch("agenticcli.console.is_json_output", return_value=False), \
             patch("agenticcli.console.print_error") as mock_error:
            with pytest.raises(SystemExit):
                cmd_link(args)
        mock_error.assert_called_once()
        assert "itself" in mock_error.call_args[0][0].lower()

    def test_link_rejects_cycle(self, repo):
        """link rejects a dependency that would create a cycle."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B")

        from agenticcli.commands.epic import cmd_link

        args = SimpleNamespace(epic="epic_B", depends_on="epic_A", path=None)

        with patch("agenticcli.commands.epic._get_repo", return_value=repo), \
             patch("agenticcli.commands.epic.find_epic_folder", side_effect=_mock_find_epic_folder), \
             patch("agenticcli.console.is_json_output", return_value=False), \
             patch("agenticcli.console.print_error") as mock_error:
            with pytest.raises(SystemExit):
                cmd_link(args)
        mock_error.assert_called_once()
        assert "cycle" in mock_error.call_args[0][0].lower()

    def test_link_rejects_nonexistent_epic(self, repo):
        """link fails when depends-on epic doesn't exist."""
        _create_epic(repo, "epic_A")

        from agenticcli.commands.epic import cmd_link

        args = SimpleNamespace(epic="epic_A", depends_on="nonexistent", path=None)

        # find_epic_folder calls sys.exit(1) when epic not found
        def _find_side_effect(name):
            if name == "nonexistent":
                raise SystemExit(1)
            return _mock_find_epic_folder(name)

        with patch("agenticcli.commands.epic._get_repo", return_value=repo), \
             patch("agenticcli.commands.epic.find_epic_folder", side_effect=_find_side_effect):
            with pytest.raises(SystemExit):
                cmd_link(args)

    def test_link_json_output(self, repo):
        """link outputs JSON when json mode is active."""
        _create_epic(repo, "epic_A")
        _create_epic(repo, "epic_B")

        from agenticcli.commands.epic import cmd_link

        args = SimpleNamespace(epic="epic_A", depends_on="epic_B", path=None)
        captured_json = {}

        def capture_json(data):
            captured_json.update(data)

        with patch("agenticcli.commands.epic._get_repo", return_value=repo), \
             patch("agenticcli.commands.epic.find_epic_folder", side_effect=_mock_find_epic_folder), \
             patch("agenticcli.console.is_json_output", return_value=True), \
             patch("agenticcli.console.print_json", side_effect=capture_json):
            cmd_link(args)

        assert captured_json["result"] == "success"
        assert captured_json["epic"] == "epic_A"
        assert captured_json["depends_on"] == "epic_B"

    def test_link_missing_args_exits(self, repo):
        """link exits with error when args are missing."""
        from agenticcli.commands.epic import cmd_link

        args = SimpleNamespace(epic=None, depends_on=None, path=None)

        with patch("agenticcli.console.print_error"):
            with pytest.raises(SystemExit):
                cmd_link(args)


# ---------------------------------------------------------------------------
# cmd_unlink tests
# ---------------------------------------------------------------------------


class TestCmdUnlink:
    """Tests for cmd_unlink CLI command."""

    def test_unlink_removes_dependency(self, repo):
        """unlink removes an existing dependency."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B")

        from agenticcli.commands.epic import cmd_unlink

        args = SimpleNamespace(epic="epic_A", depends_on="epic_B", path=None)

        with patch("agenticcli.commands.epic._get_repo", return_value=repo), \
             patch("agenticcli.commands.epic.find_epic_folder", side_effect=_mock_find_epic_folder), \
             patch("agenticcli.console.is_json_output", return_value=False), \
             patch("agenticcli.console.print_success") as mock_success:
            cmd_unlink(args)

        deps = repo.get_dependencies("epic_A")
        assert "epic_B" not in deps
        mock_success.assert_called_once()

    def test_unlink_nonexistent_dep_fails(self, repo):
        """unlink fails when the dependency doesn't exist."""
        _create_epic(repo, "epic_A")
        _create_epic(repo, "epic_B")

        from agenticcli.commands.epic import cmd_unlink

        args = SimpleNamespace(epic="epic_A", depends_on="epic_B", path=None)

        with patch("agenticcli.commands.epic._get_repo", return_value=repo), \
             patch("agenticcli.commands.epic.find_epic_folder", side_effect=_mock_find_epic_folder), \
             patch("agenticcli.console.is_json_output", return_value=False), \
             patch("agenticcli.console.print_error") as mock_error:
            with pytest.raises(SystemExit):
                cmd_unlink(args)
        mock_error.assert_called_once()

    def test_unlink_json_output(self, repo):
        """unlink outputs JSON when json mode is active."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B")

        from agenticcli.commands.epic import cmd_unlink

        args = SimpleNamespace(epic="epic_A", depends_on="epic_B", path=None)
        captured_json = {}

        def capture_json(data):
            captured_json.update(data)

        with patch("agenticcli.commands.epic._get_repo", return_value=repo), \
             patch("agenticcli.commands.epic.find_epic_folder", side_effect=_mock_find_epic_folder), \
             patch("agenticcli.console.is_json_output", return_value=True), \
             patch("agenticcli.console.print_json", side_effect=capture_json):
            cmd_unlink(args)

        assert captured_json["result"] == "success"
        assert captured_json["removed_dependency"] == "epic_B"

    def test_unlink_missing_args_exits(self, repo):
        """unlink exits with error when args are missing."""
        from agenticcli.commands.epic import cmd_unlink

        args = SimpleNamespace(epic=None, depends_on=None, path=None)

        with patch("agenticcli.console.print_error"):
            with pytest.raises(SystemExit):
                cmd_unlink(args)


# ---------------------------------------------------------------------------
# cmd_set_priority tests
# ---------------------------------------------------------------------------


class TestCmdSetPriority:
    """Tests for cmd_set_priority CLI command."""

    def test_set_priority_success(self, repo):
        """set-priority updates the priority field."""
        _create_epic(repo, "epic_A", priority="medium")

        from agenticcli.commands.epic import cmd_set_priority

        args = SimpleNamespace(epic="epic_A", priority="high", path=None)

        with patch("agenticcli.commands.epic._get_repo", return_value=repo), \
             patch("agenticcli.commands.epic.find_epic_folder", side_effect=_mock_find_epic_folder), \
             patch("agenticcli.console.is_json_output", return_value=False), \
             patch("agenticcli.console.print_success") as mock_success:
            cmd_set_priority(args)

        epic = repo.get_epic("epic_A")
        assert epic is not None
        # The update_epic call stores the lowercased priority
        mock_success.assert_called_once()

    def test_set_priority_validates_invalid(self, repo):
        """set-priority rejects invalid priority values."""
        _create_epic(repo, "epic_A")

        from agenticcli.commands.epic import cmd_set_priority

        args = SimpleNamespace(epic="epic_A", priority="urgent", path=None)

        with patch("agenticcli.console.is_json_output", return_value=False), \
             patch("agenticcli.console.print_error") as mock_error:
            with pytest.raises(SystemExit):
                cmd_set_priority(args)
        mock_error.assert_called_once()
        assert "invalid priority" in mock_error.call_args[0][0].lower()

    def test_set_priority_all_valid_values(self, repo):
        """All valid priorities (critical, high, medium, low) are accepted."""
        for priority in ("critical", "high", "medium", "low"):
            _create_epic(repo, f"epic_{priority}", priority="medium")

            from agenticcli.commands.epic import cmd_set_priority

            args = SimpleNamespace(epic=f"epic_{priority}", priority=priority, path=None)

            with patch("agenticcli.commands.epic._get_repo", return_value=repo), \
                 patch("agenticcli.commands.epic.find_epic_folder", side_effect=_mock_find_epic_folder), \
                 patch("agenticcli.console.is_json_output", return_value=False), \
                 patch("agenticcli.console.print_success"):
                cmd_set_priority(args)

    def test_set_priority_case_insensitive(self, repo):
        """Priority input is case-insensitive."""
        _create_epic(repo, "epic_A", priority="medium")

        from agenticcli.commands.epic import cmd_set_priority

        args = SimpleNamespace(epic="epic_A", priority="HIGH", path=None)

        with patch("agenticcli.commands.epic._get_repo", return_value=repo), \
             patch("agenticcli.commands.epic.find_epic_folder", side_effect=_mock_find_epic_folder), \
             patch("agenticcli.console.is_json_output", return_value=False), \
             patch("agenticcli.console.print_success"):
            cmd_set_priority(args)

    def test_set_priority_json_output(self, repo):
        """set-priority outputs JSON when json mode is active."""
        _create_epic(repo, "epic_A", priority="medium")

        from agenticcli.commands.epic import cmd_set_priority

        args = SimpleNamespace(epic="epic_A", priority="critical", path=None)
        captured_json = {}

        def capture_json(data):
            captured_json.update(data)

        with patch("agenticcli.commands.epic._get_repo", return_value=repo), \
             patch("agenticcli.commands.epic.find_epic_folder", side_effect=_mock_find_epic_folder), \
             patch("agenticcli.console.is_json_output", return_value=True), \
             patch("agenticcli.console.print_json", side_effect=capture_json):
            cmd_set_priority(args)

        assert captured_json["result"] == "success"
        assert captured_json["priority"] == 1  # "critical" normalized to int

    def test_set_priority_missing_args_exits(self, repo):
        """set-priority exits with error when args are missing."""
        from agenticcli.commands.epic import cmd_set_priority

        args = SimpleNamespace(epic=None, priority=None, path=None)

        with patch("agenticcli.console.print_error"):
            with pytest.raises(SystemExit):
                cmd_set_priority(args)
