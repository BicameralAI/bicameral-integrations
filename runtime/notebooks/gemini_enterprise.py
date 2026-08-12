# SPDX-License-Identifier: MIT
"""Official-API Gemini Notebook Enterprise provider.

This adapter uses only the documented Discovery Engine ``v1alpha`` Notebook
Enterprise REST surface. It deliberately does not emulate browser-only features,
consume browser cookies, or treat provider output as canonical Bicameral state.
"""

from __future__ import annotations

import json
import re
from typing import Any

from runtime.poll_auth import BearerAuth, PollError
from runtime.poll_client import HttpTransport, UrllibTransport
from runtime.secrets import SecretResolver

from .contract import (
    AudioOverviewReceipt,
    AudioOverviewRequest,
    GoogleDriveSourceRequest,
    NotebookAccessScope,
    NotebookCreateRequest,
    NotebookFailureClass,
    NotebookProviderCapabilities,
    NotebookProviderError,
    NotebookReceipt,
    NotebookScopeKind,
    NotebookSourceReceipt,
    NotebookSourceRequest,
    PrincipalResolver,
    ProviderApiMaturity,
    TextSourceRequest,
    WebSourceRequest,
)

_PROVIDER = "gemini_notebook_enterprise"
_API_VERSION = "v1alpha"
_ALLOWED_ENDPOINT_LOCATIONS = frozenset({"global", "us", "eu"})
_RESOURCE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._~-]{1,256}$")
_PROJECT_NUMBER_RE = re.compile(r"^[0-9]{1,32}$")
_DRIVE_DOCUMENT_RE = re.compile(r"^[A-Za-z0-9_-]{10,256}$")
_ALLOWED_DRIVE_MIME_TYPES = frozenset(
    {
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.presentation",
    }
)


