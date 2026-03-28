"""Tests for 'agentic epic from-plan' command.

Tests covering plan file parsing, seed epic creation, dry-run mode,
error cases, and status integration.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agenticguidance.services.epic_repository import EpicRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_PLAN = """\
# Add Phone Notifications

## Context

We need to add push notification support for mobile users.

## Phase 1: Backend

- Add notification service
- Integrate with FCM

## Phase 2: Frontend

- Add notification preferences UI
- Handle deep links
"""

MINIMAL_PLAN = """\
# Fix Login Bug

Quick fix for the login timeout issue.
"""


def _make_plan_file(tmp_path, content=SAMPLE_PLAN, name="test-plan.md"):
    """Create a plan file in tmp_path and return its path."""
    plan_file = tmp_path / name
    plan_file.write_text(content)
    return plan_file


# ---------------------------------------------------------------------------
# Unit tests for cmd_from_plan
# ---------------------------------------------------------------------------


class TestFromPlanDryRun:
    """Dry run should preview without creating anything."""

    def test_dry_run_prints_summary(self, tmp_path, _isolate_tinydb, capsys):
        from agenticcli.commands.epic import cmd_from_plan

        plan_file = _make_plan_file(tmp_path)

        args = SimpleNamespace(
            plan_file=str(plan_file),
            branch=None,
            dry_run=True,
            debug=False,
            json=False,
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=str(tmp_path), stderr=""
            )
            cmd_from_plan(args)

        captured = capsys.readouterr()
        assert "Add Phone Notifications" in captured.out
        assert "plan-add-phone-notifications" in captured.out
        assert "Dry run" in captured.out

    def test_dry_run_no_db_writes(self, tmp_path, _isolate_tinydb):
        from agenticcli.commands.epic import cmd_from_plan

        plan_file = _make_plan_file(tmp_path)

        args = SimpleNamespace(
            plan_file=str(plan_file),
            branch=None,
            dry_run=True,
            debug=False,
            json=False,
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=str(tmp_path), stderr=""
            )
            cmd_from_plan(args)

        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        # The autouse _isolate_tinydb fixture creates a default epic; seed should NOT exist
        all_epics = repo.list_epics()
        seed_epics = [e for e in all_epics if e.status == "seed"]
        repo.close()
        assert len(seed_epics) == 0

    def test_dry_run_json_output(self, tmp_path, _isolate_tinydb, capsys):
        from agenticcli.commands.epic import cmd_from_plan
        from agenticcli.console import set_json_output

        plan_file = _make_plan_file(tmp_path)
        set_json_output(True)

        args = SimpleNamespace(
            plan_file=str(plan_file),
            branch=None,
            dry_run=True,
            debug=False,
            json=True,
        )

        try:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[], returncode=0, stdout=str(tmp_path), stderr=""
                )
                cmd_from_plan(args)
        finally:
            set_json_output(False)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["title"] == "Add Phone Notifications"
        assert data["branch"] == "plan-add-phone-notifications"


class TestFromPlanCreatesSeedEpic:
    """Integration tests that create actual seed epics."""

    def test_creates_seed_epic(self, cli_runner, temp_repo, _isolate_tinydb):
        plan_file = _make_plan_file(temp_repo, SAMPLE_PLAN)

        from agenticcli.commands.epic import cmd_from_plan

        args = SimpleNamespace(
            plan_file=str(plan_file),
            branch=None,
            dry_run=False,
            debug=False,
            json=False,
        )
        cmd_from_plan(args)

        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        all_epics = repo.list_epics()
        seed_epics = [e for e in all_epics if e.status == "seed"]
        repo.close()

        assert len(seed_epics) == 1
        assert seed_epics[0].branch == "plan-add-phone-notifications"

    def test_stores_plan_content_as_context(self, cli_runner, temp_repo, _isolate_tinydb):
        plan_file = _make_plan_file(temp_repo, SAMPLE_PLAN)

        from agenticcli.commands.epic import cmd_from_plan

        args = SimpleNamespace(
            plan_file=str(plan_file),
            branch=None,
            dry_run=False,
            debug=False,
            json=False,
        )
        cmd_from_plan(args)

        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        all_epics = repo.list_epics()
        seed_epics = [e for e in all_epics if e.status == "seed"]

        # Get the full epic data to check context
        epic_data = repo.get_epic(seed_epics[0].epic_folder_name)
        repo.close()

        # Context should contain the plan content
        assert epic_data is not None
        # The context is stored in the epic record
        from tinydb import Query
        _repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        Epic = Query()
        docs = _repo._epics.search(Epic.epic_folder_name == seed_epics[0].epic_folder_name)
        _repo.close()
        assert len(docs) == 1
        assert "Add Phone Notifications" in docs[0].get("context", "")

    def test_stores_plan_source_path(self, cli_runner, temp_repo, _isolate_tinydb):
        plan_file = _make_plan_file(temp_repo, SAMPLE_PLAN)

        from agenticcli.commands.epic import cmd_from_plan

        args = SimpleNamespace(
            plan_file=str(plan_file),
            branch=None,
            dry_run=False,
            debug=False,
            json=False,
        )
        cmd_from_plan(args)

        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        all_epics = repo.list_epics()
        seed_epics = [e for e in all_epics if e.status == "seed"]

        from tinydb import Query
        Epic = Query()
        docs = repo._epics.search(Epic.epic_folder_name == seed_epics[0].epic_folder_name)
        repo.close()

        assert len(docs) == 1
        assert docs[0].get("plan_source") == str(plan_file.resolve())

    def test_custom_branch(self, cli_runner, temp_repo, _isolate_tinydb):
        plan_file = _make_plan_file(temp_repo, SAMPLE_PLAN)

        from agenticcli.commands.epic import cmd_from_plan

        args = SimpleNamespace(
            plan_file=str(plan_file),
            branch="my-custom-branch",
            dry_run=False,
            debug=False,
            json=False,
        )
        cmd_from_plan(args)

        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        all_epics = repo.list_epics()
        seed_epics = [e for e in all_epics if e.status == "seed"]
        repo.close()

        assert len(seed_epics) == 1
        assert seed_epics[0].branch == "my-custom-branch"


class TestFromPlanErrors:
    """Error case tests."""

    def test_missing_file_exits(self, tmp_path, _isolate_tinydb):
        from agenticcli.commands.epic import cmd_from_plan

        args = SimpleNamespace(
            plan_file=str(tmp_path / "nonexistent.md"),
            branch=None,
            dry_run=False,
            debug=False,
            json=False,
        )

        with pytest.raises(SystemExit):
            cmd_from_plan(args)

    def test_empty_file_exits(self, tmp_path, _isolate_tinydb):
        from agenticcli.commands.epic import cmd_from_plan

        plan_file = tmp_path / "empty.md"
        plan_file.write_text("")

        args = SimpleNamespace(
            plan_file=str(plan_file),
            branch=None,
            dry_run=False,
            debug=False,
            json=False,
        )

        with pytest.raises(SystemExit):
            cmd_from_plan(args)

    def test_no_heading_uses_filename(self, cli_runner, temp_repo, _isolate_tinydb):
        """Plan without a heading should use the filename as title."""
        from agenticcli.commands.epic import cmd_from_plan

        plan_file = _make_plan_file(temp_repo, "No heading here, just text.", "my-plan.md")

        args = SimpleNamespace(
            plan_file=str(plan_file),
            branch=None,
            dry_run=True,
            debug=False,
            json=False,
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=str(temp_repo), stderr=""
            )
            cmd_from_plan(args)

        # Should not crash — title falls back to filename stem


# ---------------------------------------------------------------------------
# Status integration tests
# ---------------------------------------------------------------------------


class TestSeedStatus:
    """Tests for seed status in format_status and epic list."""

    def test_seed_in_format_status(self):
        from agenticcli.console import format_status
        result = format_status("seed")
        assert "magenta" in result
        assert "seed" in result

    def test_seed_in_normalize(self):
        from agenticguidance.services.epic import normalize_epic_status
        assert normalize_epic_status("seed") == "seed"

    def test_seed_in_epic_status_enum(self):
        from agenticguidance.services.epic import EpicStatus
        assert EpicStatus.SEED.value == "seed"

    def test_seed_in_live_statuses(self):
        from agenticguidance.services.epic_repository import _LIVE_STATUSES
        assert "seed" in _LIVE_STATUSES

    def test_seed_epic_in_list_epics(self, tmp_path, _isolate_tinydb):
        """Seed epics should appear in list_epics(status='live')."""
        from tests.conftest import populate_tinydb_from_yaml

        populate_tinydb_from_yaml(
            _isolate_tinydb,
            "260322SE_seed_test",
            tmp_path / "docs" / "epics" / "live" / "260322SE_seed_test",
            {"name": "Seed Test", "status": "seed"},
        )

        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        live_epics = repo.list_epics(status="live")
        repo.close()

        seed_names = [e.epic_folder_name for e in live_epics if e.status == "seed"]
        assert "260322SE_seed_test" in seed_names


class TestSeedNeedsOrchestration:
    """Seed epics should be discovered by the planner loop."""

    def test_seed_epic_needs_orchestration(self, tmp_path, _isolate_tinydb):
        from tests.conftest import populate_tinydb_from_yaml

        populate_tinydb_from_yaml(
            _isolate_tinydb,
            "260322SE_seed_orch",
            tmp_path / "docs" / "epics" / "live" / "260322SE_seed_orch",
            {"name": "Seed Orch Test", "status": "seed"},
        )

        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)

        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow.__new__(PlannerLoopWorkflow)
        workflow._repository = repo

        needs = workflow.discover_plans_needing_orchestration()
        repo.close()

        assert "260322SE_seed_orch" in needs
