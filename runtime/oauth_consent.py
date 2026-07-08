# SPDX-License-Identifier: MIT
"""Google OAuth authorization-code consent with a loopback catcher (#227 LD6).

The one-time consent half of the durable Google credential: build the consent URL (PKCE S256 +
``state`` nonce), catch the redirect on an ephemeral ``127.0.0.1`` port, and exchange the code for
a **refresh token** — which ``RefreshTokenSecretResolver`` (FX-RUNTIME-006) then mints access tokens
from on every run. Token-safe like ``google_oauth._mint``: errors are ``(status, reason)`` only,
the response body is capped before parse, ``from None`` severs urllib causes, and the request
handler's ``log_message`` is a NO-OP — the default writes the redirect request line (which carries
the auth code + state) to stderr (audit #231 F2). Stdlib-only; tests inject the transport
(a mock does NOT promote to Live — ADR-0012).
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets as _secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable

from .poll_client import HttpTransport

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105 — an endpoint URL, not a secret
_MAX_RESPONSE = 1 * 1024 * 1024  # cap the token-endpoint body before parse (mirror google_oauth)
_TIMEOUT = 300.0  # seconds to wait for the browser redirect before failing closed


class ConsentError(RuntimeError):
    """Consent/exchange failure. Message is ``(status, reason)`` ONLY — never a code, token, body,
    or client_secret."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"oauth_consent:{reason} (status={status})")
        self.status = status
        self.reason = reason


def pkce_pair() -> tuple[str, str]:
    """A fresh (code_verifier, S256 code_challenge) pair."""
    verifier = base64.urlsafe_b64encode(_secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def consent_url(*, client_id: str, scopes: list[str], redirect_uri: str, state: str,
                code_challenge: str) -> str:
    """The Google consent URL requesting an offline (refresh-token-bearing) grant."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",  # required for a refresh token
        "prompt": "consent",  # re-issue the refresh token even on re-consent
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


class _CatcherHandler(BaseHTTPRequestHandler):
    """Single-purpose redirect catcher. NEVER logs: the request line carries code+state (F2)."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — stdlib signature
        pass  # deliberate no-op — default writes the redirect query string to stderr

    def do_GET(self) -> None:  # noqa: N802 — stdlib handler naming
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        self.server.captured = {k: v[0] for k, v in query.items()}  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Consent received. You may close this tab.")


def open_catcher() -> HTTPServer:
    """A loopback HTTP server on an ephemeral port; serves exactly one request via ``wait_for_code``."""
    server = HTTPServer(("127.0.0.1", 0), _CatcherHandler)
    server.captured = None  # type: ignore[attr-defined]
    return server


def wait_for_code(server: HTTPServer, expected_state: str, *, timeout: float = _TIMEOUT) -> str:
    """Block for the single redirect request; fail closed on timeout / state mismatch / no code."""
    server.timeout = timeout
    try:
        server.handle_request()
    finally:
        server.server_close()
    captured = getattr(server, "captured", None)
    if not isinstance(captured, dict):
        raise ConsentError(0, "redirect_timeout")
    if captured.get("state") != expected_state:
        raise ConsentError(0, "state_mismatch")  # CSRF guard — code (if any) is discarded
    code = captured.get("code", "")
    if not code:
        raise ConsentError(0, "no_code")  # e.g. the operator denied consent (error= param dropped)
    return code


def exchange_code(*, code: str, code_verifier: str, client_id: str, client_secret: str,
                  redirect_uri: str, transport: HttpTransport) -> str:
    """Exchange the auth code for a REFRESH token (the durable credential). Token-free errors."""
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = None
    try:
        response = transport.request("POST", TOKEN_URL, headers=headers, body=body)
    except Exception:  # noqa: BLE001 — a urllib exc message can embed the POST body (the secrets)
        response = None
    if response is None:  # raised OUTSIDE the except -> no __context__ carries the urllib exc
        raise ConsentError(0, "transport_error")
    if response.status != 200:
        raise ConsentError(response.status, "exchange_failed")  # body untrusted — dropped
    if len(response.body) > _MAX_RESPONSE:
        raise ConsentError(0, "oversized_body")
    try:
        parsed = json.loads(response.body)
    except (ValueError, UnicodeDecodeError):
        raise ConsentError(0, "unparseable_body") from None
    token = parsed.get("refresh_token") if isinstance(parsed, dict) else None
    if not isinstance(token, str) or not token:
        raise ConsentError(0, "missing_refresh_token")
    return token


def run_consent(*, client_id: str, client_secret: str, scopes: list[str],
                transport: HttpTransport, open_url_fn: Callable[[str], object],
                timeout: float = _TIMEOUT) -> str:
    """The full consent flow: catcher up -> browser to consent URL -> code -> refresh token."""
    server = open_catcher()
    port = server.server_address[1]
    redirect_uri = f"http://127.0.0.1:{port}/"
    verifier, challenge = pkce_pair()
    state = _secrets.token_urlsafe(16)
    url = consent_url(client_id=client_id, scopes=scopes, redirect_uri=redirect_uri,
                      state=state, code_challenge=challenge)
    print(f"Opening browser for Google consent (redirect on {redirect_uri}).")
    print(f"If no browser opens, visit:\n  {url}")  # client_id/state/challenge — no secret here
    open_url_fn(url)
    code = wait_for_code(server, state, timeout=timeout)
    return exchange_code(code=code, code_verifier=verifier, client_id=client_id,
                         client_secret=client_secret, redirect_uri=redirect_uri,
                         transport=transport)


__all__ = ["AUTH_URL", "TOKEN_URL", "ConsentError", "consent_url", "exchange_code",
           "open_catcher", "pkce_pair", "run_consent", "wait_for_code"]
