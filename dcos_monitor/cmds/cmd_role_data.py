import click
import copy
import json
from dcos_monitor.cli import get_json, pass_context
from dcos_monitor.util import print_separator

#
# Formatting constants
#
# cluster level
RESOURCE_STRING = "    {resource:<12}:{allocated:>12.2f} / {total:<12.2f} {unit:<8} {percentage:>6.2f} %"

# role level
ROLE_HEADER = "    Role: {role}"
TABLE_HEADER = "        [Resource]  :  [Allocated] / [Reserved]    [Units] "
ROLE_RESOURCE_STRING = "        {resource:<11} : {allocated:>11.2f}  /  {reserved:<11.2f}  {units}"



@click.command('role_data', short_help='Print out role data for the cluster')
@click.option('--role', type=click.STRING, default=None,
                help='query for information on an individual role')
@click.option('--role-list/--no-role-list', default=False,
                help='list all available roles')
@click.option('--role-totals/--no-role-totals', default=True,
                help='show the total cluster stats')
@click.option('--cluster-stats/--no-cluster-stats', default=True,
                help='show the total cluster stats')
@pass_context
def cli(ctx, role, role_list, role_totals, cluster_stats):
    """print out a full status report on the cluster
    """
    # Need to gather cluster stats no matter what for role data
    cluster_allocated, cluster_percentage, cluster_total = gather_cluster_stats(ctx.slave_data)

    # gather all the data
    rs = RoleStats(ctx)

    # just print out a list of roles
    if role_list:
        rs.print_role_list()
        return

    # only deciding whether or not to print
    if cluster_stats:
        print_cluster_stats(cluster_allocated, cluster_percentage, cluster_total)

    # just show me data for the one role
    if role:
        if rs.role_stats.get(role) is None:
            ctx.log.error("No such role: {0}".format(role))
            return
        rs.print_role(role, rs.role_stats[role])

    # show me what you got!
    else:
        print_separator()
        print("All Roles")
        print_separator()
        for role in rs.roles():
            rs.print_role(role, rs.role_stats[role])

    # only deciding whether or not to print
    if role_totals:
        print("")
        rs.print_totals()


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

def aggregate_resource_list(blob):
    resources = {
    }
    resource_reservations = {
    }

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

