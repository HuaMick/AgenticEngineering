"""Environment management commands.

Commands for viewing and managing environment variable injection.
"""

import sys


def handle(args, ctx=None):
    """Route env subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.env_command == "show":
        cmd_show(args, ctx)
    elif args.env_command == "export":
        cmd_export(args, ctx)
    elif args.env_command == "run":
        cmd_run(args, ctx)
    else:
        print("Usage: agentic configure env <show|export|run>", file=sys.stderr)
        sys.exit(1)


def cmd_show(args, ctx=None):
    """Show environment configuration with secrets masked."""
    from agenticcli.console import console, is_json_output, print_header, print_json

    provider = _get_provider(ctx)
    env_vars = provider.get_all()

    if is_json_output():
        print_json(provider.export_json())
        return

    print_header("Environment Configuration")

    if not env_vars:
        console.print("[dim]No environment variables configured[/dim]")
        return

    from rich.table import Table

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Variable", style="yellow")
    table.add_column("Value", style="white")
    table.add_column("Source", style="dim")
    table.add_column("Secret", style="dim")

    source_colors = {
        "config": "blue",
        "prefs": "green",
        "env": "yellow",
        "runtime": "magenta",
    }

    for name in sorted(env_vars.keys()):
        var = env_vars[name]
        color = source_colors.get(var.source.value, "white")
        secret_indicator = "[red]Yes[/red]" if var.is_secret else "[dim]No[/dim]"
        table.add_row(
            name,
            var.display_value(),
            f"[{color}]{var.source.value}[/{color}]",
            secret_indicator,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(env_vars)} variable(s)[/dim]")


def cmd_export(args, ctx=None):
    """Export environment variables in specified format."""
    from agenticcli.console import console, is_json_output, print_json

    provider = _get_provider(ctx)
    format_type = getattr(args, "format", "shell")

    if is_json_output() or format_type == "json":
        print_json(provider.export_json())
    else:
        # Shell format
        shell_export = provider.export_shell()
        if shell_export:
            console.print(shell_export)
        else:
            console.print("[dim]# No environment variables to export[/dim]")


def cmd_run(args, ctx=None):
    """Run a command with injected environment."""
    from agenticcli.console import console, is_json_output, print_error, print_json

    provider = _get_provider(ctx)
    cmd_args = getattr(args, "cmd_args", None)

    if not cmd_args:
        print_error("No command specified")
        sys.exit(1)

    # Run the command
    result = provider.run_with_env(cmd_args, capture_output=True)

    if is_json_output():
        print_json({
            "command": cmd_args,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        })
    else:
        if result.stdout:
            console.print(result.stdout, end="")
        if result.stderr:
            console.print(f"[red]{result.stderr}[/red]", end="")

    sys.exit(result.returncode)


def _get_provider(ctx):
    """Get EnvironmentProvider from context or defaults."""
    from agenticguidance.services import EnvironmentProvider

    if ctx:
        return EnvironmentProvider(
            config_dir=ctx.config_dir,
            project_root=ctx.project_root,
        )
    return EnvironmentProvider()
