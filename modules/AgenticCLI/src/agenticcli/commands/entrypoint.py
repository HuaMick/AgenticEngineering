"""Entrypoint commands for discovering and executing workflow entrypoints.

Provides CLI commands to list, show, and execute entrypoint files that define
workflow starting points for orchestration and planning.

Commands:
    list: List all available entrypoints
    show: Display contents of an entrypoint file
    execute: Execute an entrypoint with variable substitution
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml


def handle(args, ctx=None):
    """Route entrypoint subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.entrypoint_command == "list":
        cmd_list(args, ctx)
    elif args.entrypoint_command == "show":
        cmd_show(args, ctx)
    elif args.entrypoint_command == "execute":
        cmd_execute(args, ctx)
    else:
        print(
            "Usage: agentic entrypoint <list|show|execute> ...",
            file=sys.stderr,
        )
        sys.exit(1)


def _get_entrypoints_dirs() -> list[Path]:
    """Get list of directories to search for entrypoint files.

    Returns:
        List of Path objects for entrypoint directories, in priority order:
        1. Current working directory: .claude/entrypoints/
        2. Project root: modules/AgenticGuidance/entrypoints/
    """
    dirs = []

    # 1. Current working directory: .claude/entrypoints/
    cwd_entrypoints = Path.cwd() / ".claude" / "entrypoints"
    if cwd_entrypoints.exists() and cwd_entrypoints.is_dir():
        dirs.append(cwd_entrypoints)

    # 2. Project root: modules/AgenticGuidance/entrypoints/
    # Try to find the project root by looking for AgenticGuidance module
    # Start from cwd and walk up to find the project root
    current = Path.cwd()
    while current != current.parent:
        guidance_entrypoints = current / "modules" / "AgenticGuidance" / "entrypoints"
        if guidance_entrypoints.exists() and guidance_entrypoints.is_dir():
            dirs.append(guidance_entrypoints)
            break
        current = current.parent

    return dirs


def _normalize_entrypoint_name(name: str) -> str:
    """Normalize entrypoint name by removing leading underscore if present.

    Args:
        name: Entrypoint name (e.g., "_plan_build" or "plan_build")

    Returns:
        Normalized name without leading underscore.
    """
    return name.lstrip("_")


def _get_entrypoint_name_from_file(filepath: Path) -> str:
    """Extract entrypoint name from filename.

    Args:
        filepath: Path to entrypoint file.

    Returns:
        Entrypoint name without underscore prefix or extension.
    """
    # Files named _<name>.yml or _<name>.md
    stem = filepath.stem  # e.g., "_plan_build"
    return stem.lstrip("_")  # e.g., "plan_build"


def _find_entrypoint(name: str) -> Optional[Path]:
    """Resolve entrypoint name to file path.

    Args:
        name: Entrypoint name (with or without underscore prefix).

    Returns:
        Path to the entrypoint file, or None if not found.
    """
    normalized = _normalize_entrypoint_name(name)
    dirs = _get_entrypoints_dirs()

    for dir_path in dirs:
        # Try .yml first, then .md
        for ext in [".yml", ".yaml", ".md"]:
            filepath = dir_path / f"_{normalized}{ext}"
            if filepath.exists():
                return filepath

    return None


def _extract_description(filepath: Path) -> str:
    """Extract description from entrypoint file.

    For YAML files: Extract from entrypoint.goal or entrypoint.description
    For Markdown files: Extract first comment line or heading

    Args:
        filepath: Path to entrypoint file.

    Returns:
        Description string, or empty string if not found.
    """
    try:
        content = filepath.read_text()

        if filepath.suffix in (".yml", ".yaml"):
            data = yaml.safe_load(content)
            if data and isinstance(data, dict):
                entrypoint = data.get("entrypoint", {})
                # Prefer goal, fallback to description
                return entrypoint.get("goal", entrypoint.get("description", ""))

        elif filepath.suffix == ".md":
            # Try to get first heading or first non-empty line
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("#"):
                    # Remove markdown heading markers
                    return line.lstrip("#").strip()
                elif line and not line.startswith("<!--"):
                    return line[:100]  # Truncate long lines

    except Exception:
        pass

    return ""


