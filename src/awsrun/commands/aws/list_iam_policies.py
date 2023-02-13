#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""
Display the IAM policies (inline and attached) in an account.

## Overview

The list_iam_policies command will display the IAM policies, inline and
attached, associated with identities in an account. Identities include users,
groups, and roles. By default, the policy name and the identity it is
associated with are displayed. For example:

    $ awsrun --account 100200300400 list_iam_policies
    100200300400: identity=user:joe policy=attached:ReadOnlyAccess
    100200300400: identity=role:AWSServiceRoleForAutoScaling policy=attached:AutoScalingServiceRolePolicy
    100200300400: identity=role:AWSServiceRoleForECS policy=attached:AmazonECSServiceRolePolicy
    100200300400: identity=role:AWSServiceRoleForElasticLoadBalancing policy=attached:AWSElasticLoadBalancingServiceRolePolicy
    ...

In the above output, there is one attached user policy called ReadOnlyAccess and
it is associated with the "joe" user. In addition, there are several attached
role policies.  The `--users`, `--groups`, and `--roles` flags will limit the
output to policies attached to the respective identity type. For example, to
show only user policies:

    $ awsrun --account 100200300400 list_iam_policies --users
    100200300400: identity=user:joe policy=attached:ReadOnlyAccess

The `--inline` and `--attached` flags will limit the output to the type of
policy. These flags can be combined with the identity filter flags as well.  For
example, to show only inline policies associated with roles:

    $ awsrun -a 100200300400 list_iam_policies --inline --roles
    100200300400: identity=role:ECSAutoScalingRole policy=inline:service-autoscaling
    100200300400: identity=role:ECSClusterEC2Role policy=inline:ecs-service
    100200300400: identity=role:ECSServiceRole policy=inline:ecs-service

Use `--verbose` to display the JSON policy document contents. For example, to
view the contents of all user policies:

    $ awsrun --account 100200300400 list_iam_policies --users --verbose
    100200300400: identity=user:joe policy=attached:ReadOnlyAccess
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": [
                    "a4b:Get*",
                    "a4b:List*",
                    "a4b:Describe*",
                    "a4b:Search*",
                    "acm:Describe*",
                    "acm:Get*",
                    ...

In addition to filtering policies based on identity types, the `--user-name
NAME`, `--group-name NAME`, and `--role-name NAME` options will display only
policies matching the respective NAMEs. For example, to match roles with
the name "viewer":

    $ awsrun --account 100200300400 list_iam_policies --role-name viewer
    100200300400: identity=user:joe policy=attached:ReadOnlyAccess
    100200300400: identity=role:viewer policy=attached:ViewOnlyAccess

Note: the above output contained a user policy as well even though `--role-name`
was specified. Filtering on names does not exclude other identity types from the
output. To show only role policies with a name of "viewer" be sure to include
`--roles` as well:

    $ awsrun --account 100200300400 list_iam_policies --roles --role-name viewer
    100200300400: identity=role:viewer policy=attached:ViewOnlyAccess

User, group, and role name filters can be used together. For example, to filter
on the "joe" user as well as the "bu_readonly" role while excluding any group
policies:

    $ awsrun --account 100200300400 list_iam_policies --roles --role-name bu_readonly --users --user-name joe
    100200300400: identity=user:joe policy=attached:ReadOnlyAccess
    100200300400: identity=role:bu_readonly policy=attached:ReadOnlyAccess
    100200300400: identity=role:bu_readonly policy=attached:AWSSupportAccess

Multiple name filters for the same identity type can be specified by supplying
multiple flags. For example, to filter on "bu_readonly" and "viewer" roles:

    $ awsrun --account 100200300400 list_iam_policies --roles --role-name bu_readonly --role-name viewer
    100200300400: identity=role:bu_readonly policy=attached:ReadOnlyAccess
    100200300400: identity=role:bu_readonly policy=attached:AWSSupportAccess
    100200300400: identity=role:viewer policy=attached:ViewOnlyAccess

To filter on a specific policy name or to exclude a specific policy by name, use
the `--policy-name NAME` and the `--not-policy-name NAME` flags. These flags are
mutually exclusive. Like the other name filters, multiple names can be specified
by supplying additional flags.  For example:

    $ awsrun --account 100200300400 list_iam_policies --policy-name key-policy --policy-name vpc-flow-log-policy
    100200300400: identity=role:logging policy=inline:key-policy
    100200300400: identity=role:logging policy=attached:vpc-flow-log-policy

When matching policy names, if a policy name starts with the NAME specified on
the command line, it is considered a match. For example, to match any policy
that starts with "vpc":

    $ awsrun --account 100200300400 list_iam_policies --policy-name vpc
    100200300400: identity=role:logging policy=attached:vpc-flow-log-policy

