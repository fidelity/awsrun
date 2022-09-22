#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Obtain Azure credentials via a variety of means.

## Overview

This module provides a `SessionProvider` interface to obtain Azure credentials
via one of two mechanisms: DefaultAzureCredential or UsernamePasswordCredential.
Regardless of the mechanism, the session provider is responsible for returning
an Azure credential given a subscription. In Azure, when requesting credentials
for a subscription, they will be the same unless the subscriptions are within
different tenants. None of the included session providers provide support for
mulitple tenants, but one could build their own if needed.

Two concrete session provider implementations included in this module:

`CredsViaAzureDefault`
:  Credentials are obtained from one of the following sources: environment
variables, an Azure managed identity, shared token cache (Windows only), user
signed into VSCode, the Azure CLI tool, or interactively via the browser.

`CredsViaUsernamePassword`
:  Credentials are obtained using a username and password. This session provider
is almost twice as fast as `CredsViaAzureDefault` when relying on Azure CLI for
authentication, which is slow as it has to invoke `az account get-access-token`
each time a token is needed.

## Quick Start

The following quick start guide shows how to use the provided Azure session
providers. To obtain credentials for subscriptions, create an instance of a
`SessionProvider`:

    # Instantiate a single session provider and reuse it (pick one)
    # session_provider = CredsViaAzureDefault()
    session_provider = CredsViaUsernamePassword('username', 'password')

    # Obtain credentials for one or more subscriptions
    creds1 = session_provider.session('00000000-0000-0000-0000-000000000000')
    creds2 = session_provider.session('11111111-1111-1111-1111-111111111111')

    # Use the credentials to interact with Azure
    nmc1 = NetworkManagementClient(creds1, '00000000-0000-0000-0000-000000000000')
    nmc2 = NetworkManagementClient(creds2, '11111111-1111-1111-1111-111111111111')

## Caching

The same Azure credential is reused because the Azure SDK clients invoke
`get_token` on the credential object to obtain an access token. Access tokens
are cached when using `CredsViaUsernamePassword`. Likewise, when defaulting to
VSCode or Azure CLI for authentication using `CredsViaAzureDefault`, the tokens
are cached as well.

## Thread Safety

`CredsViaUsernamePassword` is thread-safe. It uses the MSAL library token
cache, which is protected by locks, so it is safe to reuse the same underlying
Azure credential object.

