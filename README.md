# dcos monitor

## Installation / Setup
This is written to be used as a Python egg/app. Once you have a DC/OS master available, you can point this application to it and run queries.

### SSH Proxy
The easiest way to run queries with this application is to use an SSH proxy. Once you get the mesos.master's internal IP and public IP, you can run queries. You can accomplish this by following the steps in this blog post: https://eric.lubow.org/2017/external-access-dc-os-master/

Once you have the SSH Proxy running, you can begin to run commands. A simple command to test to ensure things are setup correctly is to get a list of the available slaves in the cluster using: `dcos_monitor print_slave_data --list_slaves`

## Running
This is a self-documented application. So just run any command or subcommand with `--help` and you'll get more information on what's available. Both commands and subcommands offer different help menus as well.

# Contributing
I get it, this is a pretty useful and cool app. And I'm not the best programmer, so you want to make this cleaner and more useful. The more the merrier.

Just make sure that whatever you add works and is well documented in the help section and I'll test it out and merge it. Easy as that.
