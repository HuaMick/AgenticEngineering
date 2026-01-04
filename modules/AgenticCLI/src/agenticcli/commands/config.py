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


def handle(args, ctx=None):
    """Route config subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.config_command == "show":
        cmd_show(args, ctx)
    elif args.config_command == "init":
        cmd_init(args, ctx)
    elif args.config_command == "get":
        cmd_prefs_get(args, ctx)
    elif args.config_command == "set":
        cmd_prefs_set(args, ctx)
    elif args.config_command == "list":
        cmd_prefs_list(args, ctx)
    elif args.config_command == "delete":
        cmd_prefs_delete(args, ctx)
    elif args.config_command == "show-path":
        cmd_show_path(args, ctx)
    elif args.config_command == "set-path":
        cmd_set_path(args, ctx)
    elif args.config_command == "clear":
        cmd_clear(args, ctx)
    else:
        print("Usage: agentic config <show|init|get|set|list|delete|show-path|set-path|clear>", file=sys.stderr)
        sys.exit(1)


def cmd_show(args, ctx=None):
    """Display merged configuration with source attribution."""
    from agenticcli.console import console, is_json_output, print_header, print_json
    from agenticcli.workflows.config_workflow import TieredConfigLoader

    # Create tiered config loader from context or defaults
    if ctx:
        loader = ctx.get_tiered_config()
    else:
        config_dir = get_config_dir()
        loader = TieredConfigLoader(
            global_config_path=config_dir / "config.yml",
            project_config_path=None,
        )

    # Get merged config with sources
    merged_with_sources = loader.get_merged_with_sources()

    # Collect source info
    sources = _collect_sources(loader)

    if is_json_output():
        print_json({
            "merged": merged_with_sources,
            "sources": sources,
        })
    else:
        print_header("Configuration (merged)")
        _print_config_tree(merged_with_sources, indent=0)
        console.print()
        _print_sources_summary(sources)


def _collect_sources(loader) -> dict:
    """Collect information about configuration sources."""
    sources = {}

    if loader.global_config_path and loader.global_config_path.exists():
        sources["global"] = str(loader.global_config_path)

    if loader.project_config_path and loader.project_config_path.exists():
        sources["project"] = str(loader.project_config_path)

    # Collect env vars
    from agenticcli.workflows.config_workflow import ENV_VAR_MAPPING
    env_vars = [k for k in ENV_VAR_MAPPING if os.environ.get(k)]
    if env_vars:
        sources["env"] = env_vars

    return sources


def _print_config_tree(data: dict, indent: int = 0) -> None:
    """Print config tree with source attribution."""
    from agenticcli.console import console

    prefix = "  " * indent
    source_colors = {
        "default": "dim",
        "global": "blue",
        "project": "green",
        "environment": "yellow",
        "cli": "magenta",
    }

    for key, value in data.items():
        if isinstance(value, dict) and "value" in value and "source" in value:
            # Leaf node with source
            source = value["source"]
            color = source_colors.get(source, "white")
            path_info = f" ({value['path']})" if value.get("path") else ""
            console.print(f"{prefix}[cyan]{key}:[/cyan] {value['value']} [{color}]{source}{path_info}[/{color}]")
        elif isinstance(value, dict):
            # Nested dict
            console.print(f"{prefix}[cyan]{key}:[/cyan]")
            _print_config_tree(value, indent + 1)
        else:
            console.print(f"{prefix}[cyan]{key}:[/cyan] {value}")


def _print_sources_summary(sources: dict) -> None:
    """Print summary of configuration sources."""
    from agenticcli.console import console

    console.print("[bold]Sources:[/bold]")
    if sources.get("global"):
        console.print(f"  [blue]global[/blue] {sources['global']}")
    if sources.get("project"):
        console.print(f"  [green]project[/green] {sources['project']}")
    if sources.get("env"):
        console.print(f"  [yellow]env[/yellow] {len(sources['env'])} variable(s): {', '.join(sources['env'])}")
    if not sources:
        console.print("  [dim]Using defaults only[/dim]")


def cmd_init(args, ctx=None):
    """Initialize configuration."""
    from agenticcli.console import console, is_json_output, print_json, print_success, print_warning

    if ctx:
        config_dir = ctx.ensure_config_dir()
    else:
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


def cmd_prefs_get(args, ctx=None):
    """Get a preference value."""
    from agenticcli.console import console, is_json_output, print_error, print_json

    config_dir = ctx.config_dir if ctx else get_config_dir()
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


def cmd_prefs_set(args, ctx=None):
    """Set a preference value."""
    from agenticcli.console import is_json_output, print_json, print_success

    if ctx:
        config_dir = ctx.ensure_config_dir()
    else:
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


def cmd_prefs_list(args, ctx=None):
    """List all preferences."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_header,
        print_info,
        print_json,
        print_tree,
    )

    config_dir = ctx.config_dir if ctx else get_config_dir()
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