`CredsViaAzureDefault` is almost thread-safe. When the credentials are obtained
from the Azure CLI, a token cache on disk is searched. If a token does not exist
or needs to be refreshed, then the writing of the cache is not thread-safe as it
does not appear the Azure CLI provides locking or atomic moves. To minimize this
risk, this module guarantees that only one thread makes the first request for a
token, to populate the token cache or refresh it, before allowing other threads
to proceed concurrently.
"""
import functools
import threading

from azure.identity import DefaultAzureCredential, UsernamePasswordCredential

from awsrun.session import SessionProvider

# The UsernamePasswordCredenial requires a client ID, so we use the client used
# by the Azure CLI.
DEVELOPER_SIGN_ON_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"

# Scope used to test if user's password is valid before azurerun launches a
# bunch of workers.
ARM_SCOPE = "https://management.azure.com/.default"


# Decorator used to wrap the various Azure Credential classes' get_token()
# methods. In the Azure SDK, one passes these credential objects to the various
# SDK clients, which in turn invoke the get_token method on that credential
# object. Depending on the specific Azure Credential class used, some of these
# cache access tokens such as the Azure UsernamePasswordCredential and the
# AzureCliCredential.
#
# When azurerun executes, it creates a thread pool of workers that will
# concurrently execute a "command" across one or more subscriptions using one of
# the Azure SDK clients. If an access token is not in a cache or needs to be
# refreshed at the time azurerun starts, all of the workers will concurrently
# attempt to get a fresh token by making network requests to Azure AD. This is
# wasteful. It would be better if we waited for one worker to complete a call to
# get_token, thus populating any caches, and then letting the rest of the
# workers proceed concurrently.
#
# This decorator will only allow one worker thread to proceed with a get_token()
# call and force the remaining workers to be blocked until that first call has
# completed. After which, the remaining threads can proceed concurrently.
# Because get_token is called with a list of scopes, we ensure threads block
# based on the scope being requested, to make sure the cache contains the right
# access key.
def _wait_once_per_scope(func):
    done = set()
    lock = threading.RLock()

    @functools.wraps(func)
    def wrapper(*scopes, **kwargs):
        scope_key = tuple(scopes)
        with lock:
            if scope_key not in done:
                # Mark it as done even before the function call completes in
                # case it throws an exception. If the call is going to fail, no
                # need to slow the rest of the blocked threads. Fail fast.
                done.add(scope_key)
                return func(*scopes, **kwargs)
        return func(*scopes, **kwargs)

    return wrapper


# pylint: disable=too-few-public-methods


class CredsViaAzureDefault(SessionProvider):
    """A session provider that obtains credentials from a variety of sources.

    Credentials are obtained via environment variables, managed identity on an
    Azure host, shared token cache (Windows only), Azure VSCode, Azure CLI, or
    interactively via the browser. These are tried in order until one succeeds.

    The `authority` argument specifies the Microsoft authority host to use. If none
    is provided, the default is "login.microsoftonline.com".

    For more information, see [Azure SDK
    documentation](https://azuresdkdocs.blob.core.windows.net/$web/python/azure-identity/1.5.0/index.html#defaultazurecredential)
    """

    def __init__(self, authority=None):
        self.creds = DefaultAzureCredential(
            exclude_interactive_browser_credential=False, authority=authority
        )

        # Wrap the credential's get_token method to ensure that only one thread
        # calls get_token with a specific scope. All other threads requesting a
        # token of the same scope will be blocked until the first has completed.
        # It prevents a bunch of unnecessary network requets for authentication.
        self.creds.get_token = _wait_once_per_scope(self.creds.get_token)

    def session(self, _subscription_id):
        # The same credentials are used regardless of the subscription within a
        # tenant, which is why we ignore the subscription here--unlike AWS.
        return self.creds


class CredsViaUsernamePassword(SessionProvider):
    """A session provider that obtains Azure tokens via username & password.

    Credentials are obtained by authenticating with Azure AD using a username
    and password. Access tokens are cached by the underlying MSAL library and
    automatically refreshed as needed.

    The `username` is typically an email address that specifies the user.
    `Password` is the password for the specified username.

    The `tenant_id` argument is optional specifies the tenant of the user.
    Normally, this can be derived from the email address used as the username,
    so it is not required.

    The `authority` argument is optional and specifies the Microsoft authority
    host to use. If none is provided, the default is
    "login.microsoftonline.com".

    For more information, see [Azure SDK
    documentation](https://azuresdkdocs.blob.core.windows.net/$web/python/azure-identity/1.4.0/azure.identity.html#azure.identity.UsernamePasswordCredential)
    """

    def __init__(self, username, password, tenant_id=None, authority=None):
        self.creds = UsernamePasswordCredential(
            DEVELOPER_SIGN_ON_CLIENT_ID,
            username,
            password,
            tenant_id=tenant_id,
            authority=authority,
        )

        # Wrap the credential's get_token method to ensure that only one thread
        # calls get_token with a specific scope. All other threads requesting a
        # token of the same scope will be blocked until the first has completed.
        # Thus pre-filling the MSAL token cache. It prevents a bunch of
        # unnecessary network requets for authentication.
        self.creds.get_token = _wait_once_per_scope(self.creds.get_token)

        # Request a token now as it will validate the user supplied the correct
        # username and password. If we did not catch that here, then each worker
        # would end up failing---possibly locking the user's account.
        #
        # Is using this scope a safe assumption, will all users have access to
        # this scope? I'd really like to validate a person's credential before
        # we let the workers loose, but it's impossible to know what Azure SDK
        # clients will be used by the user, which dictates the scope used.
        self.creds.get_token(ARM_SCOPE)

    def session(self, _subscription_id):
        # The same credentials are used regardless of the subscription within a
        # tenant, which is why we ignore the subscription here--unlike AWS.
        return self.creds
