#
# Copyright 2019 FMR LLC <opensource@fmr.com>
#
# SPDX-License-Identifier: MIT
#
"""Plug-ins for credential loading.

Each submodule contains the built-in credential plug-ins for a Cloud Service
Provider (CSP). The default plug-in used if none is specified by a user is
`awsrun.plugins.creds.aws.Profile` if the CLI command is "awsrun". If the CLI
command is invoked as "azurerun", then `awsrun.plugins.creds.azure.Default` is
used.

Users can also build their own credential plug-ins as well. To configure the CLI
to use a user-defined plug-in, specify a `Credentials` block in the user
configuration file where "your.own.module.PluginSubclass" is implementation of
`awsrun.plugmgr.Plugin` that returns a `awsrun.session.SessionProvider`.

    Credentials:
      plugin: your.own.module.PluginSubclass
      options:
        ARG1: VAL1
        ARG2: VAL2
"""
