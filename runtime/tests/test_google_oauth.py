# SPDX-License-Identifier: MIT
"""Behavior tests for the Google OAuth refresh-token resolver (FX-RUNTIME-006).

Driven through an injected transport — no live network, no real secret (a mock does NOT promote to
Live, ADR-0012). Includes the L2 secret-leak backstops: no refresh_token/client_secret in any error,
traceback, or delegated resolve.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse

import pytest

from runtime.google_oauth import OAuthRefreshError, RefreshTokenSecretResolver
from runtime.poll_client import HttpResponse
from runtime.secrets import MappingSecretResolver

_RT = "rt_SECRET_refresh_value"
_CS = "cs_SECRET_client_value"


class _FakeTransport:
    def __init__(self, response: HttpResponse | None = None, raises: Exception | None = None) -> None:
        self._response = response
        self._raises = raises
        self.calls: list = []

    def request(self, method, url, *, headers, body=None):
        self.calls.append((method, url, headers, body))
        if self._raises is not None:
            raise self._raises
        assert self._response is not None
        return self._response


class _Clock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def _resolver(transport, *, base=None, clock=None) -> RefreshTokenSecretResolver:
    return RefreshTokenSecretResolver(
        target_key="google_drive", refresh_token=_RT, client_id="ci", client_secret=_CS,
        transport=transport, base=base, clock=clock,
    )


def _ok(token="ya29.x", expires_in=3600) -> HttpResponse:
    payload = {"access_token": token, "expires_in": expires_in, "token_type": "Bearer"}
    return HttpResponse(200, json.dumps(payload).encode("utf-8"))


def test_refresh_mints_token():
    t = _FakeTransport(_ok())
    assert _resolver(t).resolve("google_drive") == "ya29.x"
    method, url, _headers, body = t.calls[0]
    assert method == "POST" and url == "https://oauth2.googleapis.com/token"
    parsed = urllib.parse.parse_qs(body.decode())
    assert parsed["grant_type"] == ["refresh_token"] and parsed["refresh_token"] == [_RT]


def test_caches_until_expiry():
    t = _FakeTransport(_ok(expires_in=3600))
    clock = _Clock(1000.0)
    r = _resolver(t, clock=clock)
    assert r.resolve("google_drive") == "ya29.x"
    assert r.resolve("google_drive") == "ya29.x"  # within window — cached
    assert len(t.calls) == 1
    clock.t = 1000.0 + 3600 - 90  # still inside the window (expiry = now+3600-60 = 4540; 4510 < 4540)
    r.resolve("google_drive")
    assert len(t.calls) == 1
    clock.t = 1000.0 + 3600  # past expiry-skew (4600 >= 4540) → re-mint
    r.resolve("google_drive")
    assert len(t.calls) == 2


def test_delegates_other_keys():
    t = _FakeTransport(_ok())
    r = _resolver(t, base=MappingSecretResolver({"linear": "L"}))
    assert r.resolve("linear") == "L"
    assert t.calls == []  # delegated path never mints / never touches the target's secrets


def test_invalid_grant_400_token_free():
    t = _FakeTransport(HttpResponse(400, b'{"error":"invalid_grant"}'))
    with pytest.raises(OAuthRefreshError) as exc:
        _resolver(t).resolve("google_drive")
    msg = str(exc.value)
    assert _RT not in msg and _CS not in msg and "invalid_grant" not in msg


def test_transport_exception_drops_cause():
    t = _FakeTransport(raises=urllib.error.URLError(f"connect failed with body {_CS}"))
    with pytest.raises(OAuthRefreshError) as exc:
        _resolver(t).resolve("google_drive")
    assert exc.value.__cause__ is None  # raise ... from None severs the leaking cause
    chain = f"{exc.value} {exc.value.__cause__} {exc.value.__context__}"
    assert _RT not in chain and _CS not in chain


@pytest.mark.parametrize("payload", [
    {"expires_in": 3600},          # no access_token
    [{"access_token": "ya29.x"}],  # non-dict (top-level array)
    {"access_token": 123},         # non-string access_token
    "a-bare-string",
])
def test_missing_access_token_fails_closed(payload):
    t = _FakeTransport(HttpResponse(200, json.dumps(payload).encode()))
    with pytest.raises(OAuthRefreshError) as exc:
        _resolver(t).resolve("google_drive")
    assert exc.value.reason == "missing_access_token"
    assert _CS not in str(exc.value) and _RT not in str(exc.value)


def test_oversized_body_fails_closed(monkeypatch):
    import runtime.google_oauth as goauth
    monkeypatch.setattr(goauth, "_MAX_RESPONSE", 10)
    t = _FakeTransport(_ok())  # body > 10 bytes
    with pytest.raises(OAuthRefreshError) as exc:
        _resolver(t).resolve("google_drive")
    assert exc.value.reason == "oversized_body"
    assert _CS not in str(exc.value) and _RT not in str(exc.value)


def test_missing_expires_in_remints():
    t = _FakeTransport(HttpResponse(200, json.dumps({"access_token": "ya29.x"}).encode()))
    clock = _Clock(1000.0)
    r = _resolver(t, clock=clock)
    assert r.resolve("google_drive") == "ya29.x"  # works once
    r.resolve("google_drive")  # absent expires_in -> ttl 0 -> already expired -> re-mint
    assert len(t.calls) == 2


def test_control_char_input_rejected():
    from runtime.poll_auth import PollError
    with pytest.raises(PollError):
        RefreshTokenSecretResolver(target_key="google_drive", refresh_token="bad\r\ntoken",
                                   client_id="ci", client_secret=_CS, transport=_FakeTransport(_ok()))
