"""Input file validation and resolution commands.

Handles inputs.yml validation and path resolution.
Supports the nested structure used in AgenticGuidance agents:
  - layers: Reference layers for transitive loading
  - core_inputs: Agent-specific input files
  - guidelines: Guidelines the agent should follow
  - definitions: Inline definitions (not file references)
"""

import sys
from pathlib import Path

import yaml


def handle(args):
    """Route inputs subcommands."""
    if args.inputs_command == "validate":
        cmd_validate(args)
    elif args.inputs_command == "resolve":
        cmd_resolve(args)
    else:
        print("Usage: agentic inputs <validate|resolve> <file>", file=sys.stderr)
        sys.exit(1)


def _find_assets_base(inputs_file: Path) -> Path:
    """Find the assets base directory for resolving paths.

    Looks for 'assets/' directory by walking up from the inputs file.
    Returns the parent directory containing 'assets/'.
    """
    current = inputs_file.parent
    while current != current.parent:
        if (current / "assets").exists():
            return current
        # Also check if we're inside an agents directory
        if current.name == "agents" and (current.parent / "assets").exists():
            return current.parent
        current = current.parent

    # Fallback: return the inputs file's parent
    return inputs_file.parent


def _resolve_path(path_str: str, inputs_file: Path, assets_base: Path) -> Path:
    """Resolve a path string to an absolute path.

    Handles:
    - Absolute paths (returned as-is)
    - Paths starting with 'assets/' (resolved from assets_base)
    - Paths starting with 'docs/' (resolved from assets_base)
    - Relative paths (resolved from inputs_file parent)
    """
    if path_str.startswith("/"):
        return Path(path_str)

    if path_str.startswith("assets/") or path_str.startswith("docs/"):
        return assets_base / path_str

    return inputs_file.parent / path_str


def _resolve_nested_inputs(inputs_file: Path, visited: set | None = None) -> list[dict]:
    """Recursively resolve inputs from a nested inputs.yml file.

    Supports the AgenticGuidance format with:
    - layers: List of layer references with type/path/description
    - core_inputs: List of file/pattern references
    - guidelines: List of guideline file references
    - definitions: Inline definitions (skipped, not file references)

    Args:
        inputs_file: Path to inputs.yml file
        visited: Set of already visited files (to prevent circular refs)

    Returns:
        List of resolved input items with their paths
    """
    if visited is None:
        visited = set()

    file_key = str(inputs_file.resolve())
    if file_key in visited:
        return [{"error": f"Circular reference detected: {inputs_file}"}]
    visited.add(file_key)

    if not inputs_file.exists():
        return [{"error": f"File not found: {inputs_file}"}]

    try:
        content = yaml.safe_load(inputs_file.read_text())
    except yaml.YAMLError as e:
        return [{"error": f"YAML error in {inputs_file}: {e}"}]

    if not content:
        return []

    resolved = []
    assets_base = _find_assets_base(inputs_file)
    inputs_section = content.get("inputs", {})

    # Handle old flat format (list of items)
    if isinstance(inputs_section, list):
        return _resolve_flat_inputs(inputs_file, inputs_section, assets_base, visited)

    # Handle new nested format (dict with layers, core_inputs, etc.)
    if isinstance(inputs_section, dict):
        # Process layers
        layers = inputs_section.get("layers", [])
        for layer in layers:
            if isinstance(layer, dict):
                layer_type = layer.get("type", "layer")
                layer_path = layer.get("path", "")

                if layer_type == "layer" and layer_path:
                    full_path = _resolve_path(layer_path, inputs_file, assets_base)
                    # Recursively resolve layer
                    layer_inputs = _resolve_nested_inputs(full_path, visited)
                    resolved.extend(layer_inputs)
                    resolved.append({
                        "type": "layer",
                        "path": str(full_path),
                        "exists": full_path.exists(),
                        "description": layer.get("description", ""),
                        "required": layer.get("required", True),
                    })

        # Process core_inputs
        core_inputs = inputs_section.get("core_inputs", [])
        for item in core_inputs:
            if isinstance(item, dict):
                item_type = item.get("type", "file")
                item_path = item.get("path", "")

                if item_path:
                    full_path = _resolve_path(item_path, inputs_file, assets_base)

                    if item_type == "pattern":
                        # Glob pattern
                        if "*" in str(full_path):
                            # Find where the glob pattern starts
                            full_pattern = str(full_path).replace(str(assets_base) + "/", "")
                            matches = list(assets_base.glob(full_pattern)) if assets_base.exists() else []
                        else:
                            matches = [full_path] if full_path.exists() else []

                        resolved.append({
                            "type": "pattern",
                            "path": str(full_path),
                            "pattern": item_path,
                            "matches": [str(m) for m in matches],
                            "count": len(matches),
                            "description": item.get("description", ""),
                            "required": item.get("required", True),
                        })
                    else:
                        # Regular file
                        resolved.append({
                            "type": "file",
                            "path": str(full_path),
                            "exists": full_path.exists(),
                            "description": item.get("description", ""),
                            "required": item.get("required", True),
                        })

        # Process guidelines
        guidelines = inputs_section.get("guidelines", [])
        for item in guidelines:
            if isinstance(item, dict):
                item_path = item.get("path", "")
                if item_path:
                    full_path = _resolve_path(item_path, inputs_file, assets_base)
                    resolved.append({
                        "type": "guideline",
                        "path": str(full_path),
                        "exists": full_path.exists(),
                        "description": item.get("description", ""),
                    })

        # Note: 'definitions' section contains inline content, not file references
        # So we skip it during file resolution

    return resolved


