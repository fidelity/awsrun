#
# Copyright 2021 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Account loader plugins specific to AWS.

The plug-in in this module allows a user to select accounts using the metadata
filters on the `awsrun.cli` instead of explicitly listing accounts to process.
For accounts that are explicitly specified, the plug-ins are used to validate
those accounts exist. Most plugins in this module attach metadata attributes to
the account objects, which are made available to command authors.

Refer to the plug-in's documentation for a list of valid options that can be
provided via the configuration file or via azurerun CLI flags. CLI flags
override the values defined in the configuration file. The `plugin` key may be
one of the following values:

awsrun.plugins.accts.aws.SSO
:  `SSO` loads accounts and metadata for those accounts from the AWS Single
Sign-On service.
"""
import json
import tempfile
import hashlib
import logging
import re

from pathlib import Path

import boto3

from awsrun.config import Int, Str, List
from awsrun.plugmgr import Plugin
from awsrun.acctload import MetaAccountLoader, capture_groups
from awsrun.cache import PersistentExpiringValue


LOG = logging.getLogger(__name__)


class SSO(Plugin):
    """Account loader plug-in that obtains accounts via AWS Single Sign-On.

    ## Overview

    Accounts specified on the awsrun CLI via the `--account` or `--account-file`
    will be validated against the list of accounts obtained from the AWS Single
    Sign-On service.  The accounts loaded via this plug-in will also include
    metadata associated with each account parsed from the `list_accounts` AWS
    SSO call.  This metadata can be used to select accounts using the
    `--include` and `--exclude` awsrun CLI flags.  The following metadata is
    loaded for each account: `accountId` (str), `accountName` (str), and
    `emailAddress` (str).

    To use this plug-in, AWS Single Sign-On is required and the user must
    login using the AWS CLI `aws sso login` command.  The accounts accessible to
    the SSO user will be retrieved and made available when selecting accounts
    using awsrun.  The account list can be cached to avoid looking up accounts
    upon each awsrun invocation (see options below).

    The following metadata is attached to each account: `accountId` (str),
    `accountName` (str), and `emailAddress` (str). In addition, the account name
    of an AWS account can be parsed for additional metadata attributes.
    For example, assume the following AWS account names:

    - aws-retail-prod
    - aws-retail-nonprod
    - aws-wholesale-prod
    - aws-wholesale-nonprod

    Setting the `name_regexp` configuration option or the `--loader-name-regexp`
    command line flag to the following regexp `^aws-(?P<bu>[^-]+)-(?P<env>.+)`
    will attach the `bu` and `env` metadata attributes as well. More precisely,
    each **named** capture group in the pattern becomes an available metadata
    attribute. If an account name does not match the pattern, the additional
    attributes will be set to `None`.

    With the accounts loaded and metadata attached, users can specify which
    accounts to process using the `--include` and `--exclude` command line
    options. In the following example, only accounts with "john@example.com"
    email address will be selected:

        $ awsrun --include emailAddress=john@example.com aws ec2 describe-vpcs --region us-east-1

    For more information on how to use the CLI and metadata filters, refer to
    the CLI user guide in `awsrun.cli`.

    ## Configuration

    Options with an asterisk are mandatory and must be provided:

        Accounts:
          plugin: awsrun.plugins.accts.aws.SSO
          options:
            sso_start_url: URL*
            max_age: INTEGER
            str_template: STRING
            name_regexp: STRING

    ## Plug-in Options

    Options can be overridden on the azurerun CLI via command line flags.
    In those cases, the CLI flags are specified next to the option name below:

    `sso_start_url`, `--loader-sso-start-url`
    : The application start URL that begins the federation process. This is only
    used to obtain the SSO access token stored locally after the user has
    logged in via the `aws sso login` command.

    `max_age`, `--loader-max-age`
    : Cache the data retrieved from the SSO list accounts call for the specified
    number of seconds.  The default value is `3600`, which caches the account
    list for 1 hour. To disable caching, use a value of `0`.

    `str_template`, `--loader-str-template`
    : Controls how accounts are formatted as strings. This is a [Python format
    string](https://docs.python.org/3.7/library/string.html#format-string-syntax)
    that can include any of the included attributes. For example, `"{id}:{env}"`
    or `"{id}-{env}"` assuming `id` and `env` are JSON key names.

    `name_regexp`, `--loader-name-regexp`
    : Specifies a regular expression with named capture groups that will be
    applied to each AWS account name to create additional metadata attributes
    that can be used when filtering or by command authors. For example,
    `^aws-(?P<bu>[^-]+)-(?P<env>.+)` will add two metadata attributes, `bu`
    and `env`, on top of the default ones. If a name does not match, the
    attributes specified by the capture groups will be set to `None`.
    """

    def __init__(self, parser, cfg):
        super().__init__(parser, cfg)

        # Define the arguments that we want to allow a user to override via the
        # main CLI. Any CLI args added via add_argument will be commingled with
        # the main awsrun args, so they are prefixed with '--loader-' to lessen
        # chance of collision.
        group = parser.add_argument_group("account loader options")

        group.add_argument(
            "--loader-max-age",
            metavar="SECS",
            type=int,
            default=cfg("max_age", type=Int, default=3600),
            help="max age for cached list of accounts",
        )
        group.add_argument(
            "--loader-str-template",
            metavar="STRING",
            default=cfg("str_template"),
            help="format string used to display an account",
        )
        group.add_argument(
            "--loader-sso-start-url",
            metavar="STRING",
            default=cfg("sso_start_url"),
            help="AWS SSO START URL",
        )
        group.add_argument(
            "--loader-name-regexp",
            metavar="STRING",
            default=cfg("name_regexp"),
            help="regexp applied to account name for metadata attributes",
        )

    def instantiate(self, args):
        cfg = self.cfg

        loader = SSOAccountLoader(
            max_age=args.loader_max_age,
            str_template=args.loader_str_template,
            sso_start_url=args.loader_sso_start_url,
            include_attrs=cfg("include_attrs", type=List(Str), default=[]),
            exclude_attrs=cfg("exclude_attrs", type=List(Str), default=[]),
            name_regexp=args.loader_name_regexp,
        )

        return loader


class SSOAccountLoader(MetaAccountLoader):
    """Returns an `awsrun.acctload.AccountLoader` with accounts loaded from AWS SSO API.

    Accounts are loaded from the AWS SSO API using the user's locally stored SSO
    access token.  This requires that the user has signed in with the AWS CLI
    command: `aws sso login`.

    Loaded accounts will include the following metadata attribute names:
    `accountId`, `accountName`, and `emailAddress`.  This account loader will
    build account objects with those attributes attached:

        # After I've signed run "aws sso login" from the CLI
        loader = SSOAccountLoader(sso_start_url='http://example.com/')
        accts = loader.accounts()

        # Let's inspect the 1st account object and its metadata
        assert accts[0].accountId == '100200300400'
        assert accts[0].accountName == 'MyAWSAccount'
        assert accts[0].emailAddress == 'you@example.com'

    In addition, the name of the AWS account name can be parsed for additional
    metadata attributes. For example, assume the following AWS account names:

    - aws-retail-prod
    - aws-retail-nonprod
    - aws-wholesale-prod
    - aws-wholesale-nonprod

    Setting the `name_regexp` argument to the following regexp
    `^aws-(?P<bu>[^-]+)-(?P<env>.*)` will attach the `bu` and `env` metadata
    attributes as well. More precisely, each **named** capture group in the
    pattern becomes an available metadata attribute. If an account name does
    not match the pattern, the additional attributes will be set to `None`.
    """

    def __init__(
        self,
        max_age=0,
        str_template=None,
        sso_start_url="",
        include_attrs=None,
        exclude_attrs=None,
        name_regexp=None,
    ):
        include_attrs = [] if include_attrs is None else include_attrs
        exclude_attrs = [] if exclude_attrs is None else exclude_attrs

        # Check to make sure it's a valid regexp. Don't catch exception as
        # awsrun will catch it and report to user.
        if name_regexp:
            try:
                name_regexp = re.compile(name_regexp)
            except re.error as e:
                raise ValueError(f"Account name regexp invalid: {e}") from e
            if not name_regexp.groupindex:
                raise ValueError("Account name regexp has no named capture groups")

        # See botocore v2 utils.py:SSOTokenLoader
        sso_fname = hashlib.sha1(sso_start_url.encode("utf-8")).hexdigest()
        sso_token_file = Path.home() / ".aws" / "sso" / "cache" / sso_fname
        sso_token_file = sso_token_file.with_suffix(".json")

        def load_accts():
            with open(sso_token_file) as f:
                token = json.load(f)["accessToken"]
            accts = []
            sso = boto3.client("sso")
            for page in sso.get_paginator("list_accounts").paginate(accessToken=token):
                for acct in page["accountList"]:
                    if name_regexp:
                        acct.update(capture_groups(acct["accountName"], name_regexp))
                    accts.append(acct)

            return accts

        cache_file = Path(tempfile.gettempdir(), "awsrun-" + sso_fname)
        accts = PersistentExpiringValue(load_accts, cache_file, max_age=max_age)

        super().__init__(
            accts.value(),
            id_attr="accountId",
            str_template=str_template,
            include_attrs=include_attrs,
            exclude_attrs=exclude_attrs,
        )
