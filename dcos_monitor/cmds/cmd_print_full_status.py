import click
import copy
import json
import socket
import time
from dcos_monitor.cli import get_json, pass_context
from dcos_monitor.util import dget, lpad, print_separator

#
# Formatting constants
#
RESOURCE_STRING = "    {resource:<12}:{allocated:>12.2f} / {total:<12.2f} {unit:<8} {percentage:>6.2f} %"

SINGLE_PORT_RESOURCE_STRING =   "     - {port:<5}"
SINGLE_PORT_RESOURCE_STRING_ROLE =   "     - {port:<5}                [{role:^20}]"

CONTAINER_RESOURCE_STRING = "            {resource:<4}:{used:>8.2f} / {allocated:<8.2f} {unit:<8} {percentage:>6.2f} %"
ROLE_RESOURCE_STRING = "        {role:<20}: {amount:<12.2f} {unit:<8}"
ROLE_STRING = "        {role}:"
RESERVATION_STRING = "            {reservation_id:<40} {amount:<12.2f}"

PORT_RESOURCE_STRING =          "     - {start:<5} - {end:<5}"
PORT_RESOURCE_STRING_ROLE =          "     - {start:<5} - {end:<5}        [{role:^20}]"

FRAMEWORK_STRING = "{id:<51} [{name:^26}]"


@click.command('print_full_status', short_help='Print out a full status report of the cluster')
@click.option('--cluster-stats/--no-cluster-stats', default=True,
                help='show the total cluster stats')
@click.option('--reservation-breakdown/--no-reservation-breakdown', default=True,
                help='more granular reservation stats')
@click.option('--container-stats/--no-container-stats', default=False,
                help='show container level statistics (need to have access to /monitor/statistics.json for this)')
@click.option('--wait', type=click.INT, default=5,
                help='time to wait for agent response')
@pass_context
def cli(ctx, cluster_stats, reservation_breakdown, container_stats, wait):
    """print out a full status report on the cluster
    """
    cluster_allocated, cluster_percentage, cluster_total = gather_cluster_stats(ctx.slave_data)
    if cluster_stats:
        print_cluster_stats(cluster_allocated, cluster_percentage, cluster_total)

    print_separator()
    print("Agent Stats")
    print_separator()
    print("")
    print_agent_info(ctx.slave_data['slaves'], container_stats, reservation_breakdown, wait=wait)

    print_separator()
    print("Minuteman Stats")
    print_separator()
    print("")
    print_minuteman(ctx.state_data)

#### Need to refactor to pull out calculations from prints
#### Also need to refactor to rearrange function
# Memory and disk in megabytes, percentage already multiplied by 100
def print_stats(allocated, total, percentage):
    print("    [Resource]  : [Allocated] / [Total]      [Units]  [Percentage]")

    if total['cpus'] > 0:
        print(RESOURCE_STRING.format(resource = "CPU", 
                            allocated = allocated['cpus'], 
                            total = total['cpus'], 
                            percentage = percentage['cpus'],
                            unit = "Cores"))

    if total['mem'] > 0:
        print(RESOURCE_STRING.format(resource = "Memory", 
                            allocated = allocated['mem'], 
                            total = total['mem'], 
                            percentage = percentage['mem'],
                            unit = "MB"))

    # Consider adjusting for GB:
    if total['disk'] > 0:
        print(RESOURCE_STRING.format(resource = "Disk", 
                            allocated = allocated['disk'], 
                            total = total['disk'], 
                            percentage = percentage['disk'],
                            unit = "MB"))

    if total['gpus'] > 0:
        print(RESOURCE_STRING.format(resource = "GPU", 
                            allocated = allocated['gpus'], 
                            total = total['gpus'], 
                            percentage = percentage['gpus'],
                            unit = "Cores"))
        
    print("")

