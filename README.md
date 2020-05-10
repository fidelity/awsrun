[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# awsrun

CLI and API to concurrently execute user-defined commands across AWS accounts.

## Overview

awsrun is both a CLI and API to execute commands over one or more AWS accounts
concurrently. Commands are user-defined Python modules that implement a simple
interface to abstract away the complications of obtaining credentials for Boto 3
sessions - especially when using SAML authentication and/or cross-account
access. The key features of awsrun include the following:

**Concurrent Account Processing**:
Run a command concurrently across subset or all of your accounts. A worker
pool manages the execution to ensure accounts are processed quickly, so you
don't have to wait for them to be processed one at a time. Process hundreds of
accounts in a few minutes.

**SAML and Cross-Account Access**:
Tired of dealing with temporary STS credentials with SAML and cross-account
authentication? Use any of the included credential plug-ins based on your needs,
or build your own plug-in to provide credentials for your command authors. Don't
use SAML? Build profiles in your AWS credentials file instead.

**Built-in Command for AWS CLI**:
Ever wish you could run the standard AWS CLI tool across multiple accounts? Now
you can using the included
[`aws`](https://fmr-llc.github.io/commands/aws/aws.html) command. This command
is a simple wrapper for AWS's CLI, but with the added benefits of using metadata
to select multiple accounts as well as simplified credential handling.

**User-Defined Commands**:
Build your own commands using the powerful Boto 3 library without the hassle
of obtaining sessions and credentials. Thanks to a simple interface, commands
are easy to build and can be integrated directly into the CLI with custom
arguments and help messages.

**Metadata Enriched Accounts**:
Accounts can be enriched with metadata from external sources, such as a
corporate CMBD, via the account loader plug-in mechanism. This enables you to
use metadata to select accounts to process rather than explicitly listing each
account on the command line. In addition, command authors have access to this
metadata, so it can be accessed while processing an account if needed.

## Demo and Screenshots

The following examples demonstrate the wide-range of possibilities when building
your awsrun commands. Nothing is special about these commands other than the
fact they are included in the base install. You could have built these yourself.

### `aws` Demo
The following screencast illustrates the power of awsrun once it has been
configured to your environment. In this demo, we use awsrun to gather VPC
information. We could do the same using only AWS's native CLI, but that limits
us to processing one account at a time. Instead, we'll use awsrun and the
built-in [`aws`](https://fmr-llc.github.io/commands/aws/aws.html) command to
execute an AWS CLI command across multiple accounts concurrently. We'll also
make use of the awsrun's metadata explorer to select accounts for command
execution. As you are about to observe, 58 accounts were selected by the
metadata filter and then processed in 13 seconds.

![aws command](https://fmr-llc.github.io/demo.svg)

Note: The output has been obfuscated with random account numbers and
identifiers.

### `last` Screenshot
The next screenshot shows how we can use the
[`last`](https://fmr-llc.github.io/commands/aws/last.html) command to
interactively explore CloudTrail events.

![last command](https://fmr-llc.github.io/last.jpg)

### `dx_status` Screenshots
The last screenshots show two variants of output from the
[`dx_status`](https://fmr-llc.github.io/commands/aws/dx_status.html) command,
which provides an overview of any Direct Connects in an account. This includes
pulling CloudWatch metrics and generating terminal-based graphs using
[sparklines](https://en.wikipedia.org/wiki/Sparkline) and ASCII-based charts.

![dx_status spark command](https://fmr-llc.github.io/dx_status-spark.jpg)

![dx_status chart command](https://fmr-llc.github.io/dx_status-chart.jpg)

## Installation

To install from source, clone the repo and run pip install:

    $ git clone https://github.com/fmr-llc/awsrun.git
    $ cd awsrun
    $ pip3 install .

Python 3.6 or higher is required.

In order to use the built-in awsrun
[`aws`](https://fmr-llc.github.io/commands/aws/aws.html) command, the AWS CLI
tool must be
[installed](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html)
and available in your PATH. It is no longer installed as part of the awsrun
installation to allow users the choice of installing v1 or v2 of the AWS CLI
tool.

If installing AWS CLI v1 on Windows via pip, users must make sure that the AWS
CLI tool is included in their PATH. When pip installs the AWS CLI, it does not
set the appropriate PATH variables on Windows, so it may be easier to install
the AWS CLI via the MSIs provided by AWS.

## Quick Start

Out of the box, the utility of awsrun is limited as most of its power comes from
the configuration of an [account loader
plug-in](https://fmr-llc.github.io/#account-plug-ins) and a [credential loader
plug-in](https://fmr-llc.github.io/#credential-plug-ins). With that said,
however, you can still use it, as it will default to loading credentials from
your `$HOME/.aws/credentials` file. While not convenient when managing hundreds
of accounts, it will suffice to get you started.

Let's assume you wanted to list the EC2 instances in two accounts: 100200300400
and 200300400100. We can use the built-in
[`aws`](https://fmr-llc.github.io/commands/aws/aws.html) command to execute any
[AWS CLI
command](https://docs.aws.amazon.com/cli/latest/reference/index.html#cli-aws)
across one or more accounts concurrently. Be sure you have followed the
installation instructions in the previous section. Then, you'll need to create
two profiles, `[100200300400]` and `[200300400100]`, in your local AWS
credentials file `$HOME/.aws/credentials`. If awsrun cannot find a profile for
named for the specific account, it will fallback to the `[default]` profile.

Note: The AWS credentials file is not part of awsrun, but it is used as the
default mechanism to obtain credentials if more [advanced
options](https://fmr-llc.github.io/#credential-plug-ins) have not been
configured. For help on the configuration of the AWS credential file, refer to
[AWS CLI Named
Profiles](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html).

With the profiles defined, you can now run the following to list the EC2
instances in both accounts across multiple regions concurrently:

    $ awsrun --account 100200300400 --account 200300400100 aws ec2 describe-instances --region us-east-1 --region us-west-2
    2 accounts selected:

    100200300400, 200300400100

    Proceed (y/n)? y
    ...
    
If, instead, you want to list lambda functions in those accounts:

    $ awsrun --account 100200300400 --account 200300400100 aws lambda list-functions --region us-east-1 --region us-west-2
    2 accounts selected:

    100200300400, 200300400100

    Proceed (y/n)? y
    ...

There are several other [built-in
commands](https://fmr-llc.github.io/commands/aws/index.html) that have been
included in awsrun. The more interesting ones include the
[`last`](https://fmr-llc.github.io/commands/aws/last.html) command to inspect
CloudTrail events as well as the
[`dx_status`](https://fmr-llc.github.io/commands/aws/dx_status.html) command to
check the status of Direct Connect circuits. Remember, you are encouraged to
build your own custom commands. These have been provided to show you how to do
so.

## Documentation

awsrun includes extensive [documentation](https://fmr-llc.github.io/), which
includes the following:

* The [CLI User Guide](https://fmr-llc.github.io/#cli-usage) includes basic
  usage, configuration, and how to use the account loader and credential loader
  plug-ins.

* The [How-to Write Your Own
  Commands](https://fmr-llc.github.io/#user-defined-commands) guide provides
  everything you need to write your own custom awsrun commands. This is where
  you'll spend a lot of time once you become familiar with the capabilities of
  awsrun.

* The [API User Guide](https://fmr-llc.github.io/#api-usage) includes pointers
  to the key documentation required to use awsrun programmatically instead of
  via the CLI. All of the awsrun
  [modules](https://fmr-llc.github.io/#header-submodules) are also extensively
  documented.
  
* The [How-to Write Your Own
  Plug-ins](https://fmr-llc.github.io/#user-defined-plug-ins) section includes
  pointers to the documentation required to build your own account loader
  plug-in and credential plug-in if the included ones are not suitable to your
  environment.
  
## Change Log

### v2.2.0
* Add three new built-in commands:
  [`console`](https://fmr-llc.github.io/commands/aws/console.html),
  [`dx_status`](https://fmr-llc.github.io/commands/aws/dx_status.html), and
  [`last`](https://fmr-llc.github.io/commands/aws/last.html). Console generates
  sign-in URLs for the AWS Console using credentials from awsrun. Dx_status
  shows the status of Direct Connect circuits (terminal graphs too!). Last
  provides an easier way to review CloudTrail events in both an interactive and
  non-interactive manner.
  
* Add the [`cloudwatch`](https://fmr-llc.github.io/cloudwatch.html) module to
  simplify the retrieval of CloudWatch metrics using bulk retrieval for
  efficiency. This module is used be the new
  [`dx_status`](https://fmr-llc.github.io/commands/aws/dx_status.html) command.
  
* Update the included built-in commands that iterate over VPCs to filter out
  VPCs that have been shared with an account as generally that is the behavior
  one is expecting from these built-in commands.

* Remove AWS CLI as a python dependency in `setup.py`. AWS has released v2 of
  the AWS CLI, so we should not presume to install v1 via pip installation. In
  addition, AWS has stated that the only supported installation of the AWS CLI
  v2 is via their own bundled package installers. What does this mean for awsrun
  users? Install the AWS CLI on your own if you plan on using the built-in `aws`
  command.
  
* Fonts used in documentation have been updated to use Charter and Fire Mono.
  

### v2.1.0

* Add a YAML account loader plug-in to complement the CSV and JSON account
  loader plug-ins.
* Minor clarification in user guide about the interaction between `--accounts` and
  metadata filters (`--include`/`--exclude`).

### v2.0.0

* Initial open source release of awsrun from Fidelity's CloudX Network team. This
  version abstracts the Fidelity specific integrations into plug-ins, so others
  can take advantage of this tool, which has proven to be valuable for our teams.
