"""Tests for `agentic stories audit` subcommand — bidirectional gap detection.

Validates:
- Unlinked tickets (tickets without story_ids)
- Orphan stories (stories not referenced by any ticket)
- JSON output format
- Edge cases: no story file, no tickets, full coverage

Ticket: TS_004 — 260327AG_mandatory_ticket_story_binding_for_build_plans

@story US-STR-009
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agenticguidance.services.epic_repository import EpicRepository

pytestmark = pytest.mark.story("US-STR-030")


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def audit_epic(tmp_path, _isolate_tinydb, monkeypatch):
    """Create an epic with stories and tickets for audit testing.

    Sets up:
    - 3 tickets: T1 (linked to US-001), T2 (linked to US-002), T3 (unlinked)
    - 3 stories in EpicStories/: US-001, US-002, US-003
    → Expected audit: T3 unlinked, US-003 orphan
    """
    db_path = _isolate_tinydb
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

    epic_folder = tmp_path / "docs" / "epics" / "live" / "260327XX_audit_test"
    epic_folder.mkdir(parents=True)
    (tmp_path / ".git").mkdir(exist_ok=True)

    repo.create_epic({
        "epic_folder_name": "260327XX_audit_test",
        "epic_folder": str(epic_folder),
        "name": "Audit Test Epic",
        "status": "planning",
    })
    repo.add_phase("260327XX_audit_test", {
        "name": "Build Phase",
        "agent": "build-python",
        "status": "pending",
    })

    # Ticket with story_ids
    repo.add_ticket("260327XX_audit_test", "Build Phase", {
        "id": "T1", "name": "Task with stories",
        "status": "proposed", "story_ids": ["US-001"],
    })
    repo.add_ticket("260327XX_audit_test", "Build Phase", {
        "id": "T2", "name": "Another task with stories",
        "status": "proposed", "story_ids": ["US-002"],
    })
    # Ticket WITHOUT story_ids
    repo.add_ticket("260327XX_audit_test", "Build Phase", {
        "id": "T3", "name": "Task without stories",
        "status": "proposed",
    })

    # Write stories to EpicStories/ (consolidated location)
    epic_stories_dir = tmp_path / "docs" / "userstories" / "EpicStories"
    epic_stories_dir.mkdir(parents=True, exist_ok=True)
    stories_content = {
        "stories": [
            {"id": "US-001", "title": "Story One"},
            {"id": "US-002", "title": "Story Two"},
            {"id": "US-003", "title": "Orphan Story"},
        ]
    }
    (epic_stories_dir / "260327XX_audit_test.yml").write_text(yaml.dump(stories_content))

    # Monkeypatch get_epic_stories_path to resolve within test tmp_path
    import agenticcli.commands.stories as _stories_mod
    monkeypatch.setattr(_stories_mod, "get_epic_stories_path",
                        lambda name: epic_stories_dir / f"{name}.yml")

    yield {
        "repo": repo,
        "db_path": db_path,
        "epic_folder": epic_folder,
        "epic_folder_name": "260327XX_audit_test",
    }

    repo.close()


@pytest.fixture
def full_coverage_epic(tmp_path, _isolate_tinydb, monkeypatch):
    """Create an epic where all tickets have story_ids and all stories are referenced."""
    db_path = _isolate_tinydb
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

    epic_folder = tmp_path / "docs" / "epics" / "live" / "260327XX_full_cov"
    epic_folder.mkdir(parents=True)
    (tmp_path / ".git").mkdir(exist_ok=True)

    repo.create_epic({
        "epic_folder_name": "260327XX_full_cov",
        "epic_folder": str(epic_folder),
        "name": "Full Coverage Epic",
        "status": "planning",
    })
    repo.add_phase("260327XX_full_cov", {
        "name": "Build Phase",
        "agent": "build-python",
        "status": "pending",
    })

    repo.add_ticket("260327XX_full_cov", "Build Phase", {
        "id": "T1", "name": "Task 1",
        "status": "proposed", "story_ids": ["US-A01"],
    })
    repo.add_ticket("260327XX_full_cov", "Build Phase", {
        "id": "T2", "name": "Task 2",
        "status": "proposed", "story_ids": ["US-A02"],
    })

    # Write stories to EpicStories/ (consolidated location)
    epic_stories_dir = tmp_path / "docs" / "userstories" / "EpicStories"
    epic_stories_dir.mkdir(parents=True, exist_ok=True)
    stories_content = {
        "stories": [
            {"id": "US-A01", "title": "Story A1"},
            {"id": "US-A02", "title": "Story A2"},
        ]
    }
    (epic_stories_dir / "260327XX_full_cov.yml").write_text(yaml.dump(stories_content))

    # Monkeypatch get_epic_stories_path to resolve within test tmp_path
    import agenticcli.commands.stories as _stories_mod
    monkeypatch.setattr(_stories_mod, "get_epic_stories_path",
                        lambda name: epic_stories_dir / f"{name}.yml")

    yield {
        "repo": repo,
        "db_path": db_path,
        "epic_folder": epic_folder,
        "epic_folder_name": "260327XX_full_cov",
    }

    repo.close()


@pytest.fixture
def no_stories_epic(tmp_path, _isolate_tinydb, monkeypatch):
    """Create an epic WITHOUT a story file."""
    db_path = _isolate_tinydb
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

    epic_folder = tmp_path / "docs" / "epics" / "live" / "260327XX_no_stories"
    epic_folder.mkdir(parents=True)
    (tmp_path / ".git").mkdir(exist_ok=True)

    repo.create_epic({
        "epic_folder_name": "260327XX_no_stories",
        "epic_folder": str(epic_folder),
        "name": "No Stories Epic",
        "status": "planning",
    })
    repo.add_phase("260327XX_no_stories", {
        "name": "Build Phase",
        "status": "pending",
    })
    repo.add_ticket("260327XX_no_stories", "Build Phase", {
        "id": "T1", "name": "Task 1", "status": "proposed",
    })
    repo.add_ticket("260327XX_no_stories", "Build Phase", {
        "id": "T2", "name": "Task 2", "status": "proposed",
    })
    # No story file created in EpicStories/

    # Monkeypatch get_epic_stories_path to resolve within test tmp_path
    epic_stories_dir = tmp_path / "docs" / "userstories" / "EpicStories"
    epic_stories_dir.mkdir(parents=True, exist_ok=True)
    import agenticcli.commands.stories as _stories_mod
    monkeypatch.setattr(_stories_mod, "get_epic_stories_path",
                        lambda name: epic_stories_dir / f"{name}.yml")

    yield {
        "repo": repo,
        "db_path": db_path,
        "epic_folder": epic_folder,
        "epic_folder_name": "260327XX_no_stories",
    }

    repo.close()


@pytest.fixture
def no_tickets_epic(tmp_path, _isolate_tinydb, monkeypatch):
    """Create an epic with stories but NO tickets."""
    db_path = _isolate_tinydb
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

    epic_folder = tmp_path / "docs" / "epics" / "live" / "260327XX_no_tickets"
    epic_folder.mkdir(parents=True)
    (tmp_path / ".git").mkdir(exist_ok=True)

    repo.create_epic({
        "epic_folder_name": "260327XX_no_tickets",
        "epic_folder": str(epic_folder),
        "name": "No Tickets Epic",
        "status": "planning",
    })

    # Write stories to EpicStories/ (consolidated location)
    epic_stories_dir = tmp_path / "docs" / "userstories" / "EpicStories"
    epic_stories_dir.mkdir(parents=True, exist_ok=True)
    stories_content = {
        "stories": [
            {"id": "US-B01", "title": "Story B1"},
            {"id": "US-B02", "title": "Story B2"},
        ]
    }
    (epic_stories_dir / "260327XX_no_tickets.yml").write_text(yaml.dump(stories_content))

    # Monkeypatch get_epic_stories_path to resolve within test tmp_path
    import agenticcli.commands.stories as _stories_mod
    monkeypatch.setattr(_stories_mod, "get_epic_stories_path",
                        lambda name: epic_stories_dir / f"{name}.yml")

    yield {
        "repo": repo,
        "db_path": db_path,
        "epic_folder": epic_folder,
        "epic_folder_name": "260327XX_no_tickets",
    }

    repo.close()


# ---------------------------------------------------------------------------
# Tests for cmd_audit
# ---------------------------------------------------------------------------

class TestStoriesAudit:
    """Test agentic stories audit subcommand — bidirectional gap detection."""

    def test_bidirectional_gap_detection(self, audit_epic):
        """Epic with 1 unlinked ticket + 1 orphan story → both reported."""
        from agenticcli.commands.stories import cmd_audit

        args = SimpleNamespace(
            epic=str(audit_epic["epic_folder"]),
        )

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                with patch("agenticcli.commands.epic.find_epic_folder",
                           return_value=audit_epic["epic_folder"]):
                    cmd_audit(args)

                mock_json.assert_called_once()
                result = mock_json.call_args[0][0]

        # 1 unlinked ticket (T3)
        assert len(result["unlinked_tickets"]) == 1
        assert result["unlinked_tickets"][0]["ticket_id"] == "T3"

        # 1 orphan story (US-003)
        assert len(result["orphan_stories"]) == 1
        assert result["orphan_stories"][0]["story_id"] == "US-003"

        # Summary
        assert result["summary"]["unlinked_ticket_count"] == 1
        assert result["summary"]["orphan_story_count"] == 1
        assert result["summary"]["fully_covered"] is False

    def test_json_output_schema(self, audit_epic):
        """JSON output contains required keys: epic, unlinked_tickets, orphan_stories, summary."""
        from agenticcli.commands.stories import cmd_audit

        args = SimpleNamespace(epic=str(audit_epic["epic_folder"]))

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                with patch("agenticcli.commands.epic.find_epic_folder",
                           return_value=audit_epic["epic_folder"]):
                    cmd_audit(args)

                result = mock_json.call_args[0][0]

        # Top-level keys
        assert "epic" in result
        assert "unlinked_tickets" in result
        assert "orphan_stories" in result
        assert "summary" in result

        # Summary keys
        summary = result["summary"]
        assert "total_tickets" in summary
        assert "unlinked_ticket_count" in summary
        assert "total_stories" in summary
        assert "orphan_story_count" in summary
        assert "stories_yml_missing" in summary
        assert "fully_covered" in summary

        # Types
        assert isinstance(result["unlinked_tickets"], list)
        assert isinstance(result["orphan_stories"], list)
        assert isinstance(summary["total_tickets"], int)
        assert isinstance(summary["fully_covered"], bool)

    def test_no_stories_yml_all_unlinked(self, no_stories_epic):
        """Missing stories.yml → all tickets unlinked, no orphan stories."""
        from agenticcli.commands.stories import cmd_audit

        args = SimpleNamespace(epic=str(no_stories_epic["epic_folder"]))

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                with patch("agenticcli.commands.epic.find_epic_folder",
                           return_value=no_stories_epic["epic_folder"]):
                    cmd_audit(args)

                result = mock_json.call_args[0][0]

        # Both tickets are unlinked (no story_ids)
        assert len(result["unlinked_tickets"]) == 2
        unlinked_ids = {t["ticket_id"] for t in result["unlinked_tickets"]}
        assert "T1" in unlinked_ids
        assert "T2" in unlinked_ids

        # No orphan stories (there are no stories)
        assert len(result["orphan_stories"]) == 0
        assert result["summary"]["stories_yml_missing"] is True

    def test_full_coverage_zero_gaps(self, full_coverage_epic):
        """Full coverage → zero unlinked tickets, zero orphan stories, fully_covered=True."""
        from agenticcli.commands.stories import cmd_audit

        args = SimpleNamespace(epic=str(full_coverage_epic["epic_folder"]))

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                with patch("agenticcli.commands.epic.find_epic_folder",
                           return_value=full_coverage_epic["epic_folder"]):
                    cmd_audit(args)

                result = mock_json.call_args[0][0]

        assert len(result["unlinked_tickets"]) == 0
        assert len(result["orphan_stories"]) == 0
        assert result["summary"]["fully_covered"] is True
        assert result["summary"]["total_tickets"] == 2
        assert result["summary"]["total_stories"] == 2

    def test_no_tickets_all_orphans(self, no_tickets_epic):
        """Epic with no tickets → all stories are orphans."""
        from agenticcli.commands.stories import cmd_audit

        args = SimpleNamespace(epic=str(no_tickets_epic["epic_folder"]))

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                with patch("agenticcli.commands.epic.find_epic_folder",
                           return_value=no_tickets_epic["epic_folder"]):
                    cmd_audit(args)

                result = mock_json.call_args[0][0]

        # No unlinked tickets (there are no tickets)
        assert len(result["unlinked_tickets"]) == 0

        # Both stories are orphans
        assert len(result["orphan_stories"]) == 2
        orphan_ids = {s["story_id"] for s in result["orphan_stories"]}
        assert "US-B01" in orphan_ids
        assert "US-B02" in orphan_ids

        assert result["summary"]["total_tickets"] == 0
        assert result["summary"]["orphan_story_count"] == 2

    def test_missing_epic_flag_exits(self):
        """Calling audit without --epic exits with error."""
        from agenticcli.commands.stories import cmd_audit

        args = SimpleNamespace(epic=None, plan=None)

        with pytest.raises(SystemExit) as exc_info:
            cmd_audit(args)
        assert exc_info.value.code == 1
