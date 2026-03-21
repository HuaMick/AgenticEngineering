"""Preferences command - top-level command for preference management.

Promotes preference management to first-class command: `agentic prefs`.

DEPRECATED: Preference logic is now canonical in
agenticcli.commands.config (the unified config+preferences handler).
This module delegates all subcommands to config's implementations so
that both `agentic prefs` and `agentic config` stay in sync.
"""

import sys


def handle(args, ctx=None):
    """Route preferences subcommands.

    Delegates to config module which is the canonical implementation.

    Args:
        args: Parsed command arguments with args.prefs_command set.
        ctx: Optional CLIContext for dependency injection.
    """
    from agenticcli.commands.config import (
        cmd_prefs_clear,
        cmd_prefs_delete,
        cmd_prefs_get,
        cmd_prefs_list,
        cmd_prefs_set,
    )

    # Map prefs_command attribute to a synthetic args object that config
    # functions expect (they read args.key, args.value, etc. — same attrs).
    # We also need args.config_command to be unused by those functions, so
    # we simply pass args through as-is; the cmd_prefs_* functions only
    # access args.key / args.value / args.force.
    if args.prefs_command == "get":
        cmd_prefs_get(args, ctx)
    elif args.prefs_command == "set":
        cmd_prefs_set(args, ctx)
    elif args.prefs_command == "list":
        cmd_prefs_list(args, ctx)
    elif args.prefs_command == "delete":
        cmd_prefs_delete(args, ctx)
    elif args.prefs_command == "clear":
        cmd_prefs_clear(args, ctx)
    else:
        print("Usage: agentic prefs <get|set|list|delete|clear>", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Public aliases kept for backward compatibility with any direct callers.
# All implementations live in agenticcli.commands.config.
# ---------------------------------------------------------------------------

def _get_workflow(ctx):
    """Get ConfigWorkflow — delegates to config module."""
    from agenticcli.commands.config import _get_workflow as _cfg_get_workflow
    return _cfg_get_workflow(ctx)


def cmd_get(args, ctx=None):
    """Get a preference value (alias for config.cmd_prefs_get)."""
    from agenticcli.commands.config import cmd_prefs_get
    return cmd_prefs_get(args, ctx)


def cmd_set(args, ctx=None):
    """Set a preference value (alias for config.cmd_prefs_set)."""
    from agenticcli.commands.config import cmd_prefs_set
    return cmd_prefs_set(args, ctx)


def cmd_list(args, ctx=None):
    """List all preferences (alias for config.cmd_prefs_list)."""
    from agenticcli.commands.config import cmd_prefs_list
    return cmd_prefs_list(args, ctx)


def cmd_delete(args, ctx=None):
    """Delete a preference value (alias for config.cmd_prefs_delete)."""
    from agenticcli.commands.config import cmd_prefs_delete
    return cmd_prefs_delete(args, ctx)


def cmd_clear(args, ctx=None):
    """Clear all preferences (alias for config.cmd_prefs_clear)."""
    from agenticcli.commands.config import cmd_prefs_clear
    return cmd_prefs_clear(args, ctx)
