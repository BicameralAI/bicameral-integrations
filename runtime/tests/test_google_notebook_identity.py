# SPDX-License-Identifier: MIT
from __future__ import annotations

import json

import pytest

from runtime.notebooks.contract import NotebookFailureClass, NotebookProviderError
from runtime.notebooks.google_identity import (
    DRIVE_SOURCE_SCOPE,
    GoogleUserInfoPrincipalResolver,
    NOTEBOOK_OAUTH_SCOPES,
)
from runtime.poll_client import HttpResponse


class RecordingSecretResolver:
    def __init__(self, value: str = "identity-token") -> None:
        self.value = value
        self.calls: list[str] = []

    def resolve(self, connector_id: str) -> str:
        self.calls.append(connector_id)
        return self.value


class RecordingTransport:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.requests: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> HttpResponse:
        self.requests.append((method, url, dict(headers), body))
        return self.response


def _resolver(
    payload: object,
    *,
    status: int = 200,
    token: str = "identity-token",
) -> tuple[GoogleUserInfoPrincipalResolver, RecordingSecretResolver, RecordingTransport]:
    secrets = RecordingSecretResolver(token)
    transport = RecordingTransport(
        HttpResponse(status=status, body=json.dumps(payload).encode("utf-8"))
    )
    resolver = GoogleUserInfoPrincipalResolver(
        secret_resolver=secrets,
        transport=transport,
    )
    return resolver, secrets, transport


def test_scope_bundle_contains_identity_and_notebook_authorization() -> None:
    assert NOTEBOOK_OAUTH_SCOPES == (
        "openid",
        "email",
        "https://www.googleapis.com/auth/discoveryengine.readwrite",
    )
    assert DRIVE_SOURCE_SCOPE == "https://www.googleapis.com/auth/drive.readonly"


def test_resolves_only_verified_google_email() -> None:
    resolver, secrets, transport = _resolver(
        {
            "sub": "google-account-stable-subject",
            "email": "kevin@bicameral-ai.com",
            "email_verified": True,
            "hd": "bicameral-ai.com",
        }
    )

    principal = resolver.resolve_principal()

    assert principal == "kevin@bicameral-ai.com"
    assert secrets.calls == ["gemini_notebook_enterprise"]
    assert len(transport.requests) == 1
    method, url, headers, body = transport.requests[0]
    assert method == "GET"
    assert url == "https://openidconnect.googleapis.com/v1/userinfo"
    assert headers["Authorization"] == "Bearer identity-token"
    assert body is None


@pytest.mark.parametrize(
    "payload",
    [
        {"sub": "subject", "email": "kevin@bicameral-ai.com"},
        {
            "sub": "subject",
            "email": "kevin@bicameral-ai.com",
            "email_verified": False,
        },
        {"sub": "subject", "email_verified": True},
    ],
)
def test_missing_or_unverified_email_fails_closed(payload: object) -> None:
    resolver, _, _ = _resolver(payload)

    with pytest.raises(NotebookProviderError) as exc:
        resolver.resolve_principal()

    assert exc.value.failure_class is NotebookFailureClass.UNAUTHORIZED


def test_missing_google_subject_is_provider_contract_change() -> None:
    resolver, _, _ = _resolver(
        {
            "email": "kevin@bicameral-ai.com",
            "email_verified": True,
        }
    )

    with pytest.raises(NotebookProviderError) as exc:
        resolver.resolve_principal()

    assert exc.value.failure_class is NotebookFailureClass.PROVIDER_CONTRACT_CHANGED


def test_userinfo_unauthorized_does_not_echo_body_or_token() -> None:
    resolver, _, _ = _resolver(
        {"error": "identity-token should not escape"},
        status=401,
    )

    with pytest.raises(NotebookProviderError) as exc:
        resolver.resolve_principal()

    assert exc.value.failure_class is NotebookFailureClass.UNAUTHORIZED
    assert "identity-token" not in str(exc.value)


def test_empty_credential_fails_before_userinfo_request() -> None:
    resolver, secrets, transport = _resolver({}, token="")

    with pytest.raises(NotebookProviderError) as exc:
        resolver.resolve_principal()

    assert exc.value.failure_class is NotebookFailureClass.UNAUTHORIZED
    assert secrets.calls == ["gemini_notebook_enterprise"]
    assert transport.requests == []
