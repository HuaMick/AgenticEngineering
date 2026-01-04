"""Agent manifest commands.

Display and inspect agent manifests.
"""

import sys
from pathlib import Path

import yaml


def handle(args, ctx=None):
    """Route manifest subcommands."""
    if args.manifest_command == "show":
        cmd_show(args)
    elif args.manifest_command == "list":
        cmd_list(args)
    elif args.manifest_command == "validate":
        cmd_validate(args)
    else:
        print("Usage: agentic manifest <show|list|validate>", file=sys.stderr)
        sys.exit(1)


def cmd_show(args):
    """Display formatted agent manifest."""
    from agenticcli.console import console, is_json_output, print_error, print_header, print_json

    agent_path = Path(args.path)

    # Check for manifest.yml
    manifest_file = agent_path / "manifest.yml"
    if not manifest_file.exists():
        # Try looking in the path itself
        if agent_path.suffix == ".yml":
            manifest_file = agent_path
        else:
            print_error(f"No manifest.yml found in {agent_path}")
            sys.exit(1)

    if not manifest_file.exists():
        print_error(f"Manifest not found: {manifest_file}")
        sys.exit(1)

    try:
        content = yaml.safe_load(manifest_file.read_text())
    except yaml.YAMLError as e:
        print_error(f"Invalid YAML in manifest: {e}")
        sys.exit(1)

    if not content:
        print_error("Empty manifest")
        sys.exit(1)

    if is_json_output():
        print_json({"file": str(manifest_file), "manifest": content})
        return

    # Display formatted output
    print_header(f"Agent Manifest: {manifest_file}")

    # Basic info
    if "name" in content:
        console.print(f"\n[bold]Name:[/bold] [cyan]{content['name']}[/cyan]")
    if "description" in content:
        console.print(f"[bold]Description:[/bold] {content['description']}")
    if "type" in content:
        console.print(f"[bold]Type:[/bold] [magenta]{content['type']}[/magenta]")
    if "version" in content:
        console.print(f"[bold]Version:[/bold] [green]{content['version']}[/green]")

    # Triggers
    if "triggers" in content:
        console.print("\n[bold magenta]Triggers:[/bold magenta]")
        triggers = content["triggers"]
        if isinstance(triggers, list):
            for trigger in triggers:
                if isinstance(trigger, dict):
                    console.print(f"  [dim]-[/dim] [cyan]{trigger.get('event', trigger)}[/cyan]")
                else:
                    console.print(f"  [dim]-[/dim] [cyan]{trigger}[/cyan]")
        elif isinstance(triggers, dict):
            for event, config in triggers.items():
                console.print(f"  [dim]-[/dim] [cyan]{event}[/cyan]")

    # Patterns
    if "patterns" in content:
        console.print("\n[bold magenta]Patterns:[/bold magenta]")
        patterns = content["patterns"]
        if isinstance(patterns, list):
            for pattern in patterns[:5]:
                console.print(f"  [dim]-[/dim] {pattern}")
            if len(patterns) > 5:
                console.print(f"  [dim]... and {len(patterns) - 5} more[/dim]")
        elif isinstance(patterns, dict):
            for name, pattern in list(patterns.items())[:5]:
                console.print(f"  [dim]-[/dim] [cyan]{name}:[/cyan] {pattern}")

    # Capabilities
    if "capabilities" in content:
        console.print("\n[bold magenta]Capabilities:[/bold magenta]")
        caps = content["capabilities"]
        if isinstance(caps, list):
            for cap in caps:
                console.print(f"  [dim]-[/dim] [green]{cap}[/green]")
        elif isinstance(caps, dict):
            for name, desc in caps.items():
                console.print(f"  [dim]-[/dim] [green]{name}:[/green] {desc}")

    # Inputs
    if "inputs" in content:
        console.print("\n[bold magenta]Inputs:[/bold magenta]")
        inputs = content["inputs"]
        if isinstance(inputs, list):
            for inp in inputs[:5]:
                if isinstance(inp, dict):
                    console.print(f"  [dim]-[/dim] {inp.get('name', inp.get('file', inp))}")
                else:
                    console.print(f"  [dim]-[/dim] {inp}")
            if len(inputs) > 5:
                console.print(f"  [dim]... and {len(inputs) - 5} more[/dim]")

    # Outputs
    if "outputs" in content:
        console.print("\n[bold magenta]Outputs:[/bold magenta]")
        outputs = content["outputs"]
        if isinstance(outputs, list):
            for out in outputs:
                console.print(f"  [dim]-[/dim] {out}")

    console.print()


