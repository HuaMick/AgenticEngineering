"""Preferences command - top-level command for preference management.

Promotes preference management to first-class command: `agentic prefs`.
"""

import sys


def handle(args, ctx=None):
    """Route preferences subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.prefs_command == "get":
        cmd_get(args, ctx)
    elif args.prefs_command == "set":
        cmd_set(args, ctx)
    elif args.prefs_command == "list":
        cmd_list(args, ctx)
    elif args.prefs_command == "delete":
        cmd_delete(args, ctx)
    elif args.prefs_command == "clear":
        cmd_clear(args, ctx)
    else:
        print("Usage: agentic prefs <get|set|list|delete|clear>", file=sys.stderr)
        sys.exit(1)


def _get_workflow(ctx):
    """Get ConfigWorkflow from context or default."""
    from pathlib import Path

    from agenticcli.workflows.config_workflow import ConfigWorkflow

    if ctx and ctx.config_dir:
        return ConfigWorkflow(ctx.config_dir)

    import os

    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        config_dir = Path(xdg_config) / "agenticcli"
    else:
        config_dir = Path.home() / ".config" / "agenticcli"

    return ConfigWorkflow(config_dir)


def cmd_get(args, ctx=None):
    """Get a preference value."""
    import json

    from agenticcli.console import console, is_json_output, print_error, print_json

    workflow = _get_workflow(ctx)
    result = workflow.get_pref(args.key)

    if not result.success:
        if is_json_output():
            print_json({"error": result.message, "key": args.key})
        else:
            print_error(result.message)
        sys.exit(1)

    value = result.data["value"]

    if is_json_output():
        print_json({"key": args.key, "value": value})
    elif isinstance(value, (dict, list)):
        console.print(json.dumps(value, indent=2))
    else:
        console.print(f"[cyan]{args.key}[/cyan] = [green]{value}[/green]")


def cmd_set(args, ctx=None):
    """Set a preference value."""
    from agenticcli.console import is_json_output, print_json, print_success

    workflow = _get_workflow(ctx)
    result = workflow.set_pref(args.key, args.value)

    if is_json_output():
        print_json({"key": args.key, "value": result.data["value"], "set": True})
    else:
        print_success(f"Set {args.key} = {result.data['value']}")


def cmd_list(args, ctx=None):
    """List all preferences."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_header,
        print_info,
        print_json,
        print_tree,
    )

    workflow = _get_workflow(ctx)
    result = workflow.list_prefs()

    if not result.success:
        if is_json_output():
            print_json({"error": result.message})
        else:
            print_info(result.message)
        return

    prefs = result.data["preferences"]

    if is_json_output():
        print_json({"path": result.data["path"], "preferences": prefs})
    else:
        print_header(f"Preferences: {result.data['path']}")
        if prefs:
            print_tree("preferences", prefs)
        else:
            console.print("[dim](empty)[/dim]")


def cmd_delete(args, ctx=None):
    """Delete a preference value."""
    from agenticcli.console import is_json_output, print_error, print_json, print_success

    workflow = _get_workflow(ctx)
    result = workflow.delete_pref(args.key)

    if not result.success:
        if is_json_output():
            print_json({"error": result.message, "key": args.key})
        else:
            print_error(result.message)
        sys.exit(1)

    if is_json_output():
        print_json({"key": args.key, "deleted": True})
    else:
        print_success(f"Deleted {args.key}")


def cmd_clear(args, ctx=None):
    """Clear all preferences."""
    from agenticcli.console import console, is_json_output, print_json, print_success, print_warning

    workflow = _get_workflow(ctx)

    # Confirm before clearing (unless JSON mode or --force)
    if not is_json_output() and not getattr(args, "force", False):
        console.print("[yellow]This will delete all preferences.[/yellow]")
        response = input("Are you sure? [y/N] ")
        if response.lower() != "y":
            console.print("[dim]Cancelled.[/dim]")
            return

    result = workflow.clear_prefs()

    if not result.success:
        if is_json_output():
            print_json({"error": result.message})
        else:
            print_warning(result.message)
        return

    if is_json_output():
        print_json({"cleared": True})
    else:
        print_success("All preferences cleared.")
