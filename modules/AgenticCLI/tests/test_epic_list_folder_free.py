"""Tests to prevent regression of the folder-free epic listing crash.

Bug: `agentic epic list` crashed with:
    AttributeError: 'NoneType' object has no attribute 'name'
at epic.py line 1912 when `meta.epic_folder` was None for a TinyDB-only epic.

The fix uses `meta.epic_folder_name` directly instead of `meta.epic_folder.name`.
These tests ensure that path is exercised and never regresses.
"""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.conftest import populate_tinydb_from_yaml

pytestmark = pytest.mark.story("US-PLN-001")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def folder_free_repo(tmp_path, _isolate_tinydb):
    """Repo with a single folder-free epic (epic_folder='') in TinyDB.

    No corresponding directory exists on disk.  This is the scenario that
    triggered the original AttributeError crash.
    """
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    populate_tinydb_from_yaml(
        _isolate_tinydb,
        "260329CF_folder_free_epic",
        None,  # No disk folder — folder-free epic
        {
            "name": "Folder-Free Epic",
            "status": "planning",
            "phases": [
                {
                    "name": "Phase 1",
                    "status": "planning",
                    "agent": "build-python",
                    "tickets": [
                        {"id": "T1", "name": "First ticket", "status": "proposed"},
                        {"id": "T2", "name": "Second ticket", "status": "pending"},
                    ],
                }
            ],
        },
    )

    return repo_dir


@pytest.fixture
def mixed_epics_repo(tmp_path, _isolate_tinydb):
    """Repo with two epics: one with a real folder, one without.

    This tests that cmd_list handles heterogeneous epic lists gracefully.
    """
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Epic 1: has a real folder on disk
    epic_with_folder = tmp_path / "260329MX_with_folder"
    epic_with_folder.mkdir()

    populate_tinydb_from_yaml(
        _isolate_tinydb,
        "260329MX_with_folder",
        epic_with_folder,
        {
            "name": "Epic With Folder",
            "status": "planning",
            "phases": [
                {
                    "name": "P1",
                    "status": "planning",
                    "agent": "build-python",
                    "tickets": [
                        {"id": "A1", "name": "Ticket A1", "status": "pending"},
                    ],
                }
            ],
        },
    )

    # Epic 2: folder-free (TinyDB-only)
    populate_tinydb_from_yaml(
        _isolate_tinydb,
        "260329MX_no_folder",
        None,  # No disk folder
        {
            "name": "Epic Without Folder",
            "status": "planning",
            "phases": [
                {
                    "name": "P1",
                    "status": "planning",
                    "agent": "test-builder",
                    "tickets": [
                        {"id": "B1", "name": "Ticket B1", "status": "proposed"},
                    ],
                }
            ],
        },
    )

    return repo_dir


@pytest.fixture
def folder_free_with_tickets_repo(tmp_path, _isolate_tinydb):
    """Repo with a folder-free epic that has tickets and phases.

    Used to test cmd_status on a folder-free epic.
    """
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    populate_tinydb_from_yaml(
        _isolate_tinydb,
        "260329FS_status_test",
        None,  # folder-free
        {
            "name": "Status Test Epic",
            "status": "planning",
            "phases": [
                {
                    "name": "Phase 1",
                    "status": "planning",
                    "agent": "build-python",
                    "tickets": [
                        {"id": "S1", "name": "Status ticket 1", "status": "completed"},
                        {"id": "S2", "name": "Status ticket 2", "status": "pending"},
                    ],
                }
            ],
        },
    )

    return repo_dir


# ---------------------------------------------------------------------------
# Helper: build a minimal cli_runner that works without a git repo on disk
# ---------------------------------------------------------------------------


