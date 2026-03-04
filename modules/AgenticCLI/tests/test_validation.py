"""Tests for input validation utilities."""


import pytest

from agenticcli.exceptions import ValidationError
from agenticcli.validation import (
    validate_branch_name,
    validate_branch_name_or_raise,
    validate_identifier,
    validate_path_safe,
    validate_epic_folder_or_raise,
    validate_epic_folder_structure,
    validate_epic_yaml,
    validate_epic_yaml_or_raise,
)


class TestValidateBranchName:
    """Tests for branch name validation."""

    def test_valid_simple_name(self):
        """Test simple valid branch names."""
        assert validate_branch_name("main") == (True, None)
        assert validate_branch_name("feature-x") == (True, None)
        assert validate_branch_name("fix_bug") == (True, None)
        assert validate_branch_name("release/v1.0") == (True, None)

    def test_valid_complex_name(self):
        """Test complex valid branch names."""
        assert validate_branch_name("feature/user-auth/oauth2") == (True, None)
        assert validate_branch_name("hotfix-2024.01.15") == (True, None)
        assert validate_branch_name("dev_branch_123") == (True, None)

    def test_empty_name(self):
        """Test empty branch name is invalid."""
        is_valid, reason = validate_branch_name("")
        assert is_valid is False
        assert "empty" in reason

    def test_starts_with_dot(self):
        """Test branch starting with dot is invalid."""
        is_valid, reason = validate_branch_name(".hidden")
        assert is_valid is False
        assert "dot" in reason

    def test_consecutive_dots(self):
        """Test consecutive dots are invalid."""
        is_valid, reason = validate_branch_name("branch..name")
        assert is_valid is False
        assert "consecutive dots" in reason

    def test_starts_with_hyphen(self):
        """Test branch starting with hyphen is invalid."""
        is_valid, reason = validate_branch_name("-invalid")
        assert is_valid is False
        assert "hyphen" in reason

    def test_ends_with_slash(self):
        """Test branch ending with slash is invalid."""
        is_valid, reason = validate_branch_name("feature/")
        assert is_valid is False
        assert "slash" in reason

    def test_ends_with_lock(self):
        """Test branch ending with .lock is invalid."""
        is_valid, reason = validate_branch_name("branch.lock")
        assert is_valid is False
        assert ".lock" in reason

    def test_contains_special_chars(self):
        """Test special characters are invalid."""
        is_valid, reason = validate_branch_name("branch~name")
        assert is_valid is False
        assert "special" in reason

        is_valid, reason = validate_branch_name("branch^name")
        assert is_valid is False

    def test_contains_whitespace(self):
        """Test whitespace is invalid."""
        is_valid, reason = validate_branch_name("branch name")
        assert is_valid is False
        assert "whitespace" in reason

    def test_too_long(self):
        """Test branch name that's too long."""
        is_valid, reason = validate_branch_name("a" * 256)
        assert is_valid is False
        assert "too long" in reason


class TestValidateBranchNameOrRaise:
    """Tests for validate_branch_name_or_raise."""

    def test_valid_returns_name(self):
        """Test valid name returns the name."""
        assert validate_branch_name_or_raise("feature-x") == "feature-x"

    def test_invalid_raises(self):
        """Test invalid name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_branch_name_or_raise(".invalid")
        assert "dot" in str(exc_info.value)
        assert exc_info.value.exit_code == 40


class TestValidateEpicFolderStructure:
    """Tests for epic folder structure validation."""

    def test_nonexistent_folder(self, temp_dir):
        """Test nonexistent folder is invalid."""
        is_valid, issues = validate_epic_folder_structure(temp_dir / "nonexistent")
        assert is_valid is False
        assert "does not exist" in issues[0]

    def test_file_not_directory(self, temp_dir):
        """Test file instead of directory is invalid."""
        file_path = temp_dir / "plan.yml"
        file_path.write_text("test")
        is_valid, issues = validate_epic_folder_structure(file_path)
        assert is_valid is False
        assert "not a directory" in issues[0]

    def test_missing_plan_files(self, temp_dir):
        """Test missing plan_*.yml files is invalid (flattened structure)."""
        plan_dir = temp_dir / "plan_folder"
        plan_dir.mkdir()
        is_valid, issues = validate_epic_folder_structure(plan_dir)
        assert is_valid is False
        assert "no plan_*.yml files" in issues[0]

    def test_empty_directory(self, temp_dir):
        """Test empty directory is invalid (no plan_*.yml files)."""
        plan_dir = temp_dir / "plan_folder"
        plan_dir.mkdir()
        # Create a non-plan file
        (plan_dir / "README.md").write_text("# Test")
        is_valid, issues = validate_epic_folder_structure(plan_dir)
        assert is_valid is False
        assert "no plan_*.yml files" in issues[0]

    def test_valid_structure(self, temp_dir):
        """Test valid plan folder structure (flattened: plan_*.yml directly in folder)."""
        plan_dir = temp_dir / "plan_folder"
        plan_dir.mkdir()
        # Flattened: plan file directly in plan_dir
        (plan_dir / "plan_build.yml").write_text("plan:\n  name: Test")
        is_valid, issues = validate_epic_folder_structure(plan_dir)
        assert is_valid is True
        assert issues == []


class TestValidateEpicFolderOrRaise:
    """Tests for validate_epic_folder_or_raise."""

    def test_valid_returns_path(self, temp_dir):
        """Test valid folder returns path (flattened structure)."""
        plan_dir = temp_dir / "plan_folder"
        plan_dir.mkdir()
        # Flattened: plan file directly in plan_dir
        (plan_dir / "plan_build.yml").write_text("test")
        result = validate_epic_folder_or_raise(plan_dir)
        assert result == plan_dir

    def test_invalid_raises(self, temp_dir):
        """Test invalid folder raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_epic_folder_or_raise(temp_dir / "nonexistent")
        assert "does not exist" in str(exc_info.value)


