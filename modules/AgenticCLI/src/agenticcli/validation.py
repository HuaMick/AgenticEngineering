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


def validate_plan_folder_structure(path: Path) -> tuple[bool, list[str]]:
    """Validate a plan folder has the required structure.

    Expected structure:
        plan_folder/
        ├── live/           # Required
        │   └── *.yml       # At least one plan file
        ├── completed/      # Optional
        └── analysis/       # Optional

    Args:
        path: Path to the plan folder.

    Returns:
        Tuple of (is_valid, list_of_issues).
        If valid, returns (True, []).
        If invalid, returns (False, list_of_issue_strings).
    """
    issues = []

    if not path.exists():
        return False, [f"plan folder does not exist: {path}"]

    if not path.is_dir():
        return False, [f"path is not a directory: {path}"]

    # Check for live directory
    live_dir = path / "live"
    if not live_dir.exists():
        issues.append("missing 'live' directory")
    elif not live_dir.is_dir():
        issues.append("'live' is not a directory")
    else:
        # Check for at least one YAML file in live
        yaml_files = list(live_dir.glob("*.yml")) + list(live_dir.glob("*.yaml"))
        if not yaml_files:
            issues.append("no YAML files in 'live' directory")

    return len(issues) == 0, issues


def validate_plan_folder_or_raise(path: Path) -> Path:
    """Validate a plan folder structure, raising ValidationError if invalid.

    Args:
        path: Path to the plan folder.

    Returns:
        The validated path.

    Raises:
        ValidationError: If the plan folder structure is invalid.
    """
    is_valid, issues = validate_plan_folder_structure(path)
    if not is_valid:
        raise ValidationError.invalid_plan_folder(str(path), "; ".join(issues))
    return path


# Required fields for plan YAML files
PLAN_REQUIRED_FIELDS = ["plan"]
PLAN_INNER_REQUIRED_FIELDS = ["name", "status"]
PLAN_VALID_STATUSES = ["pending", "in_progress", "completed", "blocked", "cancelled"]


def validate_plan_yaml(content: str, file_path: Optional[str] = None) -> tuple[bool, list[str]]:
    """Validate plan YAML content against schema requirements.

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
    for field in PLAN_REQUIRED_FIELDS:
        if field not in data:
            violations.append(f"missing required field '{field}'")

    # Check plan inner structure if present
    if "plan" in data and isinstance(data["plan"], dict):
        plan = data["plan"]

        for field in PLAN_INNER_REQUIRED_FIELDS:
            if field not in plan:
                violations.append(f"missing required field 'plan.{field}'")

        # Validate status if present
        if "status" in plan:
            status = plan["status"]
            if status not in PLAN_VALID_STATUSES:
                violations.append(
                    f"invalid status '{status}', must be one of: {', '.join(PLAN_VALID_STATUSES)}"
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


def validate_plan_yaml_or_raise(content: str, file_path: Optional[str] = None) -> dict:
    """Validate plan YAML content, raising ValidationError if invalid.

    Args:
        content: The YAML content to validate.
        file_path: Optional file path for error context.

    Returns:
        The parsed YAML data.

    Raises:
        ValidationError: If the YAML content is invalid.
    """
    is_valid, violations = validate_plan_yaml(content, file_path)
    if not is_valid:
        raise ValidationError.schema_violation(file_path or "<string>", violations)
    return yaml.safe_load(content)


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
    """Validate an identifier (task ID, phase ID, etc.).

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
