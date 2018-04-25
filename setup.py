from setuptools import setup

setup(
    name='dcos-monitor',
    version='0.1',
    packages=['dcos_monitor', 'dcos_monitor.cmds'],
    include_package_data=True,
    install_requires=[
        'click',
        'click_log',
        'requests',
    ],
    entry_points='''
        [console_scripts]
        dcos_monitor=dcos_monitor.cli:cli
    ''',
)
