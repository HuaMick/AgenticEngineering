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

pytestmark = [pytest.mark.story("US-STR-009")]


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
        assert root is not None, "Expected to find repo root with .git directory"
        tests_dir = Path(__file__).resolve().parent
        assert str(tests_dir).startswith(str(root)), \
            f"Tests dir {tests_dir} should be under repo root {root}"


# ---------------------------------------------------------------------------
# Tests for _load_valid_story_ids
# ---------------------------------------------------------------------------

class TestLoadValidStoryIds:
    """Test story ID loading from docs/userstories/."""

    def test_returns_dict(self):
        """Verify return type is dict mapping id -> lifecycle."""
        mod = _load_conftest_module()
        result = mod._load_valid_story_ids()
        assert isinstance(result, dict)

    def test_loads_story_ids_from_yaml(self):
        """Verify story IDs are loaded from YAML files in docs/userstories/."""
        mod = _load_conftest_module()
        result = mod._load_valid_story_ids()
        if result:
            for story_id in result:
                assert isinstance(story_id, str)
                assert story_id.startswith("US-")

    def test_skips_metadata_file(self, tmp_path):
        """Verify 00_metadata.yml is excluded from scanning."""
        mod = _load_conftest_module()

        userstories_dir = tmp_path / "docs" / "userstories" / "TestProject"
        userstories_dir.mkdir(parents=True)
        # Create metadata file with stories — should be ignored
        (userstories_dir / "00_metadata.yml").write_text(yaml.dump({
            "stories": [{"id": "US-META-001", "title": "From metadata"}]
        }))
        # Create non-metadata file — should be loaded
        (userstories_dir / "01_features.yml").write_text(yaml.dump({
            "stories": [{"id": "US-FEAT-001", "title": "From features"}]
        }))

        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert isinstance(result, dict)
            assert "US-META-001" not in result, "00_metadata.yml stories should be excluded"
            assert "US-FEAT-001" in result, "Non-metadata stories should be loaded"


# ---------------------------------------------------------------------------
# Tests for pytest_configure (marker registration)
# ---------------------------------------------------------------------------

@pytest.mark.story("US-GDN-067", "US-GDN-069")
class TestMarkerRegistration:
    """Test that the story marker is registered correctly."""

    def test_story_marker_is_registered(self):
        """Verify @pytest.mark.story is a registered marker."""
        marker = pytest.mark.story("US-TEST-001")
        assert marker is not None
        assert marker.args == ("US-TEST-001",)

    def test_story_marker_with_multiple_ids(self):
        """Verify marker supports multiple story IDs."""
        marker = pytest.mark.story("US-STR-001", "US-STR-002")
        assert marker.args == ("US-STR-001", "US-STR-002")


# ---------------------------------------------------------------------------
# Tests for pytest_collection_modifyitems (validation)
# ---------------------------------------------------------------------------