def cmd_prefs_delete(args, ctx=None):
    """Delete a preference value."""
    from agenticcli.console import is_json_output, print_error, print_json, print_success

    config_dir = ctx.config_dir if ctx else get_config_dir()
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


def cmd_show_path(args, ctx=None):
    """Show all config file paths with existence status."""
    from agenticcli.console import console, is_json_output, print_header, print_json

    config_dir = ctx.config_dir if ctx else get_config_dir()
    global_config = config_dir / "config.yml"
    project_config = ctx.project_config_file if ctx else None
    custom_path_file = config_dir / "config_path.txt"

    # Check for custom path
    custom_path = None
    if custom_path_file.exists():
        custom_path = custom_path_file.read_text().strip()

    paths = []

    # Custom path (highest priority if set)
    if custom_path:
        custom_exists = Path(custom_path).exists()
        paths.append({
            "type": "custom",
            "path": custom_path,
            "exists": custom_exists,
            "priority": 1,
        })

    # Project config
    if project_config:
        paths.append({
            "type": "project",
            "path": str(project_config),
            "exists": project_config.exists(),
            "priority": 2,
        })

    # Global config
    paths.append({
        "type": "global",
        "path": str(global_config),
        "exists": global_config.exists(),
        "priority": 3,
    })

    if is_json_output():
        print_json({"paths": paths})
    else:
        print_header("Config file paths (precedence order)")
        for i, p in enumerate(paths, 1):
            status = "[green]exists[/green]" if p["exists"] else "[red]missing[/red]"
            console.print(f"  {i}. [{status}] {p['type']}: {p['path']}")


def cmd_set_path(args, ctx=None):
    """Set custom config file path."""
    from agenticcli.console import is_json_output, print_error, print_json, print_success

    custom_path = Path(args.path).resolve()

    # Validate path exists
    if not custom_path.exists():
        print_error(f"Path does not exist: {custom_path}")
        sys.exit(1)

    # Validate it's a YAML file
    try:
        yaml.safe_load(custom_path.read_text())
    except yaml.YAMLError as e:
        print_error(f"Invalid YAML file: {e}")
        sys.exit(1)

    # Store custom path
    if ctx:
        config_dir = ctx.ensure_config_dir()
    else:
        config_dir = ensure_config_dir()
    custom_path_file = config_dir / "config_path.txt"
    custom_path_file.write_text(str(custom_path))

    if is_json_output():
        print_json({"custom_path": str(custom_path), "set": True})
    else:
        print_success(f"Custom config path set: {custom_path}")


def cmd_clear(args, ctx=None):
    """Clear configuration (requires --force)."""
    from agenticcli.console import is_json_output, print_error, print_json, print_success

    if not getattr(args, "force", False):
        print_error("This will clear your configuration. Use --force to confirm.")
        sys.exit(1)

    config_dir = ctx.config_dir if ctx else get_config_dir()
    config_file = config_dir / "config.yml"
    custom_path_file = config_dir / "config_path.txt"

    cleared = []

    if config_file.exists():
        config_file.unlink()
        cleared.append(str(config_file))

    if custom_path_file.exists():
        custom_path_file.unlink()
        cleared.append(str(custom_path_file))

    if is_json_output():
        print_json({"cleared": cleared, "success": True})
    else:
        if cleared:
            print_success(f"Cleared: {', '.join(cleared)}")
        else:
            print_success("No configuration files to clear.")
