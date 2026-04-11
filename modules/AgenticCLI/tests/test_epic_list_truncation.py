# story: US-PLN-001
"""Integration tests verifying truncate_string is wired into CLI epic list output.

Validates the truncation clause of US-PLN-001 (Epic Lifecycle):
  - Long epic names are truncated in table output (not shown in full)
  - Short epic names display in full (no truncation)
  - JSON output preserves full untruncated name

Note on Rich table rendering:
  truncate_string(name, 50) first caps the name to 50 chars with "..." suffix.
  Rich's Table may then further truncate to fit column width, using Unicode
  ellipsis "…" (U+2026). Tests account for both truncation layers: we check
  that the FULL name is absent and that a recognizable prefix IS present.
"""

import json as json_mod
from types import SimpleNamespace

import pytest

from tests.conftest import populate_tinydb_from_yaml

pytestmark = pytest.mark.story("US-PLN-001")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Epic name deliberately longer than the 50-char truncation threshold in cmd_list
LONG_EPIC_NAME = "260411AG_uat_throwaway_test_epic_for_orchestrate_workflow_validation_extra"
assert len(LONG_EPIC_NAME) > 50, "Test epic name must exceed truncation threshold"

SHORT_EPIC_NAME = "260411AG_short_epic"
assert len(SHORT_EPIC_NAME) <= 50, "Short epic name must be within truncation threshold"

# A prefix short enough to survive both truncate_string and Rich column sizing.
# Rich table with default 80-col terminal gives ~32 chars for the Epic column.
# Use a conservative 20-char prefix that will always be visible.
LONG_NAME_VISIBLE_PREFIX = LONG_EPIC_NAME[:20]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def long_epic_repo(tmp_path, _isolate_tinydb):
    """Repo with a single long-named epic in TinyDB."""
    populate_tinydb_from_yaml(
        _isolate_tinydb,
        LONG_EPIC_NAME,
        None,  # folder-free (TinyDB only)
        {
            "name": LONG_EPIC_NAME,
            "status": "in_progress",
            "phases": [
                {
                    "name": "Build",
                    "status": "completed",
                    "agent": "build-python",
                    "tickets": [
                        {"id": "B1", "name": "Build ticket", "status": "completed"},
                    ],
                }
            ],
        },
    )
    return tmp_path


@pytest.fixture
def mixed_length_epics_repo(tmp_path, _isolate_tinydb):
    """Repo with both a long-named and short-named epic."""
    populate_tinydb_from_yaml(
        _isolate_tinydb,
        LONG_EPIC_NAME,
        None,
        {
            "name": LONG_EPIC_NAME,
            "status": "in_progress",
            "phases": [
                {
                    "name": "Build",
                    "status": "completed",
                    "agent": "build-python",
                    "tickets": [
                        {"id": "B1", "name": "Build ticket", "status": "completed"},
                    ],
                }
            ],
        },
    )
    populate_tinydb_from_yaml(
        _isolate_tinydb,
        SHORT_EPIC_NAME,
        None,
        {
            "name": SHORT_EPIC_NAME,
            "status": "in_progress",
            "phases": [
                {
                    "name": "Build",
                    "status": "planning",
                    "agent": "build-python",
                    "tickets": [
                        {"id": "S1", "name": "Short ticket", "status": "pending"},
                    ],
                }
            ],
        },
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests — Step 1: Long epic names truncated in table output
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-001")
class TestLongEpicNameTruncation:
    """Long epic names (>50 chars) should be truncated in table output."""

    def test_full_long_name_absent_from_table_output(
        self, long_epic_repo, _isolate_tinydb, capsys
    ):
        """The full untruncated long name must NOT appear in table output."""
        from agenticcli.commands.epic import cmd_list

        args = SimpleNamespace(all=True, json=False)
        try:
            cmd_list(args)
        except SystemExit:
            pass

        captured = capsys.readouterr()
        assert LONG_EPIC_NAME not in captured.out, (
            f"Full long name should be truncated in table output, but found: {LONG_EPIC_NAME}"
        )

    def test_table_output_shows_truncation_indicator(
        self, long_epic_repo, _isolate_tinydb, capsys
    ):
        """Table output should contain an ellipsis indicator (either '...' or '\u2026')."""
        from agenticcli.commands.epic import cmd_list

        args = SimpleNamespace(all=True, json=False)
        try:
            cmd_list(args)
        except SystemExit:
            pass

        captured = capsys.readouterr()
        # truncate_string uses "..." but Rich table may further truncate with "…" (U+2026)
        has_ascii_ellipsis = "..." in captured.out
        has_unicode_ellipsis = "\u2026" in captured.out
        assert has_ascii_ellipsis or has_unicode_ellipsis, (
            "Truncated name should contain an ellipsis indicator ('...' or '\u2026')"
        )

    def test_table_output_shows_beginning_of_long_name(
        self, long_epic_repo, _isolate_tinydb, capsys
    ):
        """Table output should preserve the beginning of the long name before truncation."""
        from agenticcli.commands.epic import cmd_list

        args = SimpleNamespace(all=True, json=False)
        try:
            cmd_list(args)
        except SystemExit:
            pass

        captured = capsys.readouterr()
        # A conservative prefix that survives both truncate_string and Rich column sizing
        assert LONG_NAME_VISIBLE_PREFIX in captured.out, (
            f"Table output should contain the beginning of the long name: {LONG_NAME_VISIBLE_PREFIX}"
        )


# ---------------------------------------------------------------------------
# Tests — Step 2: Short epic names display in full
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-001")
class TestShortEpicNameNoTruncation:
    """Short epic names (<=50 chars) should display in full without truncation."""

    def test_short_name_displayed_in_full(
        self, mixed_length_epics_repo, _isolate_tinydb, capsys
    ):
        """Short epic names should appear in full in table output."""
        from agenticcli.commands.epic import cmd_list

        args = SimpleNamespace(all=True, json=False)
        try:
            cmd_list(args)
        except SystemExit:
            pass

        captured = capsys.readouterr()
        assert SHORT_EPIC_NAME in captured.out, (
            f"Short epic name should appear in full: {SHORT_EPIC_NAME}"
        )

    def test_mixed_list_long_truncated_short_intact(
        self, mixed_length_epics_repo, _isolate_tinydb, capsys
    ):
        """When both long and short epics exist, only the long one is truncated."""
        from agenticcli.commands.epic import cmd_list

        args = SimpleNamespace(all=True, json=False)
        try:
            cmd_list(args)
        except SystemExit:
            pass

        captured = capsys.readouterr()
        # Short name should be fully present
        assert SHORT_EPIC_NAME in captured.out
        # Long name should NOT be fully present (it should be truncated)
        assert LONG_EPIC_NAME not in captured.out


# ---------------------------------------------------------------------------
# Tests — Step 3: JSON output preserves full name
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-001")
class TestJsonOutputPreservesFullName:
    """JSON output must contain the full untruncated epic name."""

    def test_json_output_has_full_long_name(
        self, long_epic_repo, _isolate_tinydb, capsys
    ):
        """JSON output must include the full untruncated epic folder name."""
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
        assert LONG_EPIC_NAME in names, (
            f"JSON output must contain full epic name '{LONG_EPIC_NAME}', got: {names}"
        )

    def test_json_output_no_ellipsis_in_name_field(
        self, long_epic_repo, _isolate_tinydb, capsys
    ):
        """JSON name field must NOT contain truncation artifacts like '...'."""
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
        for plan in data.get("plans", []):
            assert not plan["name"].endswith("..."), (
                f"JSON name should not be truncated: {plan['name']}"
            )
