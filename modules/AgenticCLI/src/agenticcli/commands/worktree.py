"""Worktree system - DEPRECATED AND REMOVED.

All development now happens on the main branch.
This module exists only to provide clear error messages if any code
still tries to import or use worktree functionality.

Epic folder utilities (get_live_epic_folders, create_epic_folder) are provided
here for backward compatibility and use by other modules.
"""

import sys
from datetime import datetime
from pathlib import Path


_DEPRECATION_MSG = (
    "ERROR: The worktree system has been deprecated and removed. "
    "All development now happens on the main branch. "
    "If you see this error, update your agent guidance or CLI scripts "
    "to stop referencing worktree commands."
)


def handle(args, ctx=None):
    """Deprecated worktree command handler."""
    print(_DEPRECATION_MSG, file=sys.stderr)
    sys.exit(1)


def _deprecated(*args, **kwargs):
    raise RuntimeError("Worktree system deprecated and removed.")


# Stubs for commonly-imported functions that are truly deprecated
cleanup_worktree_if_idle = _deprecated
find_idle_worktrees = _deprecated
load_worktree_registry = _deprecated
lookup_abbreviation = _deprecated
find_workspace_file = _deprecated
update_workspace_add = _deprecated
cmd_sync = _deprecated


# ---------------------------------------------------------------------------
# Epic folder utilities
# ---------------------------------------------------------------------------

def get_live_epic_folders(main_wt_path: Path) -> list[str]:
    """Scan docs/epics/live/ in the given path and return epic folder names.

    Args:
        main_wt_path: Path to the repository root or main worktree root.

    Returns:
        Sorted list of directory names under docs/epics/live/.
        Returns empty list if path does not exist.
    """
    epic_dir = main_wt_path / "docs" / "epics" / "live"
    if not epic_dir.exists():
        return []
    return sorted(d.name for d in epic_dir.iterdir() if d.is_dir())


def create_epic_folder(epic_path: Path) -> None:
    """Create an epic folder structure with placeholder files.

    Creates a new epic folder at the given path with a stub ticket_teach.yml
    scaffold file so the epic is immediately recognisable.

    Args:
        epic_path: Absolute or relative path where the epic folder should be
            created.  Parent directories are created as needed.
    """
    epic_path.mkdir(parents=True, exist_ok=True)

    created_date = datetime.now().strftime("%Y-%m-%d")

    stub_header = (
        "# ============================================================================\n"
        "# TEMPLATE FILE - ACTION REQUIRED\n"
        "# ============================================================================\n"
        "# This is a scaffold template created automatically.\n"
        "#\n"
        "# OPTIONS:\n"
        "#   1. POPULATE: Replace TODO sections with actual epic content\n"
        "#   2. DELETE:   Remove this file if not needed for your epic\n"
        "#\n"
        "# A file with _template_status: stub will trigger validation warnings.\n"
        "# Change to _template_status: active once populated.\n"
        "# ============================================================================\n"
    )

    ticket_teach_content = (
        f"{stub_header}\n"
        "_template_status: stub  # Change to 'active' when populated\n"
        "\n"
        "# Epic Teaching / Guidance Plan\n"
        f"# Created: {created_date}\n"
        "# Purpose: Define guidance updates and teaching phases for this epic\n"
        "\n"
        "name: TODO: epic-name\n"
        "status: planning\n"
        f"created: \"{created_date}\"\n"
        "\n"
        "objective: |\n"
        "  TODO: Describe what this epic aims to accomplish.\n"
        "\n"
        "phases: []\n"
    )

    teach_file = epic_path / "ticket_teach.yml"
    if not teach_file.exists():
        teach_file.write_text(ticket_teach_content)


