# Copyright 2026 Bicameral AI — MIT License
"""Google Drive status/reason → typed ``DiscoveryError`` taxonomy (#179).

Factored out of ``connector.py`` (Razor). Maps an untrusted Drive REST status +
error body onto the merged five-value ``DiscoveryErrorKind`` (#178). The
insufficient-scope case carries ``required_scope`` (mirroring the
``google-drive-action-needed.json`` golden fixture). Every message is generic and
token-free.
"""

from __future__ import annotations

from typing import Any

from ..types import DiscoveryError, DiscoveryErrorKind, PermissionState

# The minimal scope that enables file listing + content read (research brief F3).
_REQUIRED_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


def _reason(body: dict[str, Any]) -> str:
    """Best-effort Drive error reason (e.g. ``insufficientPermissions``), lowercased."""
    err = body.get("error")
    if isinstance(err, dict):
        errs = err.get("errors")
        if isinstance(errs, list) and errs and isinstance(errs[0], dict):
            return str(errs[0].get("reason", "")).lower()
        return str(err.get("status", "")).lower()
    return ""


def error_from_status(resp_status: int, body: Any, headers: dict[str, str] | None = None) -> DiscoveryError:
    """Map a non-200 Drive response to a typed discovery error."""
    data = body if isinstance(body, dict) else {}
    reason = _reason(data)
    hdrs = {k.lower(): v for k, v in (headers or {}).items()}
    if resp_status == 401:
        return DiscoveryError(
            kind=DiscoveryErrorKind.ACTION_NEEDED,
            message="Google credentials expired or revoked",
            permission_state=PermissionState.ACTION_NEEDED,
            action_hint="Re-authorize Google access (drive.readonly / documents.readonly).",
        )
    if resp_status == 403:
        if "insufficientpermissions" in reason or "insufficientscopes" in reason:
            return DiscoveryError(
                kind=DiscoveryErrorKind.ACTION_NEEDED,
                message="OAuth scope is insufficient for Drive discovery",
                permission_state=PermissionState.ACTION_NEEDED,
                action_hint=f"Re-authorize with {_REQUIRED_SCOPE} to enable file listing.",
            )
        if "ratelimitexceeded" in reason or "userratelimitexceeded" in reason or hdrs.get(
            "retry-after"
        ):
            return DiscoveryError(
                kind=DiscoveryErrorKind.PROVIDER_ERROR,
                message="Google Drive rate limit exceeded",
                action_hint="Retry after the rate-limit window.",
            )
        return DiscoveryError(
            kind=DiscoveryErrorKind.PERMISSION_DENIED,
            message="the connected account lacks access to this shared drive",
            permission_state=PermissionState.DENIED,
            action_hint="Grant the account access to the shared drive.",
        )
    if resp_status == 404:
        return DiscoveryError(
            kind=DiscoveryErrorKind.NOT_FOUND, message="resource not found or deleted"
        )
    if resp_status == 400:
        return DiscoveryError(
            kind=DiscoveryErrorKind.PROVIDER_ERROR,
            message="stale or invalid page token",
            action_hint="Restart listing without a page token.",
        )
    if resp_status == 429:
        return DiscoveryError(
            kind=DiscoveryErrorKind.PROVIDER_ERROR,
            message="Google Drive rate limit exceeded",
            action_hint="Retry after the rate-limit window.",
        )
    if resp_status >= 500:
        return DiscoveryError(
            kind=DiscoveryErrorKind.PROVIDER_ERROR,
            message="Google Drive provider unavailable",
            action_hint="Retry later.",
        )
    return DiscoveryError(
        kind=DiscoveryErrorKind.PROVIDER_ERROR,
        message=f"unexpected provider status {resp_status}",
    )
