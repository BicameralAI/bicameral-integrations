# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""Pure GitHub-REST-JSON → neutral discovery object mapping (#180).

Provider-specific field knowledge lives here; the connector stays a thin
auth / route / error / screen surface. Every function returns a typed neutral
object (``ProviderResourceDescriptor`` / ``ProviderItemEnvelope``) that mirrors
the golden fixtures from #177 and conforms to the bot#462 schema.

Untrusted-input discipline: a provider response is untrusted, so nested objects
are coerced (a ``null`` / non-dict ``user`` must not crash a chained ``.get``) and
free-text scalars are normalized to ``str`` before they reach the screen.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any

from ..types import (
    FreshnessMetadata,
    PermissionState,
    ProviderItemEnvelope,
    ProviderResourceDescriptor,
    ResourceRef,
)

_PROVIDER = "github"


def _d(value: Any) -> dict[str, Any]:
    """Coerce a present-but-non-dict nested field to ``{}`` (untrusted boundary)."""
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    """Free-text scalar as a string (``""`` when absent / non-string)."""
    return value if isinstance(value, str) else ""


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def map_repository(
    repo: dict[str, Any], *, captured_at: str
) -> ProviderResourceDescriptor:
    """Map a GitHub repository object into a ``repository`` descriptor."""
    full_name = _text(repo.get("full_name"))
    perms = _d(repo.get("permissions"))
    provider_metadata = {
        k: v
        for k, v in {
            "default_branch": repo.get("default_branch"),
            "visibility": repo.get("visibility"),
            "language": repo.get("language"),
        }.items()
        if v is not None
    }
    return ProviderResourceDescriptor(
        provider=_PROVIDER,
        resource_id=full_name,
        display_name=_text(repo.get("name")) or full_name,
        resource_type="repository",
        captured_at=captured_at,
        uri=_text(repo.get("html_url")) or None,
        capabilities=_repo_capabilities(perms),
        permission=PermissionState.GRANTED,
        freshness=_freshness(
            last_modified=repo.get("updated_at"), etag=repo.get("node_id")
        ),
        provider_metadata=provider_metadata,
    )


def _repo_capabilities(perms: dict[str, Any]) -> tuple[str, ...]:
    caps = ["list", "read", "search"]
    # `watch` (change notification) only when the installation can subscribe.
    if perms.get("admin") or perms.get("maintain") or perms.get("push"):
        caps.append("watch")
    return tuple(caps)


def map_issue(
    issue: dict[str, Any], *, resource_id: str, fetched_at: str
) -> ProviderItemEnvelope:
    """Map a GitHub issue object into an ``issue`` item envelope."""
    number = issue.get("number")
    content = _text(issue.get("body"))
    labels = [
        _text(label.get("name"))
        for label in issue.get("labels", [])
        if isinstance(label, dict)
    ]
    provider_metadata = {
        k: v
        for k, v in {
            "number": number,
            "state": issue.get("state"),
            "author_login": _d(issue.get("user")).get("login"),
            "labels": labels or None,
        }.items()
        if v is not None
    }
    return ProviderItemEnvelope(
        provider=_PROVIDER,
        resource_id=resource_id,
        item_id=f"issue-{number}",
        item_type="issue",
        content=content,
        fetched_at=fetched_at,
        title=_text(issue.get("title")) or None,
        uri=_text(issue.get("html_url")) or None,
        content_hash=_content_hash(content),
        freshness=_freshness(last_modified=issue.get("updated_at")),
        provider_metadata=provider_metadata,
    )


def map_pull_request(
    pr: dict[str, Any], *, resource_id: str, fetched_at: str
) -> ProviderItemEnvelope:
    """Map a GitHub pull-request object into a ``pull_request`` item envelope."""
    number = pr.get("number")
    content = _text(pr.get("body"))
    provider_metadata = {
        k: v
        for k, v in {
            "number": number,
            "state": pr.get("state"),
            "merged": pr.get("merged"),
            "author_login": _d(pr.get("user")).get("login"),
            "base_branch": _d(pr.get("base")).get("ref"),
        }.items()
        if v is not None
    }
    return ProviderItemEnvelope(
        provider=_PROVIDER,
        resource_id=resource_id,
        item_id=f"pr-{number}",
        item_type="pull_request",
        content=content,
        fetched_at=fetched_at,
        title=_text(pr.get("title")) or None,
        uri=_text(pr.get("html_url")) or None,
        content_hash=_content_hash(content),
        freshness=_freshness(last_modified=pr.get("updated_at")),
        provider_metadata=provider_metadata,
    )


def map_file_content(
    file: dict[str, Any], *, resource_id: str, fetched_at: str
) -> ProviderItemEnvelope:
    """Map a GitHub contents-API file object into a ``file`` item envelope.

    The GitHub ``GET /repos/{owner}/{repo}/contents/{path}`` response encodes
    file content as base64; we decode it here. Non-file entries (directories,
    symlinks, submodules) are routed before this function is called and never
    reach it.
    """
    file_path = _text(file.get("path"))
    raw_b64 = _text(file.get("content")).replace("\n", "")
    try:
        content = base64.b64decode(raw_b64).decode("utf-8", errors="replace")
    except Exception:
        content = ""
    provider_metadata = {
        k: v
        for k, v in {
            "path": file_path or None,
            "sha": file.get("sha"),
            "size": file.get("size"),
            "encoding": file.get("encoding"),
        }.items()
        if v is not None
    }
    return ProviderItemEnvelope(
        provider=_PROVIDER,
        resource_id=resource_id,
        item_id=f"file-{file_path}",
        item_type="file",
        content=content,
        fetched_at=fetched_at,
        title=_text(file.get("name")) or None,
        uri=_text(file.get("html_url")) or None,
        content_hash=_content_hash(content),
        freshness=_freshness(etag=file.get("sha")),
        provider_metadata=provider_metadata,
    )


def _freshness(
    *, last_modified: Any = None, etag: Any = None, item_count: Any = None
) -> FreshnessMetadata | None:
    lm = last_modified if isinstance(last_modified, str) else None
    et = etag if isinstance(etag, str) else None
    ic = item_count if isinstance(item_count, int) else None
    if lm is None and et is None and ic is None:
        return None
    return FreshnessMetadata(last_modified=lm, etag=et, item_count=ic)


def parent_ref(resource_id: str) -> ResourceRef | None:
    """``ResourceRef`` to the parent repo of an ``owner/repo/...`` resource id."""
    parts = resource_id.split("/")
    if len(parts) < 2:
        return None
    repo = f"{parts[0]}/{parts[1]}"
    return ResourceRef(resource_id=repo, display_name=parts[1])
