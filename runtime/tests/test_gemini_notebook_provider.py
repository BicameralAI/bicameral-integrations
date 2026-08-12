# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from runtime.notebooks import (
    GeminiNotebookEnterpriseProvider,
    GoogleDriveSourceRequest,
    NotebookAccessScope,
    NotebookCreateRequest,
    NotebookFailureClass,
    NotebookProviderError,
    NotebookScopeKind,
    ProviderApiMaturity,
    TextSourceRequest,
    WebSourceRequest,
)
from runtime.poll_client import HttpResponse


class RecordingTransport:
    def __init__(self, *responses: HttpResponse) -> None:
        self.responses = list(responses)
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
        if not self.responses:
            raise AssertionError("unexpected provider request")
        return self.responses.pop(0)


class RecordingSecretResolver:
    def __init__(self, value: str) -> None:
        self.value = value
        self.calls: list[str] = []

    def resolve(self, connector_id: str) -> str:
        self.calls.append(connector_id)
        return self.value


@dataclass
class FixedPrincipalResolver:
    value: str
    calls: int = 0

    def resolve_principal(self) -> str:
        self.calls += 1
        return self.value


def _response(payload: object, status: int = 200) -> HttpResponse:
    return HttpResponse(status=status, body=json.dumps(payload).encode("utf-8"))


def _provider(
    transport: RecordingTransport,
    *,
    secret: str = "provider-token",
    effective_principal: str = "kevin@bicameral-ai.com",
) -> tuple[
    GeminiNotebookEnterpriseProvider,
    RecordingSecretResolver,
    FixedPrincipalResolver,
]:
    secrets = RecordingSecretResolver(secret)
    principals = FixedPrincipalResolver(effective_principal)
    provider = GeminiNotebookEnterpriseProvider(
        project_number="123456789",
        location="global",
        endpoint_location="global",
        secret_resolver=secrets,
        principal_resolver=principals,
        transport=transport,
    )
    return provider, secrets, principals


def _user_scope(principal: str = "kevin@bicameral-ai.com") -> NotebookAccessScope:
    return NotebookAccessScope(NotebookScopeKind.USER, principal)


def test_capabilities_advertise_only_proven_v1_surface() -> None:
    provider, _, _ = _provider(RecordingTransport())

    assert provider.capabilities.api_maturity is ProviderApiMaturity.PREVIEW
    assert provider.capabilities.supported_scope_kinds == frozenset({NotebookScopeKind.USER})
    assert provider.capabilities.create_notebook is True
    assert provider.capabilities.get_notebook is True
    assert provider.capabilities.add_source is True
    assert provider.capabilities.create_audio_overview is False
    assert provider.capabilities.notebook_chat is False


def test_create_notebook_uses_official_rest_shape_and_preserves_provider_facts() -> None:
    transport = RecordingTransport(
        _response(
            {
                "name": "projects/123456789/locations/global/notebooks/nb-123",
                "notebookId": "nb-123",
                "title": "Bicameral POC",
                "metadata": {
                    "userRole": "PROJECT_ROLE_OWNER",
                    "isShared": False,
                    "isShareable": True,
                },
            }
        )
    )
    provider, secrets, principals = _provider(transport)

    receipt = provider.create_notebook(
        NotebookCreateRequest(
            client_request_id="req-1",
            access_scope=_user_scope(),
            title="Bicameral POC",
        )
    )

    assert principals.calls == 1
    assert secrets.calls == ["gemini_notebook_enterprise"]
    assert len(transport.requests) == 1
    method, url, headers, raw_body = transport.requests[0]
    assert method == "POST"
    assert url == (
        "https://global-discoveryengine.googleapis.com/v1alpha/"
        "projects/123456789/locations/global/notebooks"
    )
    assert headers["Authorization"] == "Bearer provider-token"
    assert json.loads(raw_body or b"{}") == {"title": "Bicameral POC"}
    assert receipt.notebook_id == "nb-123"
    assert receipt.effective_principal_ref == "kevin@bicameral-ai.com"
    assert receipt.effective_provider_role == "PROJECT_ROLE_OWNER"
    assert receipt.is_shared is False
    assert receipt.is_shareable is True
    assert receipt.source_receipts == ()


@pytest.mark.parametrize("kind", [NotebookScopeKind.GROUP, NotebookScopeKind.WORKSPACE])
def test_unsupported_scope_fails_before_secret_resolution_or_mutation(kind: NotebookScopeKind) -> None:
    transport = RecordingTransport()
    provider, secrets, principals = _provider(transport)

    with pytest.raises(NotebookProviderError) as exc:
        provider.create_notebook(
            NotebookCreateRequest(
                client_request_id="req-unsupported",
                access_scope=NotebookAccessScope(kind, "team@example.com"),
                title="must not exist",
            )
        )

    assert exc.value.failure_class is NotebookFailureClass.UNSUPPORTED_SCOPE
    assert principals.calls == 0
    assert secrets.calls == []
    assert transport.requests == []


def test_principal_mismatch_fails_before_secret_resolution_or_mutation() -> None:
    transport = RecordingTransport()
    provider, secrets, principals = _provider(
        transport,
        effective_principal="other@bicameral-ai.com",
    )

    with pytest.raises(NotebookProviderError) as exc:
        provider.create_notebook(
            NotebookCreateRequest(
                client_request_id="req-mismatch",
                access_scope=_user_scope(),
                title="must not exist",
            )
        )

    assert exc.value.failure_class is NotebookFailureClass.PRINCIPAL_MISMATCH
    assert principals.calls == 1
    assert secrets.calls == []
    assert transport.requests == []