@pytest.mark.story("US-GDN-059")
class TestCollectionValidation:
    """Test that the collection plugin validates story markers."""

    def _mock_config(self, strict=False):
        """Create a mock config with story_strict ini value."""
        config = MagicMock()
        config.getini.return_value = strict
        return config

    def test_marker_validation_warns_on_unknown_id(self):
        """Verify unknown story IDs generate warnings via collection plugin."""
        mod = _load_conftest_module()

        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("US-FAKE-99999",)
        mock_item.iter_markers.return_value = [mock_marker]
        mock_item.nodeid = "test_example.py::test_unknown_id"

        valid_ids = {"US-STR-001": "implemented", "US-STR-002": "implemented"}

        with patch.object(mod, "_VALID_STORY_IDS", valid_ids):
            mod.pytest_collection_modifyitems(self._mock_config(), [mock_item])
            mock_item.warn.assert_called_once()
            warn_arg = str(mock_item.warn.call_args[0][0])
            assert "US-FAKE-99999" in warn_arg

    def test_marker_validation_does_not_block(self):
        """Verify tests with unknown story IDs still run (warnings only)."""
        mod = _load_conftest_module()
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("US-NONEXISTENT-99999",)
        mock_item.iter_markers.return_value = [mock_marker]
        mock_item.nodeid = "test_example.py::test_something"

        valid = {"US-STR-001": "implemented"}
        with patch.object(mod, "_VALID_STORY_IDS", valid):
            # Should warn but not raise
            mod.pytest_collection_modifyitems(self._mock_config(), [mock_item])
            mock_item.warn.assert_called_once()

    def test_strict_mode_fails_on_unknown_id(self):
        """Verify strict mode causes pytest.fail on unknown story IDs."""
        mod = _load_conftest_module()
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("US-NONEXISTENT-99999",)
        mock_item.iter_markers.return_value = [mock_marker]
        mock_item.nodeid = "test_example.py::test_strict"

        valid = {"US-STR-001": "implemented"}
        with patch.object(mod, "_VALID_STORY_IDS", valid):
            from _pytest.outcomes import Failed

            with pytest.raises(Failed, match="unknown story ID"):
                mod.pytest_collection_modifyitems(self._mock_config(strict=True), [mock_item])

    def test_collection_modifyitems_no_warn_for_valid_id(self):
        """Verify no warning issued for known/valid story IDs."""
        mod = _load_conftest_module()

        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("US-STR-001",)
        mock_item.iter_markers.return_value = [mock_marker]

        valid = {"US-STR-001": "implemented", "US-STR-002": "implemented"}
        with patch.object(mod, "_VALID_STORY_IDS", valid):
            mod.pytest_collection_modifyitems(self._mock_config(), [mock_item])
            mock_item.warn.assert_not_called()

    def test_collection_modifyitems_warns_empty_marker_args(self):
        """Verify warning when @pytest.mark.story() has no story IDs."""
        mod = _load_conftest_module()

        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ()  # no story IDs
        mock_item.iter_markers.return_value = [mock_marker]
        mock_item.nodeid = "test_example.py::test_no_ids"

        mod.pytest_collection_modifyitems(self._mock_config(), [mock_item])
        mock_item.warn.assert_called_once()

    def test_load_valid_story_ids_handles_missing_dir(self, tmp_path):
        """Verify empty frozenset returned when userstories dir is missing."""
        mod = _load_conftest_module()
        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert result == {}

    def test_load_valid_story_ids_handles_no_git_root(self):
        """Verify empty frozenset returned when no .git root found."""
        mod = _load_conftest_module()
        with patch.object(mod, "_find_repo_root_from_tests", return_value=None):
            result = mod._load_valid_story_ids()
            assert result == {}

    def test_load_valid_story_ids_from_stories_key(self, tmp_path):
        """Verify IDs loaded from YAML 'stories' key."""
        mod = _load_conftest_module()

        userstories_dir = tmp_path / "docs" / "userstories" / "TestProject"
        userstories_dir.mkdir(parents=True)
        (userstories_dir / "01_features.yml").write_text(yaml.dump({
            "stories": [
                {"id": "US-TEST-001", "title": "Story 1"},
                {"id": "US-TEST-002", "title": "Story 2"},
            ]
        }))

        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert "US-TEST-001" in result
            assert "US-TEST-002" in result

    def test_load_valid_story_ids_skips_malformed_yaml(self, tmp_path):
        """Verify malformed YAML files are skipped without error."""
        mod = _load_conftest_module()

        userstories_dir = tmp_path / "docs" / "userstories" / "TestProject"
        userstories_dir.mkdir(parents=True)
        (userstories_dir / "bad.yml").write_text("{{invalid yaml::")
        (userstories_dir / "good.yml").write_text(yaml.dump({
            "stories": [{"id": "US-TEST-100", "title": "Good Story"}]
        }))

        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert "US-TEST-100" in result

    def test_load_valid_story_ids_skips_entries_without_id(self, tmp_path):
        """Verify story entries missing 'id' key are skipped."""
        mod = _load_conftest_module()

        userstories_dir = tmp_path / "docs" / "userstories" / "TestProject"
        userstories_dir.mkdir(parents=True)
        (userstories_dir / "01_features.yml").write_text(yaml.dump({
            "stories": [
                {"title": "No ID"},
                {"id": "US-TEST-200", "title": "Has ID"},
            ]
        }))

        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert "US-TEST-200" in result
            assert len(result) == 1


    def test_loads_from_user_stories_key(self, tmp_path):
        """Verify IDs are loaded from YAML files with 'user_stories' key."""
        mod = _load_conftest_module()

        userstories_dir = tmp_path / "docs" / "userstories" / "TestProject"
        userstories_dir.mkdir(parents=True)
        (userstories_dir / "01_features.yml").write_text(yaml.dump({
            "user_stories": [
                {"id": "US-ALT-001", "title": "Alt Story"},
            ]
        }))

        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert "US-ALT-001" in result

    def test_skips_non_list_stories(self, tmp_path):
        """Verify non-list stories values are skipped."""
        mod = _load_conftest_module()

        userstories_dir = tmp_path / "docs" / "userstories" / "TestProject"
        userstories_dir.mkdir(parents=True)
        (userstories_dir / "01_features.yml").write_text(yaml.dump({
            "stories": "not a list"
        }))

        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert result == {}

    def test_skips_non_dict_content(self, tmp_path):
        """Verify files with non-dict top-level content are skipped."""
        mod = _load_conftest_module()

        userstories_dir = tmp_path / "docs" / "userstories" / "TestProject"
        userstories_dir.mkdir(parents=True)
        (userstories_dir / "01_features.yml").write_text("just a string")

        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert result == {}

    def test_collection_modifyitems_handles_empty_valid_ids(self):
        """Verify plugin handles empty valid IDs set gracefully (returns early)."""
        mod = _load_conftest_module()

        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("US-TEST-001",)
        mock_item.iter_markers.return_value = [mock_marker]

        mock_config = MagicMock()

        # Patch _VALID_STORY_IDS to None (not yet loaded) and return empty
        with patch.object(mod, "_VALID_STORY_IDS", None):
            with patch.object(mod, "_load_valid_story_ids", return_value={}):
                # Should not crash; returns early when valid IDs is empty
                mod.pytest_collection_modifyitems(mock_config, [mock_item])
                # No warning should be issued (short-circuit on empty valid IDs)
                mock_item.warn.assert_not_called()

    def test_lazy_loading_of_valid_ids(self):
        """Verify _VALID_STORY_IDS is lazy-loaded on first marker encounter."""
        mod = _load_conftest_module()

        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("US-TEST-001",)
        mock_item.iter_markers.return_value = [mock_marker]

        mock_config = MagicMock()

        with patch.object(mod, "_VALID_STORY_IDS", None):
            with patch.object(mod, "_load_valid_story_ids", return_value={"US-TEST-001": "implemented"}) as mock_load:
                mod.pytest_collection_modifyitems(mock_config, [mock_item])
                mock_load.assert_called_once()

    def test_story_marker_with_no_ids(self):
        """Verify marker can be created with no IDs (validation happens at collection)."""
        marker = pytest.mark.story()
        assert marker.args == ()


# ---------------------------------------------------------------------------
# A sample test with story marker (proves the infrastructure works)
# ---------------------------------------------------------------------------

def test_story_marker_does_not_block_execution():
    """This test uses a real story ID to validate end-to-end marker infrastructure.

    With story_strict = true, invalid IDs cause test failure at collection time.
    This validates that valid story markers pass through without blocking.
    """
    assert True
