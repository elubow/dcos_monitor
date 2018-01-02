import click
from dcos_monitor.cli import pass_context

@click.command('dummy', short_help='Responsds with default true')
@pass_context
def cli(ctx):
    """we can safely ignore whether or not state json exists."""
    return True
