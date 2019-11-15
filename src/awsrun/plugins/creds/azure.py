#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Plug-ins for Azure credential loading.

The plug-ins in this module allow a user to control how credentials are obtained
for the Azure accounts specified on the awsrun CLI. To configure the awsrun CLI to
use one of these plug-ins, or a user-defined plug-in, specify a `Credentials`
block in the user configuration file:

    Credentials:
      plugin: PYTHON_MODULE.CLASSNAME
      options:
        ARG1: VAL1
        ARG2: VAL2

Refer to each plug-in's documentation for a list of valid options that can be
provided via the configuration file or via awsrun CLI flags. CLI flags override
the values defined in the configuration file. The `plugin` key may be one of the
following values:

awsrun.plugins.creds.azure.Profile
:  `Profile` uses standard Azure configuration files for credentials.

your.own.module.PluginSubclass
:  A custom plug-in installed in the Python path that subclasses
`awsrun.plugmgr.Plugin` that returns a `awsrun.session.SessionProvider`.
"""