# Collect information (totals) about a cluster from a 'slaves' block
def gather_cluster_stats(slaves):
    resources = ['mem', 'cpus', 'gpus', 'disk']

    allocated = {}
    percentage = {}
    total = {}
    for resource in resources:
        total[resource] = sum([slave['resources'][resource] for slave in slaves['slaves']])
        allocated[resource] = sum([slave['used_resources'][resource] for slave in slaves['slaves']])
        percentage[resource] = 0 if total[resource] == 0 else 100 * allocated[resource] / total[resource]
    return allocated, percentage, total

# Display information about a cluster gathered by gather_cluster_stats
def print_cluster_stats(allocated, percentage, total):
    print_separator()
    print("Cluster:")
    print_separator()

    print_stats(allocated, total, percentage)


# Rerrange stats about a slave from a 'slaves' block (and display it).
def print_slave_stats(slave):
    allocated = {}
    total = {}
    percentage = {}

    resources = ['mem', 'cpus', 'gpus', 'disk']

    for resource in resources:
        total[resource] = slave['resources'][resource]
        allocated[resource] = slave['used_resources'][resource]
        percentage[resource] = 0 if slave['resources'][resource] == 0 else (
            100.0 * slave['used_resources'][resource] / slave['resources'][resource])

    print_stats(allocated, total, percentage)

def aggregate_resource_list(blob):
    resources = {
    }
    resource_reservations = {
    }

    # print_separator(24,'+')
    # print("starting blob:")
    # print(blob)
    # print_separator(24,'+')


    for item in blob:
        
        # Create resource types:
        if item['name'] not in resources:
            resources[item['name']] = {}
        if item['name'] not in resource_reservations:
            # print("Adding role {} to resource reservations".format(item['name']))
            resource_reservations[item['name']] = {}

        if item['role'] not in resource_reservations[item['name']]:
            # print("-----Creating empty list for resource_reservations[{}][{}]".format(item['name'],item['role']))
            resource_reservations[item['name']][item['role']] = []
        
        # print(resource_reservations[item['name']][item['role']])

        if item['type'] == 'SCALAR':
            # desired:
            #  - resources['cpu']['hdfs-principal'] = 3 (scalar)
            #  - resource_breakdowns['cpu']['hdfs-principal] = [] (list of dicts)
            
            # Populate values in resource types
            if item['role'] not in resources[item['name']]:
                resources[item['name']][item['role']] = item['scalar']['value']
            else:
                resources[item['name']][item['role']] += item['scalar']['value']

            if 'reservation' in item:
                resource_reservations[item['name']][item['role']].append(
                        {'amount': item['scalar']['value'],
                        'resource_id': item['reservation']['labels']['labels'][0]['value']}
                )
        
            # print(resource_reservations[item['name']][item['role']])

        if item['type'] == 'RANGES':
            # print_separator(8,'|')
            # print("processing:")
            # print(item)
            # desired:
            #  - resources['cpu']['hdfs-principal'] = []
            #  - resource_breakdowns['cpu']['hdfs-principal] = [] (list of dicts)
            if item['role'] not in resources[item['name']]:
                resources[item['name']][item['role']] = copy.deepcopy(item['ranges']['range'])
            else:
                resources[item['name']][item['role']] += item['ranges']['range']

            if 'reservation' in item:
                new_dict = {'ranges': item['ranges']['range'], 'resource_id': item['reservation']['labels']['labels'][0]['value']}
                resource_reservations[item['name']][item['role']].append(new_dict)

        
        # print(resource_reservations[item['name']][item['role']])


    return resources, resource_reservations

# XXX factor out get_statistics to a utility file
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

