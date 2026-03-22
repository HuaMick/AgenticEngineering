"""Tests for Story lifecycle field, transitions, and update_lifecycle()."""

import tempfile
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.story("US-STR-005")

from agenticguidance.services.story import (
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
