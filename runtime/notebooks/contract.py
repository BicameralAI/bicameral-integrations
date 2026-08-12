# SPDX-License-Identifier: MIT
"""Provider-neutral contract for governed external notebook/reasoning surfaces.

Factory ADR-0004 owns the cross-repository authority rule: a provider notebook is
an explicitly scoped external processing surface, not canonical Bicameral truth.
This module carries only execution-shape facts. It grants no permission and owns
no Product/Decision admission behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class NotebookScopeKind(str, Enum):
    """Reserved access-scope vocabulary.

    A provider advertises the subset it actually supports. Reserving ``group``
    and ``workspace`` here does not make either executable.
    """

    USER = "user"
    GROUP = "group"
    WORKSPACE = "workspace"


class ProviderApiMaturity(str, Enum):
    STABLE = "stable"
    PREVIEW = "preview"
    EXPERIMENTAL = "experimental"


class NotebookFailureClass(str, Enum):
    UNAUTHORIZED = "unauthorized"
    PRINCIPAL_MISMATCH = "principal_mismatch"
    UNSUPPORTED_SCOPE = "unsupported_scope"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    PROVIDER_PRECONDITION_FAILED = "provider_precondition_failed"
    PROVIDER_NOT_FOUND = "provider_not_found"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_TRANSIENT_FAILURE = "provider_transient_failure"
    PROVIDER_CONTRACT_CHANGED = "provider_contract_changed"


@dataclass(frozen=True)
class NotebookAccessScope:
    kind: NotebookScopeKind
    principal_ref: str


@dataclass(frozen=True)
class NotebookProviderCapabilities:
    provider: str
    api_maturity: ProviderApiMaturity
    supported_scope_kinds: frozenset[NotebookScopeKind]
    create_notebook: bool
    get_notebook: bool
    add_source: bool
    create_audio_overview: bool
    notebook_chat: bool = False


@dataclass(frozen=True)
class NotebookCreateRequest:
    client_request_id: str
    access_scope: NotebookAccessScope
    title: str


@dataclass(frozen=True)
class AudioOverviewRequest:
    client_request_id: str
    access_scope: NotebookAccessScope
    source_ids: tuple[str, ...] = ()
    episode_focus: str | None = None
    language_code: str | None = None


@dataclass(frozen=True)
class TextSourceRequest:
    authoritative_ref: str
    source_name: str
    content: str


@dataclass(frozen=True)
class WebSourceRequest:
    authoritative_ref: str
    source_name: str
    url: str


@dataclass(frozen=True)
class GoogleDriveSourceRequest:
    authoritative_ref: str
    source_name: str
    document_id: str
    mime_type: str


NotebookSourceRequest = TextSourceRequest | WebSourceRequest | GoogleDriveSourceRequest


@dataclass(frozen=True)
class NotebookSourceReceipt:
    authoritative_ref: str
    source_id: str
    provider_resource_name: str
    title: str | None
    status: str | None


@dataclass(frozen=True)
class NotebookReceipt:
    provider: str
    provider_api_maturity: ProviderApiMaturity
    client_request_id: str
    operation: str
    status: str
    notebook_id: str | None
    provider_resource_name: str | None
    title: str | None
    project_ref: str
    location: str
    scope_kind: NotebookScopeKind
    effective_principal_ref: str
    effective_provider_role: str | None
    is_shared: bool | None
    is_shareable: bool | None
    source_receipts: tuple[NotebookSourceReceipt, ...] = ()


@dataclass(frozen=True)
class AudioOverviewReceipt:
    provider: str
    provider_api_maturity: ProviderApiMaturity
    client_request_id: str
    status: str
    notebook_id: str
    audio_overview_id: str
    provider_resource_name: str
    project_ref: str
    location: str
    scope_kind: NotebookScopeKind
    effective_principal_ref: str
    source_ids: tuple[str, ...]


class NotebookProviderError(RuntimeError):
    """Sanitized provider failure.

    ``reason`` is a stable Bicameral reason, never provider response text or a
    credential-bearing exception string.
    """

    def __init__(
        self,
        failure_class: NotebookFailureClass,
        *,
        status: int = 0,
        reason: str = "",
    ) -> None:
        self.failure_class = failure_class
        self.status = status
        self.reason = reason
        super().__init__(
            f"notebook provider failed "
            f"(class={failure_class.value}, status={status}, reason={reason or 'unknown'})"
        )


@runtime_checkable
class PrincipalResolver(Protocol):
    """Resolve the effective, already-authorized provider principal safely.

    Implementations belong to the operator identity/credential boundary. The
    resolver returns an identity reference, never a token.
    """

    def resolve_principal(self) -> str: ...


@runtime_checkable
class NotebookProvider(Protocol):
    @property
    def capabilities(self) -> NotebookProviderCapabilities: ...

    def create_notebook(self, request: NotebookCreateRequest) -> NotebookReceipt: ...

    def get_notebook(
        self,
        notebook_id: str,
        *,
        access_scope: NotebookAccessScope,
        client_request_id: str,
    ) -> NotebookReceipt: ...

    def add_sources(
        self,
        notebook_id: str,
        sources: list[NotebookSourceRequest],
        *,
        access_scope: NotebookAccessScope,
        client_request_id: str,
    ) -> NotebookReceipt: ...

    def create_audio_overview(
        self,
        notebook_id: str,
        request: AudioOverviewRequest,
    ) -> AudioOverviewReceipt: ...
