#
# Copyright 2019 FMR LLC <opensource@fmr.com>
#
# SPDX-License-Identifier: MIT
#
"""Execute kubectl commands on EKS clusters.

NOTE: Be sure you have the most recent version of the AWS CLI installed as well
as the latest version of `kubectl`.  There have been recent changes in those
tools that cause compatibility issues with each other.

This awsrun command is a thin wrapper around the kubectl command. It adapts
kubectl for use with awsrun CLI tool allowing one to execute kubectl commands
across one or more AWS accounts, clusters, and namespaces. Let's walk through a
simple tutorial on its use.

To list all pods within all namespaces within all clusters in an account in
a region, we can use the standard `get pods` kubectl command:

    $ awsrun --account 100200300400 kubectl get pods --all-namespaces --region us-east-1

As with all awsrun commands, you can specify mulitple accounts via multiple
`--account` flags, via `--account-file`, or via the use of the `--include` and
`--exclude` account filters using an account loader. Likewise, multiple regions
may be specified via multiple `--region` flags. Refer to the awsrun
documentation for more information.

You can use one or more `--cluster` flags to target specific clusters. By
default, all clusters are targeted as shown in the prior example. To list all
pods in all namespaces for a specific cluster named `my-cluster`:

    $ awsrun --account 100200300400 kubectl get pods --cluster my-cluster --all-namespaces --region us-east-1

You can also use one or more `--namespace` flags to target specific namespaces.
By default, if no namespaces are specified, the `default` namespace is used. For
example, to list the pods in only the `kube-system` namespace in all clusters:

    $ awsrun --account 100200300400 kubectl get pods --namespace kube-system --region us-east-1

To list the EKS clusters in an account, use the `--list-clusters` argument.
Note: this is not a standard kubectl flag, but rather an awsrun addition to
simplify identifying cluster names in an account:

    $ awsrun --account 100200300400 kubectl --list-clusters --region us-east-1
    my-cluster-1
    my-cluster-2
    Processed 1 account in 0:00:01.496644

The awsrun kubectl command also supports annotation of output. This can be
helpful when running a command against multiple accounts, regions, clusters, and
namespaces. Without annotations, it is not possible to identify which output
belongs to which cluster. For example, the command below lists the pods within
the `kube-system` namespace in a single account across multiple regions:

    $ awsrun --account 100200300400 kubectl get pods --namespace kube-system --region us-east-1 --region us-east-2
    NAME                       READY     STATUS    RESTARTS   AGE
    aws-node-6pjq4             1/1       Running   0          1d
    aws-node-8bc8w             1/1       Running   0          1d
    coredns-56b5694569-m4zzn   1/1       Running   0          1d
    coredns-56b5694569-p7x7r   1/1       Running   0          1d
    kube-proxy-69nhw           1/1       Running   0          1d
    kube-proxy-ft5g8           1/1       Running   0          1d
    NAME                      READY     STATUS    RESTARTS   AGE
    aws-node-8w2gp            1/1       Running   2          9d
    aws-node-gmksn            1/1       Running   0          9d
    coredns-6f74b9cc4-8m8gb   1/1       Running   0          9d
    coredns-6f74b9cc4-djlds   1/1       Running   0          9d
    kube-proxy-8tpl4          1/1       Running   0          9d
    kube-proxy-fmtbn          1/1       Running   0          9d

Using the `--awsrun-annotate text` option will prefix each line with the
account, region, cluster name, and namespace:

    $ awsrun --account 100200300400 kubectl get pods --namespace kube-system --region us-east-1 --region us-east-2 --awsrun-annotate text
    100200300400/us-east-1/ecc-pe2-us-east-1/kube-system: NAME                       READY     STATUS    RESTARTS   AGE
    100200300400/us-east-1/ecc-pe2-us-east-1/kube-system: aws-node-6pjq4             1/1       Running   0          1d
    100200300400/us-east-1/ecc-pe2-us-east-1/kube-system: aws-node-8bc8w             1/1       Running   0          1d
    100200300400/us-east-1/ecc-pe2-us-east-1/kube-system: coredns-56b5694569-m4zzn   1/1       Running   0          1d
    100200300400/us-east-1/ecc-pe2-us-east-1/kube-system: coredns-56b5694569-p7x7r   1/1       Running   0          1d
    100200300400/us-east-1/ecc-pe2-us-east-1/kube-system: kube-proxy-69nhw           1/1       Running   0          1d
    100200300400/us-east-1/ecc-pe2-us-east-1/kube-system: kube-proxy-ft5g8           1/1       Running   0          1d
    100200300400/us-east-2/ecc-pe2-us-east-2/kube-system: NAME                      READY     STATUS    RESTARTS   AGE
    100200300400/us-east-2/ecc-pe2-us-east-2/kube-system: aws-node-8w2gp            1/1       Running   2          9d
    100200300400/us-east-2/ecc-pe2-us-east-2/kube-system: aws-node-gmksn            1/1       Running   0          9d
    100200300400/us-east-2/ecc-pe2-us-east-2/kube-system: coredns-6f74b9cc4-8m8gb   1/1       Running   0          9d
    100200300400/us-east-2/ecc-pe2-us-east-2/kube-system: coredns-6f74b9cc4-djlds   1/1       Running   0          9d
    100200300400/us-east-2/ecc-pe2-us-east-2/kube-system: kube-proxy-8tpl4          1/1       Running   0          9d
    100200300400/us-east-2/ecc-pe2-us-east-2/kube-system: kube-proxy-fmtbn          1/1       Running   0          9d

You can also annotate JSON and YAML output from kubectl commands. For example,
without annotation:

    $ awsrun --account 100200300400 kubectl get pods --namespace kube-system --region us-east-1 --region us-east-2
    apiVersion: v1
    items:
    -   apiVersion: v1
        kind: Pod
        metadata:
    ...
    apiVersion: v1
    items:
    -   apiVersion: v1
        kind: Pod
        metadata:
    ...

With the `--awsrun-annotate yaml` option:

    $ awsrun --account 100200300400 kubectl get pods --namespace kube-system --region us-east-1 --region us-east-2 --awsrun-annotate yaml
    Account: '100200300400'
    Cluster: ecc-pe2-us-east-1
    Namespace: kube-system
    Region: us-east-1
    Results:
        apiVersion: v1
        items:
        -   apiVersion: v1
            kind: Pod
            metadata:
    ...
    Account: '100200300400'
    Cluster: ecc-pe2-us-east-2
    Namespace: kube-system
    Region: us-east-2
    Results:
        apiVersion: v1
        items:
        -   apiVersion: v1
            kind: Pod
            metadata:
    ...

Finally, you can also use this wrapper to simply download a valid kubeconfig
file for an EKS cluster that has AWS STS credential embedded in the file. This
file can then be used with your system kubectl command to execute commands on a
cluster. For example, to create kubeconfig files for the `kube-system` namespace
all clusters within an account:

    $ awsrun --account 100200300400 kubectl --namespace kube-system --region us-east-1
    kubeconfig saved to /Users/pete/.kube/awsrun-100200300400-us-east-1-ecc-pe2-us-east-1-kube-system

This file contains a valid kubeconfig that can be used kubectl via the
`--kubeconfig` option:

    $ kubectl --kubeconfig /Users/pete/.kube/awsrun-100200300400-us-east-1-ecc-pe2-us-east-1-kube-system get pods

Again, as with all awsrun commands, you can target multiple accounts and
regions allowing you to create valid kubeconfig files for many clusters in a
single awsrun command.
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

import yaml

from awsrun.argparse import AppendWithoutDefault
from awsrun.config import List, Str, StrMatch
from awsrun.runner import RegionalCommand

LOG = logging.getLogger(__name__)


class CLICommand(RegionalCommand):
    """Execute kubectl commands on EKS clusters"""

    @classmethod
    def regional_from_cli(cls, parser, argv, cfg):
        parser.add_argument(
            "--list-clusters",
            action="store_true",
            help="list the EKS cluster",
        )
        parser.add_argument(
            "--cluster",
            dest="clusters",
            action=AppendWithoutDefault,
            default=cfg("cluster", type=List(Str), default=[]),
            help="EKS cluster name",
        )
        parser.add_argument(
            "--namespace",
            "-n",
            dest="namespaces",
            action=AppendWithoutDefault,
            default=cfg("namespace", type=List(Str), default=["default"]),
            help="EKS cluster namespace",
        )
        parser.add_argument(
            "--output",
            "-o",
            default=cfg("namespace", type=Str),
            help="Specify output format of kubectl",
        )

        # Note: normally one would not prefix an awsrun command's arguments with
        # '--awsrun-', but this is a special exception because there could be
        # valid kubectl args interspersed among the awsrun command flags. To
        # avoid namespace collisions, the kubectl command args are prefixed.
        parser.add_argument(
            "--awsrun-output-dir",
            metavar="DIR",
            default=cfg("awsrun_output_dir"),
            help="output directory to write results to separate files",
        )

        parser.add_argument(
            "--awsrun-annotate",
            choices=["json", "yaml", "text"],
            default=cfg("awsrun_annotate", type=StrMatch("^(json|yaml|text)$")),
            help="annotate each result with account/region/cluster/namespace",
        )

        # Let's gobble up any native kubuctl args that should not be used with
        # this wrapper, which decides the server, context, user, etc ... based
        # on how the awsrun wrapper is invoked. We also don't include these
        # flags in the help message as they are really part of the kubectl tool.
        # We capture these flags so we can check for their presence later and
        # remind users not to specify them.
        prohibited = [
            "kubeconfig",
            "context",
            ("server", "s"),
            "user",
            "username",
            "password",
            "client-key",
            "client-certificate",
            "client-authority",
            "as",
            "as-group",
            "token",
        ]

        for arg in prohibited:
            if isinstance(arg, tuple):
                parser.add_argument(f"--{arg[0]}", f"-{arg[1]}", help=argparse.SUPPRESS)
            else:
                parser.add_argument(f"--{arg}", help=argparse.SUPPRESS)

        # We parse the known args and then collect the rest as those will be
        # passed to the kubectl command later.
        args, remaining = parser.parse_known_args(argv)
        args.kubectl_args = remaining

        for arg in (a[0] if isinstance(a, tuple) else a for a in prohibited):
            attr = arg.replace("-", "_")
            if getattr(args, attr) is not None:
                parser.error("Do not specify --{arg} with awsrun kubectl")
            delattr(args, attr)

        if args.awsrun_annotate and args.output:
            if args.awsrun_annotate != "text":
                if args.awsrun_annotate != args.output:
                    parser.error(
                        "When specifying --awsrun-annotate, you do not need the --output flag"
                    )

        return cls(**vars(args))

    def __init__(
        self,
        kubectl_args,
        regions,
        clusters,
        namespaces,
        list_clusters,
        output,
        awsrun_output_dir,
        awsrun_annotate,
    ):
        super().__init__(regions)
        self.clusters = clusters
        self.list_flag = list_clusters
        self.namespaces = namespaces
        self.kubectl_args = kubectl_args
        self.output = output
        self.output_dir = awsrun_output_dir
        self.annotate = awsrun_annotate

        # Make sure user has both dependent binaries installed
        has_prereqs = True
        path = shutil.which("kubectl")
        if path:
            self.kubectlcli_path = path
        else:
            print(
                "'kubectl' not found in PATH, have you installed it?", file=sys.stderr
            )
            has_prereqs = False

        if not shutil.which("aws"):
            print(
                "AWS CLI not found in PATH, have you installed it?",
                file=sys.stderr,
            )
            has_prereqs = False

        if not has_prereqs:
            sys.exit(1)

    def regional_execute(self, session, acct, region):
        eks = session.client("eks", region_name=region)

        # User only wants to list the clusters in the account/region, so we
        # print this out and then return immediately.
        if self.list_flag:
            if self.annotate == "json":
                clusters = json.dumps(_list_clusters(eks))
            elif self.annotate == "yaml":
                clusters = yaml.dump(_list_clusters(eks))
            else:
                clusters = "\n".join(_list_clusters(eks)) + "\n"
            return [_Result(clusters, None, None, None)]

        results = []
        for name in self.clusters if self.clusters else _list_clusters(eks):
            cluster = eks.describe_cluster(name=name)
            for namespace in self.namespaces:
                # Write a kubecfg file to ~/.kube/awsrun-ACCT-CLUSTER-NAMESPACE
                filename = _save_kubecfg(
                    name, namespace, str(acct), region, cluster, session
                )

                # If user doesn't pass any kubectl commands, then just move on
                # as we've already save the credentials for them.
                if not self.kubectl_args:
                    text = f"kubeconfig saved to {filename}"
                    text = (
                        f'"{text}"'
                        if self.annotate in ["json", "yaml"]
                        else f"{text}\n"
                    )
                    results.append(_Result(text, None, name, namespace))
                    continue

                # Invoke kubectl and return results being careful to ensure that
                # we honor kubectl's stdout and stderr.
                cmd = [self.kubectlcli_path]
                if self.annotate and self.annotate != "text":
                    cmd += ["--output", self.annotate]
                elif self.output:
                    cmd += ["--output", self.output]
                cmd += self.kubectl_args

                # Set the KUBECONFIG env variable instead of using the
                # --kubeconfig command line option because not all kubectl
                # plugins support it. KUBECONFIG is more widely supported.
                os.environ["KUBECONFIG"] = str(filename)

                LOG.info("setting KUBECONFIG to %s", filename)
                LOG.info("running %s", cmd)

                result = subprocess.run(
                    cmd,
                    env=os.environ,
                    check=False,
                    universal_newlines=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                results.append(_Result(result.stdout, result.stderr, name, namespace))

        return results

    def regional_collect_results(self, acct, region, get_result):
        """Print the results to the console and files if specified."""

        def annotate_lines(result, text, file=sys.stderr):
            prefix = f"{acct}/{region}"
            if result.cluster and result.namespace:
                prefix += f"/{result.cluster}/{result.namespace}"
            for line in filter(None, text.split("\n") if text else ""):
                print(f"{prefix}: {line}", file=file, flush=True)

        def annotate_format(result, loader, dumper):
            try:
                d = {}
                d["Account"] = str(acct)
                d["Region"] = region
                if result.cluster and result.namespace:
                    d["Cluster"] = result.cluster
                    d["Namespace"] = result.namespace
                d["Results"] = loader(result.stdout)
                dumper(d, sys.stdout, indent=4)
                print()
            except Exception as e:  # pylint: disable=broad-except
                annotate_lines(result, f"cannot parse output: {e}", file=sys.stderr)

        try:
            # Let's get the return value from the execute method, which is the
            # ProcessCompleted object from the subprocess.run() method above ...
            results = get_result()

        except Exception as e:  # pylint: disable=broad-except
            # ... unless there was an exception in which case it is raised by
            # the call to get_result and we handle it here.
            LOG.info("%s/%s: error: %s", acct, region, e, exc_info=True)
            print(f"{acct}/{region}: error: {e}", file=sys.stderr)
            return

        for result in results:
            # Print stderr from AWS CLI always annotating the lines
            annotate_lines(result, result.stderr, file=sys.stderr)

            # Print stdout from AWS CLI annotating when appropriate
            if not self.annotate:
                print(result.stdout, end="", flush=True)
            elif self.annotate == "json":
                annotate_format(result, json.loads, json.dump)
            elif self.annotate == "yaml":
                annotate_format(result, yaml.safe_load, yaml.dump)
            elif self.annotate == "text":
                annotate_lines(result, result.stdout)

            # Save stdout and stderr from kubectl to disk if requested
            if self.output_dir and result.cluster and result.namespace:
                # Recall, the acct object passed to execute() can be anything. The
                # str() method should provide us a unique means of identifying the
                # account, but we need to escape any slashes if we use this as part
                # of a filename so pathlib doesn't interpret as directories.
                escaped = re.sub(r"[\\/]", "_", str(acct))
                name = (
                    self.output_dir
                    / f"{escaped}-{region}-{result.cluster}-{result.namespace}"
                )

                _save_output(name.with_suffix(".stdout.log"), result.stdout)
                if result.stderr:
                    _save_output(name.with_suffix(".stderr.log"), result.stderr)


_Result = namedtuple("Result", ["stdout", "stderr", "cluster", "namespace"])


_KUBECONFIG = """
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: {certificate}
    server: {endpoint}
  name: {cluster}
