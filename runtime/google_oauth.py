# SPDX-License-Identifier: MIT
"""Google OAuth refresh-token resolver (FX-RUNTIME-006) — the durable stdlib Google auth path.

Mints a fresh Google access token from a refresh token on each ``resolve(target_key)``, caching until
the returned ``expires_in``. The refresh-token grant is a **plain form POST** (no RSA/JWT signing —
research #125 F2), so this is **stdlib-only**; a service-account token needs RS256 (research #125 F3) and
stays operator-runtime (``google-auth``), NOT built here.

Token-safe (the ``GatewaySink`` discipline): the ``refresh_token`` + ``client_secret`` never appear in any
error, traceback (``raise … from None`` severs the urllib cause whose message embeds the POST body), log,
or a delegated (non-target) resolve. Fail-closed on every untrusted edge. The real network call is
operator-run (``UrllibTransport`` default); tests inject a transport (a mock does NOT promote to Live —
ADR-0012).
"""

from __future__ import annotations

import json
import time
import urllib.parse
from typing import Callable

from .poll_auth import _reject_control_chars
from .poll_client import HttpTransport, UrllibTransport
from .secrets import SecretResolver

_TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105 — an endpoint URL, not a secret
_MAX_RESPONSE = 1 * 1024 * 1024  # cap the token-endpoint body before parse (this module owns the cap;
#                                  the recorded transport does NOT cap — mirror doc_fetch)
_SKEW = 60.0  # refresh this many seconds before the stated expiry


class OAuthRefreshError(RuntimeError):
    """Raised when a Google token refresh fails. The message is ``(status, reason)`` ONLY — never the
    response body, URL, ``refresh_token``, or ``client_secret``."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"oauth_refresh:{reason} (status={status})")
        self.status = status
        self.reason = reason


class RefreshTokenSecretResolver:
    """``SecretResolver`` that mints a fresh Google access token for ``target_key`` from a refresh token;
    delegates every other key to ``base``. Stdlib-only, token-safe, fail-closed, in-memory cache only."""

    def __init__(
        self,
        *,
        target_key: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        transport: HttpTransport | None = None,
        base: SecretResolver | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        for name, val in (("refresh_token", refresh_token), ("client_id", client_id),
                          ("client_secret", client_secret)):
            _reject_control_chars(f"google_oauth:{name}", val)  # token-free label on a poisoned input
        self._target = target_key
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._transport = transport or UrllibTransport()
        self._base = base
        self._clock = clock or time.time
        self._token = ""  # nosec B105 — empty in-memory token cache, not a secret literal
        self._expiry = 0.0

    def resolve(self, connector_id: str) -> str:
        if connector_id != self._target:  # delegate — never touches this resolver's secrets
            return self._base.resolve(connector_id) if self._base is not None else ""
        now = self._clock()
        if self._token and now < self._expiry:
            return self._token
        self._token, ttl = self._mint()
        self._expiry = now + ttl - _SKEW
        return self._token

    def _mint(self) -> tuple[str, float]:
        body = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
        }).encode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = None
        try:
            response = self._transport.request("POST", _TOKEN_URL, headers=headers, body=body)
        except Exception:  # noqa: BLE001 — a urllib exc message can embed the POST body (the secrets)
            response = None
        if response is None:  # raised OUTSIDE the except → no __context__/__cause__ carries the urllib exc
            raise OAuthRefreshError(0, "transport_error")
        if response.status != 200:
            raise OAuthRefreshError(response.status, "refresh_failed")  # body untrusted — dropped
        if len(response.body) > _MAX_RESPONSE:
            raise OAuthRefreshError(0, "oversized_body")
        try:
            parsed = json.loads(response.body)
        except (ValueError, UnicodeDecodeError):
            raise OAuthRefreshError(0, "unparseable_body") from None
        token = parsed.get("access_token") if isinstance(parsed, dict) else None
        if not isinstance(token, str) or not token:
            raise OAuthRefreshError(0, "missing_access_token")
        exp = parsed.get("expires_in")
        ttl = float(exp) if isinstance(exp, (int, float)) and not isinstance(exp, bool) else 0.0
        return token, ttl  # absent/non-numeric expires_in -> ttl 0 -> re-mint next call (never stale)


__all__ = ["RefreshTokenSecretResolver", "OAuthRefreshError"]