def print_agent_info(slaves, get_container_stats, get_reservation_breakdown, wait = 5):
    data_start = {}
    data_end = {}
    if get_container_stats:
        for slave in slaves:
            stats = get_statistics(slave['hostname'])
            if stats is not None:
                data_start[slave['hostname']] = {
                    container['executor_id']:container for container in stats}

        # Wait between polls.  Precision not necessary.
        time.sleep(wait)
        for slave in slaves:
            stats = get_statistics(slave['hostname'])
            if stats is not None:
                data_end[slave['hostname']] = {
                    container['executor_id']:container for container in stats}

    for slave in slaves:
        hostname = slave['hostname']
        # print(slave)
        slave_type = 'slave_public' if 'public_ip' in slave['attributes'] else 'slave'
        print_separator()
        print("{id:<44} IP: {ip:<16} [{slave_type:^12}]".format(id=slave['id'], ip=hostname, slave_type=slave_type))
        print_separator()
        print("")
        
        # print(slave)

        print_slave_stats(slave)
        print_slave_reservations(slave, get_reservation_breakdown)

        if get_container_stats:
            print_separator(60, spaces=4)
            lpad("Containers: ")
            for executor in data_end[hostname]:
                if executor in data_start[hostname]:
                    stats = calculate_container_stats(data_start[hostname][executor]['statistics'], 
                                            data_end[hostname][executor]['statistics'])
                    print_separator()
                    # print(slave['id'])
                    # print(hostname)
                    # print(executor)
                    # print(stats)
                    print_container_stats(executor, stats)
                else:
                    # If executor present in 'data_end' but not 'data_start', use data_end for both,
                    # then skip printing CPU (memory only uses data_end, CPU uses both)
                    stats = calculate_container_stats(data_end[hostname][executor]['statistics'], 
                                            data_end[hostname][executor]['statistics'])
                    print_container_stats(executor, stats, single_data_point = True)
        print("")

def calculate_container_stats(start, end):
    stats = {}

    timestamp_delta = end['timestamp'] - start['timestamp']

    # print(end)
    stats['memory_allocated'] = end['mem_limit_bytes']
    stats['memory_used'] = end['mem_rss_bytes']
    stats['memory_utilization'] = 100.0 * end['mem_rss_bytes'] / end['mem_limit_bytes']

    cpus_time_delta = (end['cpus_system_time_secs'] + end['cpus_user_time_secs']
                       - start['cpus_system_time_secs'] - start['cpus_user_time_secs'])
    if(abs(cpus_time_delta) < 1e-12) or timestamp_delta == 0:
        cpus_time_delta = 0
        timestamp_delta = 1
    stats['cpus_used'] = float(cpus_time_delta / timestamp_delta)
    stats['cpus_allocated'] = end['cpus_limit']
    stats['cpus_utilization'] = 100 * stats['cpus_used'] / stats['cpus_allocated']

    return stats

def print_slave_reservations(slave, get_reservation_breakdown):
    reserved_resources_full = slave['reserved_resources_full']
    used_resources_full = slave['used_resources_full']

    # print(json.dumps(reserved_resources_full))
    # print(json.dumps(used_resources_full))

    # print(reserved_resources_full)
    combined_reserved_resources = []
    for role in reserved_resources_full:
        combined_reserved_resources += reserved_resources_full[role]
        # print_separator(10, '+')
        # print(json.dumps(reserved_resources_full[role]))
        # print("Aggregating...")
        # res = aggregate_resource_list(reserved_resources_full[role])
    # print("Aggregating combined")
    # print("Combined:")
    # print(json.dumps(combined_reserved_resources))
    reserved, reserved_reservations = aggregate_resource_list(combined_reserved_resources)
    # print(reserved)
    # print(reserved_reservations)

    # print(used_resources_full)
    # print("Aggregating...")
    # (we don't use allocated_reservations right now)
    allocated, allocated_reservations = aggregate_resource_list(used_resources_full)


    print_separator(60, spaces=4)
    lpad("Reserved Resources (By Role):")
    print_role_breakdown(reserved, reserved_reservations, get_reservation_breakdown)
    print("")
    print_separator(60, spaces=4)
    lpad("Allocated Resources (By Role):")
    print_role_breakdown(allocated)

    # if get_reservation_breakdown:
    #     print_separator(60, spaces=4)
    #     print("    Resource Reservations (By Role):")
    #     print_resource_reservations(reserved_reservations)
    # print(reserved_reservations['ports'])

    print("")
    print_separator(60, spaces=4)

    if 'ports' not in reserved:
        reserved['ports'] = {}
    if 'ports' not in allocated:
        allocated['ports'] = {}
    if 'ports' not in reserved_reservations:
        reserved_reservations['ports'] = {}
    print_ports(slave, reserved['ports'], allocated['ports'], reserved_reservations['ports'], get_reservation_breakdown)

