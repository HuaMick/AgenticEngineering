import click

@click.group()
def worktree():
    """Worktree management commands."""
    pass

@worktree.command()
@click.argument('branch')
@click.option('--base', help='Base branch')
def create(branch, base):
    """Create a new worktree."""
    click.echo(f"Creating worktree for branch: {branch} (base: {base})")
    click.echo("Not implemented yet.")

@worktree.command()
def list():
    """List worktrees."""
    click.echo("Listing worktrees...")
    click.echo("Not implemented yet.")
