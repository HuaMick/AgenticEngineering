"""Tests for Story lifecycle field, transitions, and update_lifecycle()."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

pytestmark = pytest.mark.story("US-STR-020")

from agenticguidance.services.story import (
    ANCHOR_UNREACHABLE,
    LIFECYCLE_STATES,
    LIFECYCLE_TRANSITIONS,
    Story,
    StoryService,
)


class TestLifecycleConstants:
    def test_all_states_defined(self):
        assert LIFECYCLE_STATES == (
            "proposal", "under-construction", "implemented", "deprecated", "archived"
        )

    def test_all_states_have_transitions(self):
        for state in LIFECYCLE_STATES:
            assert state in LIFECYCLE_TRANSITIONS

    def test_archived_has_no_transitions(self):
        assert LIFECYCLE_TRANSITIONS["archived"] == []

    def test_transitions_are_forward_only(self):
        """Each state can only transition to the next state in the chain."""
        for i, state in enumerate(LIFECYCLE_STATES[:-1]):
            targets = LIFECYCLE_TRANSITIONS[state]
            assert len(targets) == 1
            assert targets[0] == LIFECYCLE_STATES[i + 1]


class TestStoryLifecycleField:
    def test_default_lifecycle(self):
        s = Story(id="US-TEST-001", title="Test")
        assert s.lifecycle == "implemented"

    def test_explicit_lifecycle(self):
        s = Story(id="US-TEST-001", title="Test", lifecycle="proposal")
        assert s.lifecycle == "proposal"

    def test_each_lifecycle_value(self):
        for state in LIFECYCLE_STATES:
            s = Story(id="US-TEST-001", title="Test", lifecycle=state)
            assert s.lifecycle == state


class TestCanTransitionTo:
    def test_proposal_to_under_construction(self):
        s = Story(id="US-TEST-001", title="Test", lifecycle="proposal")
        assert s.can_transition_to("under-construction") is True

    def test_proposal_cannot_skip_to_implemented(self):
        s = Story(id="US-TEST-001", title="Test", lifecycle="proposal")
        assert s.can_transition_to("implemented") is False

    def test_under_construction_to_implemented(self):
        s = Story(id="US-TEST-001", title="Test", lifecycle="under-construction")
        assert s.can_transition_to("implemented") is True

    def test_implemented_to_deprecated(self):
        s = Story(id="US-TEST-001", title="Test", lifecycle="implemented")
        assert s.can_transition_to("deprecated") is True

    def test_deprecated_to_archived(self):
        s = Story(id="US-TEST-001", title="Test", lifecycle="deprecated")
        assert s.can_transition_to("archived") is True

    def test_archived_cannot_transition(self):
        s = Story(id="US-TEST-001", title="Test", lifecycle="archived")
        for state in LIFECYCLE_STATES:
            assert s.can_transition_to(state) is False

    def test_cannot_go_backwards(self):
        s = Story(id="US-TEST-001", title="Test", lifecycle="implemented")
        assert s.can_transition_to("proposal") is False
        assert s.can_transition_to("under-construction") is False

    def test_invalid_current_lifecycle(self):
        s = Story(id="US-TEST-001", title="Test", lifecycle="bogus")
        assert s.can_transition_to("proposal") is False


class TestParsing:
    def test_lifecycle_parsed_from_yaml(self, tmp_path):
        story_file = tmp_path / "stories.yml"
        story_file.write_text(yaml.dump({
            "stories": [{
                "id": "US-TEST-001",
                "title": "Test Story",
                "lifecycle": "proposal",
            }]
        }))
        svc = StoryService(tmp_path)
        stories = svc.load_all()
        assert len(stories) == 1
        assert stories[0].lifecycle == "proposal"

    def test_missing_lifecycle_defaults_to_implemented(self, tmp_path):
        story_file = tmp_path / "stories.yml"
        story_file.write_text(yaml.dump({
            "stories": [{
                "id": "US-TEST-001",
                "title": "Test Story",
            }]
        }))
        svc = StoryService(tmp_path)
        stories = svc.load_all()
        assert len(stories) == 1
        assert stories[0].lifecycle == "implemented"


class TestUpdateLifecycle:
    def _make_service(self, tmp_path, lifecycle="proposal"):
        story_file = tmp_path / "stories.yml"
        story_file.write_text(yaml.dump({
            "stories": [{
                "id": "US-TEST-001",
                "title": "Test Story",
                "lifecycle": lifecycle,
            }]
        }))
        return StoryService(tmp_path)

    def test_valid_transition(self, tmp_path):
        svc = self._make_service(tmp_path, "proposal")
        result = svc.update_lifecycle("US-TEST-001", "under-construction")
        assert result is True
        # Re-read to verify persistence
        svc2 = StoryService(tmp_path)
        story = svc2.get_by_id("US-TEST-001")
        assert story.lifecycle == "under-construction"

    def test_invalid_transition_rejected(self, tmp_path):
        svc = self._make_service(tmp_path, "proposal")
        result = svc.update_lifecycle("US-TEST-001", "implemented")
        assert result is False

    def test_invalid_target_state(self, tmp_path):
        svc = self._make_service(tmp_path, "proposal")
        result = svc.update_lifecycle("US-TEST-001", "bogus")
        assert result is False

    def test_nonexistent_story(self, tmp_path):
        svc = self._make_service(tmp_path)
        result = svc.update_lifecycle("US-NOPE-999", "under-construction")
        assert result is False

    def test_full_lifecycle(self, tmp_path):
        svc = self._make_service(tmp_path, "proposal")
        transitions = [
            "under-construction",
            "implemented",
            "deprecated",
            "archived",
        ]
        for target in transitions:
            result = svc.update_lifecycle("US-TEST-001", target)
            assert result is True, f"Failed transition to {target}"
        story = svc.get_by_id("US-TEST-001")
        assert story.lifecycle == "archived"


# ---------------------------------------------------------------------------
# US-STR-020: compute_story_status — lifecycle-override and anchor fallback
# ---------------------------------------------------------------------------

class TestArchivedOverridesTestState:
    """Archived/deprecated lifecycle overrides any test state in status computation."""

    def test_archived_lifecycle_with_failing_test(self):
        """lifecycle=archived + test_status=fail → 'archived', not 'unhealthy'."""
        svc = StoryService(userstories_dir=None)
        story = Story(
            id="US-TEST-001",
            title="Archived Story",
            lifecycle="archived",
            test_status="fail",
        )
        status = svc.compute_story_status(story)
        assert status == "archived"

    def test_deprecated_lifecycle_with_failing_test(self):
        """lifecycle=deprecated + test_status=fail → 'archived', not 'unhealthy'."""
        svc = StoryService(userstories_dir=None)
        story = Story(
            id="US-TEST-001",
            title="Deprecated Story",
            lifecycle="deprecated",
            test_status="fail",
        )
        status = svc.compute_story_status(story)
        assert status == "archived"

    def test_archived_lifecycle_with_passing_test(self):
        """lifecycle=archived + test_status=pass → still 'archived'."""
        svc = StoryService(userstories_dir=None)
        story = Story(
            id="US-TEST-001",
            title="Archived Story",
            lifecycle="archived",
            test_status="pass",
        )
        status = svc.compute_story_status(story)
        assert status == "archived"

    def test_implemented_lifecycle_with_failing_test_is_unhealthy(self):
        """Sanity check: lifecycle=implemented + test_status=fail → 'unhealthy'."""
        svc = StoryService(userstories_dir=None)
        story = Story(
            id="US-TEST-001",
            title="Implemented Story",
            lifecycle="implemented",
            test_status="fail",
        )
        status = svc.compute_story_status(story)
        assert status == "broken"


class TestTreeHashFallback:
    """When last_pass_commit is unreachable, tree_hash provides a fallback."""

    def test_unreachable_commit_with_matching_tree_hash_is_not_stale(self, tmp_path):
        """ANCHOR_UNREACHABLE + _tree_hash_matches=True → story is NOT stale."""
        svc = StoryService(userstories_dir=None)
        story = Story(
            id="US-TEST-001",
            title="Story with squash-merged commit",
            test_status="pass",
            last_pass_commit="dead0000deadbeef",
            last_pass_tree_hash="abc123",
            related_files=["modules/foo/bar.py"],
        )
        _git_module = "agenticguidance.services.story._git_changed_files_since"
        _hash_module = "agenticguidance.services.story._tree_hash_matches"

        with patch(_git_module, return_value=ANCHOR_UNREACHABLE):
            with patch(_hash_module, return_value=True):
                status = svc.compute_story_status(story, repo_root=tmp_path)
        # Tree hash matched → not stale → falls through to "passing"
        assert status == "passing"

    def test_unreachable_commit_with_mismatched_tree_hash_is_stale(self, tmp_path):
        """ANCHOR_UNREACHABLE + _tree_hash_matches=False → story IS stale."""
        svc = StoryService(userstories_dir=None)
        story = Story(
            id="US-TEST-001",
            title="Story with moved tree",
            test_status="pass",
            last_pass_commit="dead0000deadbeef",
            last_pass_tree_hash="old_hash_xyz",
            related_files=["modules/foo/bar.py"],
        )
        _git_module = "agenticguidance.services.story._git_changed_files_since"
        _hash_module = "agenticguidance.services.story._tree_hash_matches"

        with patch(_git_module, return_value=ANCHOR_UNREACHABLE):
            with patch(_hash_module, return_value=False):
                status = svc.compute_story_status(story, repo_root=tmp_path)
        assert status == "stale"


class TestAnchorUnreachableReason:
    """compute_story_flags returns stale_reason=anchor_unreachable when appropriate."""

    def test_flags_anchor_unreachable_when_commit_gone_and_hash_mismatch(self, tmp_path):
        """ANCHOR_UNREACHABLE + tree_hash mismatch → stale_reason='anchor_unreachable'."""
        svc = StoryService(userstories_dir=None)
        story = Story(
            id="US-TEST-001",
            title="Anchor-unreachable story",
            test_status="pass",
            last_pass_commit="dead0000deadbeef",
            last_pass_tree_hash="mismatch_hash",
            related_files=["modules/foo/bar.py"],
        )
        _git_module = "agenticguidance.services.story._git_changed_files_since"
        _hash_module = "agenticguidance.services.story._tree_hash_matches"

        with patch(_git_module, return_value=ANCHOR_UNREACHABLE):
            with patch(_hash_module, return_value=False):
                flags = svc.compute_story_flags(story, repo_root=tmp_path)

        assert flags["stale_reason"] == "anchor_unreachable"

    def test_status_is_stale_when_anchor_unreachable_and_hash_none(self, tmp_path):
        """ANCHOR_UNREACHABLE + _tree_hash_matches=None → stale, anchor_unreachable reason."""
        svc = StoryService(userstories_dir=None)
        story = Story(
            id="US-TEST-001",
            title="Anchor-unreachable story no hash",
            test_status="pass",
            last_pass_commit="dead0000deadbeef",
            last_pass_tree_hash="",  # empty — _tree_hash_matches returns None
            related_files=["modules/foo/bar.py"],
        )
        _git_module = "agenticguidance.services.story._git_changed_files_since"

        with patch(_git_module, return_value=ANCHOR_UNREACHABLE):
            status = svc.compute_story_status(story, repo_root=tmp_path)
            flags = svc.compute_story_flags(story, repo_root=tmp_path)

        assert status == "stale"
        assert flags["stale_reason"] == "anchor_unreachable"

    def test_anchor_unreachable_not_triggered_when_commit_reachable(self, tmp_path):
        """When commit IS reachable and no files changed, stale_reason is None."""
        svc = StoryService(userstories_dir=None)
        story = Story(
            id="US-TEST-001",
            title="Normal passing story",
            test_status="pass",
            last_pass_commit="abc1234",
            related_files=["modules/foo/bar.py"],
        )
        _git_module = "agenticguidance.services.story._git_changed_files_since"

        # Commit reachable, no files changed
        with patch(_git_module, return_value=set()):
            flags = svc.compute_story_flags(story, repo_root=tmp_path)

        assert flags["stale_reason"] is None