def test_get_notebook_reconciles_exact_resource() -> None:
    transport = RecordingTransport(
        _response(
            {
                "name": "projects/123456789/locations/global/notebooks/nb-123",
                "notebookId": "nb-123",
                "title": "Bicameral POC",
                "metadata": {"userRole": "PROJECT_ROLE_OWNER"},
            }
        )
    )
    provider, _, _ = _provider(transport)

    receipt = provider.get_notebook(
        "nb-123",
        access_scope=_user_scope(),
        client_request_id="req-get",
    )

    assert transport.requests[0][0] == "GET"
    assert transport.requests[0][1].endswith("/notebooks/nb-123")
    assert transport.requests[0][3] is None
    assert receipt.operation == "get_notebook"
    assert receipt.notebook_id == "nb-123"


def test_add_sources_uses_user_contents_and_receipt_excludes_raw_content() -> None:
    transport = RecordingTransport(
        _response(
            {
                "sources": [
                    {
                        "sourceId": {"id": "src-text"},
                        "title": "Decision note",
                        "settings": {"status": "SOURCE_STATUS_COMPLETE"},
                        "name": (
                            "projects/123456789/locations/global/notebooks/nb-123/"
                            "sources/src-text"
                        ),
                    },
                    {
                        "sourceId": {"id": "src-web"},
                        "title": "Factory docs",
                        "settings": {"status": "SOURCE_STATUS_COMPLETE"},
                        "name": (
                            "projects/123456789/locations/global/notebooks/nb-123/"
                            "sources/src-web"
                        ),
                    },
                    {
                        "sourceId": {"id": "src-drive"},
                        "title": "Design doc",
                        "settings": {"status": "SOURCE_STATUS_COMPLETE"},
                        "name": (
                            "projects/123456789/locations/global/notebooks/nb-123/"
                            "sources/src-drive"
                        ),
                    },
                ]
            }
        )
    )
    provider, _, _ = _provider(transport)
    secret_text = "source body that must not enter the receipt"
    sources = [
        TextSourceRequest(
            authoritative_ref="decision://123",
            source_name="Decision note",
            content=secret_text,
        ),
        WebSourceRequest(
            authoritative_ref="https://factory.example/docs",
            source_name="Factory docs",
            url="https://factory.example/docs",
        ),
        GoogleDriveSourceRequest(
            authoritative_ref="gdrive://1AbCdEfGhIjKlMnOpQrStUvWxYz",
            source_name="Design doc",
            document_id="1AbCdEfGhIjKlMnOpQrStUvWxYz",
            mime_type="application/vnd.google-apps.document",
        ),
    ]

    receipt = provider.add_sources(
        "nb-123",
        sources,
        access_scope=_user_scope(),
        client_request_id="req-sources",
    )

    method, url, _, raw_body = transport.requests[0]
    assert method == "POST"
    assert url.endswith("/notebooks/nb-123/sources:batchCreate")
    assert json.loads(raw_body or b"{}") == {
        "userContents": [
            {"textContent": {"sourceName": "Decision note", "content": secret_text}},
            {
                "webContent": {
                    "url": "https://factory.example/docs",
                    "sourceName": "Factory docs",
                }
            },
            {
                "googleDriveContent": {
                    "documentId": "1AbCdEfGhIjKlMnOpQrStUvWxYz",
                    "mimeType": "application/vnd.google-apps.document",
                    "sourceName": "Design doc",
                }
            },
        ]
    }
    assert [item.authoritative_ref for item in receipt.source_receipts] == [
        "decision://123",
        "https://factory.example/docs",
        "gdrive://1AbCdEfGhIjKlMnOpQrStUvWxYz",
    ]
    assert secret_text not in repr(receipt)


def test_provider_error_does_not_echo_response_body_or_token() -> None:
    body = b'{"error":"provider-token should not escape"}'
    transport = RecordingTransport(HttpResponse(status=403, body=body))
    provider, _, _ = _provider(transport)

    with pytest.raises(NotebookProviderError) as exc:
        provider.get_notebook(
            "nb-123",
            access_scope=_user_scope(),
            client_request_id="req-denied",
        )

    assert exc.value.failure_class is NotebookFailureClass.UNAUTHORIZED
    assert "provider-token" not in str(exc.value)
    assert "provider-token" not in exc.value.reason


def test_malformed_provider_json_is_contract_change() -> None:
    transport = RecordingTransport(HttpResponse(status=200, body=b"not-json"))
    provider, _, _ = _provider(transport)

    with pytest.raises(NotebookProviderError) as exc:
        provider.get_notebook(
            "nb-123",
            access_scope=_user_scope(),
            client_request_id="req-bad-json",
        )

    assert exc.value.failure_class is NotebookFailureClass.PROVIDER_CONTRACT_CHANGED


def test_drive_source_rejects_unproven_mime_type_before_provider_mutation() -> None:
    transport = RecordingTransport()
    provider, secrets, _ = _provider(transport)

    with pytest.raises(ValueError, match="mime_type is unsupported"):
        provider.add_sources(
            "nb-123",
            [
                GoogleDriveSourceRequest(
                    authoritative_ref="gdrive://1AbCdEfGhIjKlMnOpQrStUvWxYz",
                    source_name="Spreadsheet",
                    document_id="1AbCdEfGhIjKlMnOpQrStUvWxYz",
                    mime_type="application/vnd.google-apps.spreadsheet",
                )
            ],
            access_scope=_user_scope(),
            client_request_id="req-drive",
        )

    # Principal resolution is allowed before local source validation, but no
    # credential is resolved and no external mutation occurs.
    assert secrets.calls == []
    assert transport.requests == []
