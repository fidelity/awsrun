#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Account loader plugins specific to Azure.

The plug-in in this module allows a user to select subscriptions using the
metadata filters on the `awsrun.cli` instead of explicitly listing accounts to
process.  For accounts that are explicitly specified, the plug-ins are used to
validate those accounts exist. Most plugins in this module attach metadata
attributes to the account objects, which are made available to command authors.

Refer to the plug-in's documentation for a list of valid options that can be
provided via the configuration file or via azurerun CLI flags. CLI flags
override the values defined in the configuration file. The `plugin` key may be
one of the following values:

awsrun.plugins.accts.azure.AzureCLI
:  `AzureCLI` loads subscriptions and metadata for those subscriptions via the
Azure CLI `az account list --all`  command.
"""
import logging

from awsrun.acctload import AzureCLIAccountLoader
from awsrun.plugmgr import Plugin


LOG = logging.getLogger(__name__)


class AzureCLI(Plugin):
    """Account loader plug-in that obtains accounts via the Azure CLI.

    ## Overview

    Accounts specified on the awsrun CLI via the `--account` or `--account-file`
    will be validated against the list of subscriptions obtained from the Azure
    CLI `az account list --all` command.  More importantly, the loaded accounts
    will include metadata associated with each from the JSON output of the Azure
    CLI command.  This metadata can be used to select accounts using the
    `--include` and `--exclude` awsrun CLI flags.

    To use this plug-in, the Azure CLI must be installed. The user must also
    login via the Azure CLI `az login` command. Upon login, the subscriptions
    available to the user will be retrieved and stored locally by the Azure CLI.
    It's important to understand that the accounts loaded by this plug-in will
    only be as recent as the last login. To refresh the list of accounts visible
    to this plug-in, simply login in again via `az login`.

    The following metadata is attached to each subscription: `id` (str), `name`
    (str), `cloudName` (str), `tenantId` (str), `homeTenantId` (str), `state`
    (str), and `isDefault` (bool). In addition, the name of an Azure
    subscription can be parsed for additional metadata attributes. For example,
    assume the following Azure subscription names:

    - azure-retail-prod
    - azure-retail-nonprod
    - azure-wholesale-prod
    - azure-wholesale-nonprod

    Setting the `name_regexp` configuration option or the `--loader-name-regexp`
    command line flag to the following regexp `^azure-(?P<bu>[^-]+)-(?P<env>.+)`
    will attach the `bu` and `env` metadata attributes as well. More precisely,
    each **named** capture group in the pattern becomes an available metadata
    attribute. If a subscription name does not match the pattern, the additional
    attributes will be set to `None`.

    With the accounts loaded and metadata attached, users can specify which
    accounts to process using the `--include` and `--exclude` command line
    options. In the following example, only production retail accounts will be
    selected:

        $ azurerun --include bu=retail --include env=prod az network vnet list

    To query the `isDefault` attribute -- a boolean value, not a string -- one
    must use a type specification:

        $ azurerun --include isDefault=bool:True az network vnet list

    For more information on how to use the CLI and metadata filters, refer to
    the CLI user guide in `awsrun.cli`.

    ## Configuration

    Options with an asterisk are mandatory and must be provided:

        Accounts:
            plugin: awsrun.plugins.accts.azure.AzureCLI
            options:
              name_regexp: STRING

    ## Plug-in Options

    Options can be overridden on the azurerun CLI via command line flags.
    In those cases, the CLI flags are specified next to the option name below:

    `name_regexp`, `--loader-name-regexp`
    : Specifies a regular expression with named capture groups that will be
    applied to each Azure subscription's name to create additional metadata
    attributes that can be used when filtering or by command authors. For
    example, `^azure-(?P<bu>[^-]+)-(?P<env>.+)` will add two metadata
    attributes, `bu` and `env`, on top of the default ones. If a name does not
    match, the attributes specified by the capture groups will be set to None.
    """

    def __init__(self, parser, cfg):
        super().__init__(parser, cfg)

        # Define the arguments that we want to allow a user to override via the
        # main CLI. Any CLI args added via add_argument will be commingled with
        # the main awsrun args, so they are prefixed with '--loader-' to lessen
        # chance of collision.
        group = parser.add_argument_group("account loader options")
        group.add_argument(
            "--loader-name-regexp",
            metavar="STRING",
            default=cfg("name_regexp"),
            help="regexp applied to subscription name for metadata attributes",
        )

    def instantiate(self, args):
        return AzureCLIAccountLoader(name_regexp=args.loader_name_regexp)
