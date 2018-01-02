# dcos monitor

## Installation / Setup
This is written to be used as a Python egg/app. Once you have a DC/OS master available, you can point this application to it and run queries.

### SSH Proxy
The easiest way to run queries with this application is to use an SSH proxy. Once you get the mesos.master's internal IP and public IP, you can run queries. You can accomplish this by following the steps in this blog post: https://eric.lubow.org/2017/external-access-dc-os-master/

Once you have the SSH Proxy running, you can begin to run commands. A simple command to test to ensure things are setup correctly is to get a list of the available slaves in the cluster using: `dcos_monitor print_slave_data --list_slaves`
