import click
import copy
import json
import requests
import socket
import time
from dcos_monitor.cli import get_json, pass_context, get_auth_token
from dcos_monitor.util import dget, lpad, print_separator

# Hack to get working in proxy environment (basically ignores proxy)
session = requests.Session()
session.trust_env = False

@click.command('print_marathon_apps', short_help='Print out the current status of Marathon apps')
@click.option('--marathon_user', type=click.STRING,
              help='login for marathon')
@click.option('--marathon_password', type=click.STRING,
              help='password for marathon')
@pass_context
def cli(ctx, marathon_user, marathon_password):
    """print out a full status of marathon
    """
    ctx.log.error("SORRY this doesn't work at the moment. exiting...")
    return

    GET_MARATHON = True
    SHOW_INACTIVE = False
    if ctx.token == None:
        ctx.log.debug("no token found, logging in...")
        ctx.log.debug("get_auth_token({0}, {1}, {2})".format(ctx.master, marathon_user, marathon_password))
        ctx.token = get_auth_token(ctx.master, marathon_user, marathon_password)

        ctx.log.debug("token found")
    apps, json_string = get_marathon_apps(ctx.master, ctx.token)
    ctx.log.info("using token: {0}".format(ctx.token))

    print("Marathon Apps")
    print_separator()
    print("")
    print_marathon_apps(apps, GET_MARATHON, SHOW_INACTIVE)

def get_marathon_apps(hostname, token):
    if hostname is None:
        hostname = socket.gethostname()
    headers = {'authorization': "token={token}".format(token=token)}
    response = session.get("http://{hostname}/marathon/v2/apps".format(hostname=hostname),
                 headers=headers)
    not_json = response.json()
    return not_json['apps'], response.text

def print_marathon_apps(apps, level, show_inactive):
    app_dict = {app['id']:app for app in apps}
    for app_id in sorted(app_dict.keys()): # Need to implement sorting
        app = app_dict[app_id]
        if app['instances'] > 0 or show_inactive == True:
            # print(app_id)
            print_app(app, level)
            # print(app_dict[app_id])
            # print(json.dumps(app_dict[app_id]))
            print("")

def print_app(app, level):
    resource_string="    {resource:<8}: {amount:<6} {unit:<6} "
    
    print_separator(80, '-')

    # print(json.dumps(app))
    # print_separator(40, '-')

    if app['instances'] == 0:
        print("{app:<40} ** INACTIVE **".format(app=app['id']))
    else:
        print("{app:<40} ** ACTIVE [{running} Tasks Running] **".format(app=app['id'], running=app['tasksRunning']))
    print_separator(80, '-')
    # print("{id}".format(id=app['id']))
    lpad("Roles:           {}".format('*' if 'acceptedResourceRoles' not in app or app['acceptedResourceRoles'] == None else 
                                       app['acceptedResourceRoles'] if len(app['acceptedResourceRoles']) == 1 else 
                                       ','.join(app['acceptedResourceRoles'])))
    print("")    
    lpad("Docker Image:    {}".format(dget(app,['container','docker','image'],'N/A')))
    print("")
    # print("Resources:")
    lpad("{} Instance(s), each with:".format(app['instances']))
    if app['cpus'] > 0:
        lpad(resource_string.format(amount=app['cpus'], unit='Cores', resource='CPU'))
    if app['gpus'] > 0:        
        lpad(resource_string.format(amount=app['gpus'], unit='Cores', resource='GPU'))
    if app['mem'] > 0:        
        lpad(resource_string.format(amount=app['mem'], unit='MB', resource='Memory'))
    if app['disk'] > 0:        
        lpad(resource_string.format(amount=app['disk'], unit='MB', resource='Disk'))
    # print("    {cpus:<4} Cores".format(cpus=app['cpus']))
    # print("    {} GPU Core".format(gpus=app['gpus']))
    # print("    {} MB Memory".format(mem=app['mem']))
    # print("    {} MB Disk".format(disk=app['disk']))
    # print("          {} Cores\n, {} GPUs\n, {} MB Memory\n, {} MB Disk\n".format(app['cpus'], app['gpus'], app['mem'], app['disk']))
    print("")
    if len(app['ports']) > 0 and len(app['ports']) < 10:
        lpad("Ports:")
        for port in app['ports']:
            lpad(" - {}".format(port))
        print("")
    elif len(app['ports']) >= 10:
        lpad("Ports: " + ','.join(str(x) for x in app['ports']))
        print("")

    if len(app['uris']) > 0:
        lpad("URIs:")
        for uri in app['uris']:
            lpad(" - {}".format(uri),4)
    if level > 1:
        if len(app['env']) > 0:
            print("")
            lpad("Environment Variables:")
            for v in sorted(app['env']):
                lpad("\"{}\" : \"{}\"".format(v, app['env'][v]), 8)
        if len(app['labels']) > 0:
            print("")
            lpad("Labels:")
            for v in sorted(app['labels']):
                lpad("\"{}\" : \"{}\"".format(v, app['labels'][v]), 8)

