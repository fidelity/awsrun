#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Plug-ins for account loading.

The plug-ins in this module allow a user to select accounts using the metadata
filters on the `awsrun.cli` instead of explicitly listing accounts to process.
For accounts that are explicitly specified, the plug-ins are used to validate
those accounts exist. Most plugins in this module attach metadata attributes to
the account objects, which are made available to command authors. To configure
the CLI to use one of these plug-ins, or a user-defined plug-in, specify an
`Accounts` block in the user configuration file:

    Accounts:
      plugin: PYTHON_MODULE.CLASSNAME
      options:
        ARG1: VAL1
        ARG2: VAL2

Refer to each plug-in's documentation for a list of valid options that can be
provided via the configuration file or via awsrun CLI flags. CLI flags override
the values defined in the configuration file. The `plugin` key may be one of the
following values:

awsrun.plugins.accts.Identity
:  `Identity` does not adorn accounts with additional metadata or perform
validation. If a user has not configured an account loader, this is the default.

awsrun.plugins.accts.CSV
:  `CSV` loads accounts and metadata from a CSV file.

awsrun.plugins.accts.JSON
:  `JSON` loads accounts and metadata from JSON.

awsrun.plugins.accts.YAML
:  `YAML` loads accounts and metadata from YAML.

your.own.module.PluginSubclass
:  A custom plug-in installed in the Python path that subclasses
`awsrun.plugmgr.Plugin` that returns a `awsrun.acctload.AccountLoader`.
"""

import getpass
import os
from pathlib import Path

from requests.auth import AuthBase, HTTPBasicAuth, HTTPDigestAuth
from requests_ntlm import HttpNtlmAuth

from awsrun.acctload import (
    CSVAccountLoader,
    CSVParser,
    HTTPOAuth2,
    IdentityAccountLoader,
    JSONAccountLoader,
    JSONParser,
    URLAccountLoader,
    YAMLAccountLoader,
    YAMLParser,
)
from awsrun.config import URL, Any, Bool, Choice, Dict, File, Int, List, Str
from awsrun.plugmgr import Plugin


class Identity(Plugin):
    """CLI plug-in that does not adorn accounts with additional metadata.

    ## Overview

    Accounts specified on the awsrun CLI via the `--account` or `--account-file`
    will not be loaded from an external data source to ensure they exist, nor
    will any metadata be attached to the accounts for use in awsrun commands.

    This account loader plug-in is the default if one is not specified in the
    user configuration.

    ## Configuration

        Accounts:
          plugin: awsrun.plugins.accts.Identity

    ## Plug-in Options

    There are no options for this plug-in.

    """

    def instantiate(self, args):
        return IdentityAccountLoader()


class _CachingLoaderPlugin(Plugin):
    """Base plug-in for CSV, JSON, and YAML caching account loaders."""

    def __init__(self, parser, cfg):
        super().__init__(parser, cfg)

        # Define the arguments that we want to allow a user to override via the
        # main CLI. Any CLI args added via add_argument will be commingled with
        # the main awsrun args, so they are prefixed with '--loader-' to lessen
        # chance of collision.
        group = parser.add_argument_group("account loader options")
        group.add_argument(
            "--loader-url",
            metavar="URL",
            default=cfg("url", type=URL, must_exist=True),
            help="URL to account data (also supports file:///path/to/file)",
        )

        group.add_argument(
            "--loader-no-verify",
            action="store_true",
            default=cfg("no_verify", type=Bool, default=False),
            help="disable cert verification for HTTP requests",
        )

        group.add_argument(
            "--loader-max-age",
            metavar="SECS",
            type=int,
            default=cfg("max_age", type=Int, default=0),
            help="max age for cached URL data",
        )

        group.add_argument(
            "--loader-str-template",
            metavar="STRING",
            default=cfg("str_template"),
            help="format string used to display an account",
        )

    def instantiate(self, args):
        raise NotImplementedError


class JSON(_CachingLoaderPlugin):
    """CLI plug-in that loads accounts and metadata from a JSON file/url.

    ## Overview

    Accounts specified on the awsrun CLI via the `--account` or `--account-file`
    will be validated against the list of accounts in the JSON document.  More
    importantly, loaded accounts will include metadata associated with each
    account from the JSON document. This metadata can be used to select accounts
    using the `--include` and `--exclude` awsrun CLI flags. Given the following
    JSON structure:

        [
            {"id": "100200300400", "env": "prod", "status": "active"},
            {"id": "200300400100", "env": "non-prod", "status": "active"},
            {"id": "300400100200", "env": "non-prod", "status": "suspended"}
        ]

    Users could select only the "active" accounts via the `awsrun.cli` by using
    the metadata filter options. The following would select account numbers
    "100200300400" and "200300400100":

        $ awsrun --include status=active aws ec2 describe-vpcs --region us-east-1

    Additionally, this metadata is made available to command authors for use
    within their commands. The account loader would build account objects with
    the following attribute names: `id`, `env`, and `status`. Command authors
    are provided access to these account objects in their user-defined commands
    via a parameter to `awsrun.runner.Command.execute`:

        class CLICommand(Command):
            def execute(self, session, acct):
                # The acct parameter contains the attributes from the JSON
                return f'{acct.env} account {acct.id} is {acct.status}\\n'

    In cases where the JSON key names are not valid Python identifiers, they are
    munged. Leading digits are prefixed with underscores, non-alpha numeric
    characters are replaced with underscores, and keywords are appended with an
    underscore.

    Instead of specifying accounts as a JSON array of objects as shown above,
    the JSON can be specified as a single object with account IDs as keys and
    metadata as values such as:

        {
            "100200300400": {"env": "prod", "status": "active"},
            "200300400100": {"env": "non-prod", "status": "active"},
            "300400100200": {"env": "non-prod", "status": "suspended"}
        }

    The above will create the same list account objects as the first version
    because this loader assumes a top-level JSON object is the container of
    accounts. The account objects created will contain the `id` attribute
    because the default value for the ID attribute is `id`.

    Similarly, the JSON can be specified as follows, where the account ID is
    used in the top-level object key as well as the object value metadata:

        {
            "100200300400": {"id": "100200300400", "env": "prod", "status": "active"},
            "200300400100": {"id": "200300400100", "env": "non-prod", "status": "active"},
            "300400100200": {"id": "300400100200", "env": "non-prod", "status": "suspended"}
        }

    Finally, if the account list is not at the top-level of the JSON, a path
    can be specified to point the loader to the correct location in the JSON.
    For example, a path list of "aws" and "accounts" is required to parse the
    following JSON:

        {
            "aws":
            {
                "accounts":
                [
                    {"id": "100200300400", "env": "prod", "status": "active"},
                    {"id": "200300400100", "env": "non-prod", "status": "active"},
                    {"id": "300400100200", "env": "non-prod", "status": "suspended"}
                ]
            }
        }

    ## Configuration

    Options with an asterisk are mandatory and must be provided:

        Accounts:
          plugin: awsrun.plugins.accts.JSON
          options:
            url: STRING*
            max_age: INTEGER
            id_attr: STRING*
            path:
              - STRING
            str_template: STRING
            include_attrs:
              - STRING
            exclude_attrs:
              - STRING
            no_verify: BOOLEAN

    ## Plug-in Options

    Some options can be overridden on the awsrun CLI via command line flags.
    In those cases, the CLI flags are specified next to the option name below:

    `url`, `--loader-url`
    : Load the data from the specified URL. To load a local file, use
    `file:///absolute/path/data.json`. This value **must** be provided via the
    user configuration or as an awsrun command line argument.

    `max_age`, `--loader-max-age`
    : Cache the data retrieved from the URL for the specified number of seconds.
    The default value is `0`, which disables caching. This can be useful for
    servers that are slow to generate the account list.

    `id_attr`
    : Identifies the JSON key name that contains the AWS account ID. This
    value **must** be provided so awsrun can identify the account number
    associated with each account in the JSON.

    `path`
    : Specifies the location within the JSON that contains the array of accounts
    or object of accounts. If specified, this must be a list of key names to
    traverse the JSON. The default assumes the accounts are at the top-level.

    `str_template`, `--loader-str-template`
    : Controls how accounts are formatted as strings. This is a [Python format
    string](https://docs.python.org/3.7/library/string.html#format-string-syntax)
    that can include any of the included attributes. For example, `"{id}:{env}"`
    or `"{id}-{env}"` assuming `id` and `env` are JSON key names.

    `include_attrs`
    : Include only the specified list of JSON key names from the object
    metadata. If this option is not supplied, all JSON keys are included as
    attributes on the account objects created by this loader.

    `exclude_attrs`
    : Exclude the specified list of JSON key names from the object metadata. If
    this option is not supplied, no key names are excluded as attributes on
    the account objects created by this loader.

    `no_verify`, `--loader-no-verify`
    : Disable HTTP certificate verification. This is not advisable and user will
    be warned on the command line if verification has been disabled. The default
    value is `false`.
    """

    def instantiate(self, args):
        cfg = self.cfg

        loader = JSONAccountLoader(
            url=args.loader_url,
            max_age=args.loader_max_age,
            id_attr=cfg("id_attr", must_exist=True),
            path=cfg("path", type=List(Str), default=[]),
            str_template=args.loader_str_template,
            include_attrs=cfg("include_attrs", type=List(Str), default=[]),
            exclude_attrs=cfg("exclude_attrs", type=List(Str), default=[]),
            no_verify=args.loader_no_verify,
        )

        return loader


class YAML(_CachingLoaderPlugin):
    """CLI plug-in that loads accounts and metadata from a YAML file/url.

    ## Overview

    Accounts specified on the awsrun CLI via the `--account` or `--account-file`
    will be validated against the list of accounts in the YAML document.  More
    importantly, loaded accounts will include metadata associated with each
    account from the YAML document. This metadata can be used to select accounts
    using the `--include` and `--exclude` awsrun CLI flags. Given the following
    YAML structure:

        - id: '100200300400'
          env: prod
          status: active
        - id: '200300400100'
          env: non-prod
          status: active
        - id: '300400100200'
          env: non-prod
          status: suspended

    Users could select only the "active" accounts via the `awsrun.cli` by using
    the metadata filter options. The following would select account numbers
    "100200300400" and "200300400100":

        $ awsrun --include status=active aws ec2 describe-vpcs --region us-east-1

    Additionally, this metadata is made available to command authors for use
    within their commands. The account loader would build account objects with
    the following attribute names: `id`, `env`, and `status`. Command authors
    are provided access to these account objects in their user-defined commands
    via a parameter to `awsrun.runner.Command.execute`:

        class CLICommand(Command):
            def execute(self, session, acct):
                # The acct parameter contains the attributes from the YAML
                return f'{acct.env} account {acct.id} is {acct.status}\\n'

    In cases where the YAML key names are not valid Python identifiers, they are
    munged. Leading digits are prefixed with underscores, non-alpha numeric
    characters are replaced with underscores, and keywords are appended with an
    underscore.

    Instead of specifying accounts as a YAML array of objects as shown above,
    the YAML can be specified as a single object with account IDs as keys and
    metadata as values such as:

        '100200300400':
          env: prod
          status: active
        '200300400100':
          env: non-prod
          status: active
        '300400100200':
          env: non-prod
          status: suspended

    The above will create the same list account objects as the first version
    because this loader assumes a top-level YAML object is the container of
    accounts. The account objects created will contain the `id` attribute
    because the default value for the ID attribute is `id`.

    Similarly, the YAML can be specified as follows, where the account ID is
    used in the top-level object key as well as the object value metadata. If
    the values do not match, an exception will be raised.

        '100200300400':
          id: '100200300400'
          env: prod
          status: active
        '200300400100':
          id: '200300400100'
          env: non-prod
          status: active
        '300400100200':
          id: '300400100200'
          env: non-prod
          status: suspended

    Finally, if the account list is not at the top-level of the YAML, a path
    can be specified to point the loader to the correct location in the YAML.
    For example, a path list of "aws" and "accounts" is required to parse the
    following YAML:

        aws:
          accounts:
            - id: '100200300400'
              env: prod
              status: active
            - id: '200300400100'
              env: non-prod
              status: active
            - id: '300400100200'
              env: non-prod
              status: suspended

    ## Configuration

    Options with an asterisk are mandatory and must be provided:

        Accounts:
          plugin: awsrun.plugins.accts.YAML
          options:
            url: STRING*
            max_age: INTEGER
            id_attr: STRING*
            path:
              - STRING
            str_template: STRING
            include_attrs:
              - STRING
            exclude_attrs:
              - STRING
            no_verify: BOOLEAN

    ## Plug-in Options

    Some options can be overridden on the awsrun CLI via command line flags.
    In those cases, the CLI flags are specified next to the option name below:

    `url`, `--loader-url`
    : Load the data from the specified URL. To load a local file, use
    `file:///absolute/path/data.yaml`. This value **must** be provided via the
    user configuration or as an awsrun command line argument.

    `max_age`, `--loader-max-age`
    : Cache the data retrieved from the URL for the specified number of seconds.
    The default value is `0`, which disables caching. This can be useful for
    servers that are slow to generate the account list.

    `id_attr`
    : Identifies the YAML key name that contains the AWS account ID. This
    value **must** be provided so awsrun can identify the account number
    associated with each account in the YAML.

    `path`
    : Specifies the location within the YAML that contains the array of accounts
    or object of accounts. If specified, this must be a list of key names to
    traverse the YAML. The default assumes the accounts are at the top-level.

    `str_template`, `--loader-str-template`
    : Controls how accounts are formatted as strings. This is a [Python format
    string](https://docs.python.org/3.7/library/string.html#format-string-syntax)
    that can include any of the included attributes. For example, `"{id}:{env}"`
    or `"{id}-{env}"` assuming `id` and `env` are YAML key names.

    `include_attrs`
    : Include only the specified list of YAML key names from the object
    metadata. If this option is not supplied, all YAML keys are included as
    attributes on the account objects created by this loader.

    `exclude_attrs`
    : Exclude the specified list of YAML key names from the object metadata. If
    this option is not supplied, no key names are excluded as attributes on
    the account objects created by this loader.

    `no_verify`, `--loader-no-verify`
    : Disable HTTP certificate verification. This is not advisable and user will
    be warned on the command line if verification has been disabled. The default
    value is `false`.
    """

    def instantiate(self, args):
        cfg = self.cfg

        loader = YAMLAccountLoader(
            url=args.loader_url,
            max_age=args.loader_max_age,
            id_attr=cfg("id_attr", must_exist=True),
            path=cfg("path", type=List(Str), default=[]),
            str_template=args.loader_str_template,
            include_attrs=cfg("include_attrs", type=List(Str), default=[]),
            exclude_attrs=cfg("exclude_attrs", type=List(Str), default=[]),
            no_verify=args.loader_no_verify,
        )

        return loader


class CSV(_CachingLoaderPlugin):
    """CLI plug-in loads accounts and metadata from a CSV file/url.

    ## Overview

    Accounts specified on the awsrun CLI via the `--account` or `--account-file`
    will be validated against the list of accounts in the CSV file.  More
    importantly, loaded accounts will include metadata associated with the
    columns from the CSV file. This metadata can be used to select accounts
    using the `--include` and `--exclude` awsrun CLI flags.

    The default delimiter is comma, but may be changed via an option. The
    column names must be specified on the first row of the CSV file and will
    become the attribute names on the loaded account objects. All values are
    treated as strings, and thus account IDs do not need to be quoted. Given the
    following CSV file:

         id, env, status
         100200300400, prod, active
         200300400100, non-prod, active
         300400100200, non-prod, suspended

    Users could select only the "active" accounts via the `awsrun.cli` by using
    the metadata filter options. The following would select account numbers
    "100200300400" and "200300400100":

        $ awsrun --include status=active aws ec2 describe-vpcs --region us-east-1

    Additionally, this metadata is made available to command authors for use
    within their commands. The account loader would build account objects with
    the following attribute names: `id`, `env`, and `status`. Command authors
    are provided access to these account objects in their user-defined commands
    via a parameter to `awsrun.runner.Command.execute`:

        class CLICommand(Command):
            def execute(self, session, acct):
                # The acct parameter contains the attributes from the CSV
                return f'{acct.env} account {acct.id} is {acct.status}\\n'

    In cases where the CSV column names are not valid Python identifiers, they
    are munged. Leading digits are prefixed with underscores, non-alpha numeric
    characters are replaced with underscores, and keywords are appended with an
    underscore.

    ## Configuration

    Options with an asterisk are mandatory and must be provided:

        Accounts:
          plugin: awsrun.plugins.accts.CSV
          options:
            url: STRING*
            delimiter: STRING
            max_age: INTEGER
            id_attr: STRING*
            str_template: STRING
            include_attrs:
              - STRING
            exclude_attrs:
              - STRING
            no_verify: BOOLEAN

    ## Plug-in Options

    Some options can be overridden on the awsrun CLI via command line flags.
    In those cases, the CLI flags are specified next to the option name below:

    `url`, `--loader-url`
    : Load the data from the specified URL. To load a local file, use
    `file:///absolute/path/data.csv`. This value **must** be provided via the
    user configuration or as an awsrun command line argument.

    `delimiter`, `--loader-delimiter`
    : Use the specified character as the delimiter for the CSV data. The default
    value is `","`.

    `max_age`, `--loader-max-age`
    : Cache the data retrieved from the URL for the specified number of seconds.
    The default value is `0`, which disables caching. This can be useful for
    servers that are slow to generate the account list.

    `id_attr`
    : Identifies the CSV column name that contains the AWS account ID. This
    value **must** be provided so awsrun can identify the account number
    associated with each row of account data.

    `str_template`, `--loader-str-template`
    : Controls how accounts are formatted as strings. This is a [Python format
    string](https://docs.python.org/3.7/library/string.html#format-string-syntax)
    that can include any of the included attributes. For example, `"{id}:{env}"`
    or `"{id}-{env}"` assuming `id` and `env` are column names in the CSV.

    `include_attrs`
    : Include only the specified list of column names from the CSV. If this
    option is not supplied, all column names are included as attributes on the
    account objects created by this loader.

    `exclude_attrs`
    : Exclude the specified list of column names from the CSV. If this option
    is not supplied, no column names are excluded as attributes on the account
    objects created by this loader.

    `no_verify`, `--loader-no-verify`
    : Disable HTTP certificate verification. This is not advisable and user will
    be warned on the command line if verification has been disabled. The default
    value is `false`.
    """

    def __init__(self, parser, cfg):
        super().__init__(parser, cfg)

        # Define the arguments that we want to allow a user to override via the
        # main CLI. Any CLI args added via add_argument will be commingled with
        # the main awsrun args, so they are prefixed with '--loader-' to lessen
        # chance of collision.
        group = parser.add_argument_group("CSV account loader options")
        group.add_argument(
            "--loader-delimiter",
            metavar="CHAR",
            default=cfg("delimiter", default=","),
            help="delimiter used in CSV file",
        )

    def instantiate(self, args):
        cfg = self.cfg

        loader = CSVAccountLoader(
            url=args.loader_url,
            max_age=args.loader_max_age,
            delimiter=args.loader_delimiter,
            id_attr=cfg("id_attr", must_exist=True),
            str_template=args.loader_str_template,
            include_attrs=cfg("include_attrs", type=List(Str), default=[]),
            exclude_attrs=cfg("exclude_attrs", type=List(Str), default=[]),
            no_verify=args.loader_no_verify,
        )

        return loader


class URLLoader(Plugin):
    """CLI plug-in that loads accounts and metadata from a file/url.

    ## Overview

    Accounts specified on the awsrun CLI via the `--account` or
    `--account-file` will be validated against the list of accounts loaded
    from this URL.  More importantly, loaded accounts will include metadata
    associated with each account from the document. This metadata can be used
    to select accounts using the `--include` and `--exclude` awsrun CLI flags.
    Given the following JSON document:

        [
            {"id": "100200300400", "env": "prod", "status": "active"},
            {"id": "200300400100", "env": "non-prod", "status": "active"},
            {"id": "300400100200", "env": "non-prod", "status": "suspended"}
        ]

    Users could select only the "active" accounts via the `awsrun.cli` by using
    the metadata filter options. The following would select account numbers
    "100200300400" and "200300400100":

        $ awsrun --include status=active aws ec2 describe-vpcs --region us-east-1

    Additionally, this metadata is made available to command authors for use
    within their commands. The account loader would build account objects with
    the following attribute names: `id`, `env`, and `status`. Command authors
    are provided access to these account objects in their user-defined commands
    via a parameter to `awsrun.runner.Command.execute`:

        class CLICommand(Command):
            def execute(self, session, acct):
                # The acct parameter contains the attributes from the JSON
                return f'{acct.env} account {acct.id} is {acct.status}\\n'

    In cases where the JSON key names are not valid Python identifiers, they are
    munged. Leading digits are prefixed with underscores, non-alpha numeric
    characters are replaced with underscores, and keywords are appended with an
    underscore.

    Instead of specifying accounts as a JSON array of objects as shown above,
    the JSON can be specified as a single object with account IDs as keys and
    metadata as values such as:

        {
            "100200300400": {"env": "prod", "status": "active"},
            "200300400100": {"env": "non-prod", "status": "active"},
            "300400100200": {"env": "non-prod", "status": "suspended"}
        }

    The above will create the same list account objects as the first version
    because this loader assumes a top-level JSON object is the container of
    accounts. The account objects created will contain the `id` attribute
    because the default value for the ID attribute is `id`.

    Similarly, the JSON can be specified as follows, where the account ID is
    used in the top-level object key as well as the object value metadata:

        {
            "100200300400": {"id": "100200300400", "env": "prod", "status": "active"},
            "200300400100": {"id": "200300400100", "env": "non-prod", "status": "active"},
            "300400100200": {"id": "300400100200", "env": "non-prod", "status": "suspended"}
        }

    If the account list is not at the top-level of the JSON, a path can be
    specified to point the loader to the correct location in the JSON. For
    example, a path list of "aws" and "accounts" is required to parse the
    following JSON:

        {
            "aws":
            {
                "accounts":
                [
                    {"id": "100200300400", "env": "prod", "status": "active"},
                    {"id": "200300400100", "env": "non-prod", "status": "active"},
                    {"id": "300400100200", "env": "non-prod", "status": "suspended"}
                ]
            }
        }

    The `URLLoader` can parse JSON, YAML, or CSV files loaded from a URL. Data
    can be loaded from a local file via the "file:///" URL syntax. By default,
    JSON is assumed. This can be overrided via the `parser` option. Parsing
    options such as the CSV delimiter can be specified via `parser_options`.
    When parsing CSV files, the header row is required as its names are the
    key names for the metadata associated with each account.

    If the URL requires authentication, specify one of the supported types:
    "none", "basic", "digest", "ntlm", or "oauth2" via the `auth` option. By
    default, no authentication is used. Authentication options for the URL
    such as username and password can be specified via `auth_options`.

    ## Configuration

    Options with an asterisk are mandatory and must be provided:

        Accounts:
          plugin: awsrun.plugins.accts.URLLoader
          options:
            url: STRING*
            auth: STRING ("none", "basic", "digest", "ntlm", "oauth2")
            auth_options:
              username: STRING
              password: STRING
              token_url: URL (oauth2 only)
              scope: STRING (oauth2 only, default "AppIdClaimsTrust")
              grant_type: STRING (oauth2 only, default "client_credentials")
            parser: STRING ("json", "yaml", "csv")
            parser_options:
              delimiter: STRING (csv only, default ",")
            max_age: INTEGER
            id_attr: STRING*
            path:
              - STRING
            str_template: STRING
            include_attrs:
              - STRING
            exclude_attrs:
              - STRING
            no_verify: BOOLEAN

    ## Plug-in Options

    Some options can be overridden on the awsrun CLI via command line flags.
    In those cases, the CLI flags are specified next to the option name below:

    `url`, `--loader-url`
    : Load the data from the specified URL. To load a local file, use
    `file:///absolute/path/data.json`. This value **must** be provided via the
    user configuration or as an awsrun command line argument.

    `auth`
    : Identifies the authentication type required by the URL. The default
    value is "none". Valid options include "none", "basic", "digest", "ntml",
    and "oauth2". All but "none" require that username` and `password` keys
    in `auth_options`. In addition, "oauth2" requires `token_url` key.

    `auth_options`
    : Provides options required for the specified `auth` type chosen.  The use
    of "basic", "digest", "ntml", or "oauth2" require `username` and
    `password` keys in `auth_options`. Use of "oauth2" also requires a
    `token_url` that points to the token provider. Three optional keys can be
    provided with "oauth2" to override defaults: `scope` ("AppIdClaimsTrust"),
    `grant_type` ("client_credentials"), or `intent` ("awsrun account loader
    plugin").

    `parser`
    : Specifies the parser used to parse data from the URL. The default value
    is "json". Valid options include "json", "yaml", and "csv".

    `parser_options`
    : Provides additional options to the parser method used to parse the data
    from the URL: `json.loads`, `yaml.safe_load`, and `csv.DictReader`. Most
    often this would be used to change the `delimiter` used with the CSV
    parser.

    `max_age`, `--loader-max-age`
    : Cache the data retrieved from the URL for the specified number of seconds.
    The default value is `0`, which disables caching. This can be useful for
    servers that are slow to generate the account list.

    `id_attr`
    : Identifies the JSON/YAML key name that contains the AWS account ID. This
    value **must** be provided so awsrun can identify the account number
    associated with each account in the JSON/YAML.

    `path`
    : Specifies the location within the JSON/YAML that contains the array of
    accounts or object of accounts. If specified, this must be a list of key
    names to traverse the JSON/YAML. The default assumes the accounts are at
    the top-level.

    `str_template`, `--loader-str-template`
    : Controls how accounts are formatted as strings. This is a [Python format
    string](https://docs.python.org/3.7/library/string.html#format-string-syntax)
    that can include any of the included attributes. For example, `"{id}:{env}"`
    or `"{id}-{env}"` assuming `id` and `env` are JSON/YAML/CSV key names.

    `include_attrs`
    : Include only the specified list of JSON/YAML/CSV key names from the
    object metadata. If this option is not supplied, all JSON/YAML/CSV keys
    are included as attributes on the account objects created by this loader.

    `exclude_attrs`
    : Exclude the specified list of JSON/YAML/CSV key names from the object
    metadata. If this option is not supplied, no key names are excluded as
    attributes on the account objects created by this loader.

    `no_verify`, `--loader-no-verify`
    : Disable HTTP certificate verification. This is not advisable and user will
    be warned on the command line if verification has been disabled. The default
    value is `false`.
    """

    def __init__(self, parser, cfg):
        super().__init__(parser, cfg)

        # Define the arguments that we want to allow a user to override via the
        # main CLI. Any CLI args added via add_argument will be commingled with
        # the main awsrun args, so they are prefixed with '--loader-' to lessen
        # chance of collision.
        group = parser.add_argument_group("account loader options")
        group.add_argument(
            "--loader-url",
            metavar="URL",
            default=cfg("url", type=URL, must_exist=True),
            help="URL to account data (also supports file:///path/to/file)",
        )

        group.add_argument(
            "--loader-auth",
            metavar="STRING",
            default=cfg(
                "auth",
                type=Choice("none", "basic", "digest", "ntml", "oauth2"),
                default="none",
            ),
            help="Authentication type required by the URL",
        )

        group.add_argument(
            "--loader-username",
            metavar="USER",
            help="username (or client_id) for account loader authentication",
        )

        group.add_argument(
            "--loader-password",
            metavar="PASS",
            help="password (or client_secret) for account loader authentication",
        )

        group.add_argument(
            "--loader-parser",
            metavar="STRING",
            default=cfg("parser", type=Choice("json", "yaml", "csv"), default="json"),
            help="Parser used on data from URL",
        )

        group.add_argument(
            "--loader-no-verify",
            action="store_true",
            default=cfg("no_verify", type=Bool, default=False),
            help="disable cert verification for HTTP requests",
        )

        group.add_argument(
            "--loader-cache-path",
            metavar="PATH",
            type=Path,
            default=cfg("cache_path", type=File),
            help="max age for cached URL data",
        )

        group.add_argument(
            "--loader-max-age",
            metavar="SECS",
            type=int,
            default=cfg("max_age", type=Int, default=0),
            help="max age for cached URL data",
        )

        group.add_argument(
            "--loader-str-template",
            metavar="STRING",
            default=cfg("str_template"),
            help="format string used to display an account",
        )

    def instantiate(self, args):
        cfg = self.cfg

        auth_options = cfg("auth_options", type=Dict(Str, Any), default={})

        # Check and set auth options if using authentication.
        if args.loader_auth != "none":

            # Command line flags take priority
            if args.loader_username:
                auth_options["username"] = args.loader_username
            if args.loader_password:
                auth_options["password"] = args.loader_password

            # If a username and password has not been provided via CLI flags
            # or via the configuration file, we'll fallback to environment
            # variables if they exist, or lastly we'll prompt the user
            # interactively. BUT, we don't want to do that here because the
            # URLAccountLoader caches data, so we might not need to make an
            # HTTP call, and thus prompting the user would be unneeded (and
            # annoying). So, instead, we use DeferPrompting to wrap the
            # various requests HTTP*Auth classes. This will defer the
            # instantiation of those classes until `requests` invokes the
            # callable `auth` parameter to its various methods.

            if args.loader_auth == "oauth2" and "token_url" not in auth_options:
                raise TypeError(
                    "with oauth2 authentication token_url must be set in config: Accounts->options->auth_options->token_url"
                )

        auth_types = {
            "none": _HTTPNone(),
            "basic": _DeferPrompting(HTTPBasicAuth, auth_options),
            "digest": _DeferPrompting(HTTPDigestAuth, auth_options),
            "ntlm": _DeferPrompting(HttpNtlmAuth, auth_options),
            "oauth2": _DeferPrompting(HTTPOAuth2, auth_options),
        }
        auth = auth_types[args.loader_auth]

        parsers = {
            "json": JSONParser,
            "yaml": YAMLParser,
            "csv": CSVParser,
        }
        parser_options = cfg("parser_options", type=Dict(Str, Any), default={})

        try:
            parser = parsers[args.loader_parser](**parser_options)
        except TypeError as e:
            raise TypeError(
                f"incompatible parser_options specified in config: Accounts->options->parser_options: {e}"
            )

        loader = URLAccountLoader(
            url=args.loader_url,
            parser=parser,
            auth=auth,
            max_age=args.loader_max_age,
            id_attr=cfg("id_attr", must_exist=True),
            path=cfg("path", type=List(Str), default=[]),
            str_template=args.loader_str_template,
            include_attrs=cfg("include_attrs", type=List(Str), default=[]),
            exclude_attrs=cfg("exclude_attrs", type=List(Str), default=[]),
            no_verify=args.loader_no_verify,
            cache_path=args.loader_cache_path,
        )

        return loader


def _default_username():
    return os.environ.get("AWSRUN_LOADER_USERNAME", None) or getpass.getuser()


def _default_password(user):
    return os.environ.get("AWSRUN_LOADER_PASSWORD", None) or getpass.getpass(
        f"Account loader password for {user}? "
    )


# Helper class to wrap one of `requests` auth classes to defer instantiation
# of those classes until `requests` actually needs to use the auth data. This
# is used to avoid interactively prompting a user for their password if one
# had not been specified via CLI args or their config file. The default will
# come from the env variable if set, otherwise the user is prompted. But we
# don't want to prompt when we instantiated the `requests` auth classes
# because at that time, we do not know if the account loader data has been
# cached and thus not require making an HTTP call. So, why bother prompting
# the user in that case?
class _DeferPrompting(AuthBase):
    def __init__(self, auth_class, auth_options):
        self.auth_class = auth_class
        self.auth_options = auth_options

    def __call__(self, req):
        if "username" not in self.auth_options:
            self.auth_options["username"] = _default_username()
        if "password" not in self.auth_options:
            self.auth_options["password"] = _default_password(
                self.auth_options["username"]
            )
        try:
            auth = self.auth_class(**self.auth_options)
        except TypeError as e:
            raise TypeError(
                f"incompatible auth_options specified in config: Accounts->options->auth_options: {e}"
            )
        return auth(req)


class _HTTPNone:
    """HTTPNone is a no-op auth type for requests library."""

    def __init__(self, *args, **kwargs):
        return None

    def __call__(self, req):
        return req
