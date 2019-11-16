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
Ever wish you could run the standard AWS CLI tool across multiple accounts?
Now you can using the included [`aws`](https://fmr-llc.github.io/awsrun/commands/aws/aws.html)
command. This command is a simple wrapper for AWS's CLI, but with the added
benefits of using metadata to select multiple accounts as well as simplified
credential handling.

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

## Demo

The demo below illustrates the power of awsrun once it has been configured to
your environment. We will gather information on the VPCs in an account. We
could gather this information using only AWS's native CLI, but that limits us
to processing one account at a time. Instead, we'll use awsrun and its built-in
[`aws`](https://fmr-llc.github.io/awsrun/commands/aws/aws.html) command to
execute an AWS CLI command across multiple accounts concurrently. We'll also
make use of the awsrun's metadata explorer to select accounts for command 
execution. In the demo, 58 accounts are selected by the metadata filter, and
then processed in 13 seconds.

![Example](https://fmr-llc.github.io/awsrun/demo.svg)

## Installation

To install from source, clone the repo and run pip install:

    $ git clone https://github.com/fmr-llc/awsrun.git
    $ cd awsrun
    $ pip3 install .

Python 3.6 or higher is required.

In order to use the built-in awsrun "aws" command, Windows users must make sure
that the AWS CLI tool is installed in their PATH. When pip installs the AWS CLI,
it does not set the appropriate PATH variables, so it may be easier to install
the AWS CLI via the MSI provided by AWS.

## Quick Start

Out of the box, the utility of awsrun is limited as most of its power comes from
the configuration an account loader plug-in and credential loader plug-in. With 
that said, however, you can still use it out of the box as it will default to 
loading credentials from your $HOME/.aws/credentials file. While not convenient
when managing hundreds of accounts, it will suffice to get you started.

To list the VPC information for accounts 100200300400 and 200300400100, we need to
create two profiles, `[100200300400]` and `[200300400100]`, in our AWS credentials
file, or we need to have a `[default]` profile which is used as a fallback. With
those defined, you can then run the following command to list VPCs:

    $ awsrun --account 100200300400 --account 200300400100 aws ec2 describe-vpcs --region us-east-1 --region us-west-2
    2 accounts selected:

    100200300400, 200300400100

    Proceed (y/n)? y
    ...

## Documentation

awsrun includes extensive [documentation](https://fmr-llc.github.io/awsrun/), which
includes the following:

* The [CLI User Guide](https://fmr-llc.github.io/awsrun/#cli-usage) includes basic
  usage, configuration, and how to use the account loader and credential loader
  plug-ins.

* The [How-to Write Your Own Commands](https://fmr-llc.github.io/awsrun/#user-defined-commands)
  guide provides everything you need to write your own custom awsrun commands. This is
  where you'll spend a lot of time once you become familiar with the capabilities of
  awsrun.

* The [API User Guide](https://fmr-llc.github.io/awsrun/#api-usage) includes pointers
  to the key documentation required to use awsrun programmatically instead of via the
  CLI. All of the awsrun [modules](https://fmr-llc.github.io/awsrun/#header-submodules)
  are also extensively documented.
  
* The [How-to Write Your Own Plug-ins](https://fmr-llc.github.io/awsrun/#user-defined-plug-ins)
  section includes pointers to the documentation required to build your own account
  loader plug-in and credential plug-in if the included ones are not suitable to your
  environment.
  
## Change Log

### v2.1.0

* Add a YAML account loader plug-in to complement the CSV and JSON account
  loader plug-ins.
* Minor clarification in user guide about the interaction between `--accounts` and
  metadata filters (`--include`/`--exclude`).

### v2.0.0

* Initial open source release of awsrun from Fidelity's CloudX Network team. This
  version abstracts the Fidelity specific integrations into plug-ins, so others
  can take advantage of this tool, which has proven to be valuable for our teams.
