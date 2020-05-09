"""Obtain a signin URL for the AWS Console.

The URL returned is only valid for 15 minutes. The session duration for the URL
can be adjusted via the awsrun credential plug-in parameter `--saml-duration`
and `--x-acct-duration` flags depending on which mechanism is being used to
authenticate.

Use the `--region` option to specify a region for the console login. To specify
an exact landing page, a `path` can be provided as well. For example, to land on
the routing table page in us-west-2:

    $ awsrun --account 100200300400 console --region us-west-2 "/vpc/home#RouteTables:sort=routeTableId"
"""

import json

import requests

from awsrun.runner import Command


class CLICommand(Command):
    """Obtain a signin URL for the AWS Console"""

    @classmethod
    def from_cli(cls, parser, argv, cfg):
        parser.add_argument(
            "--region",
            default=cfg("region", default="us-east-1"),
            help="generate URL for REGION",
        )
        parser.add_argument(
            "path",
            nargs="?",
            default=cfg("path", default="/console/home"),
            help="Optional path to append to AWS url",
        )
        args = parser.parse_args(argv)
        return cls(**vars(args))

    def __init__(self, region, path):
        self.region = region
        self.path = path

    def execute(self, session, acct):
        creds = session.get_credentials()

        try:
            session_creds = {}
            session_creds["sessionId"] = creds.access_key
            session_creds["sessionKey"] = creds.secret_key
            session_creds["sessionToken"] = creds.token
        except AttributeError:
            return f"{acct}: can only be used with federated auth types"

        # Retrieve a signin token from AWS federation service
        r = requests.get(
            "https://signin.aws.amazon.com/federation",
            params={"Action": "getSigninToken", "Session": json.dumps(session_creds)},
        )
        r.raise_for_status()
        signin_token = r.json()["SigninToken"]

        # Use Request to create well-formed URL that we return to user
        r = requests.Request(
            "GET",
            "https://signin.aws.amazon.com/federation",
            params={
                "Action": "login",
                "Issuer": "fmr.com",
                "Destination": f"https://console.aws.amazon.com{self.path}?region={self.region}",
                "SigninToken": signin_token,
            },
        )

        return f"{acct}: {r.prepare().url}\n"
