# story: US-PLN-047
"""Integration test for ExecutionRunner auto-record of last_pass_commit.

Verifies that when a phase completes successfully, the executor hook
resolves story IDs from tickets (primary) or pytest markers (fallback)
and calls record_story_pass() to update the YAML in-process.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.story("US-PLN-047")
class TestExecutorPassHashHook:
    """Phase-completion hook must record last_pass_commit per story."""

    def test_hook_reads_story_ids_from_tickets(self):
        """Primary path: story_ids come from ticket.story_ids."""
        from agenticcli.workflows.orchestration import ExecutionRunner

        runner = ExecutionRunner(workflow=MagicMock())

        fake_repo = MagicMock()
        fake_repo.list_tickets.return_value = [
            SimpleNamespace(
                id="T1", phase_name="Build",
                story_ids=["US-XXX-001", "US-XXX-002"],
                status="completed",
            ),
            SimpleNamespace(
                id="T2", phase_name="Test",  # different phase — must be ignored
                story_ids=["US-YYY-999"],
                status="completed",
            ),
        ]

        with patch(
            "agenticcli.commands.stories.record_story_pass"
        ) as mock_record:
            mock_record.return_value = {
                "updated": ["US-XXX-001", "US-XXX-002"],
                "missing": [],
                "commit": "abc1234",
            }
            runner._record_story_pass_for_phase(fake_repo, "epic", "Build")

        mock_record.assert_called_once()
        args, kwargs = mock_record.call_args
        # Call is positional: record_story_pass(sorted_ids)
        assert args[0] == ["US-XXX-001", "US-XXX-002"]
        assert kwargs.get("commit_kind") == "test"

    def test_hook_falls_back_to_pytest_markers(self):
        """Fallback: when no ticket story_ids, scan pytest markers."""
        from agenticcli.workflows.orchestration import ExecutionRunner

        runner = ExecutionRunner(workflow=MagicMock())
        fake_repo = MagicMock()
        fake_repo.list_tickets.return_value = [
            SimpleNamespace(
                id="T1", phase_name="Build",
                story_ids=[],
                status="completed",
            ),
        ]

        with (
            patch(
                "agenticcli.commands.stories._scan_pytest_story_markers",
                return_value={"US-ZZZ-001"},
            ),
            patch(
                "agenticcli.commands.stories.record_story_pass"
            ) as mock_record,
        ):
            mock_record.return_value = {
                "updated": ["US-ZZZ-001"],
                "missing": [],
                "commit": "def5678",
            }
            runner._record_story_pass_for_phase(fake_repo, "epic", "Build")

        mock_record.assert_called_once()
        args, _ = mock_record.call_args
        assert args[0] == ["US-ZZZ-001"]

    def test_hook_swallows_errors(self):
        """A broken hook must never block phase completion."""
        from agenticcli.workflows.orchestration import ExecutionRunner

        runner = ExecutionRunner(workflow=MagicMock())
        fake_repo = MagicMock()
        fake_repo.list_tickets.side_effect = RuntimeError("boom")

        # Must not raise
        runner._record_story_pass_for_phase(fake_repo, "epic", "Build")

    def test_hook_noop_when_no_stories_resolved(self):
        """No story_ids and no pytest markers → no record_story_pass call."""
        from agenticcli.workflows.orchestration import ExecutionRunner

        runner = ExecutionRunner(workflow=MagicMock())
        fake_repo = MagicMock()
        fake_repo.list_tickets.return_value = [
            SimpleNamespace(
                id="T1", phase_name="Build",
                story_ids=[],
                status="completed",
            ),
        ]

        with (
            patch(
                "agenticcli.commands.stories._scan_pytest_story_markers",
                return_value=set(),
            ),
            patch(
                "agenticcli.commands.stories.record_story_pass"
            ) as mock_record,
        ):
            runner._record_story_pass_for_phase(fake_repo, "epic", "Build")

        mock_record.assert_not_called()