class RoleStats:
    def __init__(self, ctx):
        # approximate data structure
        # role_stats = {
        #   '$role/total': {
        #     '$resource': {
        #       'allocated|reserved': {
        #         $task: $value,
        #         'total': $value
        #       }
        #     }
        #   }
        # }
        self.slaves = ctx.slave_data['slaves']
        self.log = ctx.log
        self.role_stats = {}
        self.total_stats = {}
        self.__populate()

    def print_role_list(self):
        for role in self.role_stats.keys():
            print(role) 

    def print_totals(self):
        self.print_role("Role Totals", self.total_stats)

    def print_role(self, role, role_stats):
        self.log.debug("{0}: {1}".format(role, role_stats))
        print(ROLE_HEADER.format(role=role))
        print(TABLE_HEADER)
        if role_stats.get('CPU', None) is not None:
            cpu = role_stats['CPU']
            cpu_reserved = cpu.get('reserved', {'total': 0.0})
            cpu_allocated = cpu.get('allocated', {'total': 0.0})
            print(ROLE_RESOURCE_STRING.format(resource="CPU", allocated=cpu_allocated['total'], reserved=cpu_reserved['total'], units=cpu.get('unit', 'Cores')))
        if role_stats.get('Mem', None) is not None:
            mem = role_stats['Mem']
            mem_reserved = mem.get('reserved', {'total': 0.0})
            mem_allocated = mem.get('allocated', {'total': 0.0})
            print(ROLE_RESOURCE_STRING.format(resource="Mem", allocated=mem_allocated['total'], reserved=mem_reserved['total'], units=mem.get('unit', 'MB')))
        if role_stats.get('Disk', None) is not None:
            disk = role_stats['Disk']
            disk_reserved = disk.get('reserved', {'total': 0.0})
            disk_allocated = disk.get('allocated', {'total': 0.0})
            print(ROLE_RESOURCE_STRING.format(resource="Disk", allocated=disk_allocated['total'], reserved=disk_reserved['total'], units=disk.get('unit', 'MB')))
        if role_stats.get('GPU', None) is not None:
            gpu = role_stats['GPU']
            gpu_reserved = gpu.get('reserved', {'total': 0.0})
            gpu_allocated = gpu.get('allocated', {'total': 0.0})
            print(ROLE_RESOURCE_STRING.format(resource="GPU", allocated=gpu_allocated['total'], reserved=gpu_reserved['total'], units=gpu.get('unit', 'Cores')))

    def roles(self):
        return self.role_stats.keys()

    def __populate(self):
        self.log.debug("__populate'ing RoleStats")
        for slave in self.slaves:
            self.__aggregate_slave_reservations(slave)

    def __aggregate_slave_reservations(self, slave):
        reserved_resources_full = slave['reserved_resources_full']
        used_resources_full = slave['used_resources_full']
    
        combined_reserved_resources = []
        for role in reserved_resources_full:
            combined_reserved_resources += reserved_resources_full[role]
        reserved, reserved_reservations = aggregate_resource_list(combined_reserved_resources)
        allocated, allocated_reservations = aggregate_resource_list(used_resources_full)
        # Reserved Resources (By Role)
        self.__aggregate_role_breakdown("reserved", reserved, reserved_reservations)
        # Allocated Resources (By Role)
        self.__aggregate_role_breakdown("allocated", allocated)
    
    def __aggregate_role_breakdown(self, btype, aggregate, reserved_reservations = None):
        if 'cpus' in aggregate:
            self.__aggregate_resource_by_roles(btype, 'CPU', 'cpus', aggregate['cpus'], "Cores")
            if reserved_reservations is not None:
                self.__aggregate_reservation_by_role(btype, reserved_reservations['cpus'], 'CPU', 'Cores')
    
        if 'mem' in aggregate:
            self.__aggregate_resource_by_roles(btype, 'Mem', 'mem', aggregate['mem'], "MB")
            if reserved_reservations is not None:
                self.__aggregate_reservation_by_role(btype, reserved_reservations['mem'], 'Mem', 'MB')
    
        if 'disk' in aggregate:
            self.__aggregate_resource_by_roles(btype, 'Disk', 'disk', aggregate['disk'], "MB")
            if reserved_reservations is not None:
                self.__aggregate_reservation_by_role(btype, reserved_reservations['disk'], 'Disk', 'MB')
    
        if 'gpus' in aggregate:
            self.__aggregate_resource_by_roles(btype, 'GPU', 'gpus', aggregate['gpus'], "Cores")
            if reserved_reservations is not None:
                self.__aggregate_reservation_by_role(btype, reserved_reservations['gpus'], 'GPU', 'Cores')
    

    def __aggregate_reservation_by_role(self, btype, reservation_list, label, unit):
        for role in reservation_list:
            total = 0
            for reservation in reservation_list[role]:
                total += reservation['amount']
                self.role_stats.setdefault(role, {}).setdefault(label, {}).setdefault(btype, {})
            self.total_stats.setdefault(label, {}).setdefault(btype, {}).setdefault('total', 0)
            self.total_stats[label][btype]['total'] += total
            self.total_stats[label]['unit'] = unit
     

    def __aggregate_resource_by_roles(self, btype, label, role, aggregate_resource, unit):
        total = 0
        for role in aggregate_resource:
            self.role_stats.setdefault(role, {}).setdefault(label, {}).setdefault(btype, {})['total'] = aggregate_resource[role]
            total += aggregate_resource[role]
        
        self.total_stats.setdefault(label, {}).setdefault(btype, {}).setdefault('total', 0)
        self.total_stats[label][btype]['total'] = self.total_stats[label][btype]['total'] + total
        self.total_stats[label]['unit'] = unit
    

