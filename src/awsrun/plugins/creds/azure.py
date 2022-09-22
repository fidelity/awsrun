#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Plug-ins for Azure credential loading.

The plug-ins in this module allow a user to control how credentials are obtained
for the Azure accounts specified on the azurerun CLI. To configure the azurerun
CLI to use one of these plug-ins, or a user-defined plug-in, specify a
`Credentials` block in the user configuration file:

    Credentials:
      plugin: PYTHON_MODULE.CLASSNAME
      options:
        ARG1: VAL1
        ARG2: VAL2

Refer to each plug-in's documentation for a list of valid options that can be
provided via the configuration file or via azurerun CLI flags. CLI flags override
the values defined in the configuration file. The `plugin` key may be one of the
following values:

awsrun.plugins.creds.azure.Default
:  `Default` uses the default Azure SDK credential methods.

awsrun.plugins.creds.azure.UsernamePassword
:  `UsernamePassword` uses a username & password for credentials.

your.own.module.PluginSubclass
:  A custom plug-in installed in the Python path that subclasses
`awsrun.plugmgr.Plugin` that returns a `awsrun.session.SessionProvider`.
"""

import getpass
import os

from awsrun.config import Str
from awsrun.plugmgr import Plugin
from awsrun.session.azure import CredsViaAzureDefault, CredsViaUsernamePassword


class Default(Plugin):
    """CLI plug-in that uses the default Azure credential mechanisms.

    ## Overview

    Credentials are obtained via environment variables, a managed identity on an
    Azure host, the shared token cache (Windows only), Azure VSCode, Azure CLI,
    or interactively via the browser. These are tried in order until one
    succeeds.

    For more information, see [Azure SDK
    documentation](https://azuresdkdocs.blob.core.windows.net/$web/python/azure-identity/1.5.0/index.html#defaultazurecredential)

    ## Configuration

    Options with an asterisk are mandatory and must be provided:

        Credentials:
          plugin: awsrun.plugins.creds.azure.Default
          options:
            authority: STRING

    ## Plug-in Options

    Some options can be overridden on the azurerun CLI via command line flags.
    In those cases, the CLI flags are specified next to the option name below:

    `authority`, `--ad-authority`
    :  The `authority` specifies the Microsoft AD authority host. If one is not
    provided, the default is "login.microsoftonline.com".
    """

    def __init__(self, parser, cfg):
        super().__init__(parser, cfg)

        # Define the arguments that we want to allow a user to override via the
        # main CLI. Any CLI args added via add_argument will be commingled with
        # the main azurerun args, so they are prefixed with '--ad-' to lessen
        # chance of a name collision.
        group = parser.add_argument_group("Azure authentication options")
        group.add_argument(
            "--ad-authority",
            metavar="NAME",
            default=self.cfg(
                "authority", type=Str, default="login.microsoftonline.com"
            ),
            help="Azure AD authority host",
        )

    def instantiate(self, args):
        return CredsViaAzureDefault(authority=args.ad_authority)


class UsernamePassword(Plugin):
    """CLI plug-in that uses the default Azure credential mechanisms.

    ## Overview

    Credentials are obtained by authenticating with Azure AD using a username
    and password. Access tokens are cached by the underlying MSAL library and
    automatically refreshed as needed.

    For more information, see [Azure SDK
    documentation](https://azuresdkdocs.blob.core.windows.net/$web/python/azure-identity/1.4.0/azure.identity.html#azure.identity.UsernamePasswordCredential)

    ## Configuration

    Options with an asterisk are mandatory and must be provided:

        Credentials:
          plugin: awsrun.plugins.creds.azure.Default
          options:
            username: EMAIL
            password: STRING
            tenant: STRING
            authority: STRING

    ## Plug-in Options

    Some options can be overridden on the azurerun CLI via command line flags.
    In those cases, the CLI flags are specified next to the option name below:

    `username`, `--ad-username`
    :  The `username` to use when requesting access tokens. It is typically an
    email address that specifies the user and Azure tenant.

    `password`, `--ad-password`
    : The password to use when requesting access tokens. The default is the
    value, if any, of the PASSWORD environment variable. If none of these are
    set, the user will be prompted via the console when azurerun is invoked.

    `tenant`, `--ad-tenant`
    : The `tenant_id` specifies the tenant where the user resides.  Normally,
    this can be derived from the email address used as the username, so it is
    not normally required.

    `authority`, `--ad-authority`
    :  The `authority` specifies the Microsoft AD authority host. If one is not
    provided, the default is "login.microsoftonline.com".
    """

    def __init__(self, parser, cfg):
        super().__init__(parser, cfg)

        # Define the arguments that we want to allow a user to override via the
        # main CLI. Any CLI args added via add_argument will be commingled with
        # the main azurerun args, so they are prefixed with '--az-' to lessen
        # chance of a name collision.
        group = parser.add_argument_group("Azure authentication options")
        group.add_argument(
            "--ad-username",
            metavar="USER",
            default=self.cfg("username", type=Str),
            help="username for Azure AD authentication",
        )

        group.add_argument(
            "--ad-password",
            metavar="PASS",
            default=self.cfg(
                "password", type=Str, default=os.environ.get("PASSWORD", None)
            ),
            help="password for Azure AD authentication",
        )

        group.add_argument(
            "--ad-tenant",
            metavar="ID",
            default=self.cfg("tenant", type=Str),
            help="Azure tenant or directory ID",
        )

        group.add_argument(
            "--ad-authority",
            metavar="NAME",
            default=self.cfg(
                "authority", type=Str, default="login.microsoftonline.com"
            ),
            help="Azure AD authority host",
        )

    def instantiate(self, args):
        args.ad_username = args.ad_username or input("Username (email address)? ")
        args.ad_password = args.ad_password or getpass.getpass(
            f"Password for {args.ad_username}? "
        )

        return CredsViaUsernamePassword(
            args.ad_username,
            args.ad_password,
            tenant_id=args.ad_tenant,
            authority=args.ad_authority,
        )