class GeminiNotebookEnterpriseProvider:
    """Gemini Notebook Enterprise implementation of the notebook provider contract.

    ``PrincipalResolver`` and ``SecretResolver`` are injected operator-boundary
    seams. Principal comparison happens before credential resolution and before
    any provider mutation.

    Audio Overview is an explicit deployment capability because the Google API is
    Preview / Pre-GA and project availability can differ. The default is off.
    """

    def __init__(
        self,
        *,
        project_number: str,
        location: str,
        endpoint_location: str,
        secret_resolver: SecretResolver,
        principal_resolver: PrincipalResolver,
        credential_key: str = _PROVIDER,
        transport: HttpTransport | None = None,
        audio_overview_enabled: bool = False,
    ) -> None:
        if not _PROJECT_NUMBER_RE.fullmatch(project_number):
            raise ValueError("project_number must contain only decimal digits")
        self._validate_segment("location", location)
        if endpoint_location not in _ALLOWED_ENDPOINT_LOCATIONS:
            raise ValueError("endpoint_location must be one of: global, us, eu")
        if not credential_key or any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in credential_key):
            raise ValueError("credential_key is invalid")

        self._project_number = project_number
        self._location = location
        self._endpoint_location = endpoint_location
        self._secret_resolver = secret_resolver
        self._principal_resolver = principal_resolver
        self._credential_key = credential_key
        self._transport = transport or UrllibTransport()
        self._audio_overview_enabled = audio_overview_enabled

    @property
    def capabilities(self) -> NotebookProviderCapabilities:
        return NotebookProviderCapabilities(
            provider=_PROVIDER,
            api_maturity=ProviderApiMaturity.PREVIEW,
            supported_scope_kinds=frozenset({NotebookScopeKind.USER}),
            create_notebook=True,
            get_notebook=True,
            add_source=True,
            create_audio_overview=self._audio_overview_enabled,
            notebook_chat=False,
        )

    @property
    def _parent(self) -> str:
        return f"projects/{self._project_number}/locations/{self._location}"

    @property
    def _base_url(self) -> str:
        host = f"{self._endpoint_location}-discoveryengine.googleapis.com"
        return f"https://{host}/{_API_VERSION}/{self._parent}"

    @staticmethod
    def _validate_segment(label: str, value: str) -> str:
        if not _RESOURCE_SEGMENT_RE.fullmatch(value):
            raise ValueError(f"{label} has an invalid provider-resource shape")
        return value

    @staticmethod
    def _required_text(label: str, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{label} must not be empty")
        return stripped

    def _authorize(self, scope: NotebookAccessScope) -> str:
        if scope.kind not in self.capabilities.supported_scope_kinds:
            raise NotebookProviderError(
                NotebookFailureClass.UNSUPPORTED_SCOPE,
                reason=f"scope:{scope.kind.value}",
            )
        requested = self._required_text("principal_ref", scope.principal_ref)
        effective = self._principal_resolver.resolve_principal().strip()
        if not effective:
            raise NotebookProviderError(
                NotebookFailureClass.UNAUTHORIZED,
                reason="effective_principal_unavailable",
            )
        if effective.casefold() != requested.casefold():
            raise NotebookProviderError(
                NotebookFailureClass.PRINCIPAL_MISMATCH,
                reason="requested_principal_does_not_match_effective_principal",
            )
        return effective

    def _headers(self) -> dict[str, str]:
        token = self._secret_resolver.resolve(self._credential_key)
        if not token:
            raise NotebookProviderError(
                NotebookFailureClass.UNAUTHORIZED,
                reason="provider_credential_unavailable",
            )
        try:
            return BearerAuth(token, extra={"Content-Type": "application/json"}).headers()
        except PollError:
            raise NotebookProviderError(
                NotebookFailureClass.UNAUTHORIZED,
                reason="provider_credential_invalid",
            ) from None

    @staticmethod
    def _failure_for_status(status: int) -> NotebookFailureClass:
        if status in {401, 403}:
            return NotebookFailureClass.UNAUTHORIZED
        if status == 404:
            return NotebookFailureClass.PROVIDER_NOT_FOUND
        if status in {400, 409, 412, 422}:
            return NotebookFailureClass.PROVIDER_PRECONDITION_FAILED
        if status == 429:
            return NotebookFailureClass.PROVIDER_RATE_LIMITED
        if status >= 500 or status == 0:
            return NotebookFailureClass.PROVIDER_TRANSIENT_FAILURE
        return NotebookFailureClass.PROVIDER_CONTRACT_CHANGED

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
        try:
            response = self._transport.request(
                method,
                url,
                headers=self._headers(),
                body=encoded,
            )
        except PollError:
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_TRANSIENT_FAILURE,
                reason="transport_failure",
            ) from None

        if not 200 <= response.status < 300:
            raise NotebookProviderError(
                self._failure_for_status(response.status),
                status=response.status,
                reason="provider_http_failure",
            )
        try:
            parsed = json.loads(response.body)
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                status=response.status,
                reason="provider_response_not_json",
            ) from None
        if not isinstance(parsed, dict):
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                status=response.status,
                reason="provider_response_not_object",
            )
        return parsed

    @staticmethod
    def _str(value: object) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _bool(value: object) -> bool | None:
        return value if isinstance(value, bool) else None

    @classmethod
    def _notebook_id(cls, payload: dict[str, Any]) -> str | None:
        direct = cls._str(payload.get("notebookId"))
        if direct:
            return direct
        name = cls._str(payload.get("name"))
        if not name:
            return None
        last = name.rsplit("/", 1)[-1]
        return last if _RESOURCE_SEGMENT_RE.fullmatch(last) else None

    def _receipt(
        self,
        payload: dict[str, Any],
        *,
        client_request_id: str,
        operation: str,
        effective_principal: str,
        scope: NotebookAccessScope,
        source_receipts: tuple[NotebookSourceReceipt, ...] = (),
        notebook_id_fallback: str | None = None,
    ) -> NotebookReceipt:
        metadata = payload.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        notebook_id = self._notebook_id(payload) or notebook_id_fallback
        return NotebookReceipt(
            provider=_PROVIDER,
            provider_api_maturity=ProviderApiMaturity.PREVIEW,
            client_request_id=client_request_id,
            operation=operation,
            status="succeeded",
            notebook_id=notebook_id,
            provider_resource_name=self._str(payload.get("name")),
            title=self._str(payload.get("title")),
            project_ref=f"projects/{self._project_number}",
            location=self._location,
            scope_kind=scope.kind,
            effective_principal_ref=effective_principal,
            effective_provider_role=self._str(metadata.get("userRole")),
            is_shared=self._bool(metadata.get("isShared")),
            is_shareable=self._bool(metadata.get("isShareable")),
            source_receipts=source_receipts,
        )

    def create_notebook(self, request: NotebookCreateRequest) -> NotebookReceipt:
        client_request_id = self._required_text("client_request_id", request.client_request_id)
        title = self._required_text("title", request.title)
        effective = self._authorize(request.access_scope)
        payload = self._request_json(
            "POST",
            f"{self._base_url}/notebooks",
            body={"title": title},
        )
        if not self._notebook_id(payload):
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                reason="create_response_missing_notebook_identity",
            )
        return self._receipt(
            payload,
            client_request_id=client_request_id,
            operation="create_notebook",
            effective_principal=effective,
            scope=request.access_scope,
        )

    def get_notebook(
        self,
        notebook_id: str,
        *,
        access_scope: NotebookAccessScope,
        client_request_id: str,
    ) -> NotebookReceipt:
        clean_id = self._validate_segment("notebook_id", notebook_id)
        client_request_id = self._required_text("client_request_id", client_request_id)
        effective = self._authorize(access_scope)
        payload = self._request_json(
            "GET",
            f"{self._base_url}/notebooks/{clean_id}",
        )
        return self._receipt(
            payload,
            client_request_id=client_request_id,
            operation="get_notebook",
            effective_principal=effective,
            scope=access_scope,
            notebook_id_fallback=clean_id,
        )

    @staticmethod
    def _source_content(source: NotebookSourceRequest) -> dict[str, Any]:
        if isinstance(source, TextSourceRequest):
            if not source.content:
                raise ValueError("text source content must not be empty")
            return {
                "textContent": {
                    "sourceName": GeminiNotebookEnterpriseProvider._required_text(
                        "source_name", source.source_name
                    ),
                    "content": source.content,
                }
            }
        if isinstance(source, WebSourceRequest):
            url = GeminiNotebookEnterpriseProvider._required_text("url", source.url)
            if not url.startswith(("https://", "http://")):
                raise ValueError("web source URL must use http or https")
            return {
                "webContent": {
                    "url": url,
                    "sourceName": GeminiNotebookEnterpriseProvider._required_text(
                        "source_name", source.source_name
                    ),
                }
            }
        if isinstance(source, GoogleDriveSourceRequest):
            if not _DRIVE_DOCUMENT_RE.fullmatch(source.document_id):
                raise ValueError("Google Drive document_id has an invalid shape")
            if source.mime_type not in _ALLOWED_DRIVE_MIME_TYPES:
                raise ValueError("Google Drive source mime_type is unsupported")
            return {
                "googleDriveContent": {
                    "documentId": source.document_id,
                    "mimeType": source.mime_type,
                    "sourceName": GeminiNotebookEnterpriseProvider._required_text(
                        "source_name", source.source_name
                    ),
                }
            }
        raise NotebookProviderError(
            NotebookFailureClass.UNSUPPORTED_OPERATION,
            reason="source_type_not_supported",
        )

    @staticmethod
    def _source_receipt(
        source: NotebookSourceRequest,
        payload: dict[str, Any],
    ) -> NotebookSourceReceipt:
        raw_source_id = payload.get("sourceId")
        source_id = raw_source_id.get("id") if isinstance(raw_source_id, dict) else None
        name = payload.get("name")
        settings = payload.get("settings")
        status = settings.get("status") if isinstance(settings, dict) else None
        if not isinstance(source_id, str) or not source_id or not isinstance(name, str) or not name:
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                reason="source_response_missing_identity",
            )
        return NotebookSourceReceipt(
            authoritative_ref=source.authoritative_ref,
            source_id=source_id,
            provider_resource_name=name,
            title=payload.get("title") if isinstance(payload.get("title"), str) else None,
            status=status if isinstance(status, str) else None,
        )

    def add_sources(
        self,
        notebook_id: str,
        sources: list[NotebookSourceRequest],
        *,
        access_scope: NotebookAccessScope,
        client_request_id: str,
    ) -> NotebookReceipt:
        clean_id = self._validate_segment("notebook_id", notebook_id)
        client_request_id = self._required_text("client_request_id", client_request_id)
        if not sources:
            raise ValueError("sources must not be empty")
        for source in sources:
            self._required_text("authoritative_ref", source.authoritative_ref)

        effective = self._authorize(access_scope)
        payload = self._request_json(
            "POST",
            f"{self._base_url}/notebooks/{clean_id}/sources:batchCreate",
            body={"userContents": [self._source_content(source) for source in sources]},
        )
        raw_sources = payload.get("sources")
        if not isinstance(raw_sources, list) or len(raw_sources) != len(sources):
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                reason="source_response_count_mismatch",
            )
        receipts: list[NotebookSourceReceipt] = []
        for source, raw in zip(sources, raw_sources, strict=True):
            if not isinstance(raw, dict):
                raise NotebookProviderError(
                    NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                    reason="source_response_not_object",
                )
            receipts.append(self._source_receipt(source, raw))

        # Source batchCreate returns source objects, not the notebook itself. Keep
        # the exact notebook identity supplied by the authorized caller and avoid
        # inventing provider role/share facts that were not returned by this call.
        return NotebookReceipt(
            provider=_PROVIDER,
            provider_api_maturity=ProviderApiMaturity.PREVIEW,
            client_request_id=client_request_id,
            operation="add_sources",
            status="succeeded",
            notebook_id=clean_id,
            provider_resource_name=f"{self._parent}/notebooks/{clean_id}",
            title=None,
            project_ref=f"projects/{self._project_number}",
            location=self._location,
            scope_kind=access_scope.kind,
            effective_principal_ref=effective,
            effective_provider_role=None,
            is_shared=None,
            is_shareable=None,
            source_receipts=tuple(receipts),
        )

    def create_audio_overview(
        self,
        notebook_id: str,
        request: AudioOverviewRequest,
    ) -> AudioOverviewReceipt:
        if not self._audio_overview_enabled:
            raise NotebookProviderError(
                NotebookFailureClass.UNSUPPORTED_OPERATION,
                reason="audio_overview_not_enabled",
            )

        clean_id = self._validate_segment("notebook_id", notebook_id)
        client_request_id = self._required_text("client_request_id", request.client_request_id)
        source_ids = tuple(self._validate_segment("source_id", source_id) for source_id in request.source_ids)
        generation_options: dict[str, Any] = {}
        if source_ids:
            generation_options["sourceIds"] = [{"id": source_id} for source_id in source_ids]
        if request.episode_focus is not None:
            generation_options["episodeFocus"] = self._required_text(
                "episode_focus", request.episode_focus
            )
        if request.language_code is not None:
            generation_options["languageCode"] = self._required_text(
                "language_code", request.language_code
            )

        effective = self._authorize(request.access_scope)
        payload = self._request_json(
            "POST",
            f"{self._base_url}/notebooks/{clean_id}/audioOverviews",
            body={"generationOptions": generation_options},
        )
        raw_overview = payload.get("audioOverview")
        if not isinstance(raw_overview, dict):
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                reason="audio_overview_response_missing_resource",
            )
        audio_id = self._str(raw_overview.get("audioOverviewId"))
        name = self._str(raw_overview.get("name"))
        status = self._str(raw_overview.get("status"))
        if not audio_id or not name or not status:
            raise NotebookProviderError(
                NotebookFailureClass.PROVIDER_CONTRACT_CHANGED,
                reason="audio_overview_response_missing_identity_or_status",
            )

        return AudioOverviewReceipt(
            provider=_PROVIDER,
            provider_api_maturity=ProviderApiMaturity.PREVIEW,
            client_request_id=client_request_id,
            status=status,
            notebook_id=clean_id,
            audio_overview_id=audio_id,
            provider_resource_name=name,
            project_ref=f"projects/{self._project_number}",
            location=self._location,
            scope_kind=request.access_scope.kind,
            effective_principal_ref=effective,
            source_ids=source_ids,
        )
