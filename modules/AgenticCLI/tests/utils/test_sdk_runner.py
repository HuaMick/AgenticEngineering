"""Tests for ROLE_MODEL_MAP and get_model_for_role in agenticcli.utils.sdk_runner.

Covers:
- ROLE_MODEL_MAP has the expected role-to-model assignments
- get_model_for_role returns correct model for mapped roles
- get_model_for_role returns None for unmapped roles
"""

import pytest

pytestmark = pytest.mark.story("US-SES-001")


class TestRoleModelMap:
    """Tests for the ROLE_MODEL_MAP constant."""

    def test_role_model_map_has_expected_keys(self):
        """ROLE_MODEL_MAP contains all expected role-to-model assignments."""
        from agenticcli.utils.sdk_runner import ROLE_MODEL_MAP

        assert ROLE_MODEL_MAP["epic-creator"] == "claude-haiku-4-5-20251001"
        assert ROLE_MODEL_MAP["planner-orchestration"] == "claude-opus-4-6"
        assert ROLE_MODEL_MAP["planner-build"] == "claude-opus-4-6"
        assert ROLE_MODEL_MAP["planner-test"] == "claude-opus-4-6"
        assert ROLE_MODEL_MAP["build-story-writer"] == "claude-sonnet-4-6"

    def test_role_model_map_is_dict(self):
        """ROLE_MODEL_MAP is a dict with string keys and string values."""
        from agenticcli.utils.sdk_runner import ROLE_MODEL_MAP

        assert isinstance(ROLE_MODEL_MAP, dict)
        for role, model in ROLE_MODEL_MAP.items():
            assert isinstance(role, str), f"Role key {role!r} should be a string"
            assert isinstance(model, str), f"Model value {model!r} for role {role!r} should be a string"

    def test_role_model_map_nonempty(self):
        """ROLE_MODEL_MAP has at least one entry."""
        from agenticcli.utils.sdk_runner import ROLE_MODEL_MAP

        assert len(ROLE_MODEL_MAP) > 0

    def test_epic_creator_uses_haiku(self):
        """epic-creator is routed to haiku for cost-efficient scaffolding."""
        from agenticcli.utils.sdk_runner import ROLE_MODEL_MAP

        assert "haiku" in ROLE_MODEL_MAP["epic-creator"].lower()

    def test_planning_roles_use_opus(self):
        """High-judgment planning roles route to opus."""
        from agenticcli.utils.sdk_runner import ROLE_MODEL_MAP

        for role in ("planner-orchestration", "planner-build", "planner-test"):
            assert "opus" in ROLE_MODEL_MAP[role].lower(), (
                f"Expected opus model for {role!r}, got {ROLE_MODEL_MAP[role]!r}"
            )

    def test_story_writer_uses_sonnet(self):
        """build-story-writer is routed to sonnet for structured writing."""
        from agenticcli.utils.sdk_runner import ROLE_MODEL_MAP

        assert "sonnet" in ROLE_MODEL_MAP["build-story-writer"].lower()


class TestGetModelForRole:
    """Tests for get_model_for_role()."""

    def test_get_model_for_role_returns_mapped(self):
        """Returns the correct model string for roles that are mapped."""
        from agenticcli.utils.sdk_runner import get_model_for_role

        assert get_model_for_role("planner-build") == "claude-opus-4-6"
        assert get_model_for_role("epic-creator") == "claude-haiku-4-5-20251001"

    def test_get_model_for_role_returns_none_for_unmapped(self):
        """Returns None for roles not present in ROLE_MODEL_MAP."""
        from agenticcli.utils.sdk_runner import get_model_for_role

        assert get_model_for_role("build-python") is None
        assert get_model_for_role("test-builder") is None
        assert get_model_for_role("nonexistent-role") is None

    def test_get_model_for_role_all_mapped_roles(self):
        """Every key in ROLE_MODEL_MAP resolves to a non-None model string."""
        from agenticcli.utils.sdk_runner import ROLE_MODEL_MAP, get_model_for_role

        for role in ROLE_MODEL_MAP:
            result = get_model_for_role(role)
            assert result is not None, f"Expected non-None model for mapped role {role!r}"
            assert isinstance(result, str)
            assert len(result) > 0

    def test_get_model_for_role_empty_string(self):
        """Empty string role returns None (not in map)."""
        from agenticcli.utils.sdk_runner import get_model_for_role

        assert get_model_for_role("") is None

    def test_get_model_for_role_planner_test(self):
        """planner-test maps to opus."""
        from agenticcli.utils.sdk_runner import get_model_for_role

        result = get_model_for_role("planner-test")
        assert result == "claude-opus-4-6"

    def test_get_model_for_role_planner_orchestration(self):
        """planner-orchestration maps to opus."""
        from agenticcli.utils.sdk_runner import get_model_for_role

        result = get_model_for_role("planner-orchestration")
        assert result == "claude-opus-4-6"

    def test_get_model_for_role_build_story_writer(self):
        """build-story-writer maps to sonnet."""
        from agenticcli.utils.sdk_runner import get_model_for_role

        result = get_model_for_role("build-story-writer")
        assert result == "claude-sonnet-4-6"
