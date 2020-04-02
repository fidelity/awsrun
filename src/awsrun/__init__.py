#
# Copyright 2019 FMR LLC <opensource@fmr.com>
#
# SPDX-License-Identifier: MIT
#
"""CLI and API to concurrently execute user-defined commands across AWS accounts.

## Overview

`awsrun` is both a CLI and API to execute commands over one or more AWS accounts
concurrently. Commands are user-defined Python modules that implement a simple
interface to abstract away the complications of obtaining credentials for Boto 3
sessions - especially when using SAML authentication and/or cross-account
access. The key features of awsrun include the following:

**Concurrent Account Processing**
:  Run a command concurrently across subset or all of your accounts. A worker
pool manages the execution to ensure accounts are processed quickly, so you
don't have to wait for them to be processed one at a time. Process hundreds of
accounts in a few minutes.

**SAML and Cross-Account Access**
:  Tired of dealing with temporary STS credentials with SAML and cross-account
authentication? Use any of the included credential plug-ins based on your needs,
or build your own plug-in to provide credentials for your command authors. Don't
use SAML? Build profiles in your AWS credentials file instead.

**Built-in Command for AWS CLI**
:  Ever wish you could run the standard AWS CLI tool across multiple accounts?
Now you can using the included `awsrun.commands.aws.aws` command. This command
is a simple wrapper for AWS's CLI, but with the added benefits of using metadata
to select multiple accounts as well as simplified credential handling.

**User-Defined Commands**
:  Build your own commands using the powerful Boto 3 library without the hassle
of obtaining sessions and credentials. Thanks to a simple interface, commands
are easy to build and can be integrated directly into the CLI with custom
arguments and help messages.

**Metadata Enriched Accounts**
:  Accounts can be enriched with metadata from external sources, such as a
corporate CMBD, via the account loader plug-in mechanism. This enables you to
use metadata to select accounts to process rather than explicitly listing each
account on the command line. In addition, command authors have access to this
metadata, so it can be accessed while processing an account if needed.

## Demo

Let's gather information on the VPCs in an account. We could gather this
information using only AWS's native CLI, but that limits us to processing one
account at a time. Instead, we'll use awsrun and the `awsrun.commands.aws.aws`
command to execute an AWS CLI command across multiple accounts concurrently.
We'll also make use of the awsrun's metadata explorer to select accounts for
command execution. When the command is run, 58 accounts are selected by the
metadata filter, and then processed in about 13 seconds:

![Example](demo.svg)

## Installation

To install from source, clone the repo and run pip install:

    $ git clone https://github.com/fmr-llc/awsrun.git
    $ cd awsrun
    $ pip3 install .

Python 3.6 or higher is required.

In order to use the built-in awsrun "aws" command, Windows must make sure that
the AWS CLI tool is installed in their PATH. When pip installs the AWS CLI, it
does not set the appropriate PATH variables, so it may be easier to install the
AWS CLI via the MSI provided by AWS.

## CLI Usage

The `awsrun.cli` is a full-featured command line tool with a plethora of options
to allow a user to invoke a "command" across one or more AWS accounts. A command
is a Python module that executes a block of Python code -- typically using the
Boto 3 library. awsrun includes a handful of built-in commands, but you are
encouraged to build your own collection of user-defined commands.

In this section of the user guide, we'll review the basic usage of the CLI, how
to run commands across accounts, and then later learn how to extend the CLI's
behavior via plug-ins for obtaining credentials and account loading. If you are
looking for reference material instead, the following pages will be of interest:

`awsrun.cli`
:  Contains the list of available CLI command line options as well as the
options that can be defined in the user configuration file. If you prefer a
user guide, then continue reading this page instead for a more verbose intro to
the CLI.

`awsrun.commands`
:  Contains the list of built-in commands available for use out of the box. Most
of these are simple examples to illustrate how to write your own commands. The
most interesting of the AWS built-in commands is the `awsrun.commands.aws.aws`
command, which is an adapter to the AWS CLI tool.

`awsrun.plugins`
:  Contains the list of plug-ins available for account loading and credential
loading. While awsrun can be used without plug-ins, it's value is diminished as
the real power comes from account selection and simplification of SAML and cross
account access.

For the remainder of this CLI overview, we'll be using the general purpose
`awsrun.commands.aws.aws` command, which is an adapter for the AWS CLI tool.
This allows users to concurrently run the AWS CLI across multiple accounts. When
combined with other awsrun features such as SAML authentication, cross-account
access, and metadata account filters, it makes the AWS CLI tool even more
powerful than it already is as you'll see.

### Synopsis

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

### Basic Usage

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
your own commands, which is covered later in [user-defined
commands](#user-defined-commands).

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

As mentioned in the [syntax](#syntax) section, there are several types of
command line arguments: core options, plug-in options, and command options.
Specifying all of these via the command line can be tedious, especially if you
use the same values all the time. Fortunately, you can define these in a YAML
configuration file. By default, the config is loaded from "$HOME/.awsrun.yaml".
If you prefer an alternate location, set the AWSRUN_CONFIG environment variable
to point elsewhere.

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
$HOME/.aws/credentials or $HOME/.aws/config. Let's look at some of the other
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
        url: https://adfs.example.com/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices
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
the [User-Defined Plug-ins](#user-defined-plug-ins) section of the guide.

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
This is covered in the section [User-Defined Commands](#user-defined-commands).

This concludes the tour of the awsrun CLI. For more information on the available
account loader plug-ins, please refer to `awsrun.plugins.accts`. And, for more
reference material on the CLI, please see `awsrun.cli`.

## API Usage

Not only is awsrun a CLI, but it is, first and foremost, an API that can be
used independently. The API contains extensive documentation on its use. Each
submodule contains an overview of the module and how to use it, which is then
followed by standard API docs for classes and methods. The available
[submodules](#header-submodules) can be found at the bottom of this page. Of
particular interest to API users will be the following submodules:

`awsrun.runner`
:  Contains the core API to execute a command across one or more accounts. You
will find the `awsrun.runner.AccountRunner` and `awsrun.runner.Command` classes
defined in this module. Build your own commands by subclassing the base class.

`awsrun.session`
:  Contains the definition of the `awsrun.session.SessionProvider`,
which is used to provide Boto 3 sessions preloaded with credentials. Included
are several built-in implementations such as `awsrun.session.CredsViaProfile`,
`awsrun.session.CredsViaSAML`, and `awsrun.session.CredsViaCrossAccount`.


## User-Defined Commands

Building your own awsrun commands is easy if you are familiar with Python and
the Boto 3 library. An awsrun command is simply a subclass of the abstract base
class `awsrun.runner.Command`. If you are writing your own command for use with
the awsrun API, then you only need to implement `awsrun.runner.Command.execute`.
Please refer to `awsrun.runner` module for details on how to use the API and the
methods available on the `awsrun.runner.Command` class.

If, on the other hand, you want to build a command that can also be used with
the awsrun CLI, then you must define a subclass of `awsrun.runner.Command`
called `CLICommand` in a Python module with the same name of the command you
wish to define. For example, to create an awsrun command called "list_vpcs", you
would create a file called "list_vpcs.py" that contains a `CLICommand`
implementation. By adhering to these guidelines, the awsrun CLI will be able to
find and dynamically load your command at runtime.

As a convenience when building commands for AWS to operate on one or more
regions, you should subclass `awsrun.runner.RegionalCommand` instead of the
`awsrun.runner.Command`, which will abstract away the explicit looping over
regions on your behalf. The majority of your AWS commands will use this regional
command base class. Refer to the documentation in `awsrun.runner` for additional
details on the differences.

Let's build a simple command to list the VPCs in an AWS account. In subsequent
sections, we will iterate on this example to illustrate important principles to
learn when writing your own commands. Because most of the AWS APIs are regional,
we'll be using the `awsrun.runner.RegionalCommand` base class. Here is the bare
minimum needed for a fully functioning CLI command to list VPCs:

    from awsrun.runner import RegionalCommand

    class CLICommand(RegionalCommand):
        def regional_execute(self, session, acct, region):
            ec2 = session.resource('ec2', region_name=region)
            ids = ', '.join(vpc.id for vpc in ec2.vpcs.all())
            return f'{acct}/{region}: {ids}\\n'

To invoke the command, assuming this code has been added to a file called
"list_vpcs.py" in your current directory, we can use the `--cmd-path` flag to
instruct awsrun to load commands from the current directory. Later we'll
learn how to install commands so you don't have to specify `--cmd-path`, but
during development, this is convenient:

    $ awsrun --cmd-path . --account 100200300400 list_vpcs --region us-east-1 --region us-west-2
    100200300400/us-east-1: vpc-12312312313, vpc-32132132132
    100200300400/us-west-2: vpc-23123123123

    Processed 1 account in 0:00:02.091249
    $

Congratulations! You've written your first awsrun command. In the upcoming
sections, we'll dig a little deeper using this example, and we'll enhance it as
we learn about a few important conventions.

### Docstrings

Two docstring conventions should be followed if you wish to have your command
integrated into the awsrun CLI help system. First, you should include a detailed
module-level docstring that provides information how to invoke your command as
well as any arguments it may define. Second, the `CLICommand` class should have
a single one-line docstring that provides a concise description of the command.

Let's enhance our "list_vpcs" command by providing a descriptive help message in
the module docstring as well as a concise one-line docstring for the class:

    \"\"\"Display the VPCs in an account.

    The `list_vpcs` command displays the IDs of each VPC. For each VPC in a
    region, a list of VPC IDs is displayed. For example:

        $ awsrun --account 100200300400 list_vpcs --region us-east-1
        100200300400/us-east-1: vpc-12312312313, vpc-32132132132
    \"\"\"

    from awsrun.runner import RegionalCommand

    class CLICommand(RegionalCommand):
        \"\"\"Display the VPCs in an account.\"\"\"

        def regional_execute(self, session, acct, region):
            ec2 = session.resource('ec2', region_name=region)
            ids = ', '.join(vpc.id for vpc in ec2.vpcs.all())
            return f'{acct}/{region}: {ids}\\n'

By following these docstring conventions, if a user passes the `-h` or `--help`
flag to your command, awsrun will print the module-level docstring to the
console:

    $ awsrun --cmd-path ./ list_vpcs --help
    usage: list_vpcs [-h] [--region REGION]

    optional arguments:
    -h, --help            show this help message and exit
    --region REGION       region in which to run commands (default: [])

    Display the VPCs configured in an account.

    The list_vpcs command displays each VPC configured as well as the list of
    CIDR blocks associated with it. For example:

        $ awsrun --account 100200300400 list_vpcs --region us-east-1
        100200300400/us-east-1: id=vpc-aabbccdd cidrs=10.0.1.0/24, 10.0.2.0/26
        100200300400/us-east-1: id=vpc-bbccddaa cidrs=10.0.5.0/22
    $

Similarly, if a user doesn't specify a command to execute, awsrun will
print a list of available commands along with the one-line docstring of the
`CLICommand` class:

    $ awsrun --cmd-path ./ --account 100200300400
    1 account selected:

    100200300400

    The following are the available commands:

    list_vpcs  Display the VPCs in an account.
    $


### CLI Arguments

The class method `awsrun.runner.RegionalCommand.regional_from_cli` can be used
if your command needs to define additional command line arguments or if it needs
to read values from the user configuration. This is a factory method that will
be called by the CLI when instantiating the command for use. It must return an
instance of the command that has been initialized using the command line flags
and/or the user configuration file.

Building on the previous example, let's provide a command line flag to print the
CIDR blocks associated with each VPC. We'll need to make the following changes:

1. Implement `awsrun.runner.RegionalCommand.regional_from_cli`, define the
   new command line flag called `--cidr` using the `argparse.ArgumentParser`
   provided to us, and then return an instance of our command.

2. Add a constructor to our command. On that constructor we'll need to add a
   boolean argument indicating whether to print the CIDR blocks. Because we are
   using `awsrun.runner.RegionalCommand.regional_from_cli`, which automatically
   adds the `--region` flag on our behalf, we must also accept a parameter on
   our constructor called `regions`.

A common pattern used in awsrun commands is to define parameter names on the
command's constructor to match the CLI flag names -- specifically the `dest`
value in `argparse.ArgumentParser.add_argument`. For example, we define the flag
name `--cidr` on the `parser` object, which is also the same name as the `cidr`
argument on the constructor. This allows you to instantiate your command with
the same one-liner for all your commands: `cls(**vars(args))`.

Here is our new version of the "list_vpcs.py" command:

    \"\"\"Display the VPCs in an account.

    The `list_vpcs` command displays the IDs of each VPC. For each VPC in a
    region, a list of VPC IDs is displayed. For example:

        $ awsrun --account 100200300400 list_vpcs --region us-east-1
        100200300400/us-east-1: vpc-12312312313, vpc-32132132132

    Specify the `--cidr` flag to include the CIDR blocks associated with
    each VPC:

        $ awsrun --account 100200300400 list_vpcs --region us-east-1 --cidr
        100200300400/us-east-1: vpc-12312312313 (10.0.1.0/24), vpc-32132132132 (10.0.2.0/24)
    \"\"\"

    from awsrun.runner import RegionalCommand

    class CLICommand(RegionalCommand):
        \"\"\"Display the VPCs in an account.\"\"\"

        @classmethod
        def regional_from_cli(cls, parser, argv, cfg):
            parser.add_argument(
                '--cidr',
                action='store_true',
                help='include CIDR blocks in output')

            args = parser.parse_args(argv)
            return cls(**vars(args))

        def __init__(self, regions, cidr=False):
            super().__init__(regions)
            self.cidr_flag = cidr

        def regional_execute(self, session, acct, region):
            ec2 = session.resource('ec2', region_name=region)
            ids = ', '.join(self.format(vpc) for vpc in ec2.vpcs.all())
            return f'{acct}/{region}: {ids}\\n'

        def format(self, vpc):
            result = f'{vpc.id}'
            if self.cidr_flag:
                cidrs = ', '.join(c['CidrBlock'] for c in vpc.cidr_block_association_set)
                result += f' ({cidrs})'
            return result

Another common pattern is to obtain the defaults for your command line flags
from the user's configuration file by using the `cfg` callable provided to us in
the factory method. This object is directly linked to the appropriate `Commands`
section of the user's configuration file, which makes it trivial to read values
from the configuration. We only need to add the `default` argument when we call
`argparse.ArgumentParser.add_argument` in our factory method:

    from awsrun.config import Bool

        @classmethod
        def regional_from_cli(cls, parser, argv, cfg):
            parser.add_argument(
                '--cidr',
                action='store_true',
                default=cfg('cidr', type=Bool, default=False),
                help='include CIDR blocks in output')

The `cfg` callable will load the key called `cidr` if it exists, otherwise it
will return `False` as the default. This allows the user to provide a default
value for the command line flag using their configuration file. In this case,
`cfg` will look for the key `Commands -> list_vpcs -> cidr`. For example, if the
YAML configuration file contained the following, then the default for the
command line argument would be `True`:

    Commands:
      list_vpcs:
        cidr: True

For consistency with the rest of awsrun, it is recommended that you use the same
configuration key names and command line flag names. This will make it easy for
your users to match configuration keys to command line flags. Nothing, however,
prevents you from choosing any name you want.  For command line flags with
hyphens, it is suggested you use underscores in the configuration key name if
you wish to remain consistent with the core awsrun flags and configuration keys.

In addition, the `cfg` callable can typecheck the values read from the user's
configuration file. In the example above, we ensure the value read from the YAML
file is a boolean. If it is not, then the program terminates with a helpful
error message stating the expected type.

For more information on how to define command line args and querying the user
configuration file, refer to `awsrun.runner.RegionalCommand.regional_from_cli`
and the `awsrun.config` documentation.

### Execute Method

The `awsrun.runner.RegionalCommand.regional_execute` method is where you define
the code to execute in each selected account and region.  In this method, you
would typically use the Boto 3 library, via the session object provided, to make
API calls to AWS. Let's look at the execute method from our first version of the
"list_vpcs" command above:

    def regional_execute(self, session, acct, region):
        ec2 = session.resource('ec2', region_name=region)
        ids = ', '.join(vpc.id for vpc in ec2.vpcs.all())
        return f'{acct}/{region}: {ids}\\n'

In this example, we create a Boto 3 EC2 resource from the `session` object for
the appropriate `region`, and then we obtain a list of all of the VPC IDs in
that region for the account being processed. Finally, we return a string, which
is then displayed on the console thanks to the default implementation of
`awsrun.runner.RegionalCommand.regional_collect_results`. Collecting results
will be discussed further in the next section.

The `acct` parameter is a string representing the account being processed,
unless you are using a custom account loader that provides a custom account
object. Depending on the account loader, this object might contain metadata
associated with it that can be accessed via this object while processing an
account. Several custom account loaders are included with awsrun in the
`awsrun.plugins.accts` module.

A common pattern for CLI-based commands is to build up a string to be displayed
to the user. By using an `io.StringIO` buffer, you'll be able to use the familiar
`print()` function to incrementally append to an in-memory buffer. Then, at the
end of the execute method, you return the contents of that buffer. For example,
the above could have been written as follows:

    import io

    def regional_execute(self, session, acct, region):
        out = io.StringIO()  # Create a string buffer
        ec2 = session.resource('ec2', region_name=region)
        ids = ', '.join(vpc.id for vpc in ec2.vpcs.all())

        # We can use the venerable print function as long as we specify
        # the buffer as the destination via `file=out` argument.
        print(f'{acct}/{region}: {ids}\\n', file=out)

        # Return the contents of the buffer, which will be sent to the
        # console by the default collect results implementation.
        return out.getvalue()

Although not much of an improvement in this trivial example, this pattern can be
very helpful when you need to "print" output from different blocks of code. Why
not simply print to standard output? Because we cannot guarantee the order in
which it will be printed to the console. Remember, awsrun processes multiple
accounts concurrently via a thread worker pool. This means one or more threads
may be printing to the console at the same time, which could result in output
that is intermixed with other workers -- especially if you are printing multiple
lines within your execute method. To properly send output to the console in a
thread-safe manner, incrementally build a string, and then return it at the end
of the execute method, which the default collector (next section) will send to
the console on your behalf safely.

This also highlights another important consequence of using a concurrent
execution model for command processing. It is important that you **never modify
instance state without synchronization** among threads. For example, it would not
be safe to define the string buffer in an instance variable called `self.out`.
If you did, then multiple threads would be appending to the same buffer, which
is certainly not what you want. This advice holds true for any mutable instance
variable - do not modify without the use of explicit synchronization. If you
need to update an instance variable, you should define your own collect results
method as described in the next section.

Please refer to the documentation for `awsrun.runner.Command.execute` and
`awsrun.runner.RegionalCommand.regional_execute` for pointers on thread-safety
when building your own commands that operate in a multi-threaded environment.

### Collecting Results

As discussed in the previous section, the default behavior of awsrun is to print
the value returned from `awsrun.runner.RegionalCommand.regional_execute` to the
console. Why does this happen? After the execute method has returned, awsrun
invokes `awsrun.runner.RegionalCommand.regional_collect_results` passing it the
return value of execute. By default, the value is printed to the console, but
you can do whatever you'd like with that value by overriding the default
implementation.

Like the execute method, the `acct` parameter is a string representing the
account or an object that was loaded by a custom account loader (see discussion
in prior section). The `get_result` parameter is a callable that provides you
access to the return value from the execute method. Invoking this function will
return that value unless there was an exception raised during execute, in which
case, it will be re-raised.

Let's take a look at the default collector implementation to see how to use the
concepts together:

    def regional_collect_results(self, acct, region, get_result):
        try:
            print(get_result(), end='', flush=True)
        except Exception as e:
            print(f'{acct}/{region}: error: {e}', flush=True, file=sys.stderr)

Why is this method thread-safe? And why should I use it to update mutable shared
state in instance variables as discussed in previous section? It is important to
understand that `awsrun.runner.RegionalCommand.regional_collect_results` is only
executed by the main thread. It will never be executed concurrently, so it is
safe to modify shared state attached to the instance from within this method. It
eliminates the need to provide your own explicit synchronization mechanisms due
to the multiple workers that might be concurrently processing accounts.

A common use case for your building your own collector is to aggregate data
across accounts in a instance variable of your command. But as we've stated, you
cannot update shared state without explicit synchronization unless you provide
your `awsrun.runner.RegionalCommand.regional_collect_results`. For example,
continuing with our "list_vpcs" command, let's add another option to summarize
the total number of VPCs and CIDRs blocks across all accounts being processed.
We'll need to define the command line flag, update our constructor to accept the
new option, and then provide our own collector implementation. Here is the new
version of our command:

    \"\"\"Display the VPCs in an account.

    The `list_vpcs` command displays the IDs of each VPC. For each VPC in a
    region, a list of VPC IDs is displayed. For example:

        $ awsrun --account 100200300400 list_vpcs --region us-east-1
        100200300400/us-east-1: vpc-12312312313, vpc-32132132132

    Specify the `--summary` flag to include a summary count of VPCs and
    CIDRs after processing all of the accounts:

        $ awsrun --account 100200300400 --account 200300400100 list_vpcs --region us-east-1 --summary
        100200300400/us-east-1: vpc-12312312313 (10.0.1.0/24), vpc-32132132132 (10.0.2.0/24)
        200300400100/us-east-1: vpc-8675309 (10.0.5.0/24, 10.0.6.0/24)
        Total VPCs: 3
        Total CIDRs: 4
    \"\"\"

    import io
    import sys

    from awsrun.config import Bool
    from awsrun.runner import RegionalCommand

    class CLICommand(RegionalCommand):
        \"\"\"Display the VPCs in an account.\"\"\"

        @classmethod
        def regional_from_cli(cls, parser, argv, cfg):
            parser.add_argument(
                '--summary',
                action='store_true',
                default=cfg('summary', type=Bool, default=False),
                help='include a summary report at the end')

            args = parser.parse_args(argv)
            return cls(**vars(args))

        def __init__(self, regions, summary=False):
            super().__init__(regions)
            self.summary_flag = summary
            self.all_cidrs = {}

        def pre_hook(self):
            self.all_cidrs.clear()

        def regional_execute(self, session, acct, region):
            ec2 = session.resource('ec2', region_name=region)
            cidrs = {}  # local variable
            for vpc in ec2.vpcs.all():
                cidrs[vpc.id] = [c['CidrBlock'] for c in vpc.cidr_block_association_set]
            return cidrs

        def regional_collect_results(self, acct, region, get_result):
            try:
                # Grab the results from the execute method
                cidrs = get_result()

                # Update the dict accumulating all of the results. Note: this is
                # safe to update without synchronization because collect_results
                # is guaranteed to be invoked sequentially by the main thread.
                self.all_cidrs.update(cidrs)

                # Print out a one line summary as we process each account like
                # we had before. Note: this is safe to print directly to stdout
                # for the same reason stated above.
                ids = ', '.join(f'{v} ({", ".join(c)})' for v, c in cidrs.items())
                print(f'{acct}/{region}: {ids}', file=sys.stdout)

            except Exception as e:
                print(f'{acct}/{region}: error: {e}', flush=True, file=sys.stderr)

        def post_hook(self):
            if self.summary_flag:
                print(f'Total VPCs: {len(self.all_cidrs.keys())}')
                print(f'Total CIDRs: {sum(len(c) for c in self.all_cidrs.values())}')

The key points to note here is that the execute method no longer returns a
simple string, but rather a dictionary of the VPCs in the account with their
CIDR blocks. Within the collect results method, we retrieve that dict via the
`get_result` callable, add it to the `all_cidrs` dict instance variable, and
then print a row of data to standard output. After all account processing has
completed, the post-hook then generates some stats from the `all_cidrs` dict and
writes it to the console.

The `awsrun.runner.Command.pre_hook` and `awsrun.runner.Command.post_hook`
methods are executed before and after all accounts have been processed. The
pre-hook is used to initialize data structures before each run of the command,
while the post-hook is used to clean up resources as well as to consume data
that has been aggregated. In our example, we clear the dictionary on each run,
remember commands can be used programmatically, so it is possible one may want
to re-use the same command instance multiple times. And then we use the
post-hook to print a summary of the data we collected during the processing of
accounts.

You should now have a good understanding of the do's and don'ts to keep in mind
when authoring your own commands. In the next section, we will discuss how to
install your commands.

### Installing Commands

After defining your command in a Python module, you will need to point awsrun
to your new command. We've been using the `--cmd-path` CLI argument to point to
the current directory thus far, but you can add one or more directories or
Python modules to your command path. By default, if you don't specify a path,
awsrun uses "awsrun.commands.aws", which contains all of the built-in commands.

Let's assume we store the "list_vpcs.py" command in "/home/me/awsrun-commands",
which is a directory that contains all of your user-defined commands. To confirm
awsrun can find your command, you can invoke the CLI without passing it a
command and it will display all of the available commands it has found in the
specified command path:

    $ awsrun --cmd-path /home/me/awsrun-commands --account 100200300400
    1 account selected:

    100200300400

    The following are the available commands:

    list_vpcs           Display VPCs configured in accounts.
    $

Not only can you specify directories to search in your command path, but you can
also specify installed Python modules that contain your commands. This might be
useful if one team in your organization distributes their own internal Python
package with their own commands. As mentioned earlier, the default command path
is "awsrun.commands.aws". Let's see what is bundled with awsrun (technically we
did not need to explicitly set the command path as its the default):

    $ awsrun --cmd-path awsrun.commands.aws --account 100200300400
    1 account selected:

    100200300400

    The following are the available commands:

    access_report       Test role access to the accounts specified.
    aws                 Execute aws cli commands concurrently.
    list_hosted_zones   Display the Route53 hosted zones in an account.
    list_iam_policies   Display the IAM policies (inline and attached) in an account.
    list_iam_roles      Display the IAM roles in an account and its trust relationships.
    list_igws           Display IGWs attached in accounts.
    list_lambdas        Display Lambda functions deployed in accounts.
    list_public_ips     Display the public IPs in an account.
    list_vpc_attribute  Display VPC attributes such as DNS settings for accounts.
    list_vpcs           Display VPCs configured in accounts.
    $

You can also specify more than one command path. For example, if you wanted to
include the default list of commands as well as all of your custom commands in
"/home/me/awsrun-commands", then provide additional `--cmd-path` flags for each
path to search:

    $ awsrun --cmd-path /home/me/awsrun-commands --cmd-path awsrun.commands.aws --account 100200300400
    1 account selected:

    100200300400

    The following are the available commands:

    access_report       Test role access to the accounts specified.
    aws                 Execute aws cli commands concurrently.
    list_hosted_zones   Display the Route53 hosted zones in an account.
    list_iam_policies   Display the IAM policies (inline and attached) in an account.
    list_iam_roles      Display the IAM roles in an account and its trust relationships.
    list_igws           Display IGWs attached in accounts.
    list_lambdas        Display Lambda functions deployed in accounts.
    list_public_ips     Display the public IPs in an account.
    list_vpc_attribute  Display VPC attributes such as DNS settings for accounts.
    list_vpcs           Display VPCs configured in accounts.
    $

A keen observer will notice that the built-in commands already include a
"list_vpcs" command, so what happens if we have the same command in our
"/home/me/awsrun-commands" directory? Command paths are searched in the order
they are specified, so in the example above, our version would be used over the
built-in version.

Specifying your command path via CLI flags can become tiresome, but as with most
CLI flags, you can add a section to your configuration file, which defaults to
"~/.awsrun.yaml". The following adds both our custom directory as well as the
built-in commands to our path:

    CLI:
      cmd_path:
        - /home/me/awsrun-commands
        - awsrun.commands.aws

For more information on the awsrun CLI command line options, please refer to the
`awsrun.cli` documentation.

## User-Defined Plug-ins

In addition to writing your own user-defined commands, you can write your own
account loader plug-ins as well as credential loader plug-ins. The following are
the high-level steps involved in writing your own plug-ins:

1. Subclass `awsrun.plugmgr.Plugin`. Be sure to read the class and module
    documentation for details on how the CLI loads your plug-in.

2. Add an `__init__` method to register command line flags and configuration
    options. Be sure to call the superclass's `__init__` method as well.

3. Provide an implementation for `awsrun.plugmgr.Plugin.instantiate`, which
    must return an instance of `awsrun.acctload.AccountLoader` or
    `awsrun.session.SessionProvider` depending on whether you are writing an
    account loader or a credential loader.

It is recommended that you review the existing plug-ins included in awsrun for
additional guidance on how to build your own.

## Roadmap

- Add tests for each module (only a handful have been done so far). PyTest is
  the framework used in awsrun. See the tests/ directory which contains the
  directories for unit and integration tests.

- Add Azure support. Specifically, add a handful of builtin session providers in
  `awsrun.plugins.creds.azure` module. Then add a few sample command modules in
  `awsrun.commands.azure` that use the Azure python SDK. Finally, uncomment the
  line in setup.py so the 'azurerun' script is installed. Adding other CSPs will
  follow the same process.

"""

name = "awsrun"
__version__ = "2.1.0"
