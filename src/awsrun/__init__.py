#
# Copyright 2019 FMR LLC <opensource@fmr.com>
#
# SPDX-License-Identifier: MIT
#
"""CLI and library to concurrently execute user-defined commands across AWS accounts.

## Overview

`awsrun` is both a CLI and library to execute commands over one or more AWS
accounts concurrently. Commands are user-defined Python modules that implement a
simple interface to abstract away the complications of obtaining credentials for
Boto3 sessions - especially when using SAML authentication and/or cross-account
access.

### CLI Usage

The awsrun CLI command is documented extensively on the `awsrun.cli` page. It
includes both a user guide as well as a reference guide on the use of the CLI
command, its command line options, use of the account loader and credential
plug-ins, as well as the syntax of the configuration file.

### Library Usage

Not only is awsrun a CLI, but it is, first and foremost, a Python package that
can be used in other Python libraries and scripts. The package contains
extensive documentation on its use. Each submodule contains an overview of the
module and how to use it, which is then followed by standard module docs for
classes and methods. The available [submodules](#header-submodules) can be found
at the bottom of this page. Of particular interest to library users will be the
following submodules:

`awsrun.runner`
: The core module to execute a command across one or more accounts. You will
find the `awsrun.runner.AccountRunner` and `awsrun.runner.Command` classes
defined in this module. Build your own commands by subclassing the base class.
See the [User-Defined Commmands](#user-defined-commands) next for more
information.

`awsrun.session`
: Contains the definition of the `awsrun.session.SessionProvider`, which is used
to provide Boto3 sessions pre-loaded with credentials. Included are several
built-in implementations such as `awsrun.session.aws.CredsViaProfile`,
`awsrun.session.aws.CredsViaSAML`, and `awsrun.session.aws.CredsViaCrossAccount`.
This module can be used outside of awsurn in other scripts. The module
documentation includes a user guide on how to do so.

### User-Defined Commands

To get the most benefit from awsrun, one typically writes their own used-defined
commands. Please refer to the `awsrun.commands` page for an extensive user guide
on building commands. In summary, a command is nothing more than a single Python
file that contains a subclass of `awsrun.runner.Command`. After the command has
been written, it must be added to the awsrun command path using the `--cmd-path`
[CLI flag](cli.html#options) or `cmd-path` option in the awsrun [configuration
file](cli.html#configuration_1).

### User-Defined Plug-ins

In addition to writing your own user-defined commands, you can write your own
account loader plug-ins as well as credential loader plug-ins. The following are
the high-level steps involved in writing your own plug-ins:

1. Subclass `awsrun.plugmgr.Plugin`. Be sure to read the class and module
   documentation for details on how the CLI loads your plug-in.

2. Add an `__init__` method to register command line flags and configuration
   options you want to make available to the end user. Be sure to call the
   superclass's `__init__` method as well.

3. Provide an implementation for `awsrun.plugmgr.Plugin.instantiate`, which must
   return an instance of either `awsrun.acctload.AccountLoader` or
   `awsrun.session.SessionProvider` depending on whether you are writing an
   account loader or a credential loader.

4. Provide an implementation for your account loader or credential loader
   returned in step 3. Refer to the `awsrun.acctload.AccountLoader` and
   `awsrun.session.SessionProvider` for the methods that must be implemented.

It is recommended that you review the existing plug-ins included in awsrun for
additional guidance on how to build your own.

## Future Plans

Prior to open-sourcing awsrun, the codebase was refactored to support the use of
other cloud service providers. This section includes the implementation details
as well as a high-level roadmap of future enhancements.

### Other CSPs

Other Cloud Service Providers (CSPs) aside from AWS and Azure can be supported.
The name of the installed CLI script is used to determine which CSP is being
used. For example, if the CLI has been installed as `awsrun`, the CSP is `aws`.
If the CLI has been installed as `azurerun`, the CSP is `azure`. The name of the
CSP dictates the following:

- The user configuration file is loaded from `$HOME/.csprun.yaml`, where `csp`
  is the name of the CSP. This allows users to have CSP-specific configuration
files.

- The environment variable used to select an alternate path for the
  configuration file is `CSPRUN_CONFIG`, where `CSP` is the name of the CSP.
  This allows users to have multiple environment variables set for different
  CSPs.

- The default command path is set to `awsrun.commands.csp`, where `csp` is the
  name of the CSP. All of the included CSP commands are isolated in modules
  dedicated to the CSP. This prevents commands for a different CSP from being
  displayed on the command line when a user lists the available commands.

- The default credential loader plug-in is `awsrun.plugins.creds.csp.Default`,
  where `csp` is the name of the CSP. Providing credentials to commands is done
  via a credential loader. When none has been specified in the configuration
  file, awsrun must default to a sane choice for a CSP.

### Roadmap

- Add tests for each module (only a handful have been done so far). PyTest is
  the framework used in awsrun. See the tests/ directory which contains the
  directories for unit and integration tests.

"""

name = "awsrun"
__version__ = "3.1.0"
