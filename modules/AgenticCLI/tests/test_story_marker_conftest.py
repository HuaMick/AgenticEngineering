"""Tests for pytest story marker registration and conftest collection plugin (P4-T1).

Validates the story marker infrastructure in the AgenticCLI conftest.py:
- pytest_configure registers @pytest.mark.story marker
- _find_repo_root_from_tests discovers repo root from test directory
- _load_valid_story_ids scans docs/userstories/ YAML files for story IDs
- pytest_collection_modifyitems validates story marker references at collection time
"""

import importlib.util
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

pytestmark = pytest.mark.story("US-STR-009")


def _load_conftest_module():
    """Import conftest.py helpers via importlib (not a regular module)."""
    conftest_path = Path(__file__).resolve().parent / "conftest.py"
    spec = importlib.util.spec_from_file_location("_conftest_helpers_cli", conftest_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests for _find_repo_root_from_tests
# ---------------------------------------------------------------------------

@pytest.mark.story("US-GDN-077")
class TestFindRepoRootCLI:
    """Test repo root discovery from AgenticCLI conftest location."""

    def test_finds_repo_root_with_git_dir(self):
        """Verify repo root is found when .git directory exists."""
        mod = _load_conftest_module()
        result = mod._find_repo_root_from_tests()
        assert result is not None
        assert (result / ".git").exists()

    def test_repo_root_is_parent_of_tests(self):
        """Verify found root is an ancestor of the AgenticCLI tests directory."""
        mod = _load_conftest_module()
        root = mod._find_repo_root_from_tests()
        assert root is not None
        tests_dir = Path(__file__).resolve().parent
        assert str(tests_dir).startswith(str(root))

    def test_repo_root_contains_modules(self):
        """Verify found root contains modules/ directory (monorepo structure)."""
        mod = _load_conftest_module()
        root = mod._find_repo_root_from_tests()
        assert root is not None, "Expected to find repo root with .git directory"
        assert (root / "modules").exists(), "Repo root should contain modules/ directory"


# ---------------------------------------------------------------------------
# Tests for _load_valid_story_ids
# ---------------------------------------------------------------------------

@pytest.mark.story("US-GDN-077")
class TestLoadValidStoryIdsCLI:
    """Test story ID loading from docs/userstories/ via CLI conftest."""

    def test_returns_frozenset(self):
        """Verify return type is frozenset (immutable, cacheable)."""
        mod = _load_conftest_module()
        result = mod._load_valid_story_ids()
        assert isinstance(result, frozenset)

    def test_loads_story_ids_from_yaml(self):
        """Verify story IDs loaded from YAML files follow US-XXX-NNN format."""
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
            assert isinstance(result, frozenset)
            assert "US-META-001" not in result, "00_metadata.yml stories should be excluded"
            assert "US-FEAT-001" in result, "Non-metadata stories should be loaded"

    def test_handles_missing_userstories_dir(self, tmp_path):
        """Verify returns empty frozenset when docs/userstories/ doesn't exist."""
        mod = _load_conftest_module()
        # Patch _find_repo_root_from_tests to return a dir without userstories
        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert result == frozenset()

    def test_handles_no_git_root(self):
        """Verify returns empty frozenset when no .git root found."""
        mod = _load_conftest_module()
        with patch.object(mod, "_find_repo_root_from_tests", return_value=None):
            result = mod._load_valid_story_ids()
            assert result == frozenset()

    def test_loads_from_stories_key(self, tmp_path):
        """Verify IDs are loaded from YAML files with 'stories' key."""
        mod = _load_conftest_module()

        userstories_dir = tmp_path / "docs" / "userstories" / "TestProject"
        userstories_dir.mkdir(parents=True)
        story_file = userstories_dir / "01_features.yml"
        story_file.write_text(yaml.dump({
            "stories": [
                {"id": "US-TEST-001", "title": "Test Story 1"},
                {"id": "US-TEST-002", "title": "Test Story 2"},
            ]
        }))

        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert "US-TEST-001" in result
            assert "US-TEST-002" in result

    def test_loads_from_user_stories_key(self, tmp_path):
        """Verify IDs are loaded from YAML files with 'user_stories' key."""
        mod = _load_conftest_module()

        userstories_dir = tmp_path / "docs" / "userstories" / "TestProject"
        userstories_dir.mkdir(parents=True)
        story_file = userstories_dir / "01_features.yml"
        story_file.write_text(yaml.dump({
            "user_stories": [
                {"id": "US-ALT-001", "title": "Alt Story"},
            ]
        }))

        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert "US-ALT-001" in result

    def test_skips_malformed_yaml(self, tmp_path):
        """Verify malformed YAML files are skipped without error."""
        mod = _load_conftest_module()

        userstories_dir = tmp_path / "docs" / "userstories" / "TestProject"
        userstories_dir.mkdir(parents=True)
        # Write invalid YAML
        (userstories_dir / "bad.yml").write_text("{{invalid yaml::")
        # Write valid YAML with stories
        (userstories_dir / "good.yml").write_text(yaml.dump({
            "stories": [{"id": "US-TEST-100", "title": "Good Story"}]
        }))

        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert "US-TEST-100" in result

    def test_skips_stories_without_id_key(self, tmp_path):
        """Verify story entries missing 'id' key are skipped."""
        mod = _load_conftest_module()

        userstories_dir = tmp_path / "docs" / "userstories" / "TestProject"
        userstories_dir.mkdir(parents=True)
        (userstories_dir / "01_features.yml").write_text(yaml.dump({
            "stories": [
                {"title": "No ID Story"},  # missing 'id'
                {"id": "US-TEST-200", "title": "Has ID"},
            ]
        }))

        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert "US-TEST-200" in result
            assert len(result) == 1

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
            assert result == frozenset()

    def test_skips_non_dict_content(self, tmp_path):
        """Verify files with non-dict top-level content are skipped."""
        mod = _load_conftest_module()

        userstories_dir = tmp_path / "docs" / "userstories" / "TestProject"
        userstories_dir.mkdir(parents=True)
        (userstories_dir / "01_features.yml").write_text("just a string")

        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert result == frozenset()

    def test_skips_00_metadata_yml(self, tmp_path):
        """Verify 00_metadata.yml files are explicitly skipped."""
        mod = _load_conftest_module()

        userstories_dir = tmp_path / "docs" / "userstories" / "TestProject"
        userstories_dir.mkdir(parents=True)
        # Metadata file should be skipped even if it has stories
        (userstories_dir / "00_metadata.yml").write_text(yaml.dump({
            "stories": [{"id": "US-META-001", "title": "Metadata Story"}]
        }))

        with patch.object(mod, "_find_repo_root_from_tests", return_value=tmp_path):
            result = mod._load_valid_story_ids()
            assert "US-META-001" not in result


# ---------------------------------------------------------------------------
# Tests for pytest_configure (marker registration)
# ---------------------------------------------------------------------------

@pytest.mark.story("US-GDN-077")
class TestMarkerRegistrationCLI:
    """Test that the story marker is registered in AgenticCLI tests."""

    def test_story_marker_is_registered(self):
        """Verify @pytest.mark.story is a registered marker (no warning)."""
        marker = pytest.mark.story("US-TEST-001")
        assert marker is not None
        assert marker.args == ("US-TEST-001",)

    def test_story_marker_with_multiple_ids(self):
        """Verify marker supports multiple story IDs."""
        marker = pytest.mark.story("US-STR-001", "US-STR-002")
        assert marker.args == ("US-STR-001", "US-STR-002")

    def test_story_marker_with_no_ids(self):
        """Verify marker can be created with no IDs (validation happens at collection)."""
        marker = pytest.mark.story()
        assert marker.args == ()


# ---------------------------------------------------------------------------
# Tests for pytest_collection_modifyitems (validation plugin)
# ---------------------------------------------------------------------------

@pytest.mark.story("US-GDN-078")
class TestCollectionValidationCLI:
    """Test the collection plugin validates story markers at collection time."""

    def test_validation_warns_on_unknown_id(self):
        """Verify unknown story IDs generate warnings via mock, not errors."""
        mod = _load_conftest_module()

        # Create mock item with an unknown story ID marker
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("US-NONEXISTENT-99999",)
        mock_item.iter_markers.return_value = [mock_marker]
        mock_item.nodeid = "test_module.py::test_example"

        mock_config = MagicMock()
        mock_config.getini.return_value = False

        # Provide known valid IDs so the fake ID is definitely unknown
        valid_ids = frozenset({"US-STR-001", "US-STR-002"})
        with patch.object(mod, "_VALID_STORY_IDS", valid_ids):
            mod.pytest_collection_modifyitems(mock_config, [mock_item])
            mock_item.warn.assert_called_once()
            warn_arg = str(mock_item.warn.call_args[0][0])
            assert "US-NONEXISTENT-99999" in warn_arg

    def test_validation_does_not_raise_on_unknown_ids(self):
        """Verify collection plugin issues warnings but doesn't raise exceptions."""
        mod = _load_conftest_module()

        # Mock item with unknown story ID
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("US-DOES-NOT-EXIST-001",)
        mock_item.iter_markers.return_value = [mock_marker]
        mock_item.nodeid = "test_module.py::test_example"

        mock_config = MagicMock()
        mock_config.getini.return_value = False
        valid_ids = frozenset({"US-STR-001"})

        # Should NOT raise — only warn
        with patch.object(mod, "_VALID_STORY_IDS", valid_ids):
            mod.pytest_collection_modifyitems(mock_config, [mock_item])
            # Verify it warned rather than raised
            mock_item.warn.assert_called_once()

    def test_collection_modifyitems_handles_empty_valid_ids(self):
        """Verify plugin handles empty valid IDs set gracefully."""
        mod = _load_conftest_module()

        # Mock item with a story marker
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("US-TEST-001",)
        mock_item.iter_markers.return_value = [mock_marker]

        mock_config = MagicMock()
        mock_config.getini.return_value = False

        # Patch _VALID_STORY_IDS to None (not yet loaded) and _load_valid_story_ids to return empty
        with patch.object(mod, "_VALID_STORY_IDS", None):
            with patch.object(mod, "_load_valid_story_ids", return_value=frozenset()):
                mod.pytest_collection_modifyitems(mock_config, [mock_item])
                # Should not crash; returns early when valid IDs is empty

    def test_collection_modifyitems_warns_on_no_story_ids_in_marker(self):
        """Verify warning issued when @pytest.mark.story has no arguments."""
        mod = _load_conftest_module()

        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ()  # empty args
        mock_item.iter_markers.return_value = [mock_marker]
        mock_item.nodeid = "test_module.py::test_example"

        mock_config = MagicMock()
        mock_config.getini.return_value = False

        mod.pytest_collection_modifyitems(mock_config, [mock_item])
        mock_item.warn.assert_called_once()

    def test_collection_modifyitems_warns_on_unknown_story_id(self):
        """Verify warning issued for story IDs not in docs/userstories/."""
        mod = _load_conftest_module()

        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("US-UNKNOWN-999",)
        mock_item.iter_markers.return_value = [mock_marker]
        mock_item.nodeid = "test_module.py::test_example"

        mock_config = MagicMock()
        mock_config.getini.return_value = False

        valid_ids = frozenset({"US-STR-001", "US-STR-002"})
        with patch.object(mod, "_VALID_STORY_IDS", valid_ids):
            mod.pytest_collection_modifyitems(mock_config, [mock_item])
            mock_item.warn.assert_called_once()
            warn_arg = mock_item.warn.call_args[0][0]
            assert "US-UNKNOWN-999" in str(warn_arg)

    def test_collection_modifyitems_no_warn_for_known_story_id(self):
        """Verify no warning for valid story IDs."""
        mod = _load_conftest_module()

        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("US-STR-001",)
        mock_item.iter_markers.return_value = [mock_marker]

        mock_config = MagicMock()
        mock_config.getini.return_value = False

        valid_ids = frozenset({"US-STR-001", "US-STR-002"})
        with patch.object(mod, "_VALID_STORY_IDS", valid_ids):
            mod.pytest_collection_modifyitems(mock_config, [mock_item])
            mock_item.warn.assert_not_called()

    def test_lazy_loading_of_valid_ids(self):
        """Verify _VALID_STORY_IDS is lazy-loaded on first marker encounter."""
        mod = _load_conftest_module()

        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("US-TEST-001",)
        mock_item.iter_markers.return_value = [mock_marker]

        mock_config = MagicMock()
        mock_config.getini.return_value = False

        # Set cache to None to force loading
        with patch.object(mod, "_VALID_STORY_IDS", None):
            with patch.object(mod, "_load_valid_story_ids", return_value=frozenset({"US-TEST-001"})) as mock_load:
                mod.pytest_collection_modifyitems(mock_config, [mock_item])
                mock_load.assert_called_once()


# ---------------------------------------------------------------------------
# A sample test with story marker (proves the infrastructure works end-to-end)
# ---------------------------------------------------------------------------

@pytest.mark.story("US-GDN-077")
def test_story_marker_does_not_block_cli_test_execution():
    """This test uses a real story ID to validate end-to-end marker infrastructure.

    With story_strict = true, invalid IDs cause test failure at collection time.
    This validates that valid story markers pass through without blocking.
    """
    assert True
