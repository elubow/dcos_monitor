import click
import json
from dcos_monitor.cli import pass_context

@click.command('print_state_data', short_help='Print the state data json')
@pass_context
def cli(ctx):
    """print out the state data to STDOUT"""
    print(json.dumps(ctx.state_data))
