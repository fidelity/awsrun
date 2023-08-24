#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Obtain boto3 sessions and credentials via a variety of means.

## Overview

This module provides a `SessionProvider` interface to obtain AWS credentials via
one of several mechanisms: the standard AWS CLI configuration files, Single Sign
On (SSO) via federated SAML authentication, or cross-account access initiated
from a base account. Regardless of the mechanism, the session provider is
responsible for returning a boto3 Session that contains the credentials for a
requested account. In some cases, those credentials are cached to limit the
number of API calls to AWS and/or Identity Providers (IdP) should a session be
requested for the same account again.

There are three concrete session provider implementations included in this
module:

`CredsViaProfile`
:  Credentials are obtained from AWS configuration and credential files.

`CredsViaSAML`
:  Credentials are obtained via a role assumed via SAML-based federation.

`CredsViaCrossAccount` respectively.
:  Credentials are obtained via a role assumed from a base account.

## Quick Start

The following quick start guides show which `SessionProvider` implementation to
use and how to use the library depending on the preferred mechanism to obtain
AWS credentials. Each section includes code examples and references to
additional documentation.

### AWS Profiles

The AWS CLI allows users to define "profiles" in their AWS credentials file
(~/.aws/credentials) and their AWS configuration file (~/.aws/config). For
example, assume ~/.aws/credentials file contains the following two profiles
defined:

    [111222333444]
    aws_access_key_id=AKIAIOSFODNN7EXAMPLE
    aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

    [222333444111]
    aws_access_key_id=BEOQODRDNEUDFEXAMPLE
    aws_secret_access_key=8weuou7etAUGZehZHoZeQHVBxogGRLEXAMPLEKEY

To create a `SessionProvider` that will read the standard AWS configuration and
credential files to provide boto3 Session objects, create an instance of
`CredsViaProfile`:

    # Instantiate a single session provider and reuse it
    session_provider = CredsViaProfile()

    # Obtain boto3 sessions for one or more accounts
    session1 = session_provider.session('111111111111')
    session2 = session_provider.session('222222222222')

    # Use the sessions to interact with AWS
    ec2 = session1.resource('ec2', region_name='us-east-1')
    iam = session2.resource('iam', region_name='us-east-1')

The `CredsViaProfile` session provider requires that all of the credentials have
been specified in the AWS configuration and credential files under profiles
named after the account ID. The benefit of using the above is that the user will
be able to use the numerous mechanisms available via the standard AWS files
including standard access/secret keys, pre-defined cross-account access, or even
an external process to obtain creds. But, of course, this assumes one has
defined all of the accounts ahead of time.