def _list_entrypoints() -> list[dict]:
    """List all available entrypoints.

    Returns:
        List of dicts with entrypoint info:
        - name: Entrypoint name (without underscore)
        - path: Full path to file
        - type: File extension (yml, yaml, md)
        - description: Extracted description
    """
    entrypoints = []
    seen_names = set()  # Track seen names to avoid duplicates

    dirs = _get_entrypoints_dirs()

    for dir_path in dirs:
        for filepath in sorted(dir_path.iterdir()):
            if not filepath.is_file():
                continue

            # Check for entrypoint naming convention: _<name>.<ext>
            if not filepath.name.startswith("_"):
                continue

            if filepath.suffix not in (".yml", ".yaml", ".md"):
                continue

            name = _get_entrypoint_name_from_file(filepath)

            # Skip duplicates (first found wins)
            if name in seen_names:
                continue
            seen_names.add(name)

            entrypoints.append({
                "name": f"_{name}",  # Include underscore in display name
                "path": str(filepath),
                "type": filepath.suffix.lstrip("."),
                "description": _extract_description(filepath),
            })

    return entrypoints


def cmd_list(args, ctx=None):
    """List all available entrypoints.

    Args:
        args: Parsed arguments.
        ctx: CLI context.
    """
    from agenticcli.console import console, is_json_output, print_json

    entrypoints = _list_entrypoints()
    json_output = is_json_output()

    if json_output:
        print_json({
            "entrypoints": entrypoints,
            "count": len(entrypoints),
        })
    else:
        console.print("\n[bold]Available Entrypoints[/bold]")
        console.print("=" * 21)

        if not entrypoints:
            console.print("  [dim]No entrypoints found.[/dim]")
        else:
            # Calculate column widths
            max_name_len = max(len(ep["name"]) for ep in entrypoints)
            name_width = max(max_name_len, 16)

            for ep in entrypoints:
                name = ep["name"]
                desc = ep["description"][:60] + "..." if len(ep["description"]) > 60 else ep["description"]
                console.print(f"  {name:<{name_width}}  {desc}")

        console.print()


def cmd_show(args, ctx=None):
    """Display full contents of an entrypoint file.

    Args:
        args: Parsed arguments with required name.
        ctx: CLI context.
    """
    from agenticcli.console import is_json_output, print_error, print_json

    name = args.name
    json_output = is_json_output()

    filepath = _find_entrypoint(name)

    if not filepath:
        print_error(f"Entrypoint not found: {name}")
        print(
            f"Hint: Use 'agentic entrypoint list' to see available entrypoints.",
            file=sys.stderr,
        )
        sys.exit(1)

    content = filepath.read_text()

    if json_output:
        print_json({
            "name": f"_{_normalize_entrypoint_name(name)}",
            "path": str(filepath),
            "type": filepath.suffix.lstrip("."),
            "content": content,
        })
    else:
        print(content)


def cmd_execute(args, ctx=None):
    """Execute an entrypoint with variable substitution.

    Reads the entrypoint file, applies variable substitution, and outputs
    the processed content to stdout.

    Args:
        args: Parsed arguments with:
            - name: Entrypoint name (required)
            - vars: List of KEY=VALUE pairs (optional)
            - context: Additional context text to prepend (optional)
        ctx: CLI context.
    """
    from agenticcli.console import is_json_output, print_error, print_json

    name = args.name
    var_pairs = getattr(args, "vars", None) or []
    context_text = getattr(args, "context", None)
    json_output = is_json_output()

    filepath = _find_entrypoint(name)

    if not filepath:
        print_error(f"Entrypoint not found: {name}")
        print(
            f"Hint: Use 'agentic entrypoint list' to see available entrypoints.",
            file=sys.stderr,
        )
        sys.exit(1)

    content = filepath.read_text()

    # Parse --vars KEY=VALUE pairs into dict
    variables = {}
    for pair in var_pairs:
        if "=" in pair:
            key, value = pair.split("=", 1)
            variables[key.strip()] = value.strip()
        else:
            print_error(f"Invalid variable format: {pair} (expected KEY=VALUE)")
            sys.exit(1)

    # Add built-in variables
    variables["TIMESTAMP"] = datetime.now().isoformat()

    # Apply variable substitution
    # Support both {{VAR}} and {{ VAR }} with optional whitespace
    def replace_var(match):
        var_name = match.group(1).strip()
        return variables.get(var_name, match.group(0))  # Keep original if not found

    content = re.sub(r"\{\{\s*(\w+)\s*\}\}", replace_var, content)

    # Prepend context if provided
    if context_text:
        content = f"# Context\n{context_text}\n\n---\n\n{content}"

    if json_output:
        print_json({
            "name": f"_{_normalize_entrypoint_name(name)}",
            "path": str(filepath),
            "variables_applied": list(variables.keys()),
            "context_prepended": context_text is not None,
            "content": content,
        })
    else:
        print(content)
