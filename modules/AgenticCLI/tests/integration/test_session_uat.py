# story: US-PLN-048
"""Integration test for the decoupled UAT workflow (US-PLN-048).

Verifies `agentic orchestrate session uat --story <id>` invokes UatRunner,
that UatRunner reads the story's uat_plan block, spawns test-uat per story
(via an injected transport in tests), and verifies the agent recorded its
own ``last_uat_commit`` via the CLI. The agent is the sole writer; the
runner only polls StoryService before/after the spawn to detect whether
the stamp changed.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.integration]


def _fake_story(sid="US-FAKE-001", uat_plan=None):
    story = SimpleNamespace(
        id=sid, title=f"Title {sid}",
        source_file="/tmp/fake.yml",
        last_uat_commit="",
    )
    story._uat_plan = uat_plan or {
        "persona": "agent-blind-test",
        "starting_state": "noop",
        "journey": [{"step": 1, "action": "check", "observe": ["ok"]}],
        "success_signals": ["everything works"],
    }
    return story


@pytest.mark.story("US-PLN-048")
class TestUatRunner:
    """UatRunner verifies the agent's self-recorded last_uat_commit stamp."""

    def test_runner_marks_pass_when_agent_stamps_commit(self):
        from agenticcli.workflows.uat import UatRunner

        story = _fake_story("US-FAKE-001")

        def fake_transport(*, story, prompt):
            assert "US-FAKE-001" in prompt
            assert "uat_plan:" in prompt
            # Prompt must instruct the agent to stamp its own pass.
            assert "agentic stories update" in prompt
            assert "--kind uat" in prompt
            return True  # pretend the agent passed AND stamped the commit

        runner = UatRunner(
            story_id="US-FAKE-001",
            transport=fake_transport,
        )

        # Simulate the agent successfully writing last_uat_commit: the
        # first _read returns "" (pre), the second returns a new hash (post).
        commit_sequence = iter(["", "abcdef1234567"])

        with (
            patch.object(
                UatRunner, "resolve_stories", return_value=[story],
            ),
            patch.object(
                UatRunner, "extract_uat_plan", return_value=story._uat_plan,
            ),
            patch.object(
                UatRunner, "_read_last_uat_commit",
                side_effect=lambda _id: next(commit_sequence),
            ),
        ):
            ok = runner.run()

        assert ok is True
        assert "US-FAKE-001" in runner.state["passed"]
        assert runner.state["commits"]["US-FAKE-001"] == "abcdef1234567"

    def test_runner_marks_fail_when_agent_forgot_to_stamp(self):
        """Agent exits cleanly but did not update last_uat_commit."""
        from agenticcli.workflows.uat import UatRunner

        story = _fake_story("US-FAKE-004")

        runner = UatRunner(
            story_id="US-FAKE-004",
            transport=lambda **k: True,  # agent "succeeded" per its own exit
        )

        with (
            patch.object(
                UatRunner, "resolve_stories", return_value=[story],
            ),
            patch.object(
                UatRunner, "extract_uat_plan", return_value=story._uat_plan,
            ),
            # Both reads return the same value → no stamp happened.
            patch.object(
                UatRunner, "_read_last_uat_commit", return_value="",
            ),
        ):
            ok = runner.run()

        assert ok is False
        assert "US-FAKE-004" in runner.state["failed"]
        assert any(
            "forgot to run" in err or "was not updated" in err
            for err in runner.state["errors"]
        ), f"expected 'forgot to run' error, got: {runner.state['errors']}"

    def test_runner_skips_stories_without_uat_plan(self):
        from agenticcli.workflows.uat import UatRunner

        story = _fake_story("US-FAKE-002")
        runner = UatRunner(story_id="US-FAKE-002", transport=lambda **k: True)

        with (
            patch.object(
                UatRunner, "resolve_stories", return_value=[story],
            ),
            patch.object(
                UatRunner, "extract_uat_plan", return_value=None,
            ),
            patch.object(
                UatRunner, "_read_last_uat_commit", return_value="",
            ),
        ):
            ok = runner.run()

        assert ok is True  # skip is not a failure
        assert "US-FAKE-002" in runner.state["skipped"]

    def test_runner_records_failure_when_agent_exit_fails(self):
        from agenticcli.workflows.uat import UatRunner

        story = _fake_story("US-FAKE-003")
        runner = UatRunner(
            story_id="US-FAKE-003",
            transport=lambda **k: False,  # agent reports failure
        )

        with (
            patch.object(
                UatRunner, "resolve_stories", return_value=[story],
            ),
            patch.object(
                UatRunner, "extract_uat_plan", return_value=story._uat_plan,
            ),
            patch.object(
                UatRunner, "_read_last_uat_commit", return_value="",
            ),
        ):
            ok = runner.run()

        assert ok is False
        assert "US-FAKE-003" in runner.state["failed"]

    def test_runner_requires_a_scope(self):
        from agenticcli.workflows.uat import UatRunner

        runner = UatRunner()  # no story_id, no epic, no stale
        ok = runner.run()
        assert ok is False
        assert runner.state["errors"], "expected a 'scope required' error"
