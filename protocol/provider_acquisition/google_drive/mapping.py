# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""Pure Google-Drive-JSON → neutral discovery object mapping (#179).

Provider knowledge lives here; the connector stays a thin auth/route/error/screen
surface. Emits typed neutral objects mirroring the golden `google-drive-*` fixtures
(#177) — id prefixes ``drive_``/``folder_``/``doc_`` match the fixtures. Document
content reuses the audited Drive doc walker (``extract_document_text``) rather than
re-deriving it (Macro-Architecture: no duplicated domain logic).

Untrusted-input discipline: a provider response is untrusted, so nested fields are
coerced and free-text scalars normalized to ``str`` before they reach the screen.
"""

from __future__ import annotations

import hashlib
from typing import Any

from connectors.google_drive.connector import extract_document_text

from ..types import (
    FreshnessMetadata,
    PermissionState,
    ProviderItemEnvelope,
    ProviderResourceDescriptor,
    ResourceRef,
)

_PROVIDER = "google_drive"
FOLDER_MIME = "application/vnd.google-apps.folder"
DOCUMENT_MIME = "application/vnd.google-apps.document"


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _freshness(
    *, last_modified: Any = None, etag: Any = None, item_count: Any = None
) -> FreshnessMetadata | None:
    lm = last_modified if isinstance(last_modified, str) else None
    et = etag if isinstance(etag, str) else None
    ic = item_count if isinstance(item_count, int) else None
    if lm is None and et is None and ic is None:
        return None
    return FreshnessMetadata(last_modified=lm, etag=et, item_count=ic)


def map_shared_drive(drive: dict[str, Any], *, captured_at: str) -> ProviderResourceDescriptor:
    """Map a Drive resource (`drives.list`/`drives.get`) into a ``shared_drive`` descriptor."""
    drive_id = _text(drive.get("id"))
    return ProviderResourceDescriptor(
        provider=_PROVIDER,
        resource_id=f"drive_{drive_id}",
        display_name=_text(drive.get("name")) or drive_id,
        resource_type="shared_drive",
        captured_at=captured_at,
        uri=f"https://drive.google.com/drive/folders/{drive_id}" if drive_id else None,
        capabilities=("list", "read", "search"),
        permission=PermissionState.GRANTED,
        freshness=_freshness(last_modified=drive.get("createdTime")),
    )


def map_folder(
    file: dict[str, Any], *, drive_id: str, drive_name: str, captured_at: str
) -> ProviderResourceDescriptor:
    """Map a folder File (`files.list`/`files.get`) into a ``folder`` descriptor."""
    file_id = _text(file.get("id"))
    return ProviderResourceDescriptor(
        provider=_PROVIDER,
        resource_id=f"folder_{file_id}",
        display_name=_text(file.get("name")) or file_id,
        resource_type="folder",
        captured_at=captured_at,
        uri=f"https://drive.google.com/drive/folders/{file_id}" if file_id else None,
        capabilities=("list", "read"),
        permission=PermissionState.GRANTED,
        parent=ResourceRef(resource_id=f"drive_{drive_id}", display_name=drive_name or None),
        freshness=_freshness(last_modified=file.get("modifiedTime")),
    )


def map_document_descriptor(
    file: dict[str, Any], *, folder_id: str, folder_name: str, captured_at: str
) -> ProviderResourceDescriptor:
    """Map a document File into a ``document`` descriptor."""
    file_id = _text(file.get("id"))
    version = file.get("version")
    provider_metadata = {
        k: v
        for k, v in {
            "mime_type": _text(file.get("mimeType")) or DOCUMENT_MIME,
            "version": str(version) if version is not None else None,
        }.items()
        if v is not None
    }
    return ProviderResourceDescriptor(
        provider=_PROVIDER,
        resource_id=f"doc_{file_id}",
        display_name=_text(file.get("name")) or file_id,
        resource_type="document",
        captured_at=captured_at,
        uri=f"https://docs.google.com/document/d/{file_id}/edit" if file_id else None,
        capabilities=("read",),
        permission=PermissionState.GRANTED,
        parent=ResourceRef(resource_id=f"folder_{folder_id}", display_name=folder_name or None),
        freshness=_freshness(last_modified=file.get("modifiedTime")),
        provider_metadata=provider_metadata,
    )


def descriptor_from_file(
    resource_id: str, file: dict[str, Any], *, captured_at: str
) -> ProviderResourceDescriptor:
    """Map a `files.get` response to a folder/document descriptor by ``resource_id`` prefix.

    Parent labels are left empty when not derivable from a single `files.get` (the
    ``display_name`` of a parent is an optional field).
    """
    if resource_id.startswith("folder_"):
        return map_folder(file, drive_id=_text(file.get("driveId")), drive_name="", captured_at=captured_at)
    parents = file.get("parents") or []
    folder_id = _text(parents[0]) if parents else ""
    return map_document_descriptor(file, folder_id=folder_id, folder_name="", captured_at=captured_at)


def map_document_item(
    document: dict[str, Any], *, resource_id: str, item_id: str, fetched_at: str
) -> ProviderItemEnvelope:
    """Map a Docs ``documents.get`` response into a ``document`` item envelope.

    Content reuses the audited Drive doc walker (``extract_document_text``).
    """
    content = extract_document_text(document)
    title = _text(document.get("title"))
    return ProviderItemEnvelope(
        provider=_PROVIDER,
        resource_id=resource_id,
        item_id=item_id,
        item_type="document",
        content=content,
        fetched_at=fetched_at,
        title=title or None,
        uri=(
            f"https://docs.google.com/document/d/{_text(document.get('documentId'))}/edit"
            if document.get("documentId")
            else None
        ),
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        freshness=None,
    )