def print_role_breakdown(aggregate, reserved_reservations = None, get_reservation_breakdown = False):
    if 'cpus' in aggregate:
        print_resource_by_roles('CPU', 'cpus', aggregate['cpus'], "Cores")
        if get_reservation_breakdown:
            print_reservation_by_role(reserved_reservations['cpus'], 'CPU', 'Cores')

    if 'mem' in aggregate:
        print_resource_by_roles('Mem', 'mem', aggregate['mem'], "MB")
        if get_reservation_breakdown:
            print_reservation_by_role(reserved_reservations['mem'], 'Mem', 'MB')

    if 'disk' in aggregate:
        print_resource_by_roles('Disk', 'disk', aggregate['disk'], "MB")
        if get_reservation_breakdown:
            print_reservation_by_role(reserved_reservations['disk'], 'Disk', 'MB')

    if 'gpus' in aggregate:
        print_resource_by_roles('GPU', 'gpus', aggregate['gpus'], "Cores")
        if get_reservation_breakdown:
            print_reservation_by_role(reserved_reservations['gpus'], 'GPU', 'Cores')

def print_reservation_by_role(reservation_list, label, unit):
    # print("    {label} ({unit}):".format(label=label, unit=unit))
    for role in reservation_list:
        print(ROLE_STRING.format(role=role))
        for reservation in reservation_list[role]:
            print(RESERVATION_STRING.format(reservation_id=reservation['resource_id'],
                                            amount=reservation['amount'],
                                            unit=unit))
    print("")
        # print(reservation_list[role])

def print_port_reservation_by_role(reservation_list, label):
    # print("    {label} ({unit}):".format(label=label, unit=unit))
    for role in reservation_list:
        print(ROLE_STRING.format(role=role))
        for reservation in reservation_list[role]:
            lpad(reservation['resource_id'], 12)
            for r in reservation['ranges']:
                if r['begin'] == r['end']:
                    lpad(SINGLE_PORT_RESOURCE_STRING.format(port=r['begin']),8)
                else:
                    lpad(PORT_RESOURCE_STRING.format(start=r['begin'], end=r['end']),8)

# Print information about the ports in use (one per line) / available on a slave
def print_ports(slave, reserved, allocated, reserved_reservations = None, get_reservation_breakdown = False):
    lpad("Used Ports: ")
    if 'ports' in slave['used_resources']:
        for port_range in slave['used_resources']['ports'][1:-1].split(','):
            r = port_range.strip().split('-')
            for port in range(int(r[0]), int(r[0]) + 1):
                print(SINGLE_PORT_RESOURCE_STRING.format(port=port))
    else:
        print(SINGLE_PORT_RESOURCE_STRING.format(port="{none}"))

    print("")
    lpad("Reserved Ports:")
    for role in reserved:
        for r in reserved[role]:
            if r['begin'] == r['end']:
                print(SINGLE_PORT_RESOURCE_STRING_ROLE.format(port=r['begin'],role=role))
            else:
                print(PORT_RESOURCE_STRING_ROLE.format(start=r['begin'],end=r['end'],role=role))

    if get_reservation_breakdown:
        print("")
        lpad("Reserved Ports (by Reservation):")
        print_port_reservation_by_role(reserved_reservations, 'port')
        # for role in reserved_reservations:
        #     print(role)
        #     print(reserved_reservations[role])

    print("")
    lpad("Allocated Ports:")
    for role in allocated:
        for r in allocated[role]:
            if r['begin'] == r['end']:
                print(SINGLE_PORT_RESOURCE_STRING_ROLE.format(port=r['begin'],role=role))
            else:
                print(PORT_RESOURCE_STRING_ROLE.format(start=r['begin'],end=r['end'],role=role))

    print("")
    lpad("All agent ports: ")
    for port_range in slave['resources']['ports'][1:-1].split(','):
        s,e = port_range.strip().split('-')
        print(PORT_RESOURCE_STRING.format(start=s,end=e))
    print("")

