"""Exhaustive coverage of the 7-state compute_story_status enum.

Tests every canonical status value for US-STR-020, including:
- Happy-path trigger conditions
- "Doesn't fire unless precondition" guard tests
- Orthogonal flaky flag behaviour

All tests use tmp_path (no real git activity needed; git helpers are mocked
where staleness/tree-hash checks are required).
"""

from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.story("US-STR-020")

from agenticguidance.services.story import (
    ANCHOR_UNREACHABLE,
    STORY_STATUS_SORT_ORDER,
    Story,
    StoryService,
)

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

_GIT_CHANGED = "agenticguidance.services.story._git_changed_files_since"
_TREE_HASH = "agenticguidance.services.story._tree_hash_matches"


def _svc() -> StoryService:
    """Return a StoryService with no userstories directory (pure in-memory)."""
    return StoryService(userstories_dir=None)


def _passing_story(extra: dict | None = None) -> Story:
    """Minimal passing story with a last_pass_commit set."""
    kwargs = dict(
        id="US-TEST-001",
        title="Passing story",
        test_status="pass",
        last_pass_commit="abc1234",
        related_files=["modules/foo/bar.py"],
    )
    kwargs.update(extra or {})
    return Story(**kwargs)


# ---------------------------------------------------------------------------
# Sort order sanity
# ---------------------------------------------------------------------------

class TestSortOrderConstants:
    """STORY_STATUS_SORT_ORDER must match the canonical triage priority."""

    def test_all_seven_values_present(self):
        expected = {"unhealthy", "stale", "never-passed", "no-test", "passing", "uat-verified", "archived"}
        assert set(STORY_STATUS_SORT_ORDER.keys()) == expected

    def test_unhealthy_is_highest_priority(self):
        assert STORY_STATUS_SORT_ORDER["unhealthy"] < STORY_STATUS_SORT_ORDER["stale"]

    def test_stale_before_never_passed(self):
        assert STORY_STATUS_SORT_ORDER["stale"] < STORY_STATUS_SORT_ORDER["never-passed"]

    def test_never_passed_before_no_test(self):
        assert STORY_STATUS_SORT_ORDER["never-passed"] < STORY_STATUS_SORT_ORDER["no-test"]

    def test_no_test_before_passing(self):
        assert STORY_STATUS_SORT_ORDER["no-test"] < STORY_STATUS_SORT_ORDER["passing"]

    def test_passing_before_uat_verified(self):
        assert STORY_STATUS_SORT_ORDER["passing"] < STORY_STATUS_SORT_ORDER["uat-verified"]

    def test_uat_verified_before_archived(self):
        assert STORY_STATUS_SORT_ORDER["uat-verified"] < STORY_STATUS_SORT_ORDER["archived"]


# ---------------------------------------------------------------------------
# State: archived
# ---------------------------------------------------------------------------

class TestStatusArchived:
    """lifecycle ∈ {archived, deprecated} → 'archived', overriding all else."""

    def test_archived_lifecycle_returns_archived(self):
        story = Story(id="US-TEST-001", title="T", lifecycle="archived", test_status="pass")
        assert _svc().compute_story_status(story) == "archived"

    def test_deprecated_lifecycle_returns_archived(self):
        story = Story(id="US-TEST-001", title="T", lifecycle="deprecated", test_status="pass")
        assert _svc().compute_story_status(story) == "archived"

    def test_archived_even_with_passing_test(self):
        story = Story(
            id="US-TEST-001", title="T", lifecycle="archived",
            test_status="pass", last_pass_commit="abc1234",
        )
        assert _svc().compute_story_status(story) == "archived"

    def test_implemented_does_not_return_archived(self):
        story = Story(id="US-TEST-001", title="T", lifecycle="implemented", test_status="untested")
        status = _svc().compute_story_status(story)
        assert status != "archived"


# ---------------------------------------------------------------------------
# State: unhealthy
# ---------------------------------------------------------------------------

class TestStatusUnhealthy:
    """test_status ∈ {fail, regression} → 'unhealthy'."""

    def test_fail_returns_unhealthy(self):
        story = Story(id="US-TEST-001", title="T", test_status="fail")
        assert _svc().compute_story_status(story) == "unhealthy"

    def test_regression_returns_unhealthy(self):
        story = Story(id="US-TEST-001", title="T", test_status="regression")
        assert _svc().compute_story_status(story) == "unhealthy"

    def test_fail_case_insensitive(self):
        story = Story(id="US-TEST-001", title="T", test_status="FAIL")
        assert _svc().compute_story_status(story) == "unhealthy"

    def test_regression_case_insensitive(self):
        story = Story(id="US-TEST-001", title="T", test_status="Regression")
        assert _svc().compute_story_status(story) == "unhealthy"

    def test_passing_does_not_return_unhealthy(self):
        story = _passing_story()
        with patch(_GIT_CHANGED, return_value=set()):
            status = _svc().compute_story_status(story, repo_root=Path("/fake"))
        assert status != "unhealthy"


