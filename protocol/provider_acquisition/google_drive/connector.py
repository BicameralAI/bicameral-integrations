# Copyright 2026 Bicameral AI — MIT License
"""Google Drive App discovery connector (#179).

Satisfies the merged ``DiscoveryConnector`` contract (#178) for Google Drive: shared
drives (`drives.list`), `.bicameral` project folders (`files.list`), and document
leaves (`documents.get`). Thin by design — resolve the OAuth access token via the
injected ``SecretResolver`` (reused from the runtime; **no new token type**), route
through the injected transport, map (``mapping.py``), screen fail-closed
(``screening.py``), and return a typed ``DiscoveryOutcome``.

``create_provider_resource`` is **absent**; `.bicameral` folder *creation* is
egress/proposed-action territory (ADR-0008 / ADR-0017 §4), not discovery.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from adapter.core.capabilities import SourceCapabilities, SourceMode

from ..screening import DiscoveryScreenError, screen_descriptor, screen_item
from ..types import (
    DiscoveryError,
    DiscoveryErrorKind,
    DiscoveryOutcome,
    ProviderItemEnvelope,
    ProviderResourceDescriptor,
)
from . import mapping
from .auth import build_auth_headers
from .errors import error_from_status
from .mapping import FOLDER_MIME
from .transport import DriveTransport

_OK = 200
_DRIVES = "/drive/v3/drives"
_FILES = "/drive/v3/files"
_DOCS = "https://docs.googleapis.com/v1/documents/"
_FILE_FIELDS = "id,name,mimeType,modifiedTime,version,parents,driveId"
_SHARED = {"corpora": "drive", "includeItemsFromAllDrives": "true", "supportsAllDrives": "true"}
# Fully-anchored id grammar — guards the URL splice in fetch (path/URL-injection: a
# loose match would admit `x/../y`/`x?a=b`/`x@host`/`x\r\n`), mirroring
# runtime.poll_specs.build_google_drive_spec. The live transport (deferred) reuses it.
_DOC_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,200}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _str(value: Any) -> str:
    return value if isinstance(value, str) else ""


class GoogleDriveDiscoveryConnector:
    """Drive discovery over an injected transport + ``SecretResolver`` (the OAuth token).

    ``config`` carries non-secret routing: an optional ``drive_id`` (when present,
    ``list_resources`` lists that drive's ``.bicameral`` project folders instead of
    shared drives) and an optional ``drive_name`` for parent labelling. The access
    token is resolved per call from the ``SecretResolver`` — never in ``config``.
    """

    source_id = "google_drive"

    def __init__(
        self,
        *,
        transport: DriveTransport,
        secrets: Any,  # runtime.secrets.SecretResolver (duck-typed: .resolve(id) -> str)
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.capabilities = SourceCapabilities(modes=frozenset({SourceMode.DISCOVERY}))
        self._transport = transport
        self._secrets = secrets
        self._clock = clock or _now_iso

    def _auth(self) -> tuple[dict[str, str] | None, DiscoveryError | None]:
        return build_auth_headers(self._secrets)

    def _screened(
        self, obj: ProviderResourceDescriptor | ProviderItemEnvelope
    ) -> DiscoveryError | None:
        try:
            screen_item(obj) if isinstance(obj, ProviderItemEnvelope) else screen_descriptor(obj)
        except DiscoveryScreenError as exc:
            return DiscoveryError(
                kind=DiscoveryErrorKind.PROVIDER_ERROR,
                message=f"discovery object failed sensitive-data screen ({exc})",
            )
        return None

    def _get_json(
        self, path: str, headers: dict[str, str], params: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, DiscoveryError | None]:
        """GET ``path`` → ``(json, None)`` on 200, else ``(None, typed-error)``."""
        resp = self._transport.request("GET", path, headers=headers, params=params)
        if resp.status != _OK:
            return None, error_from_status(resp.status, resp.json, resp.headers)
        return (resp.json if isinstance(resp.json, dict) else {}), None

    # -- list_resources -----------------------------------------------------

    def list_resources(
        self, *, config: dict[str, Any]
    ) -> DiscoveryOutcome[list[ProviderResourceDescriptor]]:
        headers, err = self._auth()
        if err is not None:
            return DiscoveryOutcome(error=err)
        drive_id = config.get("drive_id")
        if drive_id:
            return self._list_bicameral_folders(headers or {}, str(drive_id), config)
        return self._list_shared_drives(headers or {}, config)

    def _collect(
        self, descriptors: list[ProviderResourceDescriptor]
    ) -> DiscoveryOutcome[list[ProviderResourceDescriptor]]:
        """Screen each descriptor fail-closed; return the list or the first screen error."""
        for desc in descriptors:
            if (screen_err := self._screened(desc)) is not None:
                return DiscoveryOutcome(error=screen_err)
        return DiscoveryOutcome(value=descriptors)

    def _list_shared_drives(
        self, headers: dict[str, str], config: dict[str, Any]
    ) -> DiscoveryOutcome[list[ProviderResourceDescriptor]]:
        params = {"pageToken": config["cursor"]} if config.get("cursor") else None
        body, err = self._get_json(_DRIVES, headers, params)
        if err is not None:
            return DiscoveryOutcome(error=err)
        captured = self._clock()
        return self._collect([
            mapping.map_shared_drive(d, captured_at=captured)
            for d in (body or {}).get("drives", []) if isinstance(d, dict)
        ])

    def _list_bicameral_folders(
        self, headers: dict[str, str], drive_id: str, config: dict[str, Any]
    ) -> DiscoveryOutcome[list[ProviderResourceDescriptor]]:
        find = {"q": f"name = '.bicameral' and mimeType = '{FOLDER_MIME}' and trashed = false",
                "driveId": drive_id, **_SHARED}
        body, err = self._get_json(_FILES, headers, find)
        if err is not None:
            return DiscoveryOutcome(error=err)
        roots = [f for f in (body or {}).get("files", []) if isinstance(f, dict)]
        if not roots:  # no .bicameral folder yet — empty (not an error)
            return DiscoveryOutcome(value=[])
        kids = {"q": f"'{_str(roots[0].get('id'))}' in parents and mimeType = '{FOLDER_MIME}' "
                     "and trashed = false", "driveId": drive_id, **_SHARED}
        body2, err2 = self._get_json(_FILES, headers, kids)
        if err2 is not None:
            return DiscoveryOutcome(error=err2)
        captured, drive_name = self._clock(), _str(config.get("drive_name"))
        return self._collect([
            mapping.map_folder(f, drive_id=drive_id, drive_name=drive_name, captured_at=captured)
            for f in (body2 or {}).get("files", []) if isinstance(f, dict)
        ])

    # -- get_resource / validate_resource_access ----------------------------

    def get_resource(
        self, *, config: dict[str, Any], resource_id: str
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        return self._descriptor_by_id(resource_id)

    def validate_resource_access(
        self, *, config: dict[str, Any], resource_id: str
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        return self._descriptor_by_id(resource_id)

    def _descriptor_by_id(
        self, resource_id: str
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        headers, err = self._auth()
        if err is not None:
            return DiscoveryOutcome(error=err)
        captured = self._clock()
        if resource_id.startswith("drive_"):
            body, gerr = self._get_json(f"{_DRIVES}/{resource_id[6:]}", headers or {})
            if gerr is not None:
                return DiscoveryOutcome(error=gerr)
            return self._emit(mapping.map_shared_drive(body or {}, captured_at=captured))
        if resource_id.startswith("folder_") or resource_id.startswith("doc_"):
            file_id = resource_id.split("_", 1)[1]
            body, gerr = self._get_json(
                f"{_FILES}/{file_id}", headers or {},
                {"supportsAllDrives": "true", "fields": _FILE_FIELDS},
            )
            if gerr is not None:
                return DiscoveryOutcome(error=gerr)
            return self._emit(
                mapping.descriptor_from_file(resource_id, body or {}, captured_at=captured)
            )
        return DiscoveryOutcome(
            error=DiscoveryError(
                kind=DiscoveryErrorKind.UNSUPPORTED,
                message=f"unsupported resource id {resource_id!r}",
                action_hint="Resource ids must be 'drive_*', 'folder_*', or 'doc_*'.",
            )
        )

    def _emit(
        self, desc: ProviderResourceDescriptor
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        screen_err = self._screened(desc)
        return DiscoveryOutcome(error=screen_err) if screen_err else DiscoveryOutcome(value=desc)

    # -- fetch_provider_item ------------------------------------------------

    def fetch_provider_item(
        self, *, config: dict[str, Any], resource_id: str, item_id: str
    ) -> DiscoveryOutcome[ProviderItemEnvelope]:
        headers, err = self._auth()
        if err is not None:
            return DiscoveryOutcome(error=err)
        if not item_id.startswith("doc_"):
            return DiscoveryOutcome(
                error=DiscoveryError(
                    kind=DiscoveryErrorKind.UNSUPPORTED,
                    message=f"unsupported item kind for id {item_id!r}",
                    action_hint="Item ids must be 'doc_<id>'.",
                )
            )
        doc_id = item_id[len("doc_"):]
        if not _DOC_ID_RE.fullmatch(doc_id):  # URL-injection guard before the splice
            return DiscoveryOutcome(
                error=DiscoveryError(
                    kind=DiscoveryErrorKind.UNSUPPORTED,
                    message="malformed document id",
                    action_hint="Document ids must match [A-Za-z0-9_-]{1,200}.",
                )
            )
        body, gerr = self._get_json(f"{_DOCS}{doc_id}", headers or {})
        if gerr is not None:
            return DiscoveryOutcome(error=gerr)
        item = mapping.map_document_item(
            body or {}, resource_id=resource_id, item_id=item_id, fetched_at=self._clock()
        )
        screen_err = self._screened(item)
        return DiscoveryOutcome(error=screen_err) if screen_err else DiscoveryOutcome(value=item)
