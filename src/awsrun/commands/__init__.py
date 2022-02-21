#
# Copyright 2019 FMR LLC <opensource@fmr.com>
#
# SPDX-License-Identifier: MIT
#
"""Contains the built-in commands included in awsrun and azurerun.

The [submodules](#header-submodules) below provide the commands for different
cloud service providers (CSPs). The commands made available to the CLI user
depend on the literal name of the awsrun script installed on the filesystem. If
the awsrun CLI command is called `awsrun` on the filesystem, then the commands
in `awsrun.commands.aws` are included in the command path. If the CLI command is
called `azurerun`, then the commands in `awsrun.commands.azure` are included
instead.

While there are many included commands with awsrun (and some in azurerun), most
users will want to write their own commands tailored to specific tasks.  The
next section is a user guide on how to write your own commands. An example is
used throughout to illustrate the key concepts.

## User-Defined Commands

Building your own awsrun or azurerun commands is easy if you are familiar with
Python and the AWS Boto3 or Azure SDK library. The majority of this document
will focus building a command for awsrun as most concepts are identical for both
awsrun and azurerun user-defined commands. The last section will, however,
provide a full working azurerun example.

An awsrun command is a subclass of the abstract base class
`awsrun.runner.Command`.  If you are writing your own command, not intended for
use with the CLI, then you only need to implement the
`awsrun.runner.Command.execute` method on your subclass.  Please refer to
`awsrun.runner` for details on how to use the module and the methods available
on the `awsrun.runner.Command` class.

If, on the other hand, you want to build a command that can also be used from
the awsrun CLI, then you must define a subclass of `awsrun.runner.Command`
called `CLICommand` in a Python module with the same name of the command you
wish to define. For example, to create an awsrun command called "list_vpcs", you
would create a file called "list_vpcs.py" that contains your `CLICommand`
implementation. By adhering to these guidelines, the awsrun CLI will be able to
find and dynamically load your command at runtime.

As a convenience when building commands for AWS to operate on one or more
regions, you should subclass `awsrun.runner.RegionalCommand` instead of the
`awsrun.runner.Command`, which will abstract away the explicit looping over
regions on your behalf. The majority of your AWS commands will use this regional
command base class. Because Azure API endpoints are not region specific, you
will only use `awsrun.runner.Command` when building commands for Azure. Refer to
the documentation in `awsrun.runner` for additional details on the differences.

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
and/or the user configuration file. Note: azurerun commands will use the
non-region specific `awsrun.runner.Command.from_cli` method instead.

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
would typically use the Boto3 library, via the session object provided, to make
API calls to AWS. Let's look at the execute method from our first version of the
"list_vpcs" command above:

    def regional_execute(self, session, acct, region):
        ec2 = session.resource('ec2', region_name=region)
        ids = ', '.join(vpc.id for vpc in ec2.vpcs.all())
        return f'{acct}/{region}: {ids}\\n'

In this example, we create a Boto3 EC2 resource from the `session` object for
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

In the rare case where you, the author of a command, do not want your command to
be executed concurrently, use the `awsrun.runner.max_thread_limit` decorator on
your execute method. This will prevent awsrun for exceeding the number of
concurrent executions specified. Limiting the number of concurrent executions
shouldn't be done often as it negates one of the primary benefits of awsrun.

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

Let's assume we store the `list_vpcs.py` command in `/home/me/awsrun-commands`,
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

    access_report         Test role access to the accounts specified.
    aws                   Execute aws cli commands concurrently.
    cidr_overlap          Display VPCs configured in accounts.
    console               Obtain a signin URL for the AWS Console
    dx_status             Display the status of Direct Connects and VIFs.
    kubectl               Execute kubectl commands on EKS clusters
    last                  Displays the last CloudTrail events in an account.
    list_hosted_zones     Display the Route53 hosted zones in an account.
    list_iam_policies     Display the IAM policies (inline and attached) in an account.
    list_iam_roles        Display the IAM roles in an account and its trust relationships.
    list_igws             Display IGWs attached in accounts.
    list_lambdas          Display Lambda functions deployed in accounts.
    list_public_ips       Display the public IPs in an account.
    list_vpc_attribute    Display VPC attributes such as DNS settings for accounts.
    list_vpcs             Display VPCs configured in accounts.
    $

You can also specify more than one command path. For example, if you wanted to
include the default list of commands as well as all of your custom commands in
"/home/me/awsrun-commands", then provide additional `--cmd-path` flags for each
path to search:

    $ awsrun --cmd-path /home/me/awsrun-commands --cmd-path awsrun.commands.aws --account 100200300400
    1 account selected:

    100200300400

    The following are the available commands:

    access_report         Test role access to the accounts specified.
    aws                   Execute aws cli commands concurrently.
    cidr_overlap          Display VPCs configured in accounts.
    console               Obtain a signin URL for the AWS Console
    dx_status             Display the status of Direct Connects and VIFs.
    kubectl               Execute kubectl commands on EKS clusters
    last                  Displays the last CloudTrail events in an account.
    list_hosted_zones     Display the Route53 hosted zones in an account.
    list_iam_policies     Display the IAM policies (inline and attached) in an account.
    list_iam_roles        Display the IAM roles in an account and its trust relationships.
    list_igws             Display IGWs attached in accounts.
    list_lambdas          Display Lambda functions deployed in accounts.
    list_public_ips       Display the public IPs in an account.
    list_vpc_attribute    Display VPC attributes such as DNS settings for accounts.
    list_vpcs             Display VPCs configured in accounts.
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

### Azurerun Example

When building azurerun commands, there are a few differences compared to the
awsrun discussion in the preceding sections:

1. Use the Azure Python SDK instead of the AWS Boto3 library.

2. Subclass the non-region specific `awsrun.runner.Command`.  Implement the
   non-region specific lifecycle methods as appropriate:
   `awsrun.runner.Command.execute`, `awsrun.runner.Command.from_cli`, and
   `awsrun.runner.Command.collect_results`.

3. Edit your `~/.azurerun.yaml` file to add the path to your command if you
   don't want to specify the `--cmd-path` argument each time.

Here is the full example used in this guide rewritten for Azure.

    #!/usr/bin/env python
    \"\"\"Display the VNETs in an account.

    The `list_vnets` command displays the IDs of each VNET. For example:

        $ azurerun --account 00000000-0000-0000-0000-000000000000 list_vnets
        00000000-0000-0000-0000-000000000000/eastus2: my-prd-vnet (10.0.0.0/24)

    Specify the `--summary` flag to include a summary count of VPCs and
    CIDRs after processing all of the accounts:

        $ azurerun --account 00000000-0000-0000-0000-000000000000 --account 11111111-1111-1111-1111-111111111111 list_vnets --summary
        00000000-0000-0000-0000-000000000000/eastus2: my-prd-vnet (10.0.0.0/24)
        11111111-1111-1111-1111-111111111111/centralus: my-nonprd-vnet (10.10.0.0/24, 10.10.1.0/24)
        Total VPCs: 2
        Total CIDRs: 3
    \"\"\"

    import io
    import sys

    from awsrun.config import Bool
    from awsrun.runner import Command

    from azure.mgmt.network import NetworkManagementClient

    class CLICommand(Command):
        \"\"\"Display the VNETs in a subscription.\"\"\"

        @classmethod
        def from_cli(cls, parser, argv, cfg):
            parser.add_argument(
                '--summary',
                action='store_true',
                default=cfg('summary', type=Bool, default=False),
                help='include a summary report at the end')

            args = parser.parse_args(argv)
            return cls(**vars(args))

        def __init__(self, summary=False):
            super().__init__()
            self.summary_flag = summary
            self.all_cidrs = {}

        def pre_hook(self):
            self.all_cidrs.clear()

        def execute(self, session, acct):
            nmc = NetworkManagementClient(session, acct)
            cidrs = {}  # local variable
            for vnet in nmc.virtual_networks.list_all():
                cidrs[vnet.name] = vnet.address_space.address_prefixes
            return cidrs

        def collect_results(self, acct, get_result):
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
                print(f'{acct}: {ids}', file=sys.stdout)

            except Exception as e:
                print(f'{acct}: error: {e}', flush=True, file=sys.stderr)

        def post_hook(self):
            if self.summary_flag:
                print(f'Total VNETs: {len(self.all_cidrs.keys())}')
                print(f'Total CIDRs: {sum(len(c) for c in self.all_cidrs.values())}')


"""