def _resolve_flat_inputs(inputs_file: Path, inputs: list, assets_base: Path, visited: set) -> list[dict]:
    """Resolve inputs from a flat list format (legacy format).

    Args:
        inputs_file: Path to inputs.yml file
        inputs: List of input items
        assets_base: Base path for resolving asset references
        visited: Set of already visited files

    Returns:
        List of resolved input items
    """
    resolved = []

    for item in inputs:
        if isinstance(item, dict):
            if "layer" in item:
                # Resolve layer reference
                layer_path = _resolve_path(item["layer"], inputs_file, assets_base)
                layer_inputs = _resolve_nested_inputs(layer_path, visited)
                resolved.extend(layer_inputs)
            elif "file" in item:
                # File reference
                file_path = _resolve_path(item["file"], inputs_file, assets_base)
                resolved.append({
                    "type": "file",
                    "path": str(file_path),
                    "exists": file_path.exists(),
                    "description": item.get("description", ""),
                })
            elif "glob" in item:
                # Glob pattern
                glob_pattern = item["glob"]
                matches = list(assets_base.glob(glob_pattern)) if assets_base.exists() else []
                resolved.append({
                    "type": "glob",
                    "pattern": glob_pattern,
                    "matches": [str(m) for m in matches],
                    "count": len(matches),
                })
        elif isinstance(item, str):
            # Simple file path
            file_path = _resolve_path(item, inputs_file, assets_base)
            resolved.append({
                "type": "file",
                "path": str(file_path),
                "exists": file_path.exists(),
            })

    return resolved


def cmd_validate(args):
    """Validate all input references in an inputs.yml file."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
        print_success,
    )

    inputs_file = Path(args.file)

    if not inputs_file.exists():
        print_error(f"File not found: {inputs_file}")
        sys.exit(1)

    resolved = _resolve_nested_inputs(inputs_file)

    errors = []
    warnings = []

    for item in resolved:
        if "error" in item:
            errors.append(item["error"])
        elif item.get("type") in ("file", "layer", "guideline"):
            if not item.get("exists"):
                if item.get("required", True):
                    errors.append(f"Missing {item['type']}: {item['path']}")
                else:
                    warnings.append(f"Optional missing: {item['path']}")
        elif item.get("type") == "pattern":
            if item.get("count", 0) == 0 and item.get("required", True):
                warnings.append(f"No matches for pattern: {item['pattern']}")

    # Count by type
    type_counts = {}
    for item in resolved:
        t = item.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    if is_json_output():
        print_json({
            "file": str(inputs_file),
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "counts": type_counts,
            "total": len(resolved),
        })
    else:
        print_header(f"Validating: {inputs_file}")

        if errors:
            console.print("\n[red]Errors:[/red]")
            for err in errors:
                console.print(f"  [red]-[/red] {err}")

        if warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for warn in warnings:
                console.print(f"  [yellow]-[/yellow] {warn}")

        if not errors and not warnings:
            print_success("All references valid")

        console.print(f"\n[bold]Resolved {len(resolved)} inputs:[/bold]")
        for t, count in sorted(type_counts.items()):
            console.print(f"  [dim]-[/dim] {t}: [cyan]{count}[/cyan]")

    if errors:
        sys.exit(1)


def cmd_resolve(args):
    """Show resolved paths for all inputs."""
    from agenticcli.console import console, is_json_output, print_error, print_header, print_json

    inputs_file = Path(args.file)

    if not inputs_file.exists():
        print_error(f"File not found: {inputs_file}")
        sys.exit(1)

    resolved = _resolve_nested_inputs(inputs_file)

    # Group by type for display
    by_type = {}
    for item in resolved:
        t = item.get("type", "unknown")
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(item)

    if is_json_output():
        print_json({
            "file": str(inputs_file),
            "resolved": resolved,
            "by_type": {k: len(v) for k, v in by_type.items()},
            "total": len(resolved),
        })
        return

    print_header(f"Resolving: {inputs_file}")

    for item_type in ["layer", "file", "guideline", "pattern", "glob", "unknown"]:
        items = by_type.get(item_type, [])
        if not items:
            continue

        console.print(f"\n[bold magenta]{item_type.upper()}S[/bold magenta] ({len(items)}):")
        console.print("[dim]" + "-" * 40 + "[/dim]")

        for item in items:
            if "error" in item:
                console.print(f"  [red]ERROR:[/red] {item['error']}")
            elif item_type in ("file", "layer", "guideline"):
                if item.get("exists"):
                    status = "[green]OK[/green]"
                else:
                    status = "[red]MISSING[/red]"
                required = "" if item.get("required", True) else " [dim](optional)[/dim]"
                desc = f" [dim]- {item['description']}[/dim]" if item.get("description") else ""
                console.print(f"  [{status}] {item['path']}{required}{desc}")
            elif item_type in ("pattern", "glob"):
                count = item.get("count", 0)
                console.print(f"  [cyan][PATTERN][/cyan] {item.get('pattern', item.get('path'))} ({count} matches)")
                for match in item.get("matches", [])[:3]:
                    console.print(f"           [dim]{match}[/dim]")
                if count > 3:
                    console.print(f"           [dim]... and {count - 3} more[/dim]")

    console.print(f"\n[bold]Total:[/bold] [cyan]{len(resolved)}[/cyan] inputs resolved")
