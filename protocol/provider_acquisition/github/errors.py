# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""GitHub status → typed ``DiscoveryError`` taxonomy (#180).

Factored out of ``connector.py`` (Razor: keep the connector under the file-size
limit; ADR-0017 audit discipline note). Maps an untrusted GitHub REST status +
headers + body onto the merged five-value ``DiscoveryErrorKind`` (#178). Every
message is generic and token-free — a provider body is never echoed verbatim
beyond its short ``message`` field.
"""

from __future__ import annotations

from ..types import DiscoveryError, DiscoveryErrorKind, PermissionState
from .transport import GitHubResponse


def error_from_status(resp: GitHubResponse) -> DiscoveryError:
    """Map a non-200 GitHub response to a typed discovery error."""
    headers = {k.lower(): v for k, v in (resp.headers or {}).items()}
    body = resp.json if isinstance(resp.json, dict) else {}
    msg = str(body.get("message", "")).lower()
    if resp.status == 401:
        return DiscoveryError(
            kind=DiscoveryErrorKind.ACTION_NEEDED,
            message="installation credentials expired or invalid",
            permission_state=PermissionState.ACTION_NEEDED,
            action_hint="Regenerate or re-install the GitHub App installation.",
        )
    if resp.status == 403:
        if headers.get("x-ratelimit-remaining") == "0" or "rate limit" in msg:
            return DiscoveryError(
                kind=DiscoveryErrorKind.PROVIDER_ERROR,
                message="GitHub API rate limit exceeded",
                action_hint="Retry after the rate-limit reset.",
            )
        return DiscoveryError(
            kind=DiscoveryErrorKind.PERMISSION_DENIED,
            message="installation lacks permission for this resource",
            permission_state=PermissionState.DENIED,
            action_hint="Grant the GitHub App access to this repository.",
        )
    if resp.status == 404:
        return DiscoveryError(
            kind=DiscoveryErrorKind.NOT_FOUND, message="resource not found"
        )
    if resp.status == 422:
        return DiscoveryError(
            kind=DiscoveryErrorKind.PROVIDER_ERROR,
            message="stale or invalid pagination cursor",
            action_hint="Restart listing without a cursor.",
        )
    if resp.status >= 500:
        return DiscoveryError(
            kind=DiscoveryErrorKind.PROVIDER_ERROR,
            message="GitHub provider unavailable",
            action_hint="Retry later.",
        )
    return DiscoveryError(
        kind=DiscoveryErrorKind.PROVIDER_ERROR,
        message=f"unexpected provider status {resp.status}",
    )
