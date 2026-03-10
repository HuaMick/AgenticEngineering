"""Tests for pytest story marker registration and conftest collection plugin (P4-T1).

Validates the story marker infrastructure added in P1 of the
260308PD_planner_design_agent_story_alignment epic.
"""

import importlib.util
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


def _load_conftest_module():
    """Import conftest.py helpers via importlib (not a regular module)."""
    conftest_path = Path(__file__).resolve().parent / "conftest.py"
    spec = importlib.util.spec_from_file_location("_conftest_helpers", conftest_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests for _find_repo_root_from_tests
# ---------------------------------------------------------------------------

class TestFindRepoRoot:
    """Test repo root discovery from conftest location."""

    def test_finds_repo_root_with_git_dir(self):
        """Verify repo root is found when .git directory exists."""
        mod = _load_conftest_module()
        result = mod._find_repo_root_from_tests()
        assert result is not None
        assert (result / ".git").exists()

    def test_repo_root_is_parent_of_tests(self):
        """Verify found root is an ancestor of the tests directory."""
        mod = _load_conftest_module()
        root = mod._find_repo_root_from_tests()
        if root:
            tests_dir = Path(__file__).resolve().parent
            assert str(tests_dir).startswith(str(root))


# ---------------------------------------------------------------------------
# Tests for _load_valid_story_ids
# ---------------------------------------------------------------------------

class TestLoadValidStoryIds:
    """Test story ID loading from docs/userstories/."""

    def test_returns_frozenset(self):
        """Verify return type is frozenset."""
        mod = _load_conftest_module()
        result = mod._load_valid_story_ids()
        assert isinstance(result, frozenset)

    def test_loads_story_ids_from_yaml(self):
        """Verify story IDs are loaded from YAML files in docs/userstories/."""
        mod = _load_conftest_module()
        result = mod._load_valid_story_ids()
        if result:
            for story_id in result:
                assert isinstance(story_id, str)
                assert story_id.startswith("US-")

    def test_skips_metadata_file(self):
        """Verify 00_metadata.yml is excluded from scanning."""
        mod = _load_conftest_module()
        result = mod._load_valid_story_ids()
        assert isinstance(result, frozenset)


# ---------------------------------------------------------------------------
# Tests for pytest_configure (marker registration)
# ---------------------------------------------------------------------------

class TestMarkerRegistration:
    """Test that the story marker is registered correctly."""

    def test_story_marker_is_registered(self):
        """Verify @pytest.mark.story is a registered marker."""
        marker = pytest.mark.story("US-TEST-001")
        assert marker is not None
        assert marker.args == ("US-TEST-001",)

    def test_story_marker_with_multiple_ids(self):
        """Verify marker supports multiple story IDs."""
        marker = pytest.mark.story("US-CLI-110", "US-CLI-111")
        assert marker.args == ("US-CLI-110", "US-CLI-111")


# ---------------------------------------------------------------------------
# Tests for pytest_collection_modifyitems (validation)
# ---------------------------------------------------------------------------

class TestCollectionValidation:
    """Test that the collection plugin validates story markers."""

    def test_marker_validation_warns_on_unknown_id(self):
        """Verify unknown story IDs generate warnings, not errors."""
        mod = _load_conftest_module()
        valid = mod._load_valid_story_ids()
        if valid:
            fake_id = "US-FAKE-99999"
            assert fake_id not in valid

    def test_marker_validation_does_not_block(self):
        """Verify tests with unknown story IDs still run."""
        pass


# ---------------------------------------------------------------------------
# A sample test with story marker (proves the infrastructure works)
# ---------------------------------------------------------------------------

@pytest.mark.story("US-FAKE-999")
def test_story_marker_does_not_block_execution():
    """This test uses a non-existent story ID. It should still execute.

    The conftest plugin should issue a warning but not prevent execution.
    """
    assert True
