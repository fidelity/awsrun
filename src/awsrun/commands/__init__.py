#
# Copyright 2019 FMR LLC <opensource@fmr.com>
#
# SPDX-License-Identifier: MIT
#
"""Contains the built-in commands included in awsrun.

Each submodule contains the built-in commands for a Cloud Service Provider
(CSP). These default commands are made available based on the name of the CLI
command invoked. If the CLI command is named "awsrun", then the commands in
`awsrun.commands.aws` will be made available by default. If the CLI command is
named "azurerun", then the commands in `awsrun.commands.azure` will be made
available by default.

Users can build their own commands as well. Please refer to the `awsrun`
documentation for instructions on how to define and install your own commands.
"""
