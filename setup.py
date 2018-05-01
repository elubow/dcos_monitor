from setuptools import setup

setup(
    name='dcos-monitor',
    version='0.2',
    description='a dcos introspection tool',
    url='https://github.com/elubow/dcos_monitor',
    author='Eric Lubow',
    author_email='eric@lubow.org',
    packages=['dcos_monitor', 'dcos_monitor.cmds'],
    keywords=['dcos', 'mesos'],
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
    classifiers=[  # Optional
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    project_urls={
        'Source': 'https://github.com/elubow/dcos_monitor',
    },
)
