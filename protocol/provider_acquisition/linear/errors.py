# Copyright 2026 Bicameral AI — MIT License
"""Linear GraphQL error → typed ``DiscoveryError`` taxonomy (ADR-0017 alpha 3/3).

Factored out of ``connector.py`` (Razor). Honors the GraphQL-specific semantics
verified in the research brief (``runtime.graphql_poll`` precedent): a **200 with a
non-empty ``errors`` array** is never success, and **rate-limiting is HTTP 400 +
``errors[].code == "RATELIMITED"``**. Every message is generic and token-free.
"""

from __future__ import annotations

from typing import Any

from ..types import DiscoveryError, DiscoveryErrorKind, PermissionState

_REQUIRED_HINT = "Re-issue the Linear API key with workspace read access."


def _signature(errors: list[dict[str, Any]]) -> str:
    """Concatenate error ``code`` + ``message`` values, lowercased, for classification."""
    parts: list[str] = []
    for err in errors:
        if isinstance(err, dict):
            parts.append(str(err.get("code", "")))
            parts.append(str(err.get("message", "")))
    return " ".join(parts).lower()


def is_ratelimited(errors: list[dict[str, Any]]) -> bool:
    """True iff a GraphQL ``errors`` list carries ``code == "RATELIMITED"`` (graphql_poll parity)."""
    return any(isinstance(e, dict) and e.get("code") == "RATELIMITED" for e in errors)


def error_from_graphql(status: int, errors: list[dict[str, Any]]) -> DiscoveryError:
    """Map a GraphQL failure (HTTP status + ``errors``) to a typed discovery error."""
    if is_ratelimited(errors):
        return DiscoveryError(
            kind=DiscoveryErrorKind.PROVIDER_ERROR,
            message="Linear API rate limit exceeded",
            action_hint="Retry after the rate-limit window.",
        )
    if status == 400 or not errors:
        return DiscoveryError(
            kind=DiscoveryErrorKind.PROVIDER_ERROR,
            message=f"Linear request failed (status {status})",
            action_hint="Retry later.",
        )
    sig = _signature(errors)
    if "authentication" in sig or "unauthenticated" in sig or "invalid api key" in sig:
        return DiscoveryError(
            kind=DiscoveryErrorKind.ACTION_NEEDED,
            message="Linear authentication failed",
            permission_state=PermissionState.ACTION_NEEDED,
            action_hint=_REQUIRED_HINT,
        )
    if "forbidden" in sig or "access denied" in sig or "not authorized" in sig:
        return DiscoveryError(
            kind=DiscoveryErrorKind.PERMISSION_DENIED,
            message="the API key lacks access to this Linear resource",
            permission_state=PermissionState.DENIED,
            action_hint="Grant the key access to this team/workspace.",
        )
    if "not_found" in sig or "not found" in sig or "entitynotfound" in sig:
        return DiscoveryError(
            kind=DiscoveryErrorKind.NOT_FOUND, message="Linear resource not found"
        )
    return DiscoveryError(
        kind=DiscoveryErrorKind.PROVIDER_ERROR,
        message="Linear GraphQL error",
        action_hint="Retry later.",
    )
