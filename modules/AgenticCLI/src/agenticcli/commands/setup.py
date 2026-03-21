"""Setup command for initial configuration.

Provides a guided setup experience for AgenticCLI.
"""

import sys
from pathlib import Path


def handle(args, ctx=None):
    """Run guided setup for AgenticCLI.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    from agenticcli.console import console, is_json_output, print_header, print_json, print_success
    from agenticguidance.services import ConfigWorkflow

    # Get config directory from context or default
    if ctx and ctx.config_dir:
        config_dir = ctx.config_dir
    else:
        import os

        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            config_dir = Path(xdg_config) / "agenticcli"
        else:
            config_dir = Path.home() / ".config" / "agenticcli"

    workflow = ConfigWorkflow(config_dir)

    if is_json_output():
        # Non-interactive mode for scripts
        result = workflow.init(overwrite=getattr(args, "force", False))
        print_json(
            {
                "success": result.success,
                "message": result.message,
                "config_dir": str(config_dir),
                **(result.data or {}),
            }
        )
        if not result.success:
            sys.exit(1)
        return

    # Interactive mode
    print_header("AgenticCLI Setup")
    console.print("\nThis will initialize your AgenticCLI configuration.\n")

    # Check if already configured
    if workflow.config_file.exists():
        console.print("[yellow]Configuration already exists.[/yellow]")
        console.print(f"  Location: {workflow.config_file}")
        response = input("\nReconfigure? [y/N] ")
        if response.lower() != "y":
            console.print("[dim]Setup cancelled.[/dim]")
            return
        overwrite = True
    else:
        overwrite = False

    # Interactive prompts (with defaults)
    console.print("[bold]Configuration Options:[/bold]\n")

    repo_abbr = input("  Repository abbreviation (default: AE): ").strip() or "AE"
    base_branch = input("  Default base branch (default: main): ").strip() or "main"

    # Create configuration
    result = workflow.init(
        overwrite=overwrite,
        defaults={"repo_abbreviation": repo_abbr, "base_branch": base_branch},
    )

    if result.success:
        console.print("")
        print_success("Setup complete!")
        console.print(f"  Config location: {config_dir}")
        console.print("")
        console.print("[dim]You can modify settings anytime with:[/dim]")
        console.print("  agentic config set <key> <value>")
        console.print("  agentic config show")
    else:
        console.print(f"[red]Setup failed: {result.message}[/red]")
        sys.exit(1)
