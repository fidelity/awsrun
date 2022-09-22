#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""The awsrun CLI concurrently executes commands across AWS accounts.

## Overview

The CLI is a tool that can execute user-defined commands across one or more
accounts concurrently. This page contains both a [User Guide](#cli-user-guide)
to the CLI as well as a [Reference Guide](#cli-reference) for command line
arguments and configuration options. The user guide is intended to be a gentle
introduction on the usage and configuration of the awsrun CLI. For a general
overview of features and installation instructions, refer to the
[awsrun](https://github.com/fidelity/awsrun) project
page.

## CLI User Guide

The `awsrun.cli` is a full-featured command line tool with a plethora of options
to allow a user to invoke a "command" across one or more AWS accounts. A command
is a Python module that executes a block of Python code -- typically using the
Boto3 library. awsrun includes a handful of built-in commands, but you are
encouraged to build your own collection of user-defined commands.

In this user guide, we'll review the basic usage of the CLI, how to run commands
across accounts, and then later learn how to extend the CLI's behavior via
plug-ins for obtaining credentials and account loading. If you are looking for
reference material instead, then skip ahead to the [Reference
Guide](#cli-reference).

For the remainder of this guide, we'll be using the general purpose
`awsrun.commands.aws.aws` command, which is an adapter for the AWS CLI tool.
This allows users to concurrently run the AWS CLI across multiple accounts. When
combined with other awsrun features such as SAML authentication, cross-account
access, and metadata account filters, it makes the AWS CLI tool even more
powerful than it already is as you'll see.

### Usage

The awsrun CLI accepts several different types of command line options. There
are options for the core awsrun CLI tool itself. Options can also be specified
for plug-ins that are being used. Finally, each command can also define its own
set of command line options to control its behavior. Below is the general syntax
used when invoking the awsrun CLI:

    $ awsrun [core options] [plug-in options] command [command options]

To view a list of all the core and plug-in options, invoke the CLI using only
the `--help` flag. The CLI will print a help message to the console that
contains a detailed listing of options, as well as any defaults that have been
set via your user configuration file (next section). The list of arguments
presented will vary depending on whether or not the plug-ins you are using have
registered arguments.

To view the list of options for the command you have selected, add the `--help`
flag after the name of the command. Instead of printing the general awsrun help
message, the CLI will print the help for the command, which will include the
list of the options available for the command itself and the defaults set via
your user configuration, as well as any additional help the command author has
chosen to include.

With the syntax out of the way, let's now turn to an example to establish the
motivation for using awsrun to execute AWS CLI commands. Assume you manage the
following two AWS accounts, 100200300400 and 200300400100. Further, assume that
you store the profiles for those accounts in your ~/.aws/credentials file. With
only the standard AWS CLI tool, to find the list of VPCs for those accounts in
the us-east-1 and us-west-2 regions, you would execute the following four
commands:

    $ aws --profile 100200300400 --region us-east-1 ec2 describe-vpcs
    $ aws --profile 100200300400 --region us-west-2 ec2 describe-vpcs
    $ aws --profile 200300400100 --region us-east-1 ec2 describe-vpcs
    $ aws --profile 200300400100 --region us-west-2 ec2 describe-vpcs

Now let's use an "out of the box" installation of awsrun. We'll use the built-in
`awsrun.commands.aws.aws` command, which allows you to run an AWS CLI command
concurrently across one or more accounts and one or more regions. The following
command will execute the "ec2 describe-vpcs" across both accounts concurrently:

    $ awsrun --account 100200300400 --account 200300400100 aws ec2 describe-vpcs --region us-east-1 --region us-west-2
    2 accounts selected:

    100200300400, 200300400100

    Proceed (y/n)? y
    ...

We specify each account and region to process via multiple `--account` and
`--region` options. If you want to process a lot of accounts, you can use the
`--account-file` option, which lets you list the accounts, one per line, in a
separate file. Later, we'll explore the account loader plug-ins, which will
allow us to select accounts via metadata filters.

You may be wondering how awsrun obtains the credentials for each account. By
default, awsrun will use the same profiles from your ~/.aws/credentials file. If
a profile does not exist for an account, awsrun will fallback to the "default"
profile if you have one configured. As you'll see later, we can use other
plug-ins to obtain credentials for accounts via SAML and cross-account access.

Using awsrun to run a command over two accounts may not seem that interesting
yet, but when running the same AWS CLI command over more than a handful of
accounts, it becomes incredibly powerful especially when coupled with account
and credential loader plug-ins. Even more powerful is when you start to build
your own commands, which is covered in another guide in the `awsrun.commands`
module.

awsrun executes commands concurrently across accounts via a worker pool, which
contains ten threads by default. You can change this value by specifying the
`--threads N` flag where `N` is the desired number of workers. If you do not
want to concurrently process accounts, then specify a value of 1, which will
ensure accounts are processed one at a time. It should be noted that the unit of
concurrency is the account - not the region. I.e. each region specified will be
executed by the worker dispatched to process an account.

When selecting more than one account, the CLI will prompt you about whether or
not you wish to proceed. This is for your safety to ensure you really want to
execute command the across all of the accounts. This is particularly important
when using metadata filters as you might inadvertently select more than you
expected. You can, however, disable the prompt via the `--force` option, which
can be helpful when using the CLI in a script.

In the next section, we'll create our own user configuration file, so we define
commonly used command line arguments once. We'll also need a configuration file
to specify plug-ins and their arguments.

### Configuration

As mentioned in the [Usage](#usage) section, there are several types of command
line arguments: core options, plug-in options, and command options. Specifying
all of these via the command line can be tedious, especially if you use the same
values all the time. Fortunately, you can define these in a YAML configuration
file. By default, the config is loaded from `$HOME/.awsrun.yaml`. If you prefer
an alternate location, set the `AWSRUN_CONFIG` environment variable to point
elsewhere.

The configuration file consists of four optional top-level sections: `CLI`,
`Commands`, `Accounts`, and `Credentials`. We will hold off on our discussion of
the last two until the plug-in section. For now, however, assume we want to
change the default number of threads that awsrun uses. We could do this via the
`--threads` flag as mentioned previously. Because this flag is a core option of
the CLI, we can add the option to the `CLI` section of the config as follows:

    CLI:
      threads: 15

Likewise, if we become tired of typing the same two accounts on the command
line, we could add those too. Because this flag can be specified more than once,
it must be specified as a list in the config, and more importantly, the account
must be quoted as AWS account numbers can have leading zeros:

    CLI:
      threads: 15
      account:
        - '100200300400'
        - '200300400100'

Don't worry, if you forget to quote the account numbers, the CLI type checks all
values in the configuration and will complain if you use a number by accident.
For more information on the core command line arguments and their corresponding
configuration keys, please refer to `awsrun.cli`.

In addition to core options, you can add defaults for specific awsrun commands
in the top-level `Commands` section of the config. Again, using our previous
example, assume you always want to use "us-east-1" and "us-west-2" as the
regions when using the `awsrun.commands.aws.aws` command. All we need to do is
add an `aws` key, the name of the command, in the `Commands` section:

    Commands:
      aws:
        region:
          - us-east-1
          - us-west-2

Commands can define their own command line flags and configuration options. You
will need to refer to the documentation for each command for more information.
For example, you can find the valid flags and configuration options for the aws
command on the `awsrun.commands.aws.aws` page.

In the next section, we'll explore how to take advantage of the awsrun plug-ins
for account and credential loading.

### Credential Plug-ins

Up until this point, we have been using the default credential loader called
`awsrun.plugins.creds.aws.Profile`, which looks for account profiles in your
`$HOME/.aws/credentials` or `$HOME/.aws/config`. Let's look at some of the other
mechanisms included with awsrun such as the SAML and cross-account access
plug-ins. If you are only seeking reference material, please refer to the
`awsrun.plugins.creds` page instead.

Within many enterprises, the use of single sign-on (SSO) is prevalent and allows
for centralized account management. AWS supports federated users and SSO via the
use of a SAML-compliant Identity Provider (IdP). Rather than define IAM users in
each account, an IAM role can be created that allows for federated access via
your IdP. To use SAML-based access with AWS, you need to obtain temporary tokens
from the AWS STS service.

The `awsrun.plugins.creds.aws.SAML` credential plug-in simplifies this process
for you. At a minimum, you'll need the IAM role that has been setup for SAML as
well as the URL to your IdP. Let's assume you are using Microsoft's ADFS server
as your IdP. We'll need to add a new top-level block to our configuration called
`Credentials` with a `plugin` key that points to the SAML plug-in along with
several `options` to configure its behavior:

    Credentials:
      plugin: awsrun.plugins.creds.aws.SAML
      options:
        role: OperationsStaff
        url: 'https://adfs.example.com/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices'
        auth_type: ntlm

With the plug-in configured, we can now invoke our awsrun command as we did
before, but this time we'll specify the username to use when authenticating with
the IdP server via the `--saml-username` flag. Because we are using ADFS in this
example, we must be sure to pass our domain as part of the username. Note, if we
were using another IdP, then you might not need to specify the domain:

    $ awsrun --account 100200300400 --saml-username "dmn\\pete" aws ec2 describe-vpcs --region us-east-1
    Password for dmn\\pete?
    ...

Alternatively, rather than specifying the username every time on the command
line, we can add it to the user configuration instead as follows:

    Credentials:
      plugin: awsrun.plugins.creds.aws.SAML
      options:
        username: "dmn\\pete"
        role: OperationsStaff
        url: 'https://adfs.example.com/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices'
        auth_type: ntlm

And like most configuration values, we can still override that value with the
appropriate command line flag if needed. Don't forget that you can use the help
system to obtain a list of the available command line options for the plug-in:

    $ awsrun --help
    ...
    SAML options:
      --saml-username USER  username for SAML authentication (default: dmn\\pete)
      --saml-password PASS  password for SAML authentication (default: None)
      --saml-role ROLE      base role to assume via SAML (default: OperationsStaff)
      --saml-duration SECS  duration when requesting aws credentials in assume_role* (default: 3600)
      --saml-assertion-duration SECS
                            length of time to cache SAML assertion from IdP (default: 300)
      --saml-no-verify      disable cert verification for HTTP requests (default: False)
    ...

For more information on the SAML plug-in configuration options and command line
arguments, please refer to `awsrun.plugins.creds.aws.SAML`.

Now, let's turn our attention to cross-account access, which is commonly used
when managing hundreds of accounts. With cross-account access, users are granted
access to an IAM role in a single base account from which they can use to assume
a role into another account. This eliminates the need to grant the user access
to all of your AWS accounts, and thus simplifying the management of IAM access.

awsrun includes two cross-account plug-ins that you can use depending on how you
want to obtain credentials for the base role. One supports the use of profiles
and your AWS credential files while the other supports SAML for federated access
to the base account. Let's assume our base account is 900900900900, and it has a
role called OperationsStaff configured for SAML-based authentication. To use the
`awsrun.plugins.creds.aws.SAMLCrossAccount` plug-in, we would add the following
to our configuration:

    Credentials:
      plugin: awsrun.plugins.creds.aws.SAMLCrossAccount
      options:
        username: "dmn\\pete"
        role: OperationsStaff
        url: 'https://adfs.example.com/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices'
        auth_type: ntlm
        x_acct:
          base: '900900900900'
          role: OperationsStaff

You'll notice that most of the configuration is the same as our previous SAML
example with the exception of the `x_acct` block, which specifies our base
account as well as the cross-account role to use when making the assume role
call to the accounts being processed. Note, the `role` key in the `x_acct`
section specifies the cross-account role to assume, it is not the role used to
access the base account, which is the `role` in the `options` block.

Now when we run the awsrun command as before, the CLI obtains temporary
credentials via SAML for the base account, and then uses those credentials to
obtain a temporary credentials for each account being processed by awsrun all
without any hassle:

    $ awsrun --account 100200300400 --saml-username "dmn\\pete" aws ec2 describe-vpcs --region us-east-1
    Password for dmn\\pete?
    ...

Again, as before with the SAML plug-in, there are several options that can be
provided via the command line, which can now be seen via help:

    $ awsrun --help
    ...
    cross-account options:
      --x-acct-base ACCT        base account to assume role from (default: 900900900900)
      --x-acct-role ROLE        cross-account role to assume (default: OperationsStaff)
      --x-acct-external-id ID   external id to use when assuming role in cross-account (default: None)
      --x-acct-duration SECS    duration when requesting aws credentials in assume_role* (default: 3600)
    ...

For more information on the configuration options and command line arguments,
please see `awsrun.plugins.creds.aws.SAMLCrossAccount`. Finally, if none of the
included credential plug-ins suit your needs, you can build your own, refer to
the [User-Defined Plug-ins](index.html#user-defined-plug-ins) section of the
guide.

In the next section, we will complete our walk-thru of the awsrun CLI by
introducing the account loader plug-in, which can greatly enhance the power of
awsrun.

### Account Plug-Ins

Thus far in our tour of awsrun, we've had to explicitly specify each account to
process either through command line arguments or via the user configuration.
While sufficient when you only have a few accounts to select, it becomes
difficult to specify anything beyond a handful of accounts. Wouldn't it be nice
if you could select groups of accounts to process? Perhaps you want to run a
command across all of your production accounts, or maybe run a command across
all of the accounts of a business unit? Well, you can, by using an account
loader plug-in, either one of the included or one you build yourself. If you are
seeking reference material only, please refer to the `awsrun.plugins.accts` page.

The account loader plug-in is responsible for loading the full list of the
accounts you manage as well as the metadata associated with each account. Using
this metadata, we can specify filters on the command line or via your config to
select groups of accounts to process. awsrun includes plug-ins to load account
information from CSV, JSON, and YAML files/urls. If, on the other hand, you have
an enterprise CMDB that stores information about your accounts in a database,
then you could write your own plug-in to load accounts from it.

For the purpose of this guide, let's keep things simple and assume you have a
list of accounts and metadata for those accounts stored in a JSON file called
"/home/pete/accounts.json":

    $ cat accounts.json
    {
        "accounts": [
            { "acct": "100200300400", "env": "dev", "priority": 2, "bu": "retail" },
            { "acct": "200300400100", "env": "prd", "priority": 1, "bu": "retail" },
            { "acct": "300400100200", "env": "dev", "priority": 3, "bu": "wholesale" },
            { "acct": "400100200300", "env": "prd", "priority": 2, "bu": "wholesale" },
            { "acct": "900900900900", "env": "dev", "priority": 2, "bu": "retail" }
        ]
    }

We'll use the `awsrun.plugins.accts.JSON` plug-in to load the accounts, so we
can explore how to use the CLI's metadata filters to select accounts. To do so,
we need to add the following top-level block to our configuration file:

    Accounts:
      plugin: awsrun.plugins.accts.JSON
      options:
        url: file:///home/pete/accounts.json
        path:
          - accounts
        id_attr: acct

The `url` key specifies the path of a local file, but this could be a URL to a
web server that returns the same information. The `path` key is a list of keys
to traverse before reaching the actual list of accounts. In our example JSON
file above, all of the accounts are embedded within the "accounts" key. Finally,
the `id_attr` key provides the name of the key that contains the account number
for each account.

Note: if you've been following this guide from the beginning, then you will want
to remove the explicit list of `accounts` in the top-level `CLI` block of your
configuration, or your results will not be the same in the following examples.
If you do not, the metadata filters will apply only to the explicit list of
accounts you have specified.

With the plug-in configured, we can now use the help system to view the various
options defined by the JSON plug-in:

    $ awsrun --help
    ...
    account loader options:
      --loader-url URL       URL to account data (default: file:///tmp/accounts.json)
      --loader-no-verify     disable cert verification for HTTP requests (default: False)
      --loader-max-age SECS  max age for cached URL data (default: 0)
      --loader-str-template STRING  format string used to display an account (default: None)
    ...

In the same output, you'll also find a group of core awsrun options for account
selection, which we're going to use:

    $ awsrun --help
    ...
    account selection options:
      --account ACCT        run command on specified list of accounts (default: [])
      --account-file FILE   filename containing accounts (one per line) (default: None)
      --metadata [ATTR]     summarize metadata that can be used in filters (default: None)
      --include ATTR=VAL    include filter for accounts (default: {})
      --exclude ATTR=VAL    exclude filter for accounts (default: {})
    ...

Let's see how we take advantage of using metadata to select accounts from the
CLI to process. First, we'll list the metadata attributes that we can use:

    $ awsrun --metadata
    Valid metadata attributes:

    acct
    bu
    env

In the above output, we see the three attributes that are assigned to each
account. If we want to explore the values for one of those attributes, we can do
the following:

    $ awsrun --metadata env
    Metadata values for 'env' attribute:

    dev
    prd

Now that we know how to explore the available metadata, let's use it to select
accounts to process, which is the main benefit of using an account loader
plug-in. You'll note that we don't specify an awsrun command to execute in
the next several examples because the default behavior of the CLI is to print
the select accounts to the screen along with the list of valid commands it has
found. In the example below, we select only the "dev" accounts using the
metadata`--include ATTR=VALUE` flag:

    $ awsrun --include env=dev
    3 accounts selected:

    100200300400, 300400100200, 900900900900
    ...

If we want to select "dev" or "prd" accounts, we can specify the include flag
twice for each value, or we can combine values. When specifying more than one
value for a filter attribute, a match is successful if only one of the values
matches:

    $ awsrun --include env=dev,prd
    5 accounts selected:

    100200300400, 200300400100, 300400100200, 400100200300, 900900900900
    ...

Not only can we filter on multiple values for an attribute, we can filter on
multiple attributes. When using multiple attributes, all of the filters must
match. Here is how we would select all the "dev" and "prd" accounts for the
"retail" business unit:

    $ awsrun --include env=dev,prd --include bu=retail
    3 accounts selected:

    100200300400, 200300400100, 900900900900

What if we want to select all of the priority "1" accounts?  Recall, the
priority attribute in our JSON has integer values, so we must typecast our
filter's value on the command line to an "int" using the `--include
ATTR=TYPE:VALUE` format:

    $ awsrun --include priority=int:1
    1 account selected:

    200300400100

The supported cast operators include: `str`, `int`, `float`, or `bool`. By
default, filter values are treated as strings, but this does not prevent you
from performing an explicit cast if desired:

    $ awsrun --include env=str:dev,prd
    5 accounts selected:

    100200300400, 200300400100, 300400100200, 400100200300, 900900900900
    ...

We can also use `--exclude ATTR=VALUE` flag to exclude accounts from being
selected. This flag can be used by itself or in conjunction with include
filters. For example, if we want to select all of the "prd" accounts except for
the priority "1" accounts:

    $ awsrun --include env=prd --exclude priority=int:1
    1 account selected:

    400100200300

When using the built-in `awsrun.plugins.accts.CSV` or
`awsrun.plugins.accts.JSON` plug-ins, if you specify an account that is not
contained in the list of loaded accounts, an error is displayed to the user:

    $ awsrun --account 111111111111
    Account IDs not found: 111111111111

Lastly, one of the other benefits of using an account loader is that authors of
commands can retrieve the metadata attached to an account during the processing
of that account. This allows more complex logic to be added to awsrun commands.
This is covered in the user guide for [User-Defined
Commands](commands/index.html#execute-method).

This concludes the tour of the awsrun CLI. For more information on the available
account loader plug-ins, please refer to `awsrun.plugins.accts`. And, for more
reference material on the CLI, please see `awsrun.cli`.

## CLI Reference

The CLI is a tool that can execute user-defined commands across one or more
accounts concurrently. This section contains reference material on the various
command line arguments and configuration options for the awsrun CLI. For a
gentle introduction to the CLI, please refer to the [User
Guide](#cli-user-guide).

### Synopsis

    $ awsrun [core options] [plug-in options] command [command options]

The CLI accepts three types of command line options:

core
: Defined by the awsrun CLI itself. These control the behavior of the main
program itself. This includes options related to account selection and the
metadata filters. The available options are documented on this page in the [CLI
Options](#options) section.

plug-in
: Defined by the various account loader and credential plug-ins. The included
plug-ins extend the capabilities of awsrun by simplifying account selection
process and credential loading via SAML. Plug-ins can provide their own set of
command line arguments and configuration options. These are documented on the
plug-in pages at `awsrun.plugins.accts` and `awsrun.plugins.creds.aws`. Plug-ins
must be explicitly enabled by the user in their awsrun [config](#configuration).

command
: Defined by the command being executed. Like plug-ins, each command can define
its own set of command line arguments and configuration options. The list of
commands included with awsrun and their various options are documented on the
`awsrun.commands.aws` page. Commands define the action to be taken when
processing each account. Executing the CLI without specifying a command to run
will simply print the list of selected accounts to the console as well as a list
of the available commands that have been found in the command path.

The majority of command line options can also be specified in the awsrun
[config](#configuration) file. This can be helpful for commonly used
options. Rather than using the same command line flag on each use, the option
can be set once in the configuration file.

### Options

The following is a list of the *core* configuration options for the CLI. Some
options can be overridden on the awsrun CLI via command line flags. In those
cases, the CLI flags are specified next to the option name below. For
information on *plug-in* and *command* options, refer to the
[Synopsis](#synopsis) section above.

`account`, `--account ACCT`
:  The list of accounts to process. If specifying more than one account on the
command line, use multiple `--account` flags.

`account_file`, `--account-file`
:  Load the list of accounts to process from the specified file. The file should
contain one account per line. Blank lines are ignored as are lines that start
with a # mark.

`cmd_path`, `--cmd-path`
:  A list of locations to search for commands. This should be a list of Python
modules that contain commands or a directories containing Python files with
commands defined within. The default path is "awsrun.commands.aws".

`--metadata`
:  List the available metadata attributes from the account loader. If an
attribute name is passed as an argument to the flag, list the available values
for that metadata attribute.

`include`, `--include`
:  Include only the accounts that match the specified filter. A filter consists
of an attribute name and a list of possible values for that attribute. If more
than one attribute is specified, then all attributes must match. If more than
one value is specified for an attribute, then only one value must match.

`exclude`, `--exclude`
:  Exclude the accounts that match the specified filter. A filter consists of an
attribute name and a list of possible values for that attribute. If more than
one attribute is specified, then all attributes must match. If more than one
value is specified for an attribute, then only one value must match.

`--help`
:  Print detailed help to the console. The help also includes any defaults read
from the user's configuration file.

`--force`
:  Do not prompt the user for confirmation when processing accounts. By default,
if more than one account has been selected, the CLI prompts the user to confirm
they really want to execute the command over all of those accounts.

`log_level`, `--log-level`
:  Set the logging level. By default, the value is set to ERROR.

`--version`
:  Print the version of awsrun to the console.

When specifying the `--include` and `--exclude` filters on the CLI, the
following syntax is used:

    $ awsrun --include ATTR_NAME=TYPE:ATTR_VALUE,ATTR_VALUE,...

Where `TYPE` is optional and only needed if the values must be cast to a
different type. The type conversion applies to all of the values specified. For
more information on the use of metadata filters, see the [Account
Plug-ins](#account-plug-ins) section in the user guide above.

### Configuration

The behavior of the CLI can be controlled by passing command line arguments as
noted above, but those options can also be specified in a YAML configuration
file that is loaded from `$HOME/.awsrun.yaml` by default. Set the `AWSRUN_CONFIG`
environment variable to use an alternate configuration file. Options defined in
the configuration file can generally be overridden via command line arguments as
noted in the prior section.

The configuration file contains four, optional, top-level sections: `CLI`,
`Commands`, `Accounts`, and `Credentials`. Each section is described below in
more detail.

#### CLI

This section of the configuration contains the core options of the CLI. Below is
the syntax and expected types for each option. Options are described in detail
in the [CLI Options](#options) section of this document.

    CLI:
      account:
        - STRING
      account_file: FILENAME
      include:
        ATTR_NAME:
          - ATTR_VALUE
      exclude:
        ATTR_NAME:
          - ATTR_VALUE
      threads: INTEGER
      log_level: ("DEBUG" | "INFO" | "WARN" | "ERROR")
      cmd_path:
        - STRING

#### Commands

This section of the configuration contains the default options for specific
awsrun commands. A command is defined in its own block, where `COMMAND_NAME` is
the Python module that contains the command. I.e., the same name that one would
specify on the command line. Within the specific command block, users can define
default values for the command's various options. For the included commands with
awsrun, refer to the `awsrun.commands.aws` page for the available options on
each command.

    Commands:
      COMMAND_NAME:
        ARG: VALUE
        ...
      COMMAND_NAME:
        ARG: VALUE
        ...

#### Accounts

This section of the configuration file specifies the account loader plug-in to
be used and its default options. It must contain a `plugin` key with the path to
the account loader plug-in in the form of `PYTHON_MODULE.CLASSNAME`, so the CLI
can find and load it. If the plug-in accepts options, they can be provided in an
optional `options` block. Refer to the account loader's documentation for a list
of available configuration options. The included account loader plug-ins are
documented at the `awsrun.plugins.accts` page. For a gentle introduction to the
account loader plug-ins, see the [Account Plug-ins](#account-plug-ins) section
in the user guide above.

If this section is not defined, the CLI will use the default account loader
`awsrun.plugins.accts.Identity`.

    Accounts:
      plugin: PYTHON_MODULE.CLASSNAME
      options:
        ARG: VALUE
        ...

#### Credentials

This section of the configuration file specifies the credential loader plug-in
to be used and its default options. It must contain a `plugin` key with the path
to the credential loader plug-in in the form of `PYTHON_MODULE.CLASSNAME`, so
the CLI can find and load it. If the plug-in accepts options, they can be
provided in an optional `options` block. Refer to the credential loader's
documentation for a list of available configuration options. The included
credential loader plug-ins are documented at the `awsrun.plugins.creds.aws`
page. For a gentle introduction to the credential loader plug-ins, see the
[Credential Plug-ins](#credential-plug-ins) section in the user guide above.

If this section is not defined, the CLI will use the default credential loader
`awsrun.plugins.creds.aws.Profile.`.

    Credentials:
      plugin: PYTHON_MODULE.CLASSNAME
      options:
        ARG: VALUE
        ...

### Troubleshooting

By default, tracebacks from the core CLI are not printed to the console. Set the
environment variable `AWSRUN_TRACE` to `1` to print tracebacks to the console.
Note: that variable name does not change with different CSPs.

    $ AWSRUN_TRACE=1 awsrun --account 100200300400 ...

Tracebacks from exceptions that arise from within a user-defined command,
however, are displayed if the default logging level is set to `WARN`. You do not
need to set the environment variable for command exceptions.

    $ awsrun --log-level WARN --account 100200300400 ...

"""

import argparse
import logging
import os
import sys
import traceback
from datetime import timedelta
from functools import partial
from pathlib import Path

from awsrun import __version__
from awsrun.acctload import AccountLoader
from awsrun.argparse import (
    AppendAttributeValuePair,
    AppendWithoutDefault,
    RawAndDefaultsFormatter,
)
from awsrun.cmdmgr import CommandManager
from awsrun.config import Any, Choice, Config, Dict, File, Int, List, Str
from awsrun.plugmgr import PluginManager
from awsrun.runner import AccountRunner
from awsrun.session import SessionProvider

LOG = logging.getLogger(__name__)

SHORT_DESCRIPTION = """
Executes a command concurrently across one or more AWS accounts.

Accounts can be specified by using one or more --account flags.
Alternatively, one or more filter flags (--include or --exclude) can be
used to select accounts based on metadata attributes. To list the
attributes available, use the --metadata flag. To list the possible
values for an attribute, pass the attribute name to the --metadata
flag.

The list of available commands, and brief descriptions of each, can be
displayed by omitting the command.  Each command can have its own set
of command line arguments, which can be viewed by passing --help after
the command.
    """.strip()


# setup.py establishes this as the entry point for the awsrun CLI.
def main():
    """The main entry point for the `*run` CLI tool installed with this package.

    Runs the CLI tool. Exits with a `0` status code upon success. Upon error,
    prints the error message to standard error. By default, a stack trace is not
    included to minimize output. If the trace is desired, set the `AWSRUN_TRACE`
    environment variable to `1`.

    The CLI tool is installed on the system via the setup.py entry_points key.
    There can be many instances of this command installed on the system with
    different names. The CLI uses the name of the shell script installed to
    determine default path locations for commands as well as the default
    session manager.
    """
    try:
        csp = _CSP.from_prog_name(sys.argv[0])
        _cli(csp)

    except Exception as e:  # pylint: disable=broad-except
        # Don't print stack traces by default as it can be overwhelming (scary)
        # for those not familiar with Python development.
        if os.getenv("AWSRUN_TRACE"):
            traceback.print_exc(file=sys.stderr)

        print(e, file=sys.stderr)
        sys.exit(1)


def _cli(csp):
    """Parses command line arguments and invokes the awsrun CLI.

    This function may exit and terminate the Python program. It is the driver of
    the main interactive command line tool and may print output to the console.
    """

    # Load the main user configuration file, which is used extensively to
    # provide default values for argparse arguments. This allows users to
    # specify default values for commonly used flags.
    config = Config.from_file(csp.config_filename())

    # Build a callable to simplify access to the 'CLI' section of the config.
    cfg = partial(config.get, "CLI", type=Str)

    # Argument parsing for awsrun is performed in four distinct stages because
    # arguments are defined by the main CLI program, plug-ins can define their
    # own arguments, and commands can also define their own arguments.
    #
    #   1. Parse *known* args for the main CLI
    #   2. Parse *known* args for the plug-ins
    #   3. Parse *remaining* args to grab the command and its args
    #   4. Parse the command's args later in cmdmgr.py
    #
    # Visually, here is a representation of the above;
    #
    #             awsrun and plug-in args          command             cmd args
    #        vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv vvvvvvvvvvvvv vvvvvvvvvvvvvvvvvvvvvvvvvvvv
    # awsrun --account 123 --saml-username pete access_report --region us-east-1 --verbose
    #        ^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    #           stage 1           stage 2          stage 3    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    #                                                                    stage 4
    #
    # In stage 1, this function calls `parse_known_args` in argparse, which does
    # not error out if an unknown argument is encountered. Why do we do this?
    # Because there may be arguments intermixed with the main awsrun args that
    # are intended for a plug-in, so we don't want argparse to terminate the
    # main program, which the more commonly used `parse_args` would do. Note:
    # the main awsrun arguments on the CLI can be specified anywhere before the
    # command. Note: flags defined in a command with the same name as a flag in
    # the main CLI will be eaten by stage 1 processing. I.e. if the main CLI
    # defines a flag called --count and a command author builds a command that
    # also takes a flag called --count, then in an invocation such:
    #
    #   awsrun --account 123 access_report --count
    #
    # The --count arg would never make it to stage 4 processing as it would
    # be shadowed and consumed by stage 1.
    #
    # In stage 2, this function uses the PluginManager to load plug-ins, which
    # may have registered additional command line arguments on the main parser.
    # The PluginManager uses `parse_known_args` when loading each plug-in, again
    # for the same reason as above. There may be arguments destined for a
    # different plug-in that has yet to be loaded, so we don't want to error
    # out. Note: plug-in flags can also shadow command flags as described above.
    # This is why plug-in author's should use a prefix on their flags to
    # minimize chance of collision.
    #
    # In stage 3, this function registers arguments for a help flag, the awsrun
    # command name, and gathers the remaining arguments after the command name.
    # It then calls `parse_args` as all command line arguments should have been
    # consumed at this point. If there are any extra arguments, argparse will
    # error and exit out with an appropriate message.
    #
    # Finally, in stage 4, this function uses the CommandManager to load the
    # command via the name and collected arguments from stage 3. The command
    # manager creates a new argument parser internally to parse the arguments
    # that were sent to the command as each command has the option to register
    # command line arguments.

    # STAGE 1 Argument Processing (see description above)

    # Do not add_help here or --help will not include descriptions of arguments
    # that were registered by the plug-ins. We will add the help flag in stage 3
    # processing.
    parser = argparse.ArgumentParser(
        add_help=False,
        allow_abbrev=False,
        formatter_class=RawAndDefaultsFormatter,
        description=SHORT_DESCRIPTION,
    )

    acct_group = parser.add_argument_group("account selection options")
    acct_group.add_argument(
        "--account",
        metavar="ACCT",
        action=AppendWithoutDefault,
        default=cfg("account", type=List(Str), default=[]),
        dest="accounts",
        help="run command on specified list of accounts",
    )

    acct_group.add_argument(
        "--account-file",
        metavar="FILE",
        type=argparse.FileType("r"),
        default=cfg("account_file", type=File),
        help="filename containing accounts (one per line)",
    )

    acct_group.add_argument(
        "--metadata",
        metavar="ATTR",
        nargs="?",
        const=True,
        help="summarize metadata that can be used in filters",
    )

    acct_group.add_argument(
        "--include",
        metavar="ATTR=VAL",
        action=AppendAttributeValuePair,
        default=cfg("include", type=Dict(Str, List(Any)), default={}),
        help="include filter for accounts",
    )

    acct_group.add_argument(
        "--exclude",
        metavar="ATTR=VAL",
        action=AppendAttributeValuePair,
        default=cfg("exclude", type=Dict(Str, List(Any)), default={}),
        help="exclude filter for accounts",
    )

    parser.add_argument(
        "--threads",
        metavar="N",
        type=int,
        default=cfg("threads", type=Int, default=10),
        help="number of concurrent threads to use",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="do not prompt user if # of accounts is > 1",
    )

    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__
    )

    parser.add_argument(
        "--log-level",
        default=cfg(
            "log_level", type=Choice("DEBUG", "INFO", "WARN", "ERROR"), default="ERROR"
        ),
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        help="set the logging level",
    )

    parser.add_argument(
        "--cmd-path",
        action=AppendWithoutDefault,
        metavar="PATH",
        default=cfg("cmd_path", type=List(Str), default=[csp.default_command_path()]),
        help="directory or python package used to find commands",
    )

    # Parse only the _known_ arguments as there may be additional args specified
    # by the user that are intended for consumption by the account loader plugin
    # or the auth plugin. We save the remaining args and will pass those to the
    # plugin manager responsible for loading the plugins.
    args, remaining_argv = parser.parse_known_args()

    # With the log level now available from the CLI options, setup logging so it
    # can be used immediately by the various python modules in this package.
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(name)s %(levelname)s [%(threadName)s] %(message)s",
    )

    # STAGE 2 Argument Processing (see description above).

    # The plugin manager will load the two plugins and handle command line
    # parsing of any arguments registered by the plugins.
    plugin_mgr = PluginManager(config, parser, args, remaining_argv)
    plugin_mgr.parse_args("Accounts", default="awsrun.plugins.accts.Identity")
    plugin_mgr.parse_args("Credentials", default=csp.default_session_provider())

    # STAGE 3 Argument Processing (see description above).

    # The help flag is added to the parser _after_ loading all of the plugins
    # because plugins can register their own flags, which means if the help flag
    # were added before this point, and a user passed the -h flag, it would not
    # include descriptions for any of the args registered by the plugins.
    parser.add_argument("-h", "--help", action="help")
    parser.add_argument("command", nargs="?", help="command to execute")
    parser.add_argument(
        "arguments", nargs=argparse.REMAINDER, default=[], help="arguments for command"
    )

    # Now we parse the remaining args that were not consumed by the plugins,
    # which will typically include the awsrun command name and any of its args.
    # If there are extra args or unknown args, parse_args will exit here with an
    # error message and usage string. Note that we obtain the remaining unused
    # argv from the plugin manager as well as the namespace to add these last
    # arguments.
    args = parser.parse_args(plugin_mgr.remaining_argv, plugin_mgr.args)

    # Use the plugin manager to create the actual account loader that will be
    # used to load accounts and metadata for accounts.
    account_loader = plugin_mgr.instantiate("Accounts", must_be=AccountLoader)

    # Check to see if user is inquiring about the metadata associated with
    # accounts. If they pass --metadata by itself, print out a list of all
    # possible attribute names. If they pass an arg to --metadata, such as
    # "--metadata BU", then print out all the possible values of that attr,
    # so they can build filters for it.
    if args.metadata:
        attrs = account_loader.attributes()
        if args.metadata in attrs:
            print(f"Metadata values for '{args.metadata}' attribute:\n")
            print(
                "\n".join(sorted(str(x) for x in attrs[args.metadata] if x is not None))
            )
        elif attrs:
            print("Valid metadata attributes:\n")
            print("\n".join(sorted(attrs)))
        else:
            print("No metadata attributes available")
        sys.exit(0)

    # Check to see if the user wants to load additional accounts from a file
    # specified on the command line. If so, the account IDs will be appended to
    # any accounts defined on the command line or in the user config.
    if args.account_file:
        args.accounts.extend(
            a.strip()
            for a in args.account_file
            if not (a.isspace() or a.startswith("#"))
        )

    # Obtain a list of account *objects* for the specified account IDs. The
    # resulting objects will depend upon the account loader plugin used. Some
    # plugins will return rich objects with attributes containing metadata and
    # others may just return a simple list of IDs as strings. The point is that
    # this is an opaque object that will be passed to the runner and then to the
    # command being run.
    accounts = account_loader.accounts(args.accounts, args.include, args.exclude)

    # If we get to here and there are still 0 accounts, that means there were
    # no accounts specified via --accounts, no accounts specified in the user
    # config, no accounts specified in a separate file, or none of the
    # specified accounts matched the filters, so we just exit.
    if not accounts:
        print("No accounts selected", file=sys.stderr)
        sys.exit(1)

    # The command manager will be used to search, parse command arguments, and
    # instantiate the command that was specified on the CLI. It can also provide
    # a list of all commands found in the paths provided.
    command_mgr = CommandManager.from_paths(*args.cmd_path)

    # If no command was supplied, then print the list of accounts that were
    # selected along with a list of all the valid and known commands. This
    # allows users to test filters to see which accounts will be acted upon.
    if not args.command:
        _print_accounts(accounts)
        _print_valid_commands(command_mgr.commands())
        sys.exit(1)

    # STAGE 4 Argument Processing (see description above). When the command
    # manager loads the command, it will create a new argument parser, so
    # command author's can define any arguments they might want. After this
    # step, all command line arguments have been fully processed.
    try:
        command = command_mgr.instantiate_command(
            args.command, args.arguments, partial(config.get, "Commands", args.command)
        )

    # Most exceptions are passed upwards, but we explicitly catch a failure when
    # trying to instantiate the command selected by the user, so we can include a
    # list of valid commands that the command manager knows about. The exception
    # re-raised so it will be handled by the same error handling logic in main().
    except Exception:
        _print_valid_commands(command_mgr.commands(), out=sys.stderr)
        raise

    # Safety check to make sure user knows they are impacting more than one
    # account. This can be disabled with the -f flag.
    if len(accounts) > 1 and not args.force:
        _ask_for_confirmation(accounts)

    # Load up a session provider to hand out creds for the runner.
    session_provider = plugin_mgr.instantiate("Credentials", must_be=SessionProvider)

    # This is the main entry point into the awsrun library. Note: the entirety of
    # awsrun can be used without the need of the CLI. One only needs a list of
    # accounts, an awsrun.runner.Command, and an awsrun.session.SessionProvider.
    runner = AccountRunner(session_provider, args.threads)
    elapsed = runner.run(command, accounts, key=account_loader.acct_id)

    # Show a quick summary on how long the command took to run.
    pluralize = "s" if len(accounts) != 1 else ""
    print(
        f"\nProcessed {len(accounts)} account{pluralize} in {timedelta(seconds=elapsed)}",
        file=sys.stderr,
    )


def _print_valid_commands(commands, out=sys.stdout):
    """Pretty print a table of commands.

    The argument is a dict where keys are the names and values are CLICommand
    classes from the command modules.
    """
    if not commands:
        print("No commands found, did you specify the correct --cmd-path?", file=out)
        return

    print("The following are the available commands:\n", file=out)
    max_cmd_len = max(len(name) for name in commands.keys())
    for name in sorted(commands.keys()):
        # By convention, as documented in user documentation, class docstring
        # is used when printing a summary of commands.
        docstring = commands[name].__doc__ or ""
        print(f"{name:{max_cmd_len}}  {docstring}", file=out)
    print(file=out)


def _print_accounts(accts, out=sys.stdout):
    """Print the list of accounts."""
    count = len(accts)
    print(f'{count} account{"s" if count != 1 else ""} selected:\n', file=out)
    print(", ".join(str(a) for a in accts), file=out, end="\n\n")


def _ask_for_confirmation(accts):
    """Prompt user for confirmation and list accounts to be acted upon."""
    _print_accounts(accts, out=sys.stderr)
    print("Proceed (y/n)? ", flush=True, end="", file=sys.stderr)
    answer = input()
    if not answer.lower() in ["y", "yes"]:
        print("Exiting", file=sys.stderr)
        sys.exit(0)


class _CSP:
    """Represents a Cloud Service Provider (CSP) default settings.

    This class provides the default user configuration path, default command
    path, and the default session provider. It also includes a factory method
    to create an instance based on the filename of the CLI script itself. This
    is used to adapt the CLI behavior based on the CSP based solely on the
    name.

    To add a new CSP to awsrun, the following must be completed:

    1. Create a new submodule called `aws.commands.csp` where `csp` is the name
       of the CSP being added. For example, `aws.commands.gcp`. In this module,
       define one or more command submodules. For example, to build an command
       called "access_check", create `aws.commands.gcp.access_check.py` with a
       `CLICommand` class defined. See top-level `awsrun` documentation on how
       to build commands.

    2. Create a new submodule called `aws.plugins.creds.csp` where `csp` is the
       name of the CSP being added. For example, `aws.commands.creds.gcp`. In
       this module, define one or more plug-ins that return an instance of a
       `awsrun.session.SessionProvider`. See top-level `awsrun` documentation
       on how to build plug-ins.
    """

    @classmethod
    def from_prog_name(cls, prog_name):
        """Return CSP instance based on prog_name."""

        # Identify the CSP name from the name of the installed CLI tool. The
        # installed CLI will be called "awsrun" or "azurerun".
        csp = Path(prog_name).name.replace("run", "")
        if csp not in ["aws", "azure"]:
            raise Exception(f"unknown variant: {csp}")
        return cls(csp)

    def __init__(self, name):
        self.name = name

    def config_filename(self):
        """Returns the path to the user configuration."""
        env_var = self.name.upper() + "RUN_CONFIG"
        dotfile = "." + self.name.lower() + "run.yaml"
        return os.environ.get(env_var, Path.home() / dotfile)

    def default_command_path(self):
        """Returns the path to the builtin commands submodule."""
        return "awsrun.commands." + self.name.lower()

    def default_session_provider(self):
        """Returns the module name of the builtin Profile session provider."""
        return "awsrun.plugins.creds." + self.name.lower() + ".Default"


if __name__ == "__main__":
    main()
