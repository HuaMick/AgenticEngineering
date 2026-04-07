"""Tests for the naming utility module.

Tests the YYMMDDXX_description naming convention implementation.
"""

from datetime import datetime
from pathlib import Path

import pytest

pytestmark = [pytest.mark.story("US-GDN-100")]

from agenticcli.utils.naming import (
    generate_epic_folder_name,
    get_worktree_id,
    parse_epic_folder_name,
    sanitize_description,
    validate_epic_folder_name,
)



class TestGetWorktreeId:
    """Tests for worktree ID extraction."""

    def test_extracts_suffix_after_hyphen(self):
        """Extracts first 2 chars of suffix after last hyphen, uppercased."""
        path = Path("/home/code/AgenticEngineering-agenticguidance")
        assert get_worktree_id(path) == "AG"

    def test_handles_multiple_hyphens(self):
        """Takes suffix after the LAST hyphen."""
        path = Path("/home/code/AgenticEngineering-agentic-cli")
        assert get_worktree_id(path) == "CL"

    def test_no_hyphen_uses_directory_name(self):
        """When no hyphen, uses first 2 chars of directory name."""
        path = Path("/home/code/MyProject")
        assert get_worktree_id(path) == "MY"

    def test_short_suffix_padded_with_x(self):
        """Single char suffix gets padded with X."""
        path = Path("/home/code/Repo-a")
        assert get_worktree_id(path) == "AX"

    def test_empty_suffix_returns_xx(self):
        """Empty suffix returns XX default."""
        path = Path("/home/code/Repo-")
        assert get_worktree_id(path) == "XX"

    def test_lowercase_suffix_uppercased(self):
        """Suffix is always uppercased."""
        path = Path("/home/code/Repo-lowercase")
        assert get_worktree_id(path) == "LO"

    def test_mixed_case_suffix(self):
        """Mixed case suffix uses first 2 chars uppercased."""
        path = Path("/home/code/Repo-FeatureBranch")
        assert get_worktree_id(path) == "FE"

    def test_branch_with_yymmddxx_pattern_extracts_directly(self):
        """Branch matching YYMMDDXX pattern extracts code directly."""
        path = Path("/home/code/Repo-260208PN")
        result = get_worktree_id(path, branch="260208PN")
        assert result == "PN"


class TestSanitizeDescription:
    """Tests for description sanitization."""

    def test_lowercase_conversion(self):
        """Description is lowercased."""
        assert sanitize_description("My Feature") == "my_feature"

    def test_space_to_underscore(self):
        """Spaces become underscores."""
        assert sanitize_description("my feature name") == "my_feature_name"

    def test_hyphen_to_underscore(self):
        """Hyphens become underscores."""
        assert sanitize_description("my-feature-name") == "my_feature_name"

    def test_special_chars_removed(self):
        """Special characters are removed."""
        assert sanitize_description("Fix: Bug #123!") == "fix_bug_123"

    def test_multiple_underscores_collapsed(self):
        """Multiple underscores collapse to single."""
        assert sanitize_description("my   feature___name") == "my_feature_name"

    def test_leading_trailing_underscores_stripped(self):
        """Leading/trailing underscores are stripped."""
        assert sanitize_description("_my_feature_") == "my_feature"

    def test_max_length_50(self):
        """Description truncated to 50 characters."""
        long_desc = "a" * 100
        result = sanitize_description(long_desc)
        assert len(result) <= 50

    def test_max_length_no_trailing_underscore(self):
        """Truncation doesn't leave trailing underscore."""
        desc = "my_" + "a" * 50
        result = sanitize_description(desc)
        assert not result.endswith("_")

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert sanitize_description("") == ""

    def test_only_special_chars(self):
        """String with only special chars returns empty."""
        assert sanitize_description("!@#$%") == ""


class TestGenerateEpicFolderName:
    """Tests for epic folder name generation."""

    def test_basic_generation(self):
        """Generates name in YYMMDDXX_description format."""
        path = Path("/home/code/AgenticEngineering-agenticguidance")
        date = datetime(2026, 1, 15)
        name = generate_epic_folder_name(path, "naming audit", date)
        assert name == "260115AG_naming_audit"

    def test_uses_current_date_by_default(self):
        """Uses current date when not specified."""
        path = Path("/home/code/Repo-test")
        name = generate_epic_folder_name(path, "feature")
        # Check format: 6 digits + 2 letters + underscore + description
        assert len(name.split("_")[0]) == 8  # YYMMDDXX

    def test_description_sanitized(self):
        """Description is sanitized in the name."""
        path = Path("/home/code/Repo-test")
        date = datetime(2026, 1, 15)
        name = generate_epic_folder_name(path, "My Feature!", date)
        assert name == "260115TE_my_feature"

    def test_branch_none_uses_path_fallback(self):
        """branch=None preserves existing path-suffix behavior."""
        path = Path("/home/code/Repo-test")
        date = datetime(2026, 2, 8)
        name = generate_epic_folder_name(path, "feature", date, branch=None)
        assert name == "260208TE_feature"


class TestValidateEpicFolderName:
    """Tests for epic folder name validation."""

    def test_valid_name_passes(self):
        """Valid names pass validation."""
        is_valid, error = validate_epic_folder_name("260115AG_naming_audit")
        assert is_valid is True
        assert error is None

    def test_invalid_date_fails(self):
        """Names without proper date prefix fail."""
        is_valid, error = validate_epic_folder_name("2601AG_feature")
        assert is_valid is False
        assert error is not None

    def test_lowercase_worktree_id_fails(self):
        """Lowercase worktree IDs fail."""
        is_valid, error = validate_epic_folder_name("260115ag_feature")
        assert is_valid is False

    def test_missing_underscore_fails(self):
        """Names without underscore separator fail."""
        is_valid, error = validate_epic_folder_name("260115AGfeature")
        assert is_valid is False

    def test_uppercase_description_fails(self):
        """Uppercase in description fails."""
        is_valid, error = validate_epic_folder_name("260115AG_Feature")
        assert is_valid is False

    def test_special_chars_in_description_fails(self):
        """Special chars in description fail."""
        is_valid, error = validate_epic_folder_name("260115AG_my-feature")
        assert is_valid is False

    def test_valid_with_numbers_in_description(self):
        """Numbers in description are allowed."""
        is_valid, error = validate_epic_folder_name("260115AG_feature_v2")
        assert is_valid is True


class TestParseEpicFolderName:
    """Tests for epic folder name parsing."""

    def test_parses_valid_name(self):
        """Valid names are parsed into components."""
        result = parse_epic_folder_name("260115AG_naming_convention_audit")
        assert result == {
            "date": "260115",
            "worktree_id": "AG",
            "description": "naming_convention_audit",
        }

    def test_returns_none_for_invalid(self):
        """Invalid names return None."""
        result = parse_epic_folder_name("invalid-name")
        assert result is None

    def test_parses_short_description(self):
        """Short descriptions are parsed correctly."""
        result = parse_epic_folder_name("260115AG_a")
        assert result["description"] == "a"