contexts:
- context:
    cluster: {cluster}
    namespace: {namespace}
    user: aws
  name: aws
current-context: aws
kind: Config
preferences: {{}}
users:
- name: aws
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      args:
      - --region
      - {region}
      - eks
      - get-token
      - --cluster-name
      - {cluster}
      command: aws
      env:
      - name: AWS_ACCESS_KEY_ID
        value: {access_key}
      - name: AWS_SECRET_ACCESS_KEY
        value: {secret_key}
      - name: AWS_SESSION_TOKEN
        value: {session_token}
"""


def _save_output(name, text):
    with name.open("w") as out:
        out.write(text)


def _save_kubecfg(name, namespace, account_id, region, cluster, session):
    creds = session.get_credentials()
    substitions = {
        "cluster": name,
        "namespace": namespace,
        "account_id": account_id,
        "region": region,
        "endpoint": cluster["cluster"]["endpoint"],
        "certificate": cluster["cluster"]["certificateAuthority"]["data"],
        "access_key": creds.access_key,
        "secret_key": creds.secret_key,
        "session_token": creds.token,
    }

    kubedir = Path.home() / Path(".kube")
    kubedir.mkdir(parents=True, exist_ok=True)

    filename = kubedir / Path(f"awsrun-{account_id}-{region}-{name}-{namespace}")
    _save_output(filename, _KUBECONFIG.format(**substitions))
    return filename


def _list_clusters(eks):
    clusters = []
    for page in eks.get_paginator("list_clusters").paginate():
        for name in page["clusters"]:
            clusters.append(name)
    return clusters
