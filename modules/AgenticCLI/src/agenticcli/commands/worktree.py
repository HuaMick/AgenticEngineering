"""Worktree system - DEPRECATED AND REMOVED.

All development now happens on the main branch.
This module exists only to provide clear error messages if any code
still tries to import or use worktree functionality.
"""

import sys


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


# Stubs for commonly-imported functions
cleanup_worktree_if_idle = _deprecated
find_idle_worktrees = _deprecated
create_planning_folder = _deprecated
load_worktree_registry = _deprecated
lookup_abbreviation = _deprecated
find_workspace_file = _deprecated
update_workspace_add = _deprecated
cmd_sync = _deprecated