# ---------------------------------------------------------------------------
# State: never-passed
# ---------------------------------------------------------------------------

class TestStatusNeverPassed:
    """test_status not pass + id in story_markers → 'never-passed'."""

    def test_untested_with_marker_returns_never_passed(self):
        story = Story(id="US-TEST-001", title="T", test_status="untested")
        markers = {"US-TEST-001"}
        status = _svc().compute_story_status(story, story_markers=markers)
        assert status == "never-passed"

    def test_empty_test_status_with_marker_returns_never_passed(self):
        story = Story(id="US-TEST-001", title="T", test_status="")
        markers = {"US-TEST-001"}
        status = _svc().compute_story_status(story, story_markers=markers)
        assert status == "never-passed"

    def test_never_passed_not_triggered_without_marker(self):
        """Without story_markers, untested story returns no-test, not never-passed."""
        story = Story(id="US-TEST-001", title="T", test_status="untested")
        status = _svc().compute_story_status(story, story_markers={"US-DIFFERENT-001"})
        assert status == "no-test"

    def test_never_passed_not_triggered_when_id_absent_from_markers(self):
        """story id not in markers → no-test, even when markers param is provided."""
        story = Story(id="US-TEST-001", title="T", test_status="untested")
        status = _svc().compute_story_status(story, story_markers={"US-OTHER-999"})
        assert status == "no-test"


# ---------------------------------------------------------------------------
# State: no-test
# ---------------------------------------------------------------------------

class TestStatusNoTest:
    """test_status not pass + id NOT in story_markers (or markers is None) → 'no-test'."""

    def test_untested_no_markers_returns_no_test(self):
        story = Story(id="US-TEST-001", title="T", test_status="untested")
        assert _svc().compute_story_status(story) == "no-test"

    def test_empty_test_status_no_markers_returns_no_test(self):
        story = Story(id="US-TEST-001", title="T", test_status="")
        assert _svc().compute_story_status(story) == "no-test"

    def test_no_test_not_returned_when_test_status_pass(self):
        story = _passing_story()
        with patch(_GIT_CHANGED, return_value=set()):
            status = _svc().compute_story_status(story, repo_root=Path("/fake"))
        assert status != "no-test"


# ---------------------------------------------------------------------------
# State: stale
# ---------------------------------------------------------------------------

class TestStatusStale:
    """test_status=pass + related_file changed since last_pass_commit → 'stale'."""

    def test_related_file_changed_returns_stale(self, tmp_path):
        story = _passing_story()
        with patch(_GIT_CHANGED, return_value={"modules/foo/bar.py"}):
            status = _svc().compute_story_status(story, repo_root=tmp_path)
        assert status == "stale"

    def test_no_change_does_not_return_stale(self, tmp_path):
        story = _passing_story()
        with patch(_GIT_CHANGED, return_value=set()):
            status = _svc().compute_story_status(story, repo_root=tmp_path)
        assert status != "stale"

    def test_stale_not_returned_when_test_status_fail(self, tmp_path):
        """Unhealthy takes priority over stale."""
        story = _passing_story({"test_status": "fail"})
        with patch(_GIT_CHANGED, return_value={"modules/foo/bar.py"}):
            status = _svc().compute_story_status(story, repo_root=tmp_path)
        assert status == "unhealthy"

    def test_stale_not_returned_when_archived(self, tmp_path):
        """Archived lifecycle overrides stale."""
        story = _passing_story({"lifecycle": "archived"})
        with patch(_GIT_CHANGED, return_value={"modules/foo/bar.py"}):
            status = _svc().compute_story_status(story, repo_root=tmp_path)
        assert status == "archived"

    def test_global_watch_change_also_triggers_stale(self, tmp_path):
        story = _passing_story({"related_files": []})
        global_watch = ["pyproject.toml"]
        with patch(_GIT_CHANGED, return_value={"pyproject.toml"}):
            status = _svc().compute_story_status(
                story, repo_root=tmp_path, global_watch=global_watch
            )
        assert status == "stale"


# ---------------------------------------------------------------------------
# State: uat-verified
# ---------------------------------------------------------------------------

