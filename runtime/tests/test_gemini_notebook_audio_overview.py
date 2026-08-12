# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from runtime.notebooks import (
    AudioOverviewRequest,
    GeminiNotebookEnterpriseProvider,
    NotebookAccessScope,
    NotebookFailureClass,
    NotebookProviderError,
    NotebookScopeKind,
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
    def __init__(self, value: str = "provider-token") -> None:
        self.value = value
        self.calls: list[str] = []

    def resolve(self, connector_id: str) -> str:
        self.calls.append(connector_id)
        return self.value


@dataclass
class FixedPrincipalResolver:
    value: str = "kevin@bicameral-ai.com"
    calls: int = 0

    def resolve_principal(self) -> str:
        self.calls += 1
        return self.value


def _provider(
    transport: RecordingTransport,
    *,
    enabled: bool,
) -> tuple[GeminiNotebookEnterpriseProvider, RecordingSecretResolver, FixedPrincipalResolver]:
    secrets = RecordingSecretResolver()
    principals = FixedPrincipalResolver()
    provider = GeminiNotebookEnterpriseProvider(
        project_number="123456789",
        location="global",
        endpoint_location="global",
        secret_resolver=secrets,
        principal_resolver=principals,
        transport=transport,
        audio_overview_enabled=enabled,
    )
    return provider, secrets, principals


def _request() -> AudioOverviewRequest:
    return AudioOverviewRequest(
        client_request_id="req-audio",
        access_scope=NotebookAccessScope(
            NotebookScopeKind.USER,
            "kevin@bicameral-ai.com",
        ),
        source_ids=("src-1", "src-2"),
        episode_focus="Architecture and authority boundaries",
        language_code="en",
    )


def test_audio_overview_defaults_to_unadvertised_and_fails_before_identity_or_secret() -> None:
    transport = RecordingTransport()
    provider, secrets, principals = _provider(transport, enabled=False)

    assert provider.capabilities.create_audio_overview is False
    with pytest.raises(NotebookProviderError) as exc:
        provider.create_audio_overview("nb-123", _request())

    assert exc.value.failure_class is NotebookFailureClass.UNSUPPORTED_OPERATION
    assert principals.calls == 0
    assert secrets.calls == []
    assert transport.requests == []


def test_enabled_audio_overview_uses_documented_generation_options_and_safe_receipt() -> None:
    transport = RecordingTransport(
        HttpResponse(
            status=200,
            body=json.dumps(
                {
                    "audioOverview": {
                        "status": "AUDIO_OVERVIEW_STATUS_IN_PROGRESS",
                        "audioOverviewId": "audio-123",
                        "generationOptions": {},
                        "name": (
                            "projects/123456789/locations/global/notebooks/nb-123/"
                            "audioOverviews/audio-123"
                        ),
                    }
                }
            ).encode("utf-8"),
        )
    )
    provider, secrets, principals = _provider(transport, enabled=True)

    assert provider.capabilities.create_audio_overview is True
    receipt = provider.create_audio_overview("nb-123", _request())

    assert principals.calls == 1
    assert secrets.calls == ["gemini_notebook_enterprise"]
    method, url, headers, raw_body = transport.requests[0]
    assert method == "POST"
    assert url.endswith("/notebooks/nb-123/audioOverviews")
    assert headers["Authorization"] == "Bearer provider-token"
    assert json.loads(raw_body or b"{}") == {
        "generationOptions": {
            "sourceIds": [{"id": "src-1"}, {"id": "src-2"}],
            "episodeFocus": "Architecture and authority boundaries",
            "languageCode": "en",
        }
    }
    assert receipt.status == "AUDIO_OVERVIEW_STATUS_IN_PROGRESS"
    assert receipt.audio_overview_id == "audio-123"
    assert receipt.notebook_id == "nb-123"
    assert receipt.effective_principal_ref == "kevin@bicameral-ai.com"
    assert receipt.source_ids == ("src-1", "src-2")
    assert "provider-token" not in repr(receipt)


def test_audio_overview_can_omit_source_ids_to_use_all_notebook_sources() -> None:
    transport = RecordingTransport(
        HttpResponse(
            status=200,
            body=json.dumps(
                {
                    "audioOverview": {
                        "status": "AUDIO_OVERVIEW_STATUS_IN_PROGRESS",
                        "audioOverviewId": "audio-all",
                        "name": (
                            "projects/123456789/locations/global/notebooks/nb-123/"
                            "audioOverviews/audio-all"
                        ),
                    }
                }
            ).encode("utf-8"),
        )
    )
    provider, _, _ = _provider(transport, enabled=True)
    request = AudioOverviewRequest(
        client_request_id="req-all",
        access_scope=NotebookAccessScope(
            NotebookScopeKind.USER,
            "kevin@bicameral-ai.com",
        ),
    )

    receipt = provider.create_audio_overview("nb-123", request)

    assert json.loads(transport.requests[0][3] or b"{}") == {"generationOptions": {}}
    assert receipt.source_ids == ()


def test_audio_overview_existing_resource_maps_to_provider_precondition_failure() -> None:
    transport = RecordingTransport(HttpResponse(status=409, body=b'{"error":"already exists"}'))
    provider, _, _ = _provider(transport, enabled=True)

    with pytest.raises(NotebookProviderError) as exc:
        provider.create_audio_overview("nb-123", _request())

    assert exc.value.failure_class is NotebookFailureClass.PROVIDER_PRECONDITION_FAILED
    assert "already exists" not in str(exc.value)


def test_audio_overview_missing_resource_is_contract_change() -> None:
    transport = RecordingTransport(HttpResponse(status=200, body=b"{}"))
    provider, _, _ = _provider(transport, enabled=True)

    with pytest.raises(NotebookProviderError) as exc:
        provider.create_audio_overview("nb-123", _request())

    assert exc.value.failure_class is NotebookFailureClass.PROVIDER_CONTRACT_CHANGED