Please refer to the [AWS CLI Configuration and Credential
Files](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
for additional details on the use of the standard AWS files.

### SAML SSO

AWS supports federated SSO access via SAML. In this scenario, rather than
defining AWS credentials in AWS configuration files (see previous section), the
user authenticates to their local Identity Provider (IdP), such as ADFS or
PingFederate, to obtain a SAML assertion that is used to assume an AWS role
within an account to obtain credentials for API usage.

To create a `SessionProvider` that will obtain credentials via SAML-based
federated access using ADFS, create an instance of `CredsViaSAML` and use NTLM
to authenticate to the ADFS server:

    # Instantiate a single session provider and reuse it
    session_provider = CredsViaSAML(
        role='RoleName',  # Name (not ARN) of the AWS role to assume
        url='https://adfs.example.com/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices',
        auth=requests_ntlm.HttpNtlmAuth('domain\\username', 'password'))

    # Obtain boto3 sessions for one or more accounts
    session1 = session_provider.session('111111111111')
    session2 = session_provider.session('222222222222')

    # Use the sessions to interact with AWS
    ec2 = session1.resource('ec2', region_name='us-east-1')
    iam = session2.resource('iam', region_name='us-east-1')

`CredsViaSAML` is configurable and can be used with other IdP servers by
adjusting the `auth` method and/or providing additional HTTP headers. For
example, assume a PingFederate IdP is used and requires a specific HTTP user
agent header on authentication requests:

    # Instantiate a single session provider and reuse it
    session_provider = CredsViaSAML(
        role='RoleName',  # Name (not ARN) of the AWS role to assume
        url='https://adfs.example.com/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices',
        auth=requests.auth.HTTPBasicAuth('username', 'password'),
        headers={'User-Agent': 'My Agent'})

Please refer to [Using SAML-Based Federation for API Access to
AWS](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_saml.html)
for additional details on the use of federated SSO with SAML.

### Cross Account

In large companies with a significant number of AWS accounts, it is more common
to use cross-account access to simplify management of credentials and limit
direct access to accounts. With this mechanism, a user obtains credentials for a
"base" or "source" account from which they assume role into other accounts
provided IAM permissions have been setup properly. The benefit is that a user
does not need direct access to every account. Only access to the "base" account
is required from which the user can "hop off" to other accounts.

To create a `SessionProvider` that will assume a role from a base account,
create an appropriate session provider for the base account, and then pass that
to the `CredsViaCrossAccount`. The following example assumes the credentials for
the base account (111111111111) are stored in profile defined in the local AWS
files:

    # Instantiate a session provider for the base account
    base_session_provider = CredsViaProfile()

    # Instantiate a session provider for cross-account access
    session_provider = CredsViaCrossAccount(
        base_auth=base_session_provider,
        base_acct='111111111111',     # the hop off account
        role='CrossAccountRoleName')  # the name (not an ARN)

    # Obtain boto3 sessions for any accts that allow cross-account access
    session1 = session_provider.session('222222222222')
    session2 = session_provider.session('333333333333')

    # Use the sessions to interact with AWS
    ec2 = session1.resource('ec2', region_name='us-east-1')
    iam = session2.resource('iam', region_name='us-east-1')

In large companies, it's likely more common that SAML is used for direct access
to the base account, and then cross-account access to the remainder of accounts:

    # Instantiate a session provider for the base account
    session_provider = CredsViaSAML(
        role='BaseRoleName',  # Name (not ARN) of the AWS role to assume
        url='https://adfs.example.com/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices',
        auth=requests_ntlm.HttpNtlmAuth('domain\\username', 'password'))

    # Instantiate a session provider for cross-account access
    session_provider = CredsViaCrossAccount(
        base_auth=base_session_provider,
        base_acct='111111111111',     # the hop off account
        role='CrossAccountRoleName')  # the name (not an ARN)

This method of cross-account access will only work if the proper IAM permissions
have been granted to the base user/role and cross-account roles. The base
user/role will need the AssumeRole permission, and the cross-account roles will
need to have an assume role policy document that permits access from the base
account.

Although, the `CredsViaProfile` session provider can support cross-account
access, it does require that every account must be defined in the local AWS
files. For a corporation with hundreds of accounts that change all the time,
this may not be practical. `CredsViaCrossAccount` does not use the local AWS
files. The only use of AWS files would be limited to the base account if
`CredsViaProfile` is used. If, on the other hand, SAML authentication is used
for the base account via `CredsViaSAML`, then the local AWS files aren't used at
all.

Please refer to [Providing Access to an IAM User in Another AWS Account That You
Own](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_common-scenarios_aws-accounts.html)
for additional details on cross-account access.

## Caching

AWS credentials obtained via SAML-based federation (assume_role_with_saml) or
cross account access (assume_role) are cached in memory by default for 1 hour
(3600 seconds). This means subsequent calls to `SessionProvider.session` for the
same account will return the cached set of credentials unless half of the cache
duration has transpired, in which case a new set of credentials will be
returned. If AWS credentials are expired sooner by a local policy, then lower
the duration in the `CredsViaSAML` and `CredsViaCrossAccount` constructors.

Likewise, the SAML assertion obtained via the IdP by `CredsViaSAML` is cached
for 5 minutes (300 seconds). This, too, can be adjusted in the constructor. If
the IdP expires SAML assertions sooner, then the `saml_duration` value must be
set appropriately.

Finally, it is important to note that caching in this context has no relevance
to refreshable credentials that boto3 can provide when assuming roles. This
module does not provide refreshable credentials at this time. At some point in
the future, this capability will be added.

## Exceptions

The following exceptions are defined in this module. They are only used by the
SAML and cross-account session providers to provide additional context when
something goes wrong.

`IDPAccessDeniedException`
:  Raised if the user could not be authenticated with IdP.

`IDPInvalidResponseException`
:  Raised if the SAML response cannot be found from IdP.

`IDPInvalidRoleException`
:  Raised if the user does not have access to the role.

`AWSAssumeRoleException`
:  Raised if the assume_role* calls fail.

## Thread Safety

All of the `SessionProvider` implementations are thread-safe. It is safe to
instantiate a single session provider instance and share that with one or more
threads. The session provider is intended to be used repeatedly to obtain boto3
sessions. Users should not, however, share boto3 sessions between threads per
the [Boto3 Multithreading / Multiprocessing
Notes](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/resources.html?highlight=multithreading#multithreading-multiprocessing).
"""

import base64
import logging
import random
import threading
import xml.etree.ElementTree as ET

import boto3
import botocore.exceptions
import requests
from bs4 import BeautifulSoup

from awsrun.cache import ExpiringValue
from awsrun.session import SessionProvider

LOG = logging.getLogger(__name__)


class CachingSessionProvider(SessionProvider):
    """Abstract base class for session providers that cache credentials by role.

    This class cannot be instantiated directly. Users of this class must provide
    an implementation for `credentials` and must invoke its constructor. Caching
    is based on the IAM `role` being assumed and the the account ID. Credentials
    are cached for `duration` seconds, which defaults to 1 hour.
    """

    def __init__(self, role, duration=3600):
        self._role = role
        self._duration = duration

        # Cache of temporary credentials. Keys are tuples of account and role.
        # Values are ExpiringValue objects holding AWS credentials. The lock is
        # to protect access to the cache.
        self._creds = {}
        self._lock = threading.Lock()

    def session(self, acct_id):
        """Returns a boto3 Session with credentials for the requested account.

        The `acct_id` is a string containing the AWS account ID. The returned
        boto3 Session object is ready to use and loaded with the requested
        credentials.

        The credentials loaded into the boto3 Session object are cached in the
        event this method is invoked multiple times for the same account. Users
        are guaranteed that the credentials will be valid for half of the cache
        duration time specified in the constructor.
        """
        with self._lock:
            # setdefault is technically atomic in cpython 2.7 or 3.2 higher, so
            # the lock may seem redundant, but it's safer to make this explicit.
            ev = self._creds.setdefault(
                (acct_id, self._role),
                ExpiringValue(lambda: self.credentials(acct_id), self._duration / 2),
            )

        creds = ev.value()

        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )

    def credentials(self, acct_id):
        """Returns a dict containing AWS credentials for the requested account.

        The `acct_id` is a string containing the AWS account ID. The returned
        dict must include the following keys: "AccessKeyId", "SecretAccessKey",
        and "SessionToken". This dict will be cached by the session provider.

        Refer to the module documentation for the exceptions that may be raised.
        """
        raise NotImplementedError


class CredsViaProfile(SessionProvider):
    """A session provider that uses AWS configuration and credential files.

    This class requires that credentials for accounts have already been
    configured in the standard AWS CLI configuration and credential files with
    profile names that match account ID. For example, if ~/.aws/credentials
    contains the following, then this session provider can be used to access
    accounts 11122233344 and 222333444111:

        [111222333444]
        aws_access_key_id=AKIAIOSFODNN7EXAMPLE
        aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

        [222333444111]
        aws_access_key_id=BEOQODRDNEUDFEXAMPLE
        aws_secret_access_key=8weuou7etAUGZehZHoZeQHVBxogGRLEXAMPLEKEY

    If a profile does not exist for an account, this class will fallback to the
    "default" profile to obtain credentials for the account:

        [default]
        aws_access_key_id=BEOQODRDNEUDFEXAMPLE
        aws_secret_access_key=8weuou7etAUGZehZHoZeQHVBxogGRLEXAMPLEKEY

    By leveraging the standard AWS CLI credential and configuration files, users
    can specify credentials in a variety of ways including standard access and
    secret keys, pre-defined cross-account access, or even use an external
    process to obtain credentials.
    """

    def session(self, acct_id):
        try:
            return boto3.Session(profile_name=acct_id)

        except botocore.exceptions.ProfileNotFound:
            LOG.info(
                "no profile found for %s, falling back to default profile", acct_id
            )
            return boto3.Session()


class CredsViaSAML(CachingSessionProvider):
    """A session provider that uses federated SAML authentication.

    This class relies on a SAML Identity Provider (IdP) to provide a SAML
    assertion to an authenticated user, which is then sent to AWS to obtain the
    credentials for an AWS account.

    The `role` is the name of the IAM role (not the ARN) to assume in the AWS
    account. This is used when making the underlying AWS assume_role_with_saml
    API call.

    The `url` is the URL to the IdP web server that will provide a SAML
    assertion to the user once they have authenticated. The HTTP authentication
    method used is specified in the `auth` parameter. This must be an instance
    of a
    [requests](https://2.python-requests.org/en/master/user/authentication/)
    authentication method such as HTTPBasicAuth, HTTPDigestAuth, or HttpNtlmAuth
    (from the [requests_ntlm](https://github.com/requests/requests-ntlm)
    package). If additional HTTP headers must be provided to the IdP in the
    authentication request, specify a dict of header/value pairs via the
    `headers` argument. To disable certificate verification, which is strongly
    discouraged, set `no_verify` to `True`.

    The AWS credentials for the role and account are cached for `duration`
    seconds, which defaults to 1 hour. Likewise, the SAML assertion obtained
    from the IdP is cached for `saml_duration`, which defaults to 5 minutes.
    """

    def __init__(
        self,
        role,
        url,
        auth,
        http_method,
        headers=None,
        duration=3600,
        saml_duration=300,
        no_verify=False,
    ):
        super().__init__(role, duration)
        self._url = url
        self._auth = auth
        self._http_method = http_method
        self._headers = {} if headers is None else headers
        self._cached_saml = ExpiringValue(self._request_assertion, saml_duration)
        self._no_verify = no_verify

    def assertion(self, refresh=False):
        """Returns a SAML assertion from the IdP.

        This value is cached by default. If refresh is True, the value is
        refreshed first, then returned.  See the module documentation for the
        exceptions that may be raised.
        """
        return self._cached_saml.value(refresh)

    def _request_assertion(self):
        """Returns a non-cached SAML assertion from the IdP.

        See the module documentation for the exceptions that may be raised.
        """
        LOG.info("Fetching SAML assertion")
        with requests.Session() as s:
            s.auth = self._auth
            s.headers.update(self._headers)
            if self._http_method == "GET":
                resp = s.get(self._url, verify=not self._no_verify)
            else:
                authData = {
                    "UserName": s.auth.username,
                    "Password": s.auth.password,
                    "AuthMethod": "FormsAuthentication",
                }
                resp = s.post(self._url, data=authData, verify=not self._no_verify)

        if resp.status_code == 401:
            raise IDPAccessDeniedException("Could not authenticate")
        if not 200 <= resp.status_code < 300:
            raise IDPInvalidResponseException(
                f"{resp.status_code} response from {self._url}"
            )

        soup = BeautifulSoup(resp.text, "html.parser")
        saml = [
            t.get("value")
            for t in soup.find_all("input")
            if t.get("name") == "SAMLResponse"
        ]

        if len(saml) != 1:
            raise IDPInvalidResponseException(
                "Cannot extract SAML assertion from response"
            )

        # Indexing is guaranteed to succeed as we check the length above
        return saml[0]

    def credentials(self, acct_id):
        saml = self.assertion()
        root = ET.fromstring(base64.b64decode(saml))

        # Extract all the roles from the SAML response.
        roles = []
        for attr in root.iter("{urn:oasis:names:tc:SAML:2.0:assertion}Attribute"):
            if attr.get("Name") == "https://aws.amazon.com/SAML/Attributes/Role":
                for value in attr.iter(
                    "{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue"
                ):
                    roles.append(value.text)
        LOG.info("roles in SAML response: %s", roles)

        # Note the format of the attribute value should be role,principal but
        # lots of blogs list it as principal,role so let's reverse them if
        # needed. We also filter out any that do not match the account or role
        # that user instantiated the class with.
        filtered_roles = []
        for r, p in [arns.split(",") for arns in roles]:
            if ":saml-provider/" in r:
                r, p = p, r
            if r.endswith(f":{acct_id}:role/{self._role}"):
                filtered_roles.append((r, p))

        if len(filtered_roles) != 1:
            raise IDPInvalidRoleException(f"Cannot find {acct_id}/{self._role}")

        # All index accesses below are guaranteed to not fail because we ensure
        # there is an element in filter_roles, and the values are 2-item tuples
        # we created ourselves.
        role_arn = filtered_roles[0][0]
        principal_arn = filtered_roles[0][1]

        LOG.info("Assuming role with SAML for %s with %s", role_arn, principal_arn)
        assumed_role = boto3.client("sts").assume_role_with_saml(
            RoleArn=role_arn,
            PrincipalArn=principal_arn,
            SAMLAssertion=saml,
            DurationSeconds=self._duration,
        )

        if not assumed_role:
            raise AWSAssumeRoleException(f"Cannot assume role: {role_arn}")

        return assumed_role["Credentials"]


class CredsViaCrossAccount(CachingSessionProvider):
    """A session provider that uses cross-account access.

    This class obtains credentials for a "base" or "source" account, which are
    then used to assume role to another account to obtain credentials for that
    account. Please refer to the quick start for more details on cross-account
    access.

    The `base_auth` must be a `SessionProvider` that can obtain credentials for
    the `base_acct`. This might be an instance of `CredsViaProfile` or
    `CredsViaSAML` for example.

    The `role` is the name of the IAM role (not the ARN) to assume in the AWS
    account. This is used when making the underlying AWS assume_role API call.
    Note: this role does not refer to the base account, but rather the role used
    for the cross-account access.

    The `external_id` is an optional string containing a unique ID that can be
    used as part of an IAM trust policy in the remote accounts. Most users will
    not use this unless they are doing cross-account access to 3rd parties.
    Please refer to the [AWS Guide on External
    IDs](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-user_externalid.html).
    for more information.

    The AWS credentials for the role and account are cached for `duration`
    seconds, which defaults to 1 hour.
    """

    def __init__(self, base_auth, base_acct, role, external_id=None, duration=3600):
        super().__init__(role, duration)
        self._base_auth = base_auth
        self._base_acct = base_acct
        self._external_id = external_id

    def credentials(self, acct_id):
        sts = self._base_auth.session(self._base_acct).client("sts")

        role_arn = f"arn:aws:iam::{acct_id}:role/{self._role}"
        LOG.info("Assuming cross-account role for %s", role_arn)

        kwargs = {
            "RoleArn": role_arn,
            "RoleSessionName": f"AWSRunSession{random.randint(10000, 99999)}",
            "DurationSeconds": self._duration,
        }

        if self._external_id:
            kwargs["ExternalId"] = self._external_id

        assumed_role = sts.assume_role(**kwargs)

        if not assumed_role:
            raise AWSAssumeRoleException(f"Cannot assume role: {role_arn}")

        return assumed_role["Credentials"]


class IDPAccessDeniedException(Exception):
    """Raised if IDP cannot authenticate username and password."""


class IDPInvalidResponseException(Exception):
    """Raised if IDP response does not contain a SAML assertion."""


class IDPInvalidRoleException(Exception):
    """Raised if role and account are not found in SAML response."""


class AWSAssumeRoleException(Exception):
    """Raised if AWS role cannot be assumed."""
