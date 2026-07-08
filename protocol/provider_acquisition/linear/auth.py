# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""Linear API-key auth for discovery (ADR-0017 alpha 3/3).

Reuses the runtime ``SecretResolver`` as the token provider (``resolve("linear")
-> personal API key``) — **no new token type**. The key rides in the **raw
``Authorization`` header with NO ``Bearer`` prefix** (verified F1; distinct from
Drive's Bearer), matching ``runtime.poll_auth.ApiKeyHeaderAuth("Authorization", key)``.
Token-free errors; the key is screened for header-smuggling control chars before the
header splice.
"""

from __future__ import annotations

from typing import Any

from ..types import DiscoveryError, DiscoveryErrorKind, PermissionState


def _key_is_clean(value: str) -> bool:
    """True when the API key carries no header-smuggling control chars (``\\t`` allowed)."""
    return all(ch == "\t" or (0x20 <= ord(ch) != 0x7F) for ch in value)


def build_auth_headers(secrets: Any) -> tuple[dict[str, str] | None, DiscoveryError | None]:
    """Resolve the Linear API key and build the raw ``Authorization`` header, or a typed error.

    ``secrets`` is duck-typed as a ``SecretResolver`` (``.resolve(id) -> str``). An empty
    / malformed key yields a typed ``ACTION_NEEDED`` outcome (re-connect), never a crash
    and never the key value in the message.
    """
    key = secrets.resolve("linear")
    if not key:
        return None, DiscoveryError(
            kind=DiscoveryErrorKind.ACTION_NEEDED,
            message="missing Linear API key",
            permission_state=PermissionState.ACTION_NEEDED,
            action_hint="Connect Linear and provide a personal API key.",
        )
    if not _key_is_clean(key):
        return None, DiscoveryError(
            kind=DiscoveryErrorKind.ACTION_NEEDED,
            message="malformed Linear API key",
            permission_state=PermissionState.ACTION_NEEDED,
            action_hint="Re-issue the Linear API key.",
        )
    # Raw key in Authorization — NO "Bearer " prefix (Linear personal-API-key contract).
    return {"Authorization": key, "Content-Type": "application/json"}, None
