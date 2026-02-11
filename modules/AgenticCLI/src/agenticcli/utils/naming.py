"""Plan folder naming utilities.

Implements the YYMMDDXX_description naming convention for plan folders.
Tool-offloading pattern: deterministic naming belongs in CLI, not agent guidance.
"""

import re
from datetime import datetime
from pathlib import Path


def get_worktree_id(worktree_path: Path, branch: str | None = None) -> str:
    """Extract 2-character worktree identifier from path or registry.

    Algorithm:
    1. If branch provided, look up abbreviation from worktree registry
    2. Parse worktree path (e.g., /home/code/AgenticEngineering-agenticguidance)
    3. Extract suffix after last hyphen (e.g., agenticguidance)
    4. Take first 2 characters, uppercase (e.g., AG)

    Special cases:
    - No hyphen in path: Use first 2 chars of directory name
    - Empty result: Default to "XX"

    Args:
        worktree_path: Path to the worktree directory.
        branch: Optional branch name for registry lookup.

    Returns:
        2-character uppercase identifier (e.g., "AG", "CL", "XX").

    Examples:
        >>> get_worktree_id(Path("/home/code/AgenticEngineering-agenticguidance"))
        'AG'
        >>> get_worktree_id(Path("/home/code/AgenticEngineering-agentic-cli"))
        'CL'
        >>> get_worktree_id(Path("/home/code/MyProject"))
        'MY'
    """
    # Try extracting 2-letter code directly from branch name (YYMMDDXX pattern)
    if branch:
        branch_match = re.match(r"^\d{6}([A-Za-z]{2})", branch)
        if branch_match:
            return branch_match.group(1).upper()

    # Try registry lookup if branch is provided
    if branch:
        try:
            from agenticcli.commands.worktree import load_worktree_registry, lookup_abbreviation
            # Try loading registry from worktree_path or its parent paths
            for candidate in [worktree_path, worktree_path.parent]:
                registry = load_worktree_registry(candidate)
                if registry:
                    abbr = lookup_abbreviation(registry, branch)
                    if abbr:
                        return abbr[:2].upper()
        except ImportError:
            pass

    dir_name = worktree_path.name

    if "-" in dir_name:
        # Extract suffix after last hyphen
        suffix = dir_name.rsplit("-", 1)[-1]
    else:
        # No hyphen: use directory name
        suffix = dir_name

    # If suffix matches YYMMDDXX pattern, extract just the 2-letter code
    suffix_match = re.match(r"^\d{6}([A-Za-z]{2})", suffix)
    if suffix_match:
        return suffix_match.group(1).upper()

    if len(suffix) >= 2:
        return suffix[:2].upper()
    elif len(suffix) == 1:
        return (suffix + "X").upper()
    else:
        return "XX"


def sanitize_description(description: str) -> str:
    """Sanitize description for use in folder names.

    Rules:
    - Lowercase
    - Replace spaces with underscores
    - Remove special characters except underscore
    - Max 50 characters

    Args:
        description: Raw description text.

    Returns:
        Sanitized description suitable for folder names.

    Examples:
        >>> sanitize_description("My Feature Name")
        'my_feature_name'
        >>> sanitize_description("Fix: Bug #123!")
        'fix_bug_123'
        >>> sanitize_description("A" * 100)
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    """
    # Lowercase
    result = description.lower()

    # Replace spaces and hyphens with underscores
    result = result.replace(" ", "_").replace("-", "_")

    # Remove non-alphanumeric except underscore
    result = re.sub(r"[^a-z0-9_]", "", result)

    # Collapse multiple underscores
    result = re.sub(r"_+", "_", result)

    # Strip leading/trailing underscores
    result = result.strip("_")

    # Max 50 characters
    if len(result) > 50:
        result = result[:50].rstrip("_")

    return result


def generate_plan_folder_name(
    worktree_path: Path,
    description: str,
    date: datetime | None = None,
    branch: str | None = None,
) -> str:
    """Generate plan folder name in YYMMDDXX_description format.

    Args:
        worktree_path: Path to the worktree directory.
        description: Human-readable description of the plan.
        date: Optional date to use (defaults to today).
        branch: Optional branch name for worktree registry lookup.

    Returns:
        Folder name matching pattern YYMMDDXX_description.

    Examples:
        >>> generate_plan_folder_name(
        ...     Path("/home/code/AgenticEngineering-agenticguidance"),
        ...     "naming convention audit"
        ... )
        '260115AG_naming_convention_audit'
        >>> generate_plan_folder_name(
        ...     Path("/home/code/AgenticEngineering-260208PN"),
        ...     "phone notifications",
        ...     branch="260208PN"
        ... )
        '260208PN_phone_notifications'
    """
    if date is None:
        date = datetime.now()

    date_prefix = date.strftime("%y%m%d")
    worktree_id = get_worktree_id(worktree_path, branch=branch)
    sanitized_desc = sanitize_description(description)

    return f"{date_prefix}{worktree_id}_{sanitized_desc}"


def validate_plan_folder_name(name: str) -> tuple[bool, str | None]:
    """Validate that a folder name matches the YYMMDDXX_description pattern.

    Args:
        name: Folder name to validate.

    Returns:
        Tuple of (is_valid, error_message).
        If valid, error_message is None.

    Examples:
        >>> validate_plan_folder_name("260115AG_naming_convention_audit")
        (True, None)
        >>> validate_plan_folder_name("invalid-name")
        (False, "Name must match pattern YYMMDDXX_description")
    """
    # Pattern: 6 digits + 2 uppercase letters + underscore + lowercase/digits/underscores
    pattern = r"^\d{6}[A-Z]{2}_[a-z0-9_]+$"

    if re.match(pattern, name):
        return True, None
    else:
        return False, "Name must match pattern YYMMDDXX_description (e.g., 260115AG_my_feature)"


def parse_plan_folder_name(name: str) -> dict[str, str] | None:
    """Parse a plan folder name into its components.

    Args:
        name: Folder name to parse.

    Returns:
        Dictionary with date, worktree_id, description keys, or None if invalid.

    Examples:
        >>> parse_plan_folder_name("260115AG_naming_convention_audit")
        {'date': '260115', 'worktree_id': 'AG', 'description': 'naming_convention_audit'}
    """
    is_valid, _ = validate_plan_folder_name(name)
    if not is_valid:
        return None

    return {
        "date": name[:6],
        "worktree_id": name[6:8],
        "description": name[9:],
    }
