#
# Copyright 2019 FMR LLC <opensource@fidelity.com>
#
# SPDX-License-Identifier: MIT
#
"""Obtain CSP sessions and credentials.

## Overview

This module provides a `SessionProvider` interface to obtain credentials for a
Cloud Service Provider (CSP). Regardless of the mechanism, the session provider
is responsible for returning a session that contains the credentials for a
requested account. Credentials constitute different structures based on the SDK
of the given CSP.

`awsrun.session.aws`
:  Credentials obtained from AWS are Boto3 session objects that can be used to
obtain Boto3 clients and resources.

`awsrun.session.azure`
:  Credentials obtained from Azure are the new-style azure.core that can be used
as arguments to the various Azure clients.
"""


class SessionProvider:
    """A session provider is used to obtain sessions for accounts.

    This is an abstract base class and cannot be instantiated directly.
    """

    def session(self, acct_id):
        """Returns a session with credentials for the requested account.

        The `acct_id` is a string representing an account within a CSP. The
        returned session object is ready to use and loaded with the requested
        credentials.
        """
        raise NotImplementedError
