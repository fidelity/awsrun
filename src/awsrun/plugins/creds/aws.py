#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Plug-ins for AWS credential loading.

The plug-ins in this module allow a user to control how credentials are obtained
for the AWS accounts specified on the awsrun CLI. To configure the awsrun CLI to
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

awsrun.plugins.creds.aws.Profile
:  `Profile` uses standard AWS configuration files for credentials.

awsrun.plugins.creds.aws.SAML
:  `SAML` uses federated user authentication via SAML for credentials.

awsrun.plugins.creds.aws.ProfileCrossAccount
:  `ProfileCrossAccount` uses a profile base account for cross-account access.

awsrun.plugins.creds.aws.SAMLCrossAccount
:  `SAMLCrossAccount` uses a SAML base account for cross-account access.

your.own.module.PluginSubclass
:  A custom plug-in installed in the Python path that subclasses
`awsrun.plugmgr.Plugin` that returns a `awsrun.session.SessionProvider`.
"""

import getpass
import os

from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from requests_ntlm import HttpNtlmAuth

from awsrun.config import URL, Bool, Choice, Dict, Int, Str
from awsrun.plugmgr import Plugin
from awsrun.session.aws import CredsViaCrossAccount, CredsViaProfile, CredsViaSAML

# This is only used to prevent pdoc (the doc generator) from exposing
# AbstractCrossAccount in the module's documentation, which is intended for CLI
# users and not programmers as this module deals with plugin configurations.
__all__ = ["Profile", "SAML", "ProfileCrossAccount", "SAMLCrossAccount"]

_AUTH_CLASSES = {"basic": HTTPBasicAuth, "digest": HTTPDigestAuth, "ntlm": HttpNtlmAuth}


class Profile(Plugin):
    """CLI plug-in that uses standard AWS configuration files for credentials.

    ## Overview

    The AWS CLI allows users to define "profiles" in their AWS credentials file
    (~/.aws/credentials) and their AWS configuration file (~/.aws/config). For
    example, if ~/.aws/credentials file defines the following two profiles, then
    awsrun can be used to access accounts 111222333444 and 222333444111:

        [111222333444]
        aws_access_key_id=AKIAIOSFODNN7EXAMPLE
        aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

        [222333444111]
        aws_access_key_id=BEOQODRDNEUDFEXAMPLE
        aws_secret_access_key=8weuou7etAUGZehZHoZeQHVBxogGRLEXAMPLEKEY

    If a profile is not explicitly defined for an account, this plug-in will
    fallback to the "default" profile for account access. For example:

        [default]
        aws_access_key_id=BEOQODRDNEUDFEXAMPLE
        aws_secret_access_key=8weuou7etAUGZehZHoZeQHVBxogGRLEXAMPLEKEY

    By leveraging the standard AWS CLI credential and configuration files, users
    can specify credentials in a variety of ways including standard access and
    secret keys, pre-defined cross-account access, or even use an external
    process to obtain credentials.

    Please refer to the [AWS CLI Configuration and Credential
    Files](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
    for additional details on the use of the standard AWS files and how to
    configure them.

    ## Configuration

        Credentials:
          plugin: awsrun.plugins.creds.aws.Profile

    ## Plug-in Options

    There are no options for this plug-in.
    """

    def instantiate(self, args):
        return CredsViaProfile()


Default = Profile
"""Default session provider used if one is not configured by user."""


class SAML(Plugin):
    """CLI plug-in that uses federated authentication via SAML for credentials.

    AWS supports federated Single Sign On (SSO) access via SAML. With this
    plug-in, the user authenticates to an Identity Provider (IdP), such as ADFS
    or PingFederate, to obtain a SAML assertion that is used to assume an AWS
    role within an account to obtain credentials. Unlike the `Profile` plug-in,
    this plug-in does not rely on the standard AWS credentials or configuration
    files, and thus does not require defining all accounts ahead of time. This
    plug-in does, however, require that the IdP is configured to grant a user
    access to authorized AWS accounts.

    Please refer to [Using SAML-Based Federation for API Access to
    AWS](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_saml.html)
    for additional details on the use of federated SSO with SAML.

    ## Configuration

    Options with an asterisk are mandatory and must be provided:

        Credentials:
          plugin: awsrun.plugins.creds.aws.SAML
          options:
            username: STRING
            password: STRING
            role: STRING*
            url: STRING*
            auth_type: ("basic" | "digest" | "ntlm")
            http_method: ("GET"| "POST")
            http_headers:
              STRING: STRING
            no_verify: BOOLEAN
            duration: INTEGER
            assertion_duration: INTEGER

    ## Plug-in Options

    Some options can be overridden on the awsrun CLI via command line flags.
    In those cases, the CLI flags are specified next to the option name below:

    `username`, `--saml-username`
    : The username to use when authenticating with the IdP server. If this value
    is not provided, the following environment variables are checked in order:
    LOGNAME, USER, LNAME and USERNAME. If authenticating to an ADFS server, the
    username should be in the form of "domain\\username".

    `password`, `--saml-password`
    : The password to use when authenticating with the IdP server. The default
    is the value, if any, of the PASSWORD environment variable. If none of these
    are set, the user will be prompted via the console when awsrun is invoked.

    `role`, `--saml-role`
    : The AWS role name, not ARN, to assume in the account when federating via
    SAML. This value **must** be provided via the user configuration or as an
    awsrun command line argument.

    `url`
    : The URL to the IdP web server that will provide a SAML assertion upon
    successful authentication. This value **must** be provided via the user
    configuration file. The IdP URL will typically have a reference to AWS such
    as `urn:amazon:webservices`.

    `auth_type`
    : The HTTP authentication method to use when authenticating with the IdP. If
    specified, it must be one of `basic`, `digest`, or `ntlm`. The default value
    is `basic`. If using NTLM, username should be specified as `domain\\username`.

    `http_method`
    : The HTTP method to use when authenticating with the IdP. If
    specified, it must be one of `GET`, `POST`. The default value
    is `GET`.

    `http_headers`
    : Additional HTTP headers to send in the request to the IdP. If specified,
    it must be a dictionary of `key: value` pairs, where keys and values are
    strings. This can be useful if the IdP processes requests differently based
    on headers such as User-Agent for example.

    `no_verify`, `--saml-no-verify`
    : Disable HTTP certificate verification. This is not advisable and user will
    be warned on the command line if verification has been disabled. The default
    value is `false`.

    `duration`, `--saml-duration`
    : The amount of time, in seconds, that the AWS credentials for the role /
    account combination are cached in memory. The default value is `3600`
    seconds (1 hour). Caching can be disabled by specifying `0` seconds. If AWS
    credentials are expired sooner by a local IAM policy, then lower the value.

    `assertion_duration`, `--saml-assertion-duration`
    : The amount of time, in seconds, that the SAML assertion received from the
    IdP is cached in memory. The default value is `300` seconds (5 minutes).
    Caching can be disabled by specifying `0` seconds.
    """

    def __init__(self, parser, cfg):
        super().__init__(parser, cfg)

        # Define the arguments that we want to allow a user to override via the
        # main CLI. Any CLI args added via add_argument will be commingled with
        # the main awsrun args, so they are prefixed with '--saml-' to lessen
        # chance of a name collision.
        group = parser.add_argument_group("SAML options")
        group.add_argument(
            "--saml-username",
            metavar="USER",
            default=self.cfg("username", type=Str, default=getpass.getuser()),
            help="username for SAML authentication",
        )

        group.add_argument(
            "--saml-password",
            metavar="PASS",
            default=self.cfg(
                "password", type=Str, default=os.environ.get("PASSWORD", None)
            ),
            help="password for SAML authentication",
        )

        group.add_argument(
            "--saml-role",
            metavar="ROLE",
            default=self.cfg("role", type=Str, must_exist=True),
            help="base role to assume via SAML",
        )

        group.add_argument(
            "--saml-duration",
            metavar="SECS",
            type=int,
            default=cfg("duration", type=Int, default=3600),
            help="duration when requesting aws credentials in assume_role*",
        )

        group.add_argument(
            "--saml-assertion-duration",
            metavar="SECS",
            type=int,
            default=cfg("assertion_duration", type=Int, default=300),
            help="length of time to cache SAML assertion from IdP",
        )

        group.add_argument(
            "--saml-no-verify",
            action="store_true",
            default=cfg("no_verify", type=Bool, default=False),
            help="disable cert verification for HTTP requests",
        )

    def instantiate(self, args):
        cfg = self.cfg

        # We don't prompt for this password above when checking the PASSWORD
        # environment as we wouldn't have access to the username. which should
        # be included in the prompt to the user to remind them of the username
        # being used.
        args.saml_password = args.saml_password or getpass.getpass(
            f"Password for {args.saml_username}? "
        )

        # Look up the requests compatible HTTP Auth classes by type specified.
        auth = _AUTH_CLASSES[
            cfg("auth_type", type=Choice("basic", "digest", "ntlm"), default="basic")
        ]

        # Build a session provider using the combination of options that have
        # been specified in the user's configuration file or have been
        # overridden on the command line.
        session_provider = CredsViaSAML(
            role=args.saml_role,
            url=cfg("url", type=URL, must_exist=True),
            auth=auth(args.saml_username, args.saml_password),
            http_method=cfg("http_method", type=Choice("GET", "POST"), default="GET"),
            headers=cfg("http_headers", type=Dict(Str, Str), default={}),
            duration=args.saml_duration,
            saml_duration=args.saml_assertion_duration,
            no_verify=args.saml_no_verify,
        )

        # Test if password provided is correct. If the wrong password is used and
        # one cannot be authenticated, then AccountRunner might inadvertently lock
        # the user out as it will attempt to get SAML creds for each account. If
        # this fails, an exception will be thrown and caught in the main CLI.
        session_provider.assertion()

        return session_provider


class AbstractCrossAccount(Plugin):
    """Abstract base class for cross-account access plug-ins.

    This class registers the command line arguments relevant to cross-account
    access such as the base account, role, and external id. Subclasses must
    implement the `_get_base_auth` method.
    """

    def __init__(self, parser, cfg):
        super().__init__(parser, cfg)

        # Define the arguments that we want to allow a user to override via the main
        # CLI. Any CLI args added via add_argument will be commingled with the main
        # awsrun args, so they are prefixed with '--creds-' to lessen chance of a
        # name collision.
        group = parser.add_argument_group("cross-account options")
        group.add_argument(
            "--x-acct-base",
            metavar="ACCT",
            default=cfg("x_acct", "base", type=Str, must_exist=True),
            help="base account to assume role from",
        )

        group.add_argument(
            "--x-acct-role",
            metavar="ROLE",
            default=cfg("x_acct", "role", type=Str, must_exist=True),
            help="cross-account role to assume",
        )

        group.add_argument(
            "--x-acct-external-id",
            metavar="ID",
            default=cfg("x_acct", "external_id", type=Str),
            help="external id to use when assuming role in cross-account",
        )

        group.add_argument(
            "--x-acct-duration",
            metavar="SECS",
            type=int,
            default=cfg("x_acct", "duration", type=Int, default=3600),
            help="duration when requesting aws credentials in assume_role*",
        )

    # Normally I would not use "get" in a method name as I find it redundant,
    # but I needed to make this private (even though subclasses must implement
    # it), so that pdoc (the doc generator) would not display this method in the
    # generated pages for this module as these pages are intended for the CLI
    # user and not a developer.
    def _get_base_auth(self):
        """Return the session provider to obtain credentials for the base account.

        This method must be implemented by subclasses. It must return an
        instance of `session.SessionProvider` that can be used to obtain
        credentials for the base account used for cross-account access.
        """
        raise NotImplementedError

    def instantiate(self, args):
        session_provider = CredsViaCrossAccount(
            base_auth=self._get_base_auth().instantiate(args),
            base_acct=args.x_acct_base,
            role=args.x_acct_role,
            external_id=args.x_acct_external_id,
            duration=args.x_acct_duration,
        )

        return session_provider


class ProfileCrossAccount(AbstractCrossAccount):
    """CLI plug-in that uses a profile base account for cross-account access.

    AWS supports cross-account access from one "base" or "source" account to
    another account. This plug-in obtains credentials for the base account via
    the `Profile` plug-in, and then uses those credentials to assume role to the
    other account provided the proper IAM permissions have been setup. Cross
    account access is typically used in large enterprises with a significant
    number of AWS accounts to simply management of credentials. The benefit is
    that a user does not need direct access to every account. Only access to the
    base account is required from which the user can "hop off" to other
    accounts.

    Please refer to [Providing Access to an IAM User in Another AWS Account That
    You
    Own](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_common-scenarios_aws-accounts.html)
    for additional details on cross-account access.

    ## Configuration

        Credentials:
          plugin: awsrun.plugins.creds.aws.ProfileCrossAccount
          options:
            x_acct:
              base: STRING*
              role: STRING*
              external_id: STRING
              duration: INTEGER

    ## Plug-in Options

    Some options can be overridden on the awsrun CLI via command line flags.
    In those cases, the CLI flags are specified next to the option name below.

    `x_acct: base`, `--x-acct-base`
    : The base or source account from which to "hop off" to other accounts. This
    value **must** be provided via the user configuration or as an awsrun
    command line argument. `Profile` authentication will be used to obtain
    credentials for this base account, so the user must have a profile named for
    this account in their local AWS credentials and/or configuration files.

    `x_acct: role`, `--x-acct-role`
    : The IAM role name, not ARN, to assume from the base account to obtain
    credentials for other accounts. This value **must** be provided via the user
    configuration or as an awsrun command line argument.

    `x_acct: external_id`, `--x-acct-external-id`
    : An optional external ID to use when assuming role in cross-account access.
    This is typically used by service providers that use cross-account access to
    customer accounts as an extra layer of security. Most users will not use
    this feature if accessing accounts within a single organization.

    `x_acct: duration`, `--x-acct-duration`
    : The amount of time, in seconds, that the AWS credentials for the role /
    cross-account combination are cached in memory. The default value is `3600`
    seconds (1 hour). Caching can be disabled by specifying `0` seconds. If AWS
    credentials are expired sooner by a local IAM policy, then lower the value.
    """

    def __init__(self, parser, cfg):
        self._base_auth = Profile(parser, cfg)
        super().__init__(parser, cfg)

    def _get_base_auth(self):
        return self._base_auth


class SAMLCrossAccount(AbstractCrossAccount):
    """CLI plug-in that uses a SAML base account for cross-account access.

    AWS supports cross-account access from one "base" or "source" account to
    another account. This plug-in obtains credentials for the base account via
    the `SAML` plug-in, and then uses those credentials to assume role to the
    other account provided the proper IAM permissions have been setup. Cross
    account access is typically used in large enterprises with a significant
    number of AWS accounts to simply management of credentials. The benefit is
    that a user does not need direct access to every account. Only access to the
    base account is required from which the user can "hop off" to other
    accounts.

    Please refer to [Providing Access to an IAM User in Another AWS Account That
    You
    Own](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_common-scenarios_aws-accounts.html)
    for additional details on cross-account access.

    ## Configuration

    Options with an asterisk are mandatory and must be provided:

        Credentials:
          plugin: awsrun.plugins.creds.aws.SAMLCrossAccount
          options:
            username: STRING
            password: STRING
            role: STRING*
            url: STRING*
            auth_type: ("basic" | "digest" | "ntlm")
            http_method: ("GET"| "POST")
            http_headers:
              STRING: STRING
            no_verify: BOOLEAN
            duration: INTEGER
            assertion_duration: INTEGER
            x_acct:
              base: STRING*
              role: STRING*
              external_id: STRING
              duration: INTEGER

    ## Plug-in Options

    Some options can be overridden on the awsrun CLI via command line flags.
    In those cases, the CLI flags are specified next to the option name below.

    `username`, `--saml-username`
    : The username to use when authenticating with the IdP server for the base
    account. If this value is not provided, the following environment variables
    are checked in order: LOGNAME, USER, LNAME and USERNAME.

    `password`, `--saml-password`
    : The password to use when authenticating with the IdP server for the base
    account. The default is the value, if any, of the PASSWORD environment
    variable. If none of these are set, the user will be prompted via the
    console when awsrun is invoked.

    `role`, `--saml-role`
    : The AWS role name, not ARN, to assume in the base or source account when
    federating via SAML. This value **must** be provided via the user
    configuration or as an awsrun command line argument. Note: this is not the
    IAM role name used when performing the cross-account assume role (see
    `x_acct: role` below).

    `url`
    : The URL to the IdP web server that will provide a SAML assertion upon
    successful authentication for the base account. This value **must** be
    provided via the user configuration file. The IdP URL will typically have a
    reference to AWS such as `urn:amazon:webservices`.

    `auth_type`
    : The HTTP authentication method to use when authenticating with the IdP. If
    specified, it must be one of `basic`, `digest`, or `ntlm`. The default value
    is `basic`. If using NTLM, username should be specified as `domain\\username`.

    `http_method`
    : The HTTP method to use when authenticating with the IdP. If
    specified, it must be one of `GET`, `POST`. The default value
    is `GET`.

    `http_headers`
    : Additional HTTP headers to send in the request to the IdP. If specified,
    it must be a dictionary of `key: value` pairs, where keys and values are
    strings. This can be useful if the IdP processes requests differently based
    on headers such as User-Agent for example.

    `no_verify`, `--saml-no-verify`
    : Disable HTTP certificate verification. This is not advisable and user will
    be warned on the command line if verification has been disabled. The default
    value is `false`.

    `duration`, `--saml-duration`
    : The amount of time, in seconds, that the AWS credentials for the role /
    base account combination are cached in memory. The default value is `3600`
    seconds (1 hour). Caching can be disabled by specifying `0` seconds. If AWS
    credentials are expired sooner by a local IAM policy, then lower the value.

    `assertion_duration`, `--saml-assertion-duration`
    : The amount of time, in seconds, that the SAML assertion received from the
    IdP is cached in memory. The default value is `300` seconds (5 minutes).
    Caching can be disabled by specifying `0` seconds.

    `x_acct: base`, `--x-acct-base`
    : The base or source account from which to "hop off" to other accounts. This
    value **must** be provided via the user configuration or as an awsrun
    command line argument. SAML-based authentication will be used to obtain
    credentials for this base account.

    `x_acct: role`, `--x-acct-role`
    : The IAM role name, not ARN, to assume from the base account to obtain
    credentials for other accounts. This value **must** be provided via the user
    configuration or as an awsrun command line argument. Note: this value is not
    the role used for the SAML authentication to the base account (see the
    `role` option above). It can, however, be the same value depending on how
    IAM roles have been setup.

    `x_acct: external_id`, `--x-acct-external-id`
    : An optional external ID to use when assuming role in cross-account access.
    This is typically used by service providers that use cross-account access to
    customer accounts as an extra layer of security. Most users will not use
    this feature if accessing accounts within a single organization.

    `x_acct: duration`, `--x-acct-duration`
    : The amount of time, in seconds, that the AWS credentials for the role /
    cross-account combination are cached in memory. The default value is `3600`
    seconds (1 hour). Caching can be disabled by specifying `0` seconds. If AWS
    credentials are expired sooner by a local IAM policy, then lower the value.
    """

    def __init__(self, parser, cfg):
        self._base_auth = SAML(parser, cfg)
        super().__init__(parser, cfg)

    def _get_base_auth(self):
        return self._base_auth
