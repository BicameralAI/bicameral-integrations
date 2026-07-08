# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""Pure Linear-GraphQL-node → neutral discovery object mapping (ADR-0017 alpha 3/3).

Emits typed neutral objects mirroring the golden `linear-*` fixtures (#177); id
prefixes ``ws_``/``team_``/``proj_``/``issue_``/``comment_``. Issue-item content
reuses the audited, PII-safe ``connectors.linear.connector.parse_issue_node`` excerpt
logic (no assignee/creator identity) rather than re-deriving it.

Untrusted-input discipline: a provider response is untrusted, so nested fields are
coerced and free-text scalars normalized to ``str`` before they reach the screen.
"""

from __future__ import annotations

import hashlib
from typing import Any

from connectors.linear.connector import parse_issue_node

from ..types import (
    FreshnessMetadata,
    PermissionState,
    ProviderItemEnvelope,
    ProviderResourceDescriptor,
    ResourceRef,
)

_PROVIDER = "linear"


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _d(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _freshness(last_modified: Any = None, item_count: Any = None) -> FreshnessMetadata | None:
    lm = last_modified if isinstance(last_modified, str) else None
    ic = item_count if isinstance(item_count, int) else None
    if lm is None and ic is None:
        return None
    return FreshnessMetadata(last_modified=lm, item_count=ic)


def map_workspace(org: dict[str, Any], *, captured_at: str) -> ProviderResourceDescriptor:
    url_key = _text(org.get("urlKey"))
    return ProviderResourceDescriptor(
        provider=_PROVIDER,
        resource_id=f"ws_{url_key}",
        display_name=_text(org.get("name")) or url_key,
        resource_type="workspace",
        captured_at=captured_at,
        uri=f"https://linear.app/{url_key}" if url_key else None,
        capabilities=("list", "search"),
        permission=PermissionState.GRANTED,
    )


def map_team(
    team: dict[str, Any], *, ws_url_key: str, ws_name: str, captured_at: str
) -> ProviderResourceDescriptor:
    team_id, key = _text(team.get("id")), _text(team.get("key"))
    return ProviderResourceDescriptor(
        provider=_PROVIDER,
        resource_id=f"team_{team_id}",
        display_name=_text(team.get("name")) or key,
        resource_type="team",
        captured_at=captured_at,
        uri=f"https://linear.app/{ws_url_key}/team/{key}" if ws_url_key and key else None,
        capabilities=("list", "read", "search"),
        permission=PermissionState.GRANTED,
        parent=ResourceRef(resource_id=f"ws_{ws_url_key}", display_name=ws_name or None),
        provider_metadata={"key": key} if key else {},
    )


def map_project(
    project: dict[str, Any], *, team_id: str, ws_url_key: str, captured_at: str
) -> ProviderResourceDescriptor:
    proj_id = _text(project.get("id"))
    return ProviderResourceDescriptor(
        provider=_PROVIDER,
        resource_id=f"proj_{proj_id}",
        display_name=_text(project.get("name")) or proj_id,
        resource_type="project",
        captured_at=captured_at,
        uri=f"https://linear.app/{ws_url_key}/project/{proj_id}" if ws_url_key and proj_id else None,
        capabilities=("list", "read"),
        permission=PermissionState.GRANTED,
        parent=ResourceRef(resource_id=f"team_{team_id}"),
    )


def map_issue_descriptor(
    issue: dict[str, Any], *, team_id: str, captured_at: str
) -> ProviderResourceDescriptor:
    issue_id, identifier = _text(issue.get("id")), _text(issue.get("identifier"))
    name = _text(issue.get("title"))
    state = _d(issue.get("state"))
    provider_metadata = {
        k: v
        for k, v in {
            "identifier": identifier or None,
            "priority": issue.get("priority"),
            "state": state.get("name") if state else None,
        }.items()
        if v is not None
    }
    return ProviderResourceDescriptor(
        provider=_PROVIDER,
        resource_id=f"issue_{issue_id}",
        display_name=f"{identifier}: {name}".strip(": ").strip() or identifier or issue_id,
        resource_type="issue",
        captured_at=captured_at,
        uri=_text(issue.get("url")) or None,
        capabilities=("read",),
        permission=PermissionState.GRANTED,
        parent=ResourceRef(resource_id=f"team_{team_id}") if team_id else None,
        freshness=_freshness(issue.get("updatedAt")),
        provider_metadata=provider_metadata,
    )


def descriptor_from_node(
    prefix: str, data: dict[str, Any], *, captured_at: str
) -> ProviderResourceDescriptor | None:
    """Map a single-node get response to a descriptor by ``resource_id`` prefix.

    Returns ``None`` when the node is null/absent (→ the connector emits ``NOT_FOUND``).
    """
    if prefix == "team_":
        team = data.get("team")
        if not isinstance(team, dict):
            return None
        org = _d(team.get("organization"))
        return map_team(
            team, ws_url_key=_text(org.get("urlKey")), ws_name=_text(org.get("name")),
            captured_at=captured_at,
        )
    if prefix == "proj_":
        project = data.get("project")
        if not isinstance(project, dict):
            return None
        return map_project(
            project, team_id=_text(_d(project.get("team")).get("id")),
            ws_url_key=_text(_d(data.get("organization")).get("urlKey")), captured_at=captured_at,
        )
    issue = data.get("issue")
    if not isinstance(issue, dict):
        return None
    return map_issue_descriptor(
        issue, team_id=_text(_d(issue.get("team")).get("id")), captured_at=captured_at
    )


def map_issue_item(
    issue: dict[str, Any], *, resource_id: str, fetched_at: str
) -> ProviderItemEnvelope:
    """Issue item; content reuses ``parse_issue_node`` (PII-safe excerpt)."""
    obs = parse_issue_node(issue)  # reuse the audited excerpt + PII-safety
    identifier = _text(issue.get("identifier"))
    team = _d(issue.get("team"))
    provider_metadata = {
        k: v
        for k, v in {
            "identifier": identifier or None,
            "priority": issue.get("priority"),
            "state": _d(issue.get("state")).get("name"),
            "team_key": _text(team.get("key")) or None,
        }.items()
        if v is not None
    }
    return ProviderItemEnvelope(
        provider=_PROVIDER,
        resource_id=resource_id,
        item_id=f"issue_{_text(issue.get('id'))}",
        item_type="issue",
        content=obs.excerpt,
        fetched_at=fetched_at,
        title=obs.title or None,
        uri=_text(issue.get("url")) or None,
        content_hash=hashlib.sha256(obs.excerpt.encode("utf-8")).hexdigest(),
        freshness=_freshness(issue.get("updatedAt")),
        provider_metadata=provider_metadata,
    )


def map_comment_item(comment: dict[str, Any], *, fetched_at: str) -> ProviderItemEnvelope:
    comment_id = _text(comment.get("id"))
    body = _text(comment.get("body"))
    issue = _d(comment.get("issue"))
    issue_id, identifier = _text(issue.get("id")), _text(issue.get("identifier"))
    provider_metadata = {"parent_issue_identifier": identifier} if identifier else {}
    return ProviderItemEnvelope(
        provider=_PROVIDER,
        resource_id=f"issue_{issue_id}" if issue_id else "",
        item_id=f"comment_{comment_id}",
        item_type="comment",
        content=body,
        fetched_at=fetched_at,
        content_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        freshness=_freshness(comment.get("createdAt")),
        provider_metadata=provider_metadata,
    )