def print_resource_by_roles(label, role, aggregate_resource, unit):
    lpad("{label} ({unit}):".format(label=label, unit=unit))
    total = 0
    for role in aggregate_resource:
        print(ROLE_RESOURCE_STRING.format(role=role, amount=aggregate_resource[role], unit=""))
        total += aggregate_resource[role]
    
    print_separator(length = 32, k = '-', spaces = 8)
    print(ROLE_RESOURCE_STRING.format(role="Total", amount=total, unit=unit))
    print("")

def print_container_stats(executor, stats, single_data_point = False):
    lpad(executor,8)
    if single_data_point:
        print("            CPU not calculated for ephemeral container")
    else:
        print(CONTAINER_RESOURCE_STRING.format(resource="CPU",
                                               used=stats['cpus_used'],
                                               allocated=stats['cpus_allocated'],
                                               unit="Cores",
                                               percentage=stats['cpus_utilization']))
    
    print(CONTAINER_RESOURCE_STRING.format(resource="Mem",
                                           used=stats['memory_used'] / 1024 / 1024,
                                           allocated=stats['memory_allocated'] / 1024 / 1024,
                                           unit="MB",
                                           percentage=stats['memory_utilization']))

def print_minuteman(state):
    if 'frameworks' in state:
        for framework in state['frameworks']:
            print_separator()
            print(FRAMEWORK_STRING.format(id = framework['id'], name = framework['name']))
            if 'tasks' in framework:
                vips = aggregate_tasks_by_vip(framework['tasks'])
                for vip in vips:
                    split_vip = vip.split(':')
                    lpad("{}.{}.l4lb.thisdcos.directory:{}".format(split_vip[0], framework['name'], split_vip[1]))
                    for backend in vips[vip]:
                        lpad(" - {}:{}".format(backend[0], backend[1]))

            print("")

def aggregate_tasks_by_vip(tasks):
    vips = {}
    for task in tasks:
        if task['state'] == 'TASK_RUNNING' and 'discovery' in task and 'ports' in task['discovery'] and 'ports' in task['discovery']['ports']:
            for port in task['discovery']['ports']['ports']:
                # Who the hell came up with this structure?
                if 'labels' in port and 'labels' in port['labels']:
                    for label in port['labels']['labels']:
                        # print(label)
                        if 'VIP' in label['key']:
                            # print(label)
                            vip = label['value']
                            if vip[0] == '/':
                                vip = vip[1:]
                            port = port['number']
                            # Need to get ip addess.  Again, terrible structure.
                            running_status = get_entry_matching(task['statuses'], 'state', 'TASK_RUNNING')
                            network_infos = running_status['container_status']['network_infos']
                            ip = network_infos[0]['ip_addresses'][0]['ip_address']
                            if vip not in vips:
                                vips[vip] = [(ip, port)]
                            else:
                                vips[vip].append((ip,port))
    return vips

def get_entry_matching(entries, key, value):
    # print("Looking for '{}' = '{}'".format(key, value))
    for entry in entries:
        # print(entry)
        if key in entry and entry[key] == value:
            # print('value found')
            return entry
        else:
            # print("{}!={}".format(entry[key],value))
            pass
    return None

