"""
DCOS monitoring and introspection commands.

NOTE Adapted from a status script written by Justin Lee.
"""
import os
import sys
import click


CONTEXT_SETTINGS = dict(auto_envvar_prefix='DCOSMON')

class Context(object):

    def __init__(self):
        self.verbose = False
        self.master = ""

    def log(self, msg, *args):
        """Logs a message to stderr."""
        if args:
            msg %= args
        click.echo(msg, file=sys.stderr)

    def vlog(self, msg, *args):
        """Logs a message to stderr only if verbose is enabled."""
        if self.verbose:
            self.log(msg, *args)


pass_context = click.make_pass_decorator(Context, ensure=True)
cmd_folder = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                          'checks'))


class DCOSMonitorCLI(click.MultiCommand):

    def list_commands(self, ctx):
        rv = []
        for filename in os.listdir(cmd_folder):
            if filename.endswith('.py') and \
               filename.startswith('cmd_'):
                rv.append(filename[4:-3])
        rv.sort()
        return rv

    def get_command(self, ctx, name):
        try:
            if sys.version_info[0] == 2:
                name = name.encode('ascii', 'replace')
            mod = __import__('dcos_monitor.checks.cmd_' + name,
                             None, None, ['cli'])
        except ImportError:
            return
        return mod.cli


@click.command(cls=DCOSMonitorCLI, context_settings=CONTEXT_SETTINGS)
@click.option('--master', default='localhost',
              help='Changes the DC/OS master')
@click.option('--slave_data_file', type=click.File('rb'),
              help='use data file for slave data instead of mesos.master')
@click.option('--ignore_slave_data', is_flag=True, default=False,
              help='do not attempt to load slave data (may prevent subcmds from working)')
@click.option('--state_data_file', type=click.File('rb'),
              help='use data file for state data instead of mesos.master')
@click.option('--ignore_state_data', is_flag=True, default=False,
              help='do not attempt to load state data (may prevent subcmds from working)')
@click.option('-v', '--verbose', is_flag=True,
              help='Enables verbose mode')
@pass_context
def cli(ctx, master, slave_data_file, ignore_slave_data, state_data_file, ignore_state_data, verbose):
    """A command line interface to getting and munging data from a DC/OS cluster.
    This command must have access to the master node on port 5050. The easiest
    way to accomplish this is to setup an SSH tunnel to the master if you
    aren't using a VPN. You can also add a "--help" to any subcommand for
    additional documentation on subcommand usage. If you intend to use an SSH
    proxy, the command would look as follows:

        ssh -A -L 5050:<int master ip>:5050 core@<ext master ip>
        ssh -A -L 5050:10.0.6.89:5050 core@54.191.211.256
    """
    ctx.master = master
    ctx.slave_data_file = slave_data_file
    ctx.ignore_slave_data = ignore_slave_data
    ctx.state_data_file = state_data_file
    ctx.ignore_state_data = ignore_state_data
    ctx.verbose = verbose

    # are we loading slave data from a file or from a running cluster?
    if ctx.slave_data_file is not None:
        ctx.slave_data = load_slave_data_from_file(ctx.slave_data_file)
    else:
        ctx.slave_data = get_slave_data(ctx, ctx.master)

    # are we loading state data from a file or from a running cluster?
    if ctx.state_data_file is not None:
        ctx.state_data = load_state_data_from_file()
    else:
        ctx.state_data = get_state_data(ctx, ctx.master)


def load_slave_data_from_file(slave_data_file):
    with open(slave_data_file) as json_file:  
        data = json.load(json_file)
        return data

def load_state_data_from_file(state_data_file):
    with open(state_data_file) as json_file:  
        data = json.load(json_file)
        return data

#---- Move this in to separate file ----#
import getpass
import json
import requests
import socket

# Disable auth InsecureRequestWarning
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Hack to get working in proxy environment (basically ignores proxy)
session = requests.Session()
session.trust_env = False

def get_auth_token(hostname, username, password):
    if hostname is None:
        hostname = socket.gethostname()
    headers = {'content-type': 'application/json'}
    data = {'uid': username, 'password': password}
    response = session.post("https://{hostname}/acs/api/v1/auth/login".format(hostname=hostname),
                             headers=headers,
                             data=json.dumps(data),
                             verify=False).json()
    token = response['token'] if 'token' in response else None
    return token

def login(hostname = None):
    if hostname is None:
        hostname = socket.gethostname()
    token = None
    try:
        while not token:
            username = input("Username: ")
            password = getpass.getpass("Password: ")
            token =  get_auth_token(hostname, username, password)
    except KeyboardInterrupt:
        exit(1)
    return token


'''.json() Doesn't actually return json - it's roughly equivalent to json.loads'''
def get_json(url):
    req = session.get(url)
    return req.json()

def get_slaves(hostname = None):
    if hostname is None:
        hostname = socket.gethostname()
    port = 5050

    slaves_url = "http://{hostname}:{port}/slaves".format(hostname=hostname, port=port)

    return get_json(slaves_url)

def get_state_json(hostname = None):
    if hostname is None:
        hostname = socket.gethostname()
    port = 5050

    url = "http://{hostname}:{port}/state.json".format(hostname=hostname, port=port)

    return get_json(url)

def get_statistics(hostname):
    port = 5051

    containers_url = "http://{hostname}:{port}/monitor/statistics.json".format(
        hostname=hostname, port=port)

    try:
        containers = get_json(containers_url)
    except:
        print("Unable to connect to slave at {}.".format(containers_url))
        containers = None
    return containers

def get_state_data(ctx, master):
    try:
        state_data = get_state_json(master)
    except requests.exceptions.ConnectionError:
        if master is None:
            ctx.log("ConnectionError: Nothing listening on port 5050")
        else:
            ctx.log("ConnectionError: Unable to connect to {0}:5050".format(master))
        exit(1)

    return state_data

def get_slave_data(ctx, master):
    try:
        slave_data = get_slaves(master)
    except requests.exceptions.ConnectionError:
        if master is None:
            ctx.log("ConnectionError: Nothing listening on port 5050")
        else:
            ctx.log("ConnectionError: Unable to connect to {0}:5050".format(master))
        exit(1)

    return slave_data
