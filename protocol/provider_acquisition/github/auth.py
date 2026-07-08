# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""GitHub App installation auth for the discovery surface (#180; ADR-0017 §3/§6).

**Installation auth ONLY.** There is no PAT / imported-token entry point by
construction: the connector receives a short-lived **installation access token**
from an injected ``InstallationTokenProvider``; the GitHub App private key and
client secret are resolved hosted-side (the cloud token broker,
BicameralAI/bicameral-cloud#7) and NEVER enter this package. PAT / imported-token
fallback is rejected for alpha live fetch (the owner decision on #173).

Trust posture (mirrors ``runtime/poll_auth.py``): a token is screened for
header-smuggling control characters before it is spliced into an ``Authorization``
header, and it never appears in an error message (token-free, like ``PollError``).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class GitHubAuthError(ValueError):
    """An installation-auth input was malformed (e.g. a control char in the token).

    The message names the failure class only — it never echoes the token value.
    """


def reject_control_chars(label: str, value: str) -> None:
    """Reject CR/LF and other control chars in a token before it enters a header.

    A poisoned token must not smuggle a header break / request split. ``\\t`` is
    permitted (header-legal whitespace); everything below 0x20 and 0x7F is not.
    Raises :class:`GitHubAuthError` with a value-free message.
    """
    for ch in value:
        if ch == "\t":
            continue
        if ord(ch) < 0x20 or ord(ch) == 0x7F:
            raise GitHubAuthError(f"{label} contains a control character")


@runtime_checkable
class InstallationTokenProvider(Protocol):
    """Resolve a GitHub App **installation access token** for an installation id.

    The operator / hosted runtime supplies the real provider (the cloud#7 broker).
    Installation-only by design: there is deliberately no method that accepts a
    PAT or an imported token.
    """

    def installation_token(self, *, installation_id: str) -> str:
        """Return the installation token, or ``""`` when none is available."""
        ...


class MappingInstallationTokenProvider:
    """Reference provider over an injected ``{installation_id: token}`` mapping.

    For tests + the Beta stage. Returns ``""`` for an unknown installation — the
    connector maps an empty token to a typed ``ACTION_NEEDED`` (missing
    credentials) outcome rather than an error, because absence of a brokered token
    is an action-needed signal (install / re-broker), not a crash.
    """

    def __init__(self, tokens: dict[str, str]) -> None:
        self._tokens = dict(tokens)

    def installation_token(self, *, installation_id: str) -> str:
        return self._tokens.get(installation_id, "")