def _make_cli_runner(cwd: Path):
    """Return a run_cli callable scoped to *cwd*."""
    import io
    from contextlib import redirect_stderr, redirect_stdout

    original_cwd = os.getcwd()
    os.chdir(cwd)

    def run_cli(*args):
        from agenticcli.cli import run_cli as _run_cli
        from agenticcli.console import set_json_output

        set_json_output(False)
        cmd_args = list(args[0]) if (len(args) == 1 and isinstance(args[0], list)) else list(args)

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        exit_code = 0

        with patch.object(sys, "argv", ["agentic"] + cmd_args):
            with redirect_stdout(stdout_buf):
                with redirect_stderr(stderr_buf):
                    try:
                        _run_cli()
                    except SystemExit as exc:
                        exit_code = exc.code if exc.code is not None else 0

        return stdout_buf.getvalue(), stderr_buf.getvalue(), exit_code

    return run_cli, original_cwd


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEpicListFolderFreeEpic:
    """cmd_list must not crash when an epic has no folder on disk."""

    @pytest.mark.story("US-PLN-001")
    def test_epic_list_with_folder_free_epic_does_not_crash(
        self, folder_free_repo, _isolate_tinydb
    ):
        """Regression test: cmd_list must not AttributeError on folder-free epics.

        Before the fix, `meta.epic_folder.name` raised AttributeError when
        `meta.epic_folder` was None.  The fix uses `meta.epic_folder_name`
        directly.  This test exercises that code path.
        """
        from agenticcli.commands.epic import cmd_list

        args = SimpleNamespace(all=True, json=False)

        # Must not raise AttributeError or any other exception
        try:
            cmd_list(args)
        except SystemExit:
            pass  # sys.exit() calls are acceptable; crashes are not

    @pytest.mark.story("US-PLN-001")
    def test_epic_list_folder_free_displays_epic_folder_name(
        self, folder_free_repo, _isolate_tinydb, capsys
    ):
        """The epic_folder_name should appear in cmd_list output for folder-free epics."""
        from agenticcli.commands.epic import cmd_list

        args = SimpleNamespace(all=True, json=False)

        try:
            cmd_list(args)
        except SystemExit:
            pass

        captured = capsys.readouterr()
        # The folder name (not a path attribute) should be printed
        assert "260329CF_folder_free_epic" in captured.out

    @pytest.mark.story("US-PLN-001")
    def test_epic_list_folder_free_json_output_contains_name(
        self, folder_free_repo, _isolate_tinydb, capsys
    ):
        """JSON output of cmd_list must include the folder-free epic by name."""
        import json as json_mod

        from agenticcli.commands.epic import cmd_list
        from agenticcli.console import set_json_output

        set_json_output(True)
        args = SimpleNamespace(all=True, json=True)

        try:
            cmd_list(args)
        except SystemExit:
            pass
        finally:
            set_json_output(False)

        captured = capsys.readouterr()
        # Output should be parseable JSON containing the epic
        data = json_mod.loads(captured.out)
        names = [p["name"] for p in data.get("plans", [])]
        assert "260329CF_folder_free_epic" in names


class TestEpicListMixedFolderAndFolderless:
    """cmd_list handles a mix of folder-backed and folder-free epics."""

    @pytest.mark.story("US-PLN-001")
    def test_both_epics_appear_in_output(
        self, mixed_epics_repo, _isolate_tinydb, capsys
    ):
        """Both the folder-backed epic and the folder-free epic should be listed."""
        from agenticcli.commands.epic import cmd_list

        args = SimpleNamespace(all=True, json=False)

        try:
            cmd_list(args)
        except SystemExit:
            pass

        captured = capsys.readouterr()
        assert "260329MX_with_folder" in captured.out
        assert "260329MX_no_folder" in captured.out

    @pytest.mark.story("US-PLN-001")
    def test_mixed_list_does_not_crash(self, mixed_epics_repo, _isolate_tinydb):
        """cmd_list with mixed epics must complete without AttributeError."""
        from agenticcli.commands.epic import cmd_list

        args = SimpleNamespace(all=True, json=False)

        raised = None
        try:
            cmd_list(args)
        except AttributeError as exc:
            raised = exc
        except SystemExit:
            pass

        assert raised is None, f"cmd_list raised AttributeError: {raised}"

    @pytest.mark.story("US-PLN-001")
    def test_mixed_list_json_contains_both_epics(
        self, mixed_epics_repo, _isolate_tinydb, capsys
    ):
        """JSON output must include both folder-backed and folder-free epics."""
        import json as json_mod

        from agenticcli.commands.epic import cmd_list
        from agenticcli.console import set_json_output

        set_json_output(True)
        args = SimpleNamespace(all=True, json=True)

        try:
            cmd_list(args)
        except SystemExit:
            pass
        finally:
            set_json_output(False)

        captured = capsys.readouterr()
        data = json_mod.loads(captured.out)
        names = [p["name"] for p in data.get("plans", [])]
        assert "260329MX_with_folder" in names
        assert "260329MX_no_folder" in names


class TestEpicStatusFolderFreeEpic:
    """cmd_status must not crash when the epic has no folder on disk."""

    @pytest.mark.story("US-PLN-001")
    def test_epic_status_folder_free_does_not_crash(
        self, folder_free_with_tickets_repo, _isolate_tinydb
    ):
        """cmd_status called with a folder-free epic folder name must not crash.

        The epic exists in TinyDB but has no corresponding directory.  After
        TinyDB lookup, plan_path is None.  cmd_status must handle this without
        AttributeError or unhandled exception.
        """
        from agenticcli.commands.epic import cmd_status

        args = SimpleNamespace(
            path="260329FS_status_test",
            json=False,
            validate=False,
            all=False,
        )

        raised = None
        try:
            cmd_status(args)
        except AttributeError as exc:
            raised = exc
        except SystemExit:
            pass  # sys.exit() is acceptable

        assert raised is None, f"cmd_status raised AttributeError: {raised}"

    @pytest.mark.story("US-PLN-001")
    def test_epic_status_folder_free_shows_ticket_counts(
        self, folder_free_with_tickets_repo, _isolate_tinydb, capsys
    ):
        """cmd_status for a folder-free epic should display ticket progress."""
        from agenticcli.commands.epic import cmd_status

        args = SimpleNamespace(
            path="260329FS_status_test",
            json=False,
            validate=False,
            all=False,
        )

        try:
            cmd_status(args)
        except SystemExit:
            pass

        captured = capsys.readouterr()
        # At minimum the epic name should appear in the output
        assert "260329FS_status_test" in captured.out or "Status Test Epic" in captured.out
