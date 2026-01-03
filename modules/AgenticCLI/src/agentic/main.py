import click
from rich.console import Console

# Import commands
from agentic.commands.worktree import worktree
from agentic.commands.plan import plan
from agentic.commands.test import test
from agentic.commands.clean import clean
from agentic.commands.session import session
from agentic.commands.deploy import deploy

console = Console()

@click.group()
@click.version_option()
def cli():
    """AgenticCLI - Deterministic operations for Claude Code."""
    pass

@cli.command()
def info():
    """Display information about AgenticCLI."""
    console.print("[bold blue]AgenticCLI[/bold blue] initialized.")
    console.print("This is a scaffold for the AgenticEngineering CLI.")

# Add subcommands
cli.add_command(worktree)
cli.add_command(plan)
cli.add_command(test)
cli.add_command(clean)
cli.add_command(session)
cli.add_command(deploy)

if __name__ == "__main__":
    cli()
