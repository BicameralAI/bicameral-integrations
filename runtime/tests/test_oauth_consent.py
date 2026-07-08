# SPDX-License-Identifier: MIT
"""Behavior tests for the OAuth consent loopback flow (#227 LD6).

The catcher is driven with REAL localhost GETs; the token exchange goes through a stubbed
transport (a mock does NOT promote to Live — ADR-0012). Asserts PKCE/state correctness, the
no-secret-on-stdout/stderr discipline (audit #231 F2), and token-free failure modes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import urllib.parse
import urllib.request

import pytest

from runtime.oauth_consent import (
    ConsentError,
    consent_url,
    exchange_code,
    open_catcher,
    pkce_pair,
    run_consent,
    wait_for_code,
)
from runtime.poll_client import HttpResponse


class _StubTransport:
    def __init__(self, response: HttpResponse) -> None:
        self._response = response
        self.requests: list[tuple] = []

    def request(self, method, url, *, headers, body=None):
        self.requests.append((method, url, headers, body))
        return self._response


def _get_async(url: str) -> None:
    threading.Thread(target=lambda: urllib.request.urlopen(url, timeout=10), daemon=True).start()


def test_pkce_pair_is_s256_of_verifier():
    verifier, challenge = pkce_pair()
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    assert challenge == expected
    assert "=" not in verifier and "=" not in challenge  # unpadded per RFC 7636


def test_consent_url_carries_offline_pkce_params():
    url = consent_url(client_id="cid", scopes=["s1", "s2"], redirect_uri="http://127.0.0.1:9/",
                      state="st", code_challenge="ch")
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert q["response_type"] == ["code"] and q["client_id"] == ["cid"]
    assert q["scope"] == ["s1 s2"] and q["state"] == ["st"]
    assert q["code_challenge"] == ["ch"] and q["code_challenge_method"] == ["S256"]
    assert q["access_type"] == ["offline"]  # a refresh token requires the offline grant


def test_full_consent_flow_returns_refresh_token(capsys):
    transport = _StubTransport(
        HttpResponse(200, json.dumps({"refresh_token": "1//durable"}).encode()))

    def fake_browser(url: str) -> None:
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        _get_async(f"{q['redirect_uri'][0]}?state={urllib.parse.quote(q['state'][0])}"
                   f"&code=4/authcode-zz")

    token = run_consent(client_id="cid", client_secret="cs-shh", scopes=["s"],
                        transport=transport, open_url_fn=fake_browser, timeout=10)
    assert token == "1//durable"
    method, url, headers, body = transport.requests[0]
    form = urllib.parse.parse_qs(body.decode("utf-8"))
    assert form["grant_type"] == ["authorization_code"] and form["code"] == ["4/authcode-zz"]
    assert form["code_verifier"], "PKCE verifier must accompany the exchange"
    out = capsys.readouterr()
    for leaked in ("4/authcode-zz", "cs-shh", "1//durable"):  # F2: code/secret never printed
        assert leaked not in out.out and leaked not in out.err


def test_state_mismatch_fails_closed_token_free():
    server = open_catcher()
    port = server.server_address[1]
    _get_async(f"http://127.0.0.1:{port}/?state=WRONG&code=4/evil")
    with pytest.raises(ConsentError) as exc:
        wait_for_code(server, "expected-state", timeout=10)
    assert "state_mismatch" in str(exc.value)
    assert "4/evil" not in str(exc.value)  # the code is discarded, never surfaced


def test_redirect_without_code_fails_closed():
    server = open_catcher()
    port = server.server_address[1]
    _get_async(f"http://127.0.0.1:{port}/?state=st&error=access_denied")
    with pytest.raises(ConsentError) as exc:
        wait_for_code(server, "st", timeout=10)
    assert "no_code" in str(exc.value)


def test_exchange_failure_is_token_free():
    transport = _StubTransport(HttpResponse(400, b'{"error":"invalid_grant","code":"4/x"}'))
    with pytest.raises(ConsentError) as exc:
        exchange_code(code="4/real-code", code_verifier="v", client_id="cid",
                      client_secret="cs-shh", redirect_uri="http://127.0.0.1:1/",
                      transport=transport)
    msg = str(exc.value)
    assert "exchange_failed" in msg and "status=400" in msg
    for leaked in ("4/real-code", "cs-shh", "invalid_grant"):
        assert leaked not in msg


def test_exchange_missing_refresh_token_fails_closed():
    transport = _StubTransport(
        HttpResponse(200, json.dumps({"access_token": "ya29.only"}).encode()))
    with pytest.raises(ConsentError) as exc:
        exchange_code(code="c", code_verifier="v", client_id="cid", client_secret="cs",
                      redirect_uri="http://127.0.0.1:1/", transport=transport)
    assert "missing_refresh_token" in str(exc.value)  # ~1h-only grants are NOT durable — rejected
