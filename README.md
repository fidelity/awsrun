[![ci](https://github.com/fidelity/awsrun/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/fidelity/awsrun/actions/workflows/ci.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# awsrun & azurerun

CLI tool and library to concurrently execute user-defined commands across AWS
accounts or Azure subscriptions.

> **Note**
> As of release 3.0.0, installation has changed with the introduction of
> optional dependencies. Previously, `pip install awsrun` would install all
> dependencies needed for `awsrun`, `azurerun`, and all of the bundled
> commands. You **must** now specify the optional dependencies when installing:
> `pip install "awsrun[aws,azure]"`. See Installation for more details.

## Overview

Awsrun/azurerun is both a CLI tool and Python package that can be used to
execute commands concurrently over one or more AWS accounts or Azure
subscriptions. Commands are user-defined Python modules that implement a simple
interface to abstract away the complications of obtaining credentials for Boto3
and Azure SDK sessions&mdash;especially when using SAML authentication and/or
cross-account access in AWS. The key features of awsrun/azurerun include the
following:

**Concurrent Account Processing**:
Run a command concurrently across subset or all of your accounts/subscriptions.
A worker pool manages the execution to ensure accounts/subscriptions are
processed quickly, so you don't have to wait for them to be processed one at a
time. Process hundreds of accounts in a few minutes.

**SAML and Cross-Account Access**:
Tired of dealing with AWS temporary STS credentials with SAML and cross-account
authentication? Use any of the included credential plug-ins based on your needs,
or build your own plug-in to provide credentials for your command authors. Don't
use SAML? Define profiles in your AWS credentials file instead. With Azure, the
default credentials are obtained via the Azure CLI or interactively via the browser.

**Built-in Command for AWS CLI & Azure CLI**:
Ever wish you could run the standard AWS CLI tool or Azure CLI tool across
multiple accounts/subscriptions? Now you can using the included
[`aws`](https://fidelity.github.io/awsrun/commands/aws/aws.html) or
[`az`](https://fidelity.github.io/awsrun/commands/azure/az.html) commands. These
commands are simple wrappers for AWS's and Azure's CLI tools respectively, but
with the added benefits of using metadata to select multiple accounts as well as
simplified credential handling.

**User-Defined Commands**:
Build your own commands using the powerful Boto3 SDK or Azure SDK without the
hassle of obtaining sessions and credentials. Thanks to a simple interface,
commands are easy to build and can be integrated directly into the CLI with
custom arguments and help messages.

**Metadata Enriched Accounts**:
Accounts/subscriptions can be enriched with metadata from external sources, such
as a corporate CMBD, via the account loader plug-in mechanism. This enables you
to use metadata to select accounts to process rather than explicitly listing
each account/subscription on the command line. In addition, command authors have
access to this metadata, so it can used while processing an account if needed.

## Screenshots

These examples demonstrate the wide-range of possibilities when building your
own awsrun & azurerun commands. While these commands are included in awsrun,
they use the same command library that you would if building your own. Nothing is
special about these commands other than they are included in the base install of
awsrun. You could have built these yourself.

### awsrun `aws` command

This screencast illustrates the power of awsrun once it has been configured to
your environment using appropriate credential and account loader plug-ins. In
this demo, we use awsrun to gather VPC information. While we could do the same
using only AWS's native CLI, we would be limited to processing one account at a
time. Instead, we'll use awsrun and the built-in
[`aws`](https://fidelity.github.io/awsrun/commands/aws/aws.html) command to
execute an AWS CLI command across multiple accounts concurrently. We'll also
make use of the awsrun's metadata explorer to select accounts for command
execution.

![aws command](https://fidelity.github.io/awsrun/demo.svg)

Note: The output has been obfuscated with random account numbers and
identifiers.

### awsrun `last` command

This screenshot demonstrates the use of the
[`last`](https://fidelity.github.io/awsrun/commands/aws/last.html) command to
interactively explore CloudTrail events. Don't have a simple means to view
CloudTrail logs? Tired of using the AWS Console? The `last` command provides a
simple way of viewing events in one or more accounts.

![last command](https://fidelity.github.io/awsrun/last.jpg)

### awsrun `dx_status` command

If you manage AWS Direct Connects to provide connectivity to your on-premise
corporate networks, you might find the
[`dx_status`](https://fidelity.github.io/awsrun/commands/aws/dx_status.html)
command helpful. It provides an overview of Direct Connects contained within an
account. This includes pulling CloudWatch metrics and generating terminal-based
graphs using [sparklines](https://en.wikipedia.org/wiki/Sparkline) and
ASCII-based charts.

![dx_status spark command](https://fidelity.github.io/awsrun/dx_status-spark.jpg)

![dx_status chart command](https://fidelity.github.io/awsrun/dx_status-chart.jpg)

## Installation

Python 3.7 or higher is required.

To install only `awsrun`:

    $ pip install "awsrun[aws]"

To install only `azurerun`:

    $ pip install "awsrun[azure]"

To install both `awsrun` and `azurerun`:

    $ pip install "awsrun[aws,azure]"

In all cases, the console scripts `awsrun` and `azurerun` are installed, but
only the dependencies for the specified CSPs are installed.

Some of the bundled commands have additional dependencies. You will be prompted
to install those if you use one of them. Alternatively, you can install all of
those ahead of time:

    $ pip install "awsrun[cmds]"

Finally, to install from source with the development dependencies:

    $ git clone https://github.com/fidelity/awsrun.git
    $ cd awsrun
    $ pip install -e ".[aws,azure,cmds,dev]"

## AWS Quick Start

Out of the box, the utility of awsrun is limited as most of its power comes from
the configuration of an [account loader
plug-in](https://fidelity.github.io/awsrun/cli.html#account-plug-ins) (to
simplify the selection of multiple accounts) and a [credential loader
plug-in](https://fidelity.github.io/awsrun/cli.html#credential-plug-ins) (to
simplify access to those accounts). With that said, however, you can still use
it, as it will default to loading credentials from your `$HOME/.aws/credentials`
file. While not convenient when managing hundreds of accounts, it will suffice
to get you started.

Assume you wanted to list the EC2 instances in two accounts: 100200300400
and 200300400100. We can use the built-in
[`aws`](https://fidelity.github.io/awsrun/commands/aws/aws.html) command to
execute any [AWS CLI
command](https://docs.aws.amazon.com/cli/latest/reference/index.html#cli-aws)
across one or more accounts concurrently. Be sure you have followed the
installation instructions in the previous section. Then, create two profiles,
`[100200300400]` and `[200300400100]`, in your local AWS credentials file
`$HOME/.aws/credentials`. If awsrun cannot find a profile for named for the
specific account, it will fallback to the `[default]` profile.

Note: The AWS credentials file is not part of awsrun, but it is used as the
default mechanism to obtain credentials if more [advanced
options](https://fidelity.github.io/awsrun/plugins/creds/aws.html) have not been
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
commands](https://fidelity.github.io/awsrun/commands/aws/index.html) that have
been included in awsrun. The more interesting ones include the
[`last`](https://fidelity.github.io/awsrun/commands/aws/last.html) command to
inspect CloudTrail events as well as the
[`dx_status`](https://fidelity.github.io/awsrun/commands/aws/dx_status.html)
command to check the status of Direct Connect circuits. Remember, you are
encouraged to build your own custom commands. These have been provided to show
you how to do so.

## Azure Quick Start

Let's list all the Azure VMs in two subscriptions:
00000000-0000-0000-0000-000000000000 and 11111111-1111-1111-1111-111111111111.
We can use the built-in
[`az`](https://fidelity.github.io/awsrun/commands/azure/az.html) command to
execute an [Azure CLI
command](https://docs.microsoft.com/en-us/cli/azure/reference-index?view=azure-cli-latest)
across one or more subscriptions concurrently. Assuming you have already
followed the installation instructions:

    $ az login   # Use the Azure CLI to obtain credentials
    $ azurerun --account 00000000-0000-0000-0000-000000000000 --account 11111111-1111-1111-1111-111111111111 az vm list --output table
    2 accounts selected:

    00000000-0000-0000-0000-000000000000, 11111111-1111-1111-1111-111111111111

    Proceed (y/n)? y
    ...
    Name   ResourceGroup      Location    Zones
    -----  -----------------  ----------  -----
    vm1    rg1                centralus   1
    vm2    rg1                eastus2     1

    Name   ResourceGroup      Location    Zones
    -----  -----------------  ----------  -----
    vm1    rg2                centralus   1
    vm2    rg2                eastus1     1
    vm3    rg2                eastus2     1

Out of the box, the utility of azurerun is limited as most of its power comes
from the configuration of an [account loader
plug-in](https://fidelity.github.io/awsrun/cli.html#account-plug-ins) (to
simplify selection of multiple accounts). Using the included
[AzureCLI](https://fidelity.github.io/awsrun/plugins/accts/azure.html) plug-in,
azurerun will use the Azure CLI to obtain a list of subscriptions and metadata
associated with those. Furthermore, assuming you use a naming convention for
your subscriptions, we can parse the name to pull out additional metadata. For
example, if your subscriptions are named "azure-retail-prod" and
"azure-retail-nonprod", then we can use this regexp to add the "bu" and "env"
metadata attributes:

    azure-(?P<bu>[^-]+)-(?P<env>.+)

Create the following azurerun configuration file called `.azurerun.yaml` in your
home directory:

    Accounts:
      plugin: awsrun.plugins.accts.azure.AzureCLI
      options:
        name_regexp: 'azure-(?P<bu>[^-]+)-(?P<env>.+)'

Now, you can use the metadata filters to specify subscriptions instead of
enumerating them on the azurerun command line. Here are a few examples:

    # Let's see what metadata we can use
    $ azurerun --metadata
    bu
    cloudName
    env
    homeTenantId
    id
    isDefault
    name
    state
    tenantId

    # Run the command over all subscriptions.
    $ azurerun az vm list --output table
    ...

    # Run the command over all prod subscriptions.
    $ azurerun --include env=prod az vm list --output table
    ...

    # Run the command over all enabled, nonprod subscriptions
    $ azurerun --include state=Enabled --include Env=nonprod az vm list --output table
    ...

There are several other [built-in
commands](https://fidelity.github.io/awsrun/commands/azure/index.html) that have
been included in azurerun. Remember, you are encouraged to build your own custom
commands. These have been provided to show you how to do so.

## Documentation

awsrun includes extensive [documentation](https://fidelity.github.io/awsrun/), which
includes the following:

- The [CLI User Guide](https://fidelity.github.io/awsrun/cli.html#cli-user-guide)
  includes basic usage, configuration of awsrun, and how to use the account
  loader and credential loader plug-ins to enhance the user experience on the
  CLI.

- The [Library User Guide](https://fidelity.github.io/awsrun/#api-usage)
  includes pointers to the key documentation required to use awsrun
  programmatically instead of via the CLI. All of the awsrun
  [modules](https://fidelity.github.io/awsrun/#header-submodules) are also
  extensively documented.

- The [How-to Write Your Own
  Commands](https://fidelity.github.io/awsrun/commands/#user-defined-commands)
  guide provides everything you need to write your own custom awsrun commands.
  This is where you'll spend a lot of time once you become familiar with the
  capabilities of awsrun.

- The [How-to Write Your Own
  Plug-ins](https://fidelity.github.io/awsrun/#user-defined-plug-ins) section
  includes pointers to the documentation required to build your own account
  loader plug-in and credential plug-in if the included ones are not suitable to
  your environment.

## Change Log

### v3.1.0

- Add `URLAccountLoader` plug-in which supports HTTP authentication (basic,
  digest, oauth2). This plug-in should be preferred over the existing
  `JSONAccountLoader`, `YAMLAccountLoader`, and `CSVAccountLoader` plug-ins,
  which will eventually be deprecated.

- Add HTTP POST support to the SAML credential provider plug-in. Thanks to
  @RobertShan2000 for the contribution.

### v3.0.0

- **BREAKING CHANGE**: Installation via `pip install awsurn` no longer installs
  all of the dependencies for `awsrun`, `azurerun`, and the bundled commands.
  Instead, users must now specify which optional dependendencies to install.
  See Installation section above for details. Note: while the major version
  was bumped, there are no API changes to awsrun. This was bumped from "2"
  to "3" solely to bring awareness to the different installation instructions.

- The terminal-based UI for the `last` command, a CloudTrail event viewer,
  was rewritten using the amazing Textual TUI framework. With this change,
  several new features were added to the command: dark/light modes, mouse
  support, filtering events, exporting events, OS clipboard integration,
  highlighting of events with errors, ability to toggle layout, as well as
  a brand new look and feel. See screenshot above.

- Modernized the python packaging to use `pyproject.toml` instead of the
  `setup.py` style of packgaing.

- Thanks to Gábor Lipták for the GitHub actions contributions. This included
  adding the new check for PR titles to ensure they adhere to the Conventional
  Commits standard.

- Added a CONTRIBUTING document thanks to Brian Warner, a member of our
  open-source office at Fidelity.

### v2.5.2

- Resolve all pylint warnings.

- Update `dx_status` for `asciichart` API changes and bump version.

- Allow reuse of `argparse` option flags for command authors that use the same
  flag across multiple argparse subcommands. Previously, reuse of option flags
  was prohibited across different instances of `argparse.ArgumentParser`.

### v2.5.1

- Fix tag and redeploy pypi artifacts.

### v2.5.0

- `last` command now appends each CloudTrail event line in non-interactive mode
  with "ERROR: " and the `errorCode` from the event if present. This allows users
  to quickly identify errors (`grep ERROR`). The CloudTrail API does not provide
  a means to filter on errors, so it can only be done after retrieving events.

- `last` command TUI now allows users to filter CloudTrail events interactively
  via a popup (mapped to 'f' key). Users can specify one or more terms to match
  events. Terms are logically OR'd together. A term may be prefixed with `-` to
  exclude events matching it. For example, "errorCode -s3" will show only
  events that had errors excluding S3 events.

### v2.4.2

- Update `kubectl` wrapper to use latest `v1beta1` Kubernetes API instead of
  `v1alpha1` to fix compatibility issues with the latest version of Kubernetes
  `kubectl` and latest AWS CLI tool.

### v2.4.1

- Require Python 3.7 or greater in `setup.py`.

### v2.4.0

- Remove Python 3.6 classifier from `setup.py`.

- Update authentication method in `kubectl` wrapper from `aws-iam-authenticator`
  to use the AWS CLI command `aws eks get-token`. Users will no longer need
  to install the separate `aws-iam-authenticator` helper moving forward.

- Use `KUBECONFIG` environment variable instead of `--kubeconfig` command line
  flag when the `kubectl` wrapper command invokes the real `kubectl` command.
  This change should be transparent to users of the `kubectl` command.

### v2.3.1

- Add new sample awsrun command, `dx_maint`, that queries the AWS Health API to
  display recent and upcoming maintenance events (technically any open events)
  on Direct Connects.

- Add new sample azurerun command, `list_udrs`, that displays all User Defined
  Routes (UDRs) in an Azure VNET.

### v2.3.0

- Add support for Azure. By default, installation now installs both `awsrun` as
  well as `azurerun`. See the quick start for Azure above.

### v2.2.2

- Add a decorator `awsrun.runner.max_thread_limit` that can be used by command
  authors to limit the number of concurrent executions. There are some scenarios
  where a command author may never want their command run concurrently across
  multiple accounts. By default, awsrun uses a thread pool of ten workers, and
  users can override, so this gives command authors ability to limit if needed.

### v2.2.1

- Reorganized the documentation. The CLI user guide and reference are now part
  of the `awsrun.cli` module documentation. The user guide on writing commands
  has been moved to the `awsrun.commands` module. Lots of other minor edits were
  made as part of this reorganization. Hopefully, things are easier to find with
  the new layout.

### v2.2.0

- Add three new built-in commands:
  [`console`](https://fidelity.github.io/awsrun/commands/aws/console.html),
  [`dx_status`](https://fidelity.github.io/awsrun/commands/aws/dx_status.html),
  and [`last`](https://fidelity.github.io/awsrun/commands/aws/last.html). Console
  generates sign-in URLs for the AWS Console using credentials from awsrun.
  Dx_status shows the status of Direct Connect circuits (terminal graphs too!).
  Last provides an easier way to review CloudTrail events in both an interactive
  and non-interactive manner.

- Add the [`cloudwatch`](https://fidelity.github.io/awsrun/cloudwatch.html)
  module to simplify the retrieval of CloudWatch metrics using bulk retrieval
  for efficiency. This module is used be the new
  [`dx_status`](https://fidelity.github.io/awsrun/commands/aws/dx_status.html)
  command.

- Update the included built-in commands that iterate over VPCs to filter out
  VPCs that have been shared with an account, as opposed to being owned by the
  account, as generally that is the behavior one is expecting.

- Remove AWS CLI as a python dependency in `setup.py`. AWS has released v2 of
  the AWS CLI, so we should not presume to install v1 via pip installation. In
  addition, AWS has stated that the only supported installation of the AWS CLI
  v2 is via their own bundled package installers. What does this mean for awsrun
  users? Install the AWS CLI on your own if you plan on using the built-in `aws`
  command.

- Fonts used in documentation have been updated to use Charter and Fira Mono.

### v2.1.0

- Add a YAML account loader plug-in to complement the CSV and JSON account
  loader plug-ins.

- Minor clarification in user guide about the interaction between `--accounts` and
  metadata filters (`--include`/`--exclude`).

### v2.0.0

- Initial open source release of awsrun from Fidelity's CloudX Network team. This
  version abstracts the Fidelity specific integrations into plug-ins, so others
  can take advantage of this tool, which has proven to be valuable for our teams.
