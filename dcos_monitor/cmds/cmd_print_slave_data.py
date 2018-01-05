import click
import json
from dcos_monitor.cli import pass_context

# formatting constants
SLAVE_STRING = "  {hostname:<20} {agent_id:<40}"

@click.command('print_slave_data', short_help='Print the slave data json')
@click.option('--list_slaves', is_flag=True,
        help='list out the slave IDs with some metadata')
@click.option('--slave_id', default=None,
        help='print out the JSON for the individual slave')
@pass_context
def cli(ctx, list_slaves, slave_id):
    """print out the slave data to STDOUT"""
    if list_slaves is True:
        print("   HOSTNAME             ID")
        for slave in ctx.slave_data["slaves"]:
            print(SLAVE_STRING.format(agent_id=slave["id"], hostname=slave["hostname"]))
        return

    if slave_id is None:
        print(json.dumps(ctx.slave_data))
        return
    else:
        for slave in ctx.slave_data["slaves"]:
            if slave["id"] == slave_id:
                print(json.dumps(slave))
                break
            else:
                continue
        return

    return