class TestStatusUatVerified:
    """test_status=pass + last_uat_commit == last_pass_commit + no drift → 'uat-verified'."""

    def test_uat_verified_when_commits_equal(self, tmp_path):
        story = _passing_story({
            "last_uat_commit": "abc1234",  # equals last_pass_commit
        })
        with patch(_GIT_CHANGED, return_value=set()):
            status = _svc().compute_story_status(story, repo_root=tmp_path)
        assert status == "uat-verified"

    def test_uat_not_verified_when_commits_differ(self, tmp_path):
        story = _passing_story({
            "last_uat_commit": "different_commit",
        })
        with patch(_GIT_CHANGED, return_value=set()):
            status = _svc().compute_story_status(story, repo_root=tmp_path)
        # When commits differ, conservatively returns "passing"
        assert status == "passing"

    def test_uat_verified_not_returned_when_stale(self, tmp_path):
        """Staleness beats uat-verified."""
        story = _passing_story({
            "last_uat_commit": "abc1234",  # equals last_pass_commit
        })
        with patch(_GIT_CHANGED, return_value={"modules/foo/bar.py"}):
            status = _svc().compute_story_status(story, repo_root=tmp_path)
        assert status == "stale"

    def test_uat_not_returned_when_no_uat_commit(self, tmp_path):
        """No last_uat_commit → 'passing', not 'uat-verified'."""
        story = _passing_story({"last_uat_commit": ""})
        with patch(_GIT_CHANGED, return_value=set()):
            status = _svc().compute_story_status(story, repo_root=tmp_path)
        assert status == "passing"


# ---------------------------------------------------------------------------
# State: passing
# ---------------------------------------------------------------------------

class TestStatusPassing:
    """test_status=pass + no drift + no uat → 'passing'."""

    def test_passing_when_no_drift_no_uat(self, tmp_path):
        story = _passing_story()
        with patch(_GIT_CHANGED, return_value=set()):
            status = _svc().compute_story_status(story, repo_root=tmp_path)
        assert status == "passing"

    def test_passing_without_related_files(self):
        """Story with test_status=pass and no related_files → 'passing' (no git check)."""
        story = Story(
            id="US-TEST-001", title="T",
            test_status="pass", last_pass_commit="abc1234",
            related_files=[],
        )
        status = _svc().compute_story_status(story)
        assert status == "passing"

    def test_passing_not_returned_when_unhealthy(self):
        story = Story(id="US-TEST-001", title="T", test_status="fail")
        assert _svc().compute_story_status(story) != "passing"

    def test_passing_case_insensitive(self, tmp_path):
        """test_status='passing' (as in DB) also counts."""
        story = _passing_story({"test_status": "passing"})
        with patch(_GIT_CHANGED, return_value=set()):
            status = _svc().compute_story_status(story, repo_root=tmp_path)
        # Should be passing or uat-verified (not stale/unhealthy)
        assert status in ("passing", "uat-verified")


# ---------------------------------------------------------------------------
# Flaky flags — orthogonal to status
# ---------------------------------------------------------------------------

class TestFlakyFlags:
    """Flaky flag is orthogonal: doesn't change status, driven by Story.flaky or flaky_ids."""

    def test_flaky_field_on_story_returns_true(self, tmp_path):
        story = _passing_story({"flaky": True})
        with patch(_GIT_CHANGED, return_value=set()):
            flags = _svc().compute_story_flags(story, repo_root=tmp_path)
        assert flags["flaky"] is True

    def test_flaky_ids_param_returns_true(self, tmp_path):
        story = _passing_story({"flaky": False})
        with patch(_GIT_CHANGED, return_value=set()):
            flags = _svc().compute_story_flags(
                story, repo_root=tmp_path, flaky_ids={"US-TEST-001"}
            )
        assert flags["flaky"] is True

    def test_flaky_false_by_default(self, tmp_path):
        story = _passing_story()
        with patch(_GIT_CHANGED, return_value=set()):
            flags = _svc().compute_story_flags(story, repo_root=tmp_path)
        assert flags["flaky"] is False

    def test_flaky_story_can_still_be_passing(self, tmp_path):
        story = _passing_story({"flaky": True})
        with patch(_GIT_CHANGED, return_value=set()):
            status = _svc().compute_story_status(story, repo_root=tmp_path)
            flags = _svc().compute_story_flags(story, repo_root=tmp_path)
        assert status == "passing"
        assert flags["flaky"] is True

    def test_flaky_story_can_still_be_stale(self, tmp_path):
        story = _passing_story({"flaky": True})
        with patch(_GIT_CHANGED, return_value={"modules/foo/bar.py"}):
            status = _svc().compute_story_status(story, repo_root=tmp_path)
            flags = _svc().compute_story_flags(story, repo_root=tmp_path)
        assert status == "stale"
        assert flags["flaky"] is True

    def test_flaky_story_can_still_be_unhealthy(self):
        story = Story(id="US-TEST-001", title="T", test_status="fail", flaky=True)
        status = _svc().compute_story_status(story)
        flags = _svc().compute_story_flags(story)
        assert status == "unhealthy"
        assert flags["flaky"] is True

    def test_flaky_flag_not_affected_by_id_not_in_flaky_ids(self, tmp_path):
        """flaky_ids provided but story ID absent → flaky=False."""
        story = _passing_story({"flaky": False})
        with patch(_GIT_CHANGED, return_value=set()):
            flags = _svc().compute_story_flags(
                story, repo_root=tmp_path, flaky_ids={"US-OTHER-999"}
            )
        assert flags["flaky"] is False
