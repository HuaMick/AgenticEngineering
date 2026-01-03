import click

@click.group()
def deploy():
    """Deployment commands."""
    pass

@deploy.command()
def build():
    """Build for deployment."""
    click.echo("Building...")
    click.echo("Not implemented yet.")
