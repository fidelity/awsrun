#
# Copyright 2019 FMR LLC <opensource@fmr.com>
#
# SPDX-License-Identifier: MIT
#
"""Plug-ins for the awsrun CLI.

The awsrun CLI supports two pluggable behaviors: **account loading** and
**credential loading**. To provide choices and extensibility for CLI users,
these behaviors can be changed via a user's awsrun YAML configuration file.
Several plug-ins are included with awsrun. Users may, however, provide their own
implementations, so long as they are installed and available in the standard
Python path.

To use a plug-in, add a plug-in specification to the user configuration file.
The plug-in specification identifies the name of the plug-in, the path to the
`awsrun.plugmgr.Plugin` implementation, and, optionally, its options. The format
of the specification is as follows:

    PLUGIN_NAME:
      plugin: PYTHON_MODULE.CLASSNAME
      options:
        ARG1: VAL1
        ARG2: VAL2

The specification must begin with the `PLUGIN_NAME`, which is either `Accounts`
or `Credentials` depending on the behavior being configured. It must also
include `plugin` that identifies, via a dotted string, the Python module
concatenated with the name of a `Plugin` subclass. Plug-ins must be installed in
the standard Python path.  The specification can also optionally include
`options` that defines options made available to the plug-in.

Only one plug-in should be specified per behavior. If multiple plug-in
specifications are provided for the same behavior, the last one defined in the
configuration is used.

Non-CLI users of awsrun will not use this module.
"""
