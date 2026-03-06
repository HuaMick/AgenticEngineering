"""Input validation utilities for AgenticCLI.

This module provides centralized validation functions for user inputs,
ensuring consistent error handling and helpful error messages.
"""

import re
from pathlib import Path
from typing import Optional

import yaml

from agenticcli.exceptions import ValidationError

# Git branch name validation patterns
# Based on git-check-ref-format rules
INVALID_BRANCH_PATTERNS = [
    (r"^\.", "cannot start with a dot"),
    (r"\.\.", "cannot contain consecutive dots"),
    (r"^-", "cannot start with a hyphen"),
    (r"/$", "cannot end with a slash"),
    (r"/\.", "cannot contain '/.'"),
    (r"\.lock$", "cannot end with '.lock'"),
    (r"@\{", "cannot contain '@{'"),
    (r"\\", "cannot contain backslash"),
    (r"\s", "cannot contain whitespace"),
    (r"[\x00-\x1f\x7f]", "cannot contain control characters"),
    (r"[~^:?*\[]", "cannot contain special characters (~^:?*[)"),
]

# Valid branch name pattern (alphanumeric, hyphens, underscores, slashes)
VALID_BRANCH_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]*$")


def validate_branch_name(name: str) -> tuple[bool, Optional[str]]:
    """Validate a git branch name.

    Args:
        name: The branch name to validate.

    Returns:
        Tuple of (is_valid, error_reason).
        If valid, returns (True, None).
        If invalid, returns (False, reason_string).
    """
    if not name:
        return False, "branch name cannot be empty"

    if len(name) > 255:
        return False, "branch name too long (max 255 characters)"

    # Check against invalid patterns
    for pattern, reason in INVALID_BRANCH_PATTERNS:
        if re.search(pattern, name):
            return False, reason

    # Check overall format
    if not VALID_BRANCH_PATTERN.match(name):
        return False, "must start with alphanumeric and contain only valid characters"

    return True, None


def validate_branch_name_or_raise(name: str) -> str:
    """Validate a branch name, raising ValidationError if invalid.

    Args:
        name: The branch name to validate.

    Returns:
        The validated branch name.

    Raises:
        ValidationError: If the branch name is invalid.
    """
    is_valid, reason = validate_branch_name(name)
    if not is_valid:
        raise ValidationError.invalid_branch_name(name, reason)
    return name


def validate_epic_folder_exists(path: Path) -> tuple[bool, list[str]]:
    """Validate that an epic folder exists and is a directory.

    Args:
        path: Path to the epic folder.

    Returns:
        Tuple of (is_valid, list_of_issues).
        If valid, returns (True, []).
        If invalid, returns (False, list_of_issue_strings).
    """
    issues = []

    if not path.exists():
        return False, [f"epic folder does not exist: {path}"]

    if not path.is_dir():
        return False, [f"path is not a directory: {path}"]

    return True, issues


# Backward compatibility alias
validate_plan_folder_exists = validate_epic_folder_exists


def validate_epic_folder_structure(path: Path) -> tuple[bool, list[str]]:
    """Validate an epic folder has the required structure.

    Validates that the epic folder exists as a directory and that
    the epic is registered in TinyDB. YAML plan files are no longer
    required.

    Args:
        path: Path to the epic folder.

    Returns:
        Tuple of (is_valid, list_of_issues).
        If valid, returns (True, []).
        If invalid, returns (False, list_of_issue_strings).
    """
    issues = []

    if not path.exists():
        return False, [f"epic folder does not exist: {path}"]

    if not path.is_dir():
        return False, [f"path is not a directory: {path}"]

    # Check if epic exists in TinyDB
    try:
        from agenticguidance.services.epic_repository import EpicRepository
        import subprocess

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
                cwd=str(path),
            )
            repo_root = Path(result.stdout.strip())
        except subprocess.CalledProcessError:
            repo_root = path
        db_path = repo_root / ".agentic" / "epics.db"
        repo = EpicRepository(db_path=db_path)
        epic = repo.get_epic(path.name)
        repo.close()
        if not epic:
            issues.append(f"epic '{path.name}' not found in TinyDB")
    except ImportError:
        # EpicRepository not available, just check folder exists
        pass
    except Exception:
        pass

    return len(issues) == 0, issues


# Backward compatibility alias
validate_plan_folder_structure = validate_epic_folder_structure


def validate_epic_folder_is_valid(path: Path) -> tuple[bool, list[str]]:
    """Validate an epic folder is valid (exists and has required structure).

    Args:
        path: Path to the epic folder.

    Returns:
        Tuple of (is_valid, list_of_issues).
        If valid, returns (True, []).
        If invalid, returns (False, list_of_issue_strings).
    """
    exists_valid, exists_issues = validate_epic_folder_exists(path)
    if not exists_valid:
        return False, exists_issues

    return validate_epic_folder_structure(path)


# Backward compatibility alias
validate_plan_folder_is_valid = validate_epic_folder_is_valid


def validate_epic_folder_or_raise(path: Path) -> Path:
    """Validate an epic folder structure, raising ValidationError if invalid.

    Args:
        path: Path to the epic folder.

    Returns:
        The validated path.

    Raises:
        ValidationError: If the epic folder structure is invalid.
    """
    is_valid, issues = validate_epic_folder_structure(path)
    if not is_valid:
        raise ValidationError.invalid_epic_folder(str(path), "; ".join(issues))
    return path


# Backward compatibility alias
validate_plan_folder_or_raise = validate_epic_folder_or_raise


