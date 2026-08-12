# SPDX-License-Identifier: MIT
"""Google user-identity resolution for Notebook Enterprise operations.

Notebook mutations must be bound to the effective Google user, not a caller-
supplied email string. This resolver uses Google's documented OpenID Connect
UserInfo endpoint with the same operator-owned access-token resolver used by the
provider. Tokens and raw UserInfo payloads never leave this boundary.
"""

from __future__ import annotations

import json

from runtime.poll_auth import BearerAuth, PollError
from runtime.poll_client import HttpTransport, UrllibTransport
from runtime.secrets import SecretResolver

from .contract import NotebookFailureClass, NotebookProviderError

_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_MAX_USERINFO_RESPONSE = 256 * 1024

# Minimum consent needed for identity-bound Notebook Enterprise REST operations.
# Google Drive-backed notebook sources additionally need DRIVE_SOURCE_SCOPE.
NOTEBOOK_OAUTH_SCOPES = (
    "openid",
    "email",
    "https://www.googleapis.com/auth/discoveryengine.readwrite",
)
DRIVE_SOURCE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


class GoogleUserInfoPrincipalResolver:
    """Resolve a verified Google email from the OIDC UserInfo endpoint.

    ``sub`` is Google's durable account identifier, but the cross-repo V1
    contract currently binds ``principal_ref`` to the operator-visible account
    email. We therefore require a verified email and return it for exact scope
    matching. Future durable identity records should retain ``sub`` separately
    rather than treating email as an immutable account key.
    """

    def __init__(
        self,
        *,
        secret_resolver: SecretResolver,
        credential_key: str = "gemini_notebook_enterprise",
        transport: HttpTransport | None = None,
    ) -> None:
        self._secret_resolver = secret_resolver
        self._credential_key = credential_key
        self._transport = transport or UrllibTransport()

    def resolve_principal(self) -> str:
        token = self._secret_resolver.resolve(self._credential_key)
        if not token:
            raise NotebookProviderError(
                NotebookFailureClass.UNAUTHORIZED,
                reason="provider_credential_unavailable_for_identity",
            )
        try:
            headers = BearerAuth(token).headers()
        except PollError:
            raise NotebookProviderError(
                NotebookFailureClass.UNAUTHORIZED,
                reason="provider_credential_invalid_for_identity",
            ) from None

        try:
            response = self._transport.request(
                "GET",
                _GOOGLE_USERINFO_URL,
                headers=headers,
            )
        except PollError:
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_TRANSIENT_FAILURE,
                reason="identity_transport_failure",
            ) from None

        if response.status in {401, 403}:
            raise NotebookProviderError(
                NotebookFailureClass.UNAUTHORIZED,
                status=response.status,
                reason="identity_lookup_unauthorized",
            )
        if response.status == 429 or response.status >= 500:
            failure = (
                NotebookFailureClass.PROVIDER_RATE_LIMITED
                if response.status == 429
                else NotebookFailureClass.PROVIDER_TRANSIENT_FAILURE
            )
            raise NotebookProviderError(
                failure,
                status=response.status,
                reason="identity_lookup_provider_failure",
            )
        if response.status != 200:
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                status=response.status,
                reason="identity_lookup_unexpected_status",
            )
        if len(response.body) > _MAX_USERINFO_RESPONSE:
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                reason="identity_lookup_oversized_response",
            )

        try:
            payload = json.loads(response.body)
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                reason="identity_lookup_invalid_json",
            ) from None
        if not isinstance(payload, dict):
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                reason="identity_lookup_not_object",
            )

        subject = payload.get("sub")
        email = payload.get("email")
        verified = payload.get("email_verified")
        if not isinstance(subject, str) or not subject:
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                reason="identity_lookup_missing_subject",
            )
        if not isinstance(email, str) or not email or verified is not True:
            raise NotebookProviderError(
                NotebookFailureClass.UNAUTHORIZED,
                reason="identity_lookup_email_unverified_or_missing",
            )
        if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in email):
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                reason="identity_lookup_invalid_email",
            )
        return email


__all__ = [
    "DRIVE_SOURCE_SCOPE",
    "GoogleUserInfoPrincipalResolver",
    "NOTEBOOK_OAUTH_SCOPES",
]
