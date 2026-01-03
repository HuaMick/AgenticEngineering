import click

@click.group()
def session():
    """Remote session management."""
    pass

@session.command()
def create():
    """Create a new session."""
    click.echo("Creating remote session...")
    click.echo("Not implemented yet.")