Finally, to filter policies that contain a specific IAM action, use the
`--action-name NAME` and `--not-action-name NAME` flags. When filtering by
action names, only policies that include the action in the policy's Action or
NotAction block are included in the results.  The matching algorithm does take
into account any wildcards used in the policy.  For example, if the IAM policy
included:

    Action: [ "sts:*", "ec2:*" ]

Then searching for an action name using `--action-name sts:AssumeRole` would
match the policy, and thus be included in the output. Wildcards, however, cannot
be used in search terms as exact matches are used.  Like the other name filters,
multiple names can be specified by supplying multiple flags. For example, to
search all policies that do not start with IAM, but contain sts:AssumeRole:

    $ awsrun --account 100200300400 list_iam_policies --not-policy-name admin --action-name sts:AssumeRole
    100200300400: identity=role:automation policy=attached:automation-policy
    100200300400: identity=role:OrganizationAccountAccessRole policy=inline:AdministratorAccess

Note: search results do not take into account whether or action is allowed or
denied, only whether or not it is present in an Action or NotAction block.

To view the details of the AdministratorAccess policy, specify the `--verbose`
flag:

    $ awsrun --account 100200300400 list_iam_policies --policy-name AdministratorAccess --verbose
    100200300400: identity=role:OrganizationAccountAccessRole policy=attached:AdministratorAccess
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "*",
                "Resource": "*"
            }
        ]
    }

## Reference

### Synopsis

    $ awsrun [options] list_iam_policies [command options]

### Configuration

The following is the syntax for the options that can be specified in the user
configuration file:

    Commands:
      list_iam_policies:
        verbose: BOOLEAN
        roles: BOOLEAN
        users: BOOLEAN
        groups: BOOLEAN
        inline: BOOLEAN
        attached: BOOLEAN
        role_name:
          - STRING
        user_name:
          - STRING
        group_name:
          - STRING
        action_name:
          - STRING
        not_action_name:
          - STRING
        policy_name:
          - STRING
        not_policy_name:
          - STRING

### Command Options

Some options can be overridden on the awsrun CLI via command line flags. In
those cases, the CLI flags are specified next to the option name below:

`verbose`, `--verbose`, `-v`
:  Include the JSON policy body in the output.

`roles`, `--roles`
:  Flag to search role policies. If neither the roles, users, or groups flags
are specified, then all are searched. Specifying one or more of these flags will
limit the search to those identity types.

`users`, `--users`
:  Flag to search user policies. If neither the roles, users, or groups flags
are specified, then all are searched. Specifying one or more of these flags will
limit the search to those identity types.

`groups`, `--groups`
:  Flag to search group policies. If neither the roles, users, or groups flags
are specified, then all are searched. Specifying one or more of these flags will
limit the search to those identity types.

`inline`, `--inline`
:  Flag to search inline policies. If neither the inline or attached flags are
specified, then all are searched. Specifying one or more of these flags will
limit the search to those policy types.

`attached`, `--attached`
:  Flag to search attached policies. If neither the inline or attached flags are
specified, then all are searched. Specifying one or more of these flags will
limit the search to those policy types.

`role_name`, `--role-name`
:  Limit output to include the specified role names. When specifying multiple
values on the command line, use multiple flags for each value.

`user_name`, `--user-name`
:  Limit output to include the specified user names. When specifying multiple
values on the command line, use multiple flags for each value.

`group_name`, `--group-name`
:  Limit output to include the specified group names. When specifying multiple
values on the command line, use multiple flags for each value.

`action_name`, `--action-name`
:  Limit output to include the policy if it contains the specified Action names.
When specifying multiple values on the command line, use multiple flags for each
value. This option cannot be used in conjunction with `not_action_name`.

`not_action_name`, `--not-action-name`
:  Limit output to include the policy if it contains the specified NotAction
names. When specifying multiple values on the command line, use multiple flags
for each value. This option cannot be used in conjunction with `action_name`.

`policy_name`, `--policy-name`
:  Limit output to include the policy if its name starts with the specified
value. When specifying multiple values on the command line, use multiple flags
for each value. This option cannot be used in conjunction with
`not_policy_name`.

