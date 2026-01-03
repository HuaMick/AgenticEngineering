import click

@click.group()
def plan():
    """Planning folder state management."""
    pass

@plan.command()
@click.argument('path', required=False)
def status(path):
    """Show plan status."""
    click.echo(f"Checking status for plan: {path or 'current'}")
    click.echo("Not implemented yet.")