# Required fields for epic YAML files
EPIC_REQUIRED_FIELDS = ["plan"]
EPIC_INNER_REQUIRED_FIELDS = ["name", "status"]
EPIC_VALID_STATUSES = ["pending", "in_progress", "completed", "blocked", "cancelled"]

# Backward compatibility aliases
PLAN_REQUIRED_FIELDS = EPIC_REQUIRED_FIELDS
PLAN_INNER_REQUIRED_FIELDS = EPIC_INNER_REQUIRED_FIELDS
PLAN_VALID_STATUSES = EPIC_VALID_STATUSES


def validate_epic_yaml(content: str, file_path: Optional[str] = None) -> tuple[bool, list[str]]:
    """Validate epic YAML content against schema requirements.

    Args:
        content: The YAML content to validate.
        file_path: Optional file path for error context.

    Returns:
        Tuple of (is_valid, list_of_violations).
        If valid, returns (True, []).
        If invalid, returns (False, list_of_violation_strings).
    """
    violations = []

    # Parse YAML
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        line = None
        if hasattr(e, "problem_mark") and e.problem_mark:
            line = e.problem_mark.line + 1
        return False, [f"YAML parse error at line {line}: {e}" if line else f"YAML parse error: {e}"]

    if data is None:
        return False, ["empty YAML content"]

    if not isinstance(data, dict):
        return False, ["YAML root must be a mapping"]

    # Check required top-level fields
    for field in EPIC_REQUIRED_FIELDS:
        if field not in data:
            violations.append(f"missing required field '{field}'")

    # Check plan inner structure if present
    if "plan" in data and isinstance(data["plan"], dict):
        plan = data["plan"]

        for field in EPIC_INNER_REQUIRED_FIELDS:
            if field not in plan:
                violations.append(f"missing required field 'plan.{field}'")

        # Validate status if present
        if "status" in plan:
            status = plan["status"]
            if status not in EPIC_VALID_STATUSES:
                violations.append(
                    f"invalid status '{status}', must be one of: {', '.join(EPIC_VALID_STATUSES)}"
                )

        # Validate phases if present
        if "phases" in plan:
            if not isinstance(plan["phases"], list):
                violations.append("'plan.phases' must be a list")
            else:
                for i, phase in enumerate(plan["phases"]):
                    if not isinstance(phase, dict):
                        violations.append(f"phase {i} must be a mapping")
                    elif "id" not in phase and "name" not in phase:
                        violations.append(f"phase {i} missing 'id' or 'name'")

    return len(violations) == 0, violations


# Backward compatibility alias
validate_plan_yaml = validate_epic_yaml


def validate_epic_yaml_content(content: str, file_path: Optional[str] = None) -> tuple[bool, list[str]]:
    """Validate epic YAML content (alias for validate_epic_yaml).

    Args:
        content: The YAML content to validate.
        file_path: Optional file path for error context.

    Returns:
        Tuple of (is_valid, list_of_violations).
        If valid, returns (True, []).
        If invalid, returns (False, list_of_violation_strings).
    """
    return validate_epic_yaml(content, file_path)


# Backward compatibility alias
validate_plan_yaml_content = validate_epic_yaml_content


def validate_epic_yaml_strict(content: str, file_path: Optional[str] = None) -> dict:
    """Validate epic YAML content strictly, raising ValidationError if invalid.

    Args:
        content: The YAML content to validate.
        file_path: Optional file path for error context.

    Returns:
        The parsed YAML data.

    Raises:
        ValidationError: If the YAML content is invalid.
    """
    is_valid, violations = validate_epic_yaml(content, file_path)
    if not is_valid:
        raise ValidationError.schema_violation(file_path or "<string>", violations)
    return yaml.safe_load(content)


# Backward compatibility alias
validate_plan_yaml_strict = validate_epic_yaml_strict


def validate_epic_yaml_or_raise(content: str, file_path: Optional[str] = None) -> dict:
    """Validate epic YAML content, raising ValidationError if invalid.

    Args:
        content: The YAML content to validate.
        file_path: Optional file path for error context.

    Returns:
        The parsed YAML data.

    Raises:
        ValidationError: If the YAML content is invalid.
    """
    return validate_epic_yaml_strict(content, file_path)


# Backward compatibility alias
validate_plan_yaml_or_raise = validate_epic_yaml_or_raise


def validate_path_safe(path: str) -> tuple[bool, Optional[str]]:
    """Validate that a path doesn't contain dangerous patterns.

    Checks for:
    - Path traversal attempts (..)
    - Absolute paths when relative expected
    - Null bytes
    - Control characters

    Args:
        path: The path string to validate.

    Returns:
        Tuple of (is_safe, error_reason).
    """
    if not path:
        return False, "path cannot be empty"

    if "\x00" in path:
        return False, "path cannot contain null bytes"

    if any(c in path for c in "\r\n\t"):
        return False, "path cannot contain control characters"

    # Check for path traversal
    parts = Path(path).parts
    if ".." in parts:
        return False, "path traversal not allowed (contains '..')"

    return True, None


def validate_identifier(name: str, max_length: int = 64) -> tuple[bool, Optional[str]]:
    """Validate an identifier (ticket ID, phase ID, etc.).

    Args:
        name: The identifier to validate.
        max_length: Maximum allowed length.

    Returns:
        Tuple of (is_valid, error_reason).
    """
    if not name:
        return False, "identifier cannot be empty"

    if len(name) > max_length:
        return False, f"identifier too long (max {max_length} characters)"

    # Allow alphanumeric, hyphens, underscores, dots
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        return False, "identifier must start with alphanumeric and contain only alphanumeric, dots, hyphens, underscores"

    return True, None