class TestValidateEpicYaml:
    """Tests for plan YAML validation."""

    def test_valid_minimal_plan(self):
        """Test minimal valid plan."""
        content = """
plan:
  name: Test Plan
  status: pending
"""
        is_valid, violations = validate_epic_yaml(content)
        assert is_valid is True
        assert violations == []

    def test_valid_full_plan(self):
        """Test full valid plan with phases."""
        content = """
plan:
  name: Test Plan
  status: in_progress
  phases:
    - id: "01"
      name: Phase 1
      status: pending
    - id: "02"
      name: Phase 2
      status: pending
"""
        is_valid, violations = validate_epic_yaml(content)
        assert is_valid is True

    def test_invalid_yaml_syntax(self):
        """Test invalid YAML syntax."""
        content = "plan:\n  name: Test\n  invalid: ["
        is_valid, violations = validate_epic_yaml(content)
        assert is_valid is False
        assert any("parse error" in v.lower() for v in violations)

    def test_empty_content(self):
        """Test empty content is invalid."""
        is_valid, violations = validate_epic_yaml("")
        assert is_valid is False
        assert "empty" in violations[0]

    def test_missing_plan_field(self):
        """Test missing plan field is invalid."""
        content = "name: Test"
        is_valid, violations = validate_epic_yaml(content)
        assert is_valid is False
        assert any("'plan'" in v for v in violations)

    def test_missing_name(self):
        """Test missing plan.name is invalid."""
        content = "plan:\n  status: pending"
        is_valid, violations = validate_epic_yaml(content)
        assert is_valid is False
        assert any("'plan.name'" in v for v in violations)

    def test_invalid_status(self):
        """Test invalid status value."""
        content = """
plan:
  name: Test
  status: unknown
"""
        is_valid, violations = validate_epic_yaml(content)
        assert is_valid is False
        assert any("invalid status" in v for v in violations)

    def test_phases_not_list(self):
        """Test phases must be a list."""
        content = """
plan:
  name: Test
  status: pending
  phases: not-a-list
"""
        is_valid, violations = validate_epic_yaml(content)
        assert is_valid is False
        assert any("must be a list" in v for v in violations)

    def test_phase_missing_id_and_name(self):
        """Test phase must have id or name."""
        content = """
plan:
  name: Test
  status: pending
  phases:
    - status: pending
"""
        is_valid, violations = validate_epic_yaml(content)
        assert is_valid is False
        assert any("missing 'id' or 'name'" in v for v in violations)


class TestValidateEpicYamlOrRaise:
    """Tests for validate_epic_yaml_or_raise."""

    def test_valid_returns_data(self):
        """Test valid YAML returns parsed data."""
        content = "plan:\n  name: Test\n  status: pending"
        data = validate_epic_yaml_or_raise(content)
        assert data["plan"]["name"] == "Test"

    def test_invalid_raises(self):
        """Test invalid YAML raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_epic_yaml_or_raise("invalid: [")
        assert exc_info.value.exit_code == 40


class TestValidatePathSafe:
    """Tests for path safety validation."""

    def test_valid_relative_path(self):
        """Test valid relative paths."""
        assert validate_path_safe("docs/plans/file.yml") == (True, None)
        assert validate_path_safe("file.txt") == (True, None)

    def test_empty_path(self):
        """Test empty path is invalid."""
        is_valid, reason = validate_path_safe("")
        assert is_valid is False
        assert "empty" in reason

    def test_null_bytes(self):
        """Test null bytes are invalid."""
        is_valid, reason = validate_path_safe("file\x00.txt")
        assert is_valid is False
        assert "null bytes" in reason

    def test_path_traversal(self):
        """Test path traversal is blocked."""
        is_valid, reason = validate_path_safe("../etc/passwd")
        assert is_valid is False
        assert "traversal" in reason

    def test_control_characters(self):
        """Test control characters are invalid."""
        is_valid, reason = validate_path_safe("file\nname.txt")
        assert is_valid is False
        assert "control" in reason


class TestValidateIdentifier:
    """Tests for identifier validation."""

    def test_valid_identifiers(self):
        """Test valid identifiers."""
        assert validate_identifier("task-01") == (True, None)
        assert validate_identifier("phase.1.2") == (True, None)
        assert validate_identifier("id_123") == (True, None)

    def test_empty_identifier(self):
        """Test empty identifier is invalid."""
        is_valid, reason = validate_identifier("")
        assert is_valid is False
        assert "empty" in reason

    def test_too_long(self):
        """Test identifier that's too long."""
        is_valid, reason = validate_identifier("a" * 100, max_length=50)
        assert is_valid is False
        assert "too long" in reason

    def test_starts_with_special(self):
        """Test identifier starting with special char is invalid."""
        is_valid, reason = validate_identifier("-invalid")
        assert is_valid is False
        assert "must start with alphanumeric" in reason
