# SPDX-License-Identifier: MIT
"""Auth layer for the live-poll client (ADR-0012).

The per-request auth strategies (`ApiKeyHeaderAuth`, `BearerAuth`, `BasicAuth`) plus
the `PollError` they raise and the `_reject_control_chars` screen they share. Split
from `poll_client` to keep that module within the Section-4 file-size limit. This
module depends on nothing in `poll_client` (one-directional: `poll_client` →
`poll_auth` → ∅), so there is no import cycle.

Trust posture: a poisoned operator secret must not smuggle a header break, and the
secret must never appear in an error — every auth class screens its inputs for
control chars at construction and raises a value-free `PollError`.
"""

from __future__ import annotations

import base64
from typing import Protocol, runtime_checkable


class PollError(RuntimeError):
    """A live poll failed. Carries ``status`` + ``reason``; the message never
    includes the operator secret/token (token-free, like ``GatewayEmissionError``)."""

    def __init__(self, status: int, reason: str = "") -> None:
        self.status = status
        self.reason = reason
        super().__init__(f"poll failed (status={status}, reason={reason or 'unknown'})")


@runtime_checkable
class PollAuth(Protocol):
    """Per-request auth headers. The operator runtime supplies the resolved secret."""

    def headers(self) -> dict[str, str]: ...


def _reject_control_chars(label: str, value: str) -> None:
    """Reject CR/LF + other control/space chars in a header or token value (a
    poisoned secret or provider token must not smuggle a header break / URL split)."""
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        raise PollError(0, f"{label}_contains_control_char")


class ApiKeyHeaderAuth:
    """API-key-in-header auth (e.g. Anthropic ``x-api-key`` + ``anthropic-version``)."""

    def __init__(self, header: str, value: str, *, extra: dict[str, str] | None = None) -> None:
        self._headers = {header: value, **(extra or {})}
        for key, val in self._headers.items():
            _reject_control_chars(f"auth_header:{key}", val)

    def headers(self) -> dict[str, str]:
        return dict(self._headers)


class BearerAuth:
    """Bearer-token auth (``Authorization: Bearer <token>``) + optional ``extra`` headers
    (e.g. GitHub's ``Accept`` / ``X-GitHub-Api-Version``). CR/LF-rejecting, value-free error."""

    def __init__(self, token: str, *, extra: dict[str, str] | None = None) -> None:
        self._headers = {"Authorization": f"Bearer {token}", **(extra or {})}
        for key, val in self._headers.items():
            _reject_control_chars(f"auth_header:{key}", val)

    def headers(self) -> dict[str, str]:
        return dict(self._headers)


class BasicAuth:
    """HTTP Basic auth (``Authorization: Basic base64(user:pass)``) + optional ``extra``.

    Screens CR/LF in the **raw** ``username``/``password`` *before* base64 (the encoded
    output is always control-char-free, so screening it would be a no-op) and in any
    ``extra`` header values. cursor uses the API key as username with an empty password
    (``base64('KEY:')``); servicenow uses an integration user + password.
    """

    def __init__(
        self, username: str, password: str = "", *, extra: dict[str, str] | None = None
    ) -> None:
        _reject_control_chars("basic_username", username)
        _reject_control_chars("basic_password", password)
        token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        self._headers = {"Authorization": f"Basic {token}", **(extra or {})}
        for key, val in (extra or {}).items():
            _reject_control_chars(f"auth_header:{key}", val)

    def headers(self) -> dict[str, str]:
        return dict(self._headers)


class NoAuth:
    """No-auth strategy for public, unauthenticated reads (e.g. the MCP Registry list,
    OSV). Sends no credential header. Optional ``extra`` headers (CR/LF-screened)."""

    def __init__(self, *, extra: dict[str, str] | None = None) -> None:
        self._headers = dict(extra or {})
        for key, val in self._headers.items():
            _reject_control_chars(f"auth_header:{key}", val)

    def headers(self) -> dict[str, str]:
        return dict(self._headers)
