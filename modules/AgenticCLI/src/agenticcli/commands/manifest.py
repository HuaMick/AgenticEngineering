"""Agent manifest commands.

Display and inspect agent manifests.
"""

import sys
from pathlib import Path

import yaml


def handle(args):
    """Route manifest subcommands."""
    if args.manifest_command == "show":
        cmd_show(args)
    else:
        print("Usage: agentic manifest show <agent-path>", file=sys.stderr)
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
