# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""OAuth access-token auth for Drive discovery (#179).

Reuses the runtime ``SecretResolver`` as the token provider (``resolve("google_drive")
-> OAuth access token``) — **no new token type**, unlike #180's GitHub installation
provider. The App refresh stays operator-side (``RefreshTokenSecretResolver``); the
connector only ever sees a resolved access token. Token-free errors; the token is
screened for header-smuggling control chars before the ``Bearer`` splice
(``runtime.poll_auth`` discipline).
"""

from __future__ import annotations

from typing import Any

from ..types import DiscoveryError, DiscoveryErrorKind, PermissionState


def _token_is_clean(value: str) -> bool:
    """True when the token carries no header-smuggling control chars (``\\t`` allowed)."""
    return all(ch == "\t" or (0x20 <= ord(ch) != 0x7F) for ch in value)


def build_auth_headers(secrets: Any) -> tuple[dict[str, str] | None, DiscoveryError | None]:
    """Resolve the Google access token and build the Bearer header, or a typed error.

    ``secrets`` is duck-typed as a ``SecretResolver`` (``.resolve(id) -> str``). An
    empty / malformed token yields a typed ``ACTION_NEEDED`` outcome (re-connect),
    never a crash and never the token value in the message.
    """
    token = secrets.resolve("google_drive")
    if not token:
        return None, DiscoveryError(
            kind=DiscoveryErrorKind.ACTION_NEEDED,
            message="missing Google credentials",
            permission_state=PermissionState.ACTION_NEEDED,
            action_hint="Connect Google and grant drive.readonly / documents.readonly.",
        )
    if not _token_is_clean(token):
        return None, DiscoveryError(
            kind=DiscoveryErrorKind.ACTION_NEEDED,
            message="malformed Google credentials",
            permission_state=PermissionState.ACTION_NEEDED,
            action_hint="Re-authorize Google access.",
        )
    return {"Authorization": f"Bearer {token}"}, None
