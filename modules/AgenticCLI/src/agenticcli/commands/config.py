# story: US-SET-005
"""Unified configuration and preferences handler.

This is the single source of truth for both `agentic config` and
`agentic prefs` commands. Preference subcommands (get/set/list/delete/clear)
delegate to ConfigWorkflow for consistent behavior. Configuration subcommands
(show/init/show-path/set-path/clear) handle config file management directly.

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


def _get_workflow(ctx):
    """Get ConfigWorkflow from context or defaults.

    This is the canonical way to obtain a ConfigWorkflow for preference
    operations. Used by both this module and preferences.py.
    """
    from agenticguidance.services import ConfigWorkflow

    if ctx and ctx.config_dir:
        return ConfigWorkflow(ctx.config_dir)

    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        config_dir = Path(xdg_config) / "agenticcli"
    else:
        config_dir = Path.home() / ".config" / "agenticcli"

    return ConfigWorkflow(config_dir)


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
    from agenticguidance.services import TieredConfigLoader

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
    from agenticguidance.services import ENV_VAR_MAPPING
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


def cmd_prefs_get(args, ctx=None):
    """Get a preference value (delegates to ConfigWorkflow)."""
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


def cmd_prefs_set(args, ctx=None):
    """Set a preference value (delegates to ConfigWorkflow)."""
    from agenticcli.console import is_json_output, print_json, print_success

    workflow = _get_workflow(ctx)
    result = workflow.set_pref(args.key, args.value)

    if is_json_output():
        print_json({"key": args.key, "value": result.data["value"], "set": True})
    else:
        print_success(f"Set {args.key} = {result.data['value']}")


def cmd_prefs_list(args, ctx=None):
    """List all preferences (delegates to ConfigWorkflow)."""
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


def cmd_prefs_delete(args, ctx=None):
    """Delete a preference value (delegates to ConfigWorkflow)."""
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


def cmd_prefs_clear(args, ctx=None):
    """Clear all preferences (delegates to ConfigWorkflow).

    Used by both `agentic prefs clear` and `agentic config clear`
    when the intent is to remove preference data (not config files).
    """
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


def cmd_clear(args, ctx=None):
    """Clear configuration files (requires --force).

    Note: this clears config.yml and config_path.txt — not preferences.
    To clear preferences, use cmd_prefs_clear or `agentic prefs clear`.
    """
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
