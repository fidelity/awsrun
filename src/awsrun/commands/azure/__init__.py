#
# Copyright 2019 FMR LLC <opensource@fmr.com>
#
# SPDX-License-Identifier: MIT
#
"""Contains the built-in commands for Azure.

Each module represents an individual awsrun `awsrun.runner.Command` that can be
invoked via the command line `awsrun.cli` tool. When specifying the name of the
command to invoke, only the last portion of the dotted module name is required
as `awsrun.commands.azure` is included by default in the path used by
`awsrun.cmdmgr`.

Users can build their own commands as well. Please refer to the `awsrun`
documentation for instructions on how to define and install your own commands.
"""