`not_policy_name`, `--not-policy-name`
:  Limit output to include the policy if its name does not start with the
specified value. When specifying multiple values on the command line, use
multiple flags for each value. This option cannot be used in conjunction with
`policy_name`.
"""

import io
import json
import re

from botocore.exceptions import ClientError

from awsrun.config import Bool, List, Str
from awsrun.runner import Command


class CLICommand(Command):
    """Display the IAM policies (inline and attached) in an account."""

    @classmethod
    def from_cli(cls, parser, argv, cfg):
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="include JSON policy body",
            default=cfg("verbose", type=Bool),
        )

        include_group = parser.add_argument_group(
            "limit flags", "Search only these identity and policy types"
        )
        include_group.add_argument(
            "--roles",
            action="store_true",
            help="search role policies only",
            default=cfg("roles", type=Bool),
        )
        include_group.add_argument(
            "--users",
            action="store_true",
            help="search user policies only",
            default=cfg("users", type=Bool),
        )
        include_group.add_argument(
            "--groups",
            action="store_true",
            help="search group policies only",
            default=cfg("groups", type=Bool),
        )
        include_group.add_argument(
            "--inline",
            action="store_true",
            help="search inline policies only",
            default=cfg("inline", type=Bool),
        )
        include_group.add_argument(
            "--attached",
            action="store_true",
            help="search attached policies only",
            default=cfg("attached", type=Bool),
        )

        search_group = parser.add_argument_group(
            "filter flags", "Search only policies associated with identity name"
        )
        search_group.add_argument(
            "--role-name",
            metavar="NAME",
            action="append",
            dest="role_names",
            help="filter on role name",
            default=cfg("role_name", type=List(Str), default=[]),
        )
        search_group.add_argument(
            "--user-name",
            metavar="NAME",
            action="append",
            dest="user_names",
            help="filter on user name",
            default=cfg("user_name", type=List(Str), default=[]),
        )
        search_group.add_argument(
            "--group-name",
            metavar="NAME",
            action="append",
            dest="group_names",
            help="filter on group name",
            default=cfg("group_name", type=List(Str), default=[]),
        )

        other_group = parser.add_argument_group(
            "other filters", "Search only policies matching these other options"
        )
        action_group = other_group.add_mutually_exclusive_group()
        action_group.add_argument(
            "--action-name",
            metavar="NAME",
            action="append",
            dest="action_names",
            help="include policy if it contains the action",
            default=cfg("action_name", type=List(Str), default=[]),
        )
        action_group.add_argument(
            "--not-action-name",
            metavar="NAME",
            action="append",
            dest="not_action_names",
            help="include policy if it does not contains the action",
            default=cfg("not_action_name", type=List(Str), default=[]),
        )
        policy_group = other_group.add_mutually_exclusive_group()
        policy_group.add_argument(
            "--policy-name",
            metavar="NAME",
            action="append",
            dest="policy_names",
            help="include if policy name starts with",
            default=cfg("policy_name", type=List(Str), default=[]),
        )
        policy_group.add_argument(
            "--not-policy-name",
            metavar="NAME",
            action="append",
            dest="not_policy_names",
            help="exclude if policy name starts with",
            default=cfg("not_policy_name", type=List(Str), default=[]),
        )

        args = parser.parse_args(argv)
        return cls(**vars(args))

    def __init__(
        self,
        verbose,
        roles,
        users,
        groups,
        inline,
        attached,
        role_names,
        user_names,
        group_names,
        action_names,
        not_action_names,
        policy_names,
        not_policy_names,
    ):
        self.verbose = verbose

        # This set of flags is used to include identity and policy types
        self.include_roles = roles
        self.include_users = users
        self.include_groups = groups
        self.include_inline = inline
        self.include_attached = attached

        # If neither roles, users, or groups are specified, search all by default
        if not (roles or users or groups):
            self.include_roles = True
            self.include_users = True
            self.include_groups = True

        # If neither inline or attached are specified, search both by default
        if not (inline or attached):
            self.include_inline = True
            self.include_attached = True

        # This set of flags is used to search on a specific name(s).
        self.search_roles = role_names
        self.search_users = user_names
        self.search_groups = group_names
        self.search_actions = action_names
        self.not_search_actions = not_action_names
        self.search_policies = policy_names
        self.not_search_policies = not_policy_names

    def execute(self, session, acct):
        out = io.StringIO()
        iam = session.resource("iam")

        # Will be a dict containing all the policies associated with users,
        # groups, and roles keyed by the identity type.
        identities = {}

        if self.include_users:
            identities["user"] = get_identities(iam.users, iam.User, self.search_users)

        if self.include_groups:
            identities["group"] = get_identities(
                iam.groups, iam.Group, self.search_groups
            )

        if self.include_roles:
            identities["role"] = get_identities(iam.roles, iam.Role, self.search_roles)

        for i_type in identities:  # pylint: disable=consider-using-dict-items
            for identity in identities[i_type]:
                ip = IdentityPrinter(out, f"{acct}: identity={i_type}:{identity.name}")
                self.show_inline_policies(identity, ip)
                self.show_attached_policies(identity, ip)

        return out.getvalue()

    def show_inline_policies(self, identity, ip):
        """Prints the inline policies associated with identity."""
        if not self.include_inline:
            return

        for inline in identity.policies.all():
            # pylint: disable=cell-var-from-loop
            # We wrap the policy_document in a lambda so boto3 resource is not
            # fetched unless it is really needed. Although pylint complains
            # about wrapping the looping var in a lambda, we use the lambda
            # immediately if needed.
            if self.should_skip(inline.policy_name, lambda: inline.policy_document):
                continue

            ip.print(f"policy=inline:{inline.policy_name}")
            if self.verbose:
                ip.print(json.dumps(inline.policy_document, indent=4), prefix=False)

    def show_attached_policies(self, identity, ip):
        """Prints the attached policies associated with identity."""
        if not self.include_attached:
            return

        for attached in identity.attached_policies.all():
            # pylint: disable=cell-var-from-loop
            # We wrap the default_version.document in a lambda so boto3 resource
            # is not fetched unless it is really needed.
            if self.should_skip(
                attached.policy_name, lambda: attached.default_version.document
            ):
                continue

            ip.print(f"policy=attached:{attached.policy_name}")
            if self.verbose:
                ip.print(
                    json.dumps(attached.default_version.document, indent=4),
                    prefix=False,
                )

    def should_skip(self, name, get_doc):
        """Returns false if the policy with name and policy document should be
        skipped.  For efficiency, the get_doc argument should be a function
        that returns the policy document, so it is only called if needed."""

        if self.search_policies and not any(
            name.startswith(n) for n in self.search_policies
        ):
            return True
        if self.not_search_policies and any(
            name.startswith(n) for n in self.not_search_policies
        ):
            return True

        # Short-circuit us out of here if we don't need to search for actions,
        # which would require downloading the policy document. Recall, boto
        # loads these things lazily, so if we don't need to access it, then
        # don't load it.
        if not self.search_actions and not self.not_search_actions:
            return False

        # Since we now need to search through the actual policy for action
        # statements, invoke the function passed to actually get the policy.
        doc = get_doc()
        if self.search_actions and not has_actions(doc, self.search_actions):
            return True
        if self.not_search_actions and has_actions(doc, self.not_search_actions):
            return True

        return False


# ---------------------------------------------------------------------------
# Helper Classes


# This class is used so I don't have to pass around a bunch of args to each
# method just for printing out the standard "acct:" lines. Instead, one instance
# is instantiated with the prefix, and then this object is passed from method to
# method.
#
# Remember, do not be tempted to store mutable variables from your CLICommand
# execute method as instance variables. The execute method is NOT thread safe
# and will be running concurrently with many other threads!
class IdentityPrinter:
    """Utility class to buffer printing with a prefix."""

    def __init__(self, out, prefix=None):
        self.out = out
        self.prefix = prefix

    def print(self, msg, prefix=True):
        """Print msg to buffer, if prefix is True, prepend the prefix."""
        if prefix:
            print(f"{self.prefix} {msg}", file=self.out)
        else:
            print(msg, file=self.out)


# ---------------------------------------------------------------------------
# Helper Functions


def has_actions(policy_doc, search_actions):
    """Search a policy document, specifically the Action and NotAction blocks
    for any IAM actions that match the search_actions. Matching does take into
    account wildcards specified in the policy document. Returns true if the
    document contains any of the actions in search_actions. Note: this does not
    take into account whether an action is allowed or denied."""

    for statement in make_list(policy_doc["Statement"]):
        if "Action" in statement:
            action_block = statement["Action"]
        else:
            action_block = statement["NotAction"]

        for action in make_list(action_block):
            pattern = re.compile("^" + re.escape(action).replace("\\*", ".*") + "$")
            for search_action in search_actions:
                if pattern.search(search_action):
                    return True
    return False


def make_list(obj):
    """Returns obj if it is a list, otherwise returns a list of one element
    containing obj. This is due to AWS's inconsistent use of JSON arrays."""

    if isinstance(obj, list):
        return obj

    return [obj]


def get_identities(collection, subresource, search_names):
    """Return an iterable of IAM identities. If search_names is empty, then all
    identities from collection are returned. If search_names contains a list of
    names, a resource is created by calling subresource. The resource is then
    loaded to ensure it exists. All valid resources are returned."""

    if not search_names:
        return collection.all()

    # For each name being searched, create a resource object
    identities = [subresource(name) for name in search_names]

    # Resource objects load lazily, so we don't know if the identities
    # above are valid or not. Let's filter out only the valid ones.
    return filter(identity_exists, identities)


def identity_exists(identity):
    """Returns True if the identity exists, otherwise false. As a side
    effect, the identity's resources are loaded."""

    try:
        identity.load()
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            return False
        raise e