def _find_manifests(base_path: Path = None, max_depth: int = 4) -> list[dict]:
    """Find all manifest files in the project."""
    if base_path is None:
        base_path = Path.cwd()

    manifests = []
    search_paths = [
        base_path / "modules",
        base_path / "agents",
        base_path / "src",
    ]

    for search_path in search_paths:
        if not search_path.exists():
            continue

        for manifest_file in search_path.rglob("manifest.yml"):
            # Check depth
            rel_path = manifest_file.relative_to(search_path)
            if len(rel_path.parts) > max_depth:
                continue

            try:
                content = yaml.safe_load(manifest_file.read_text())
                if content:
                    manifests.append({
                        "path": manifest_file,
                        "name": content.get("name", manifest_file.parent.name),
                        "type": content.get("type", "unknown"),
                        "version": content.get("version", ""),
                        "description": content.get("description", "")[:60] if content.get("description") else "",
                    })
            except yaml.YAMLError:
                manifests.append({
                    "path": manifest_file,
                    "name": manifest_file.parent.name,
                    "type": "error",
                    "version": "",
                    "description": "YAML parse error",
                })

    return manifests


def cmd_list(args):
    """List all manifests found in the project."""
    from agenticcli.console import console, is_json_output, print_header, print_json

    path = Path(args.path) if hasattr(args, "path") and args.path else None
    manifests = _find_manifests(path)

    if is_json_output():
        print_json({
            "manifests": [
                {
                    "path": str(m["path"]),
                    "name": m["name"],
                    "type": m["type"],
                    "version": m["version"],
                    "description": m["description"],
                }
                for m in manifests
            ],
            "count": len(manifests),
        })
        return

    print_header("Agent Manifests")

    if not manifests:
        console.print("\n[dim]No manifests found.[/dim]")
        console.print("\n[dim]Searched in: modules/, agents/, src/[/dim]")
        return

    from rich.table import Table

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Version")
    table.add_column("Path", style="dim")

    for manifest in manifests:
        try:
            rel_path = manifest["path"].relative_to(Path.cwd())
        except ValueError:
            rel_path = manifest["path"]

        table.add_row(
            manifest["name"],
            manifest["type"],
            manifest["version"],
            str(rel_path.parent),
        )

    console.print(table)
    console.print(f"\n[dim]Found {len(manifests)} manifest(s)[/dim]")


def cmd_validate(args):
    """Validate a manifest file."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
        print_success,
    )

    manifest_path = Path(args.path)

    # Check for manifest.yml
    if manifest_path.is_dir():
        manifest_file = manifest_path / "manifest.yml"
    else:
        manifest_file = manifest_path

    if not manifest_file.exists():
        print_error(f"Manifest not found: {manifest_file}")
        sys.exit(1)

    issues = []
    warnings = []

    # Parse YAML
    try:
        content = yaml.safe_load(manifest_file.read_text())
    except yaml.YAMLError as e:
        issues.append(f"Invalid YAML: {e}")
        content = None

    if content:
        # Check required fields
        required_fields = ["name"]
        for field in required_fields:
            if field not in content:
                issues.append(f"Missing required field: {field}")

        # Check recommended fields
        recommended_fields = ["description", "version", "type"]
        for field in recommended_fields:
            if field not in content:
                warnings.append(f"Missing recommended field: {field}")

        # Validate specific fields
        if "version" in content:
            version = content["version"]
            if not isinstance(version, str) or not version:
                warnings.append("Version should be a non-empty string")

        if "triggers" in content:
            triggers = content["triggers"]
            if not isinstance(triggers, (list, dict)):
                issues.append("Triggers should be a list or dict")

        if "inputs" in content:
            inputs = content["inputs"]
            if not isinstance(inputs, list):
                issues.append("Inputs should be a list")

    is_valid = len(issues) == 0

    if is_json_output():
        print_json({
            "path": str(manifest_file),
            "valid": is_valid,
            "issues": issues,
            "warnings": warnings,
        })
        if not is_valid:
            sys.exit(1)
        return

    print_header(f"Validate: {manifest_file.name}")
    console.print(f"\n[bold]Path:[/bold] {manifest_file}")

    if issues:
        console.print("\n[red bold]Issues:[/red bold]")
        for issue in issues:
            console.print(f"  [red]✗[/red] {issue}")

    if warnings:
        console.print("\n[yellow bold]Warnings:[/yellow bold]")
        for warning in warnings:
            console.print(f"  [yellow]![/yellow] {warning}")

    console.print()
    if is_valid:
        print_success("Manifest is valid")
        if warnings:
            console.print(f"[dim]({len(warnings)} warning(s))[/dim]")
    else:
        print_error(f"Manifest has {len(issues)} issue(s)")
        sys.exit(1)
