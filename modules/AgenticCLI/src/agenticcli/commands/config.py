"""Configuration and preferences commands.

Handles user configuration stored in ~/.config/agenticcli/.
"""

import json
import os
import sys
from pathlib import Path

import yaml


def get_config_dir() -> Path:
    """Get the configuration directory path.

    Uses XDG_CONFIG_HOME if set, otherwise ~/.config/agenticcli/.
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "agenticcli"
    return Path.home() / ".config" / "agenticcli"


def ensure_config_dir() -> Path:
    """Ensure the config directory exists and return its path."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def handle(args):
    """Route config subcommands."""
    if args.config_command == "show":
        cmd_show(args)
    elif args.config_command == "init":
        cmd_init(args)
    elif args.config_command == "get":
        cmd_prefs_get(args)
    elif args.config_command == "set":
        cmd_prefs_set(args)
    elif args.config_command == "list":
        cmd_prefs_list(args)
    elif args.config_command == "delete":
        cmd_prefs_delete(args)
    else:
        print("Usage: agentic config <show|init|get|set|list|delete>", file=sys.stderr)
        sys.exit(1)


def cmd_show(args):
    """Display current configuration."""
    from agenticcli.console import console, is_json_output, print_header, print_json, print_tree

    config_dir = get_config_dir()
    config_file = config_dir / "config.yml"

    if not config_file.exists():
        if is_json_output():
            print_json({"error": "No configuration found", "hint": "Run 'agentic config init'"})
        else:
            console.print("[yellow]No configuration found.[/yellow] Run 'agentic config init' to create one.")
        return

    content = yaml.safe_load(config_file.read_text())

    if is_json_output():
        print_json({"path": str(config_file), "config": content or {}})
    else:
        print_header(f"Configuration: {config_file}")
        if content:
            print_tree("config", content)
        else:
            console.print("[dim](empty)[/dim]")


def cmd_init(args):
    """Initialize configuration."""
    from agenticcli.console import console, is_json_output, print_json, print_success, print_warning

    config_dir = ensure_config_dir()
    config_file = config_dir / "config.yml"
    prefs_file = config_dir / "preferences.yml"

    if config_file.exists():
        if is_json_output():
            print_json({"error": "Configuration already exists", "path": str(config_file)})
            return
        print_warning(f"Configuration already exists: {config_file}")
        response = input("Overwrite? [y/N] ")
        if response.lower() != "y":
            console.print("[dim]Aborted[/dim]")
            return

    # Create default config
    default_config = {
        "version": 1,
        "defaults": {
            "repo_abbreviation": "AE",
            "base_branch": "main",
        },
    }

    with open(config_file, "w") as f:
        yaml.dump(default_config, f, default_flow_style=False)

    # Create empty preferences if not exists
    created_prefs = False
    if not prefs_file.exists():
        default_prefs = {
            "worktree": {
                "default_base": "main",
            },
            "plan": {
                "auto_scaffold": True,
            },
        }
        with open(prefs_file, "w") as f:
            yaml.dump(default_prefs, f, default_flow_style=False)
        created_prefs = True

    if is_json_output():
        result = {"config_file": str(config_file), "created": True}
        if created_prefs:
            result["prefs_file"] = str(prefs_file)
        print_json(result)
    else:
        print_success(f"Created configuration: {config_file}")
        if created_prefs:
            print_success(f"Created preferences: {prefs_file}")


def _get_nested_value(data: dict, key: str):
    """Get a value using dot notation (e.g., 'worktree.default_base')."""
    keys = key.split(".")
    value = data
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return None
    return value


def _set_nested_value(data: dict, key: str, value):
    """Set a value using dot notation (e.g., 'worktree.default_base')."""
    keys = key.split(".")
    target = data
    for k in keys[:-1]:
        if k not in target:
            target[k] = {}
        target = target[k]
    target[keys[-1]] = value


def _delete_nested_value(data: dict, key: str) -> bool:
    """Delete a value using dot notation (e.g., 'worktree.default_base').

    Returns True if the key was found and deleted, False otherwise.
    """
    keys = key.split(".")
    target = data
    for k in keys[:-1]:
        if isinstance(target, dict) and k in target:
            target = target[k]
        else:
            return False

    if isinstance(target, dict) and keys[-1] in target:
        del target[keys[-1]]
        return True
    return False


def cmd_prefs_get(args):
    """Get a preference value."""
    from agenticcli.console import console, is_json_output, print_error, print_json

    config_dir = get_config_dir()
    prefs_file = config_dir / "preferences.yml"

    if not prefs_file.exists():
        print_error("No preferences found. Run 'agentic config init' to create them.")
        sys.exit(1)

    prefs = yaml.safe_load(prefs_file.read_text())
    if not prefs:
        prefs = {}

    value = _get_nested_value(prefs, args.key)
    if value is None:
        print_error(f"Key not found: {args.key}")
        sys.exit(1)

    if is_json_output():
        print_json({"key": args.key, "value": value})
    elif isinstance(value, (dict, list)):
        console.print(json.dumps(value, indent=2))
    else:
        console.print(f"[cyan]{args.key}[/cyan] = [green]{value}[/green]")


def cmd_prefs_set(args):
    """Set a preference value."""
    from agenticcli.console import is_json_output, print_json, print_success

    config_dir = ensure_config_dir()
    prefs_file = config_dir / "preferences.yml"

    if prefs_file.exists():
        prefs = yaml.safe_load(prefs_file.read_text())
        if not prefs:
            prefs = {}
    else:
        prefs = {}

    # Parse value (try JSON first, then use as string)
    try:
        value = json.loads(args.value)
    except json.JSONDecodeError:
        value = args.value

    _set_nested_value(prefs, args.key, value)

    with open(prefs_file, "w") as f:
        yaml.dump(prefs, f, default_flow_style=False)

    if is_json_output():
        print_json({"key": args.key, "value": value, "set": True})
    else:
        print_success(f"Set {args.key} = {args.value}")


def cmd_prefs_list(args):
    """List all preferences."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_header,
        print_info,
        print_json,
        print_tree,
    )

    config_dir = get_config_dir()
    prefs_file = config_dir / "preferences.yml"

    if not prefs_file.exists():
        if is_json_output():
            print_json({"error": "No preferences found", "hint": "Run 'agentic config init'"})
        else:
            print_info("No preferences found. Run 'agentic config init' to create them.")
        return

    prefs = yaml.safe_load(prefs_file.read_text())

    if is_json_output():
        print_json({"path": str(prefs_file), "preferences": prefs or {}})
    else:
        print_header(f"Preferences: {prefs_file}")
        if prefs:
            print_tree("preferences", prefs)
        else:
            console.print("[dim](empty)[/dim]")


def cmd_prefs_delete(args):
    """Delete a preference value."""
    from agenticcli.console import is_json_output, print_error, print_json, print_success

    config_dir = get_config_dir()
    prefs_file = config_dir / "preferences.yml"

    if not prefs_file.exists():
        print_error("No preferences found. Run 'agentic config init' to create them.")
        sys.exit(1)

    prefs = yaml.safe_load(prefs_file.read_text())
    if not prefs:
        prefs = {}

    if not _delete_nested_value(prefs, args.key):
        print_error(f"Key not found: {args.key}")
        sys.exit(1)

    with open(prefs_file, "w") as f:
        yaml.dump(prefs, f, default_flow_style=False)

    if is_json_output():
        print_json({"key": args.key, "deleted": True})
    else:
        print_success(f"Deleted {args.key}")
