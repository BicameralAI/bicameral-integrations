"""Behavioral tests for webhook signature verification + delivery dedup.

Signatures are computed here with stdlib hmac/base64 — independently of the
verifier's internal helpers — so a passing test is not circular.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from adapter.core.webhook_security import (
    DeliveryDedupCache,
    WebhookVerificationError,
    verify_hmac_hex,
    verify_hmac_hex_multi,
    verify_standard_webhook,
)


def _pd_sig(secret: str, body: bytes) -> str:
    return "v1=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_hmac_multi_accepts_single_and_rotated():
    body, secret = b'{"x":1}', "shhh"
    good = _pd_sig(secret, body)
    verify_hmac_hex_multi(header_sig=good, body=body, secret=secret)  # single
    # rotation set: a stale digest under an old secret + the valid one
    rotated = _pd_sig("old-secret", body) + ", " + good
    verify_hmac_hex_multi(header_sig=rotated, body=body, secret=secret)


def test_hmac_multi_fail_closed_paths():
    body, secret = b'{"x":1}', "shhh"
    good = _pd_sig(secret, body)
    for bad in [
        None,                       # missing header
        "",                         # empty header
        "garbage",                  # no v1= entry
        "v1=",                      # bare v1= -> empty candidate must NOT match
        _pd_sig(secret, b'{"x":2}'),  # tampered body
        _pd_sig("wrong", body),     # wrong secret
    ]:
        with pytest.raises(WebhookVerificationError):
            verify_hmac_hex_multi(header_sig=bad, body=body, secret=secret)
    with pytest.raises(WebhookVerificationError):  # empty secret
        verify_hmac_hex_multi(header_sig=good, body=body, secret="")

_SECRET = "whsec_" + base64.b64encode(b"super-secret-key-0123456789").decode()
_BODY = b'{"recording_id": 1, "meeting_title": "x"}'
_TS = 1_780_000_000


def _svix_sig(secret: str, wid: str, ts: int, body: bytes) -> str:
    key = base64.b64decode(secret[len("whsec_") :])
    signed = wid.encode() + b"." + str(ts).encode() + b"." + body
    return "v1," + base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()


def _svix_headers(secret=_SECRET, wid="msg_1", ts=_TS, body=_BODY) -> dict[str, str]:
    return {
        "webhook-id": wid,
        "webhook-timestamp": str(ts),
        "webhook-signature": _svix_sig(secret, wid, ts, body),
    }


# ── Svix verifier ──────────────────────────────────────────────────────────


def test_svix_valid_signature_passes():
    verify_standard_webhook(headers=_svix_headers(), body=_BODY, secret=_SECRET, now=_TS)


def test_svix_tampered_body_fails():
    with pytest.raises(WebhookVerificationError):
        verify_standard_webhook(
            headers=_svix_headers(), body=_BODY + b" ", secret=_SECRET, now=_TS
        )


def test_svix_wrong_secret_fails():
    other = "whsec_" + base64.b64encode(b"different-key-9876543210").decode()
    with pytest.raises(WebhookVerificationError):
        verify_standard_webhook(headers=_svix_headers(), body=_BODY, secret=other, now=_TS)


def test_svix_stale_timestamp_fails():
    with pytest.raises(WebhookVerificationError):
        verify_standard_webhook(
            headers=_svix_headers(), body=_BODY, secret=_SECRET, now=_TS + 3600
        )


def test_svix_key_rotation_one_valid_passes():
    headers = _svix_headers()
    headers["webhook-signature"] = "v1,not-the-right-sig " + headers["webhook-signature"]
    verify_standard_webhook(headers=headers, body=_BODY, secret=_SECRET, now=_TS)


def test_svix_missing_or_empty_secret_fails():
    with pytest.raises(WebhookVerificationError):
        verify_standard_webhook(headers=_svix_headers(), body=_BODY, secret="", now=_TS)


def test_svix_malformed_timestamp_fails():
    headers = _svix_headers()
    headers["webhook-timestamp"] = "abc"
    with pytest.raises(WebhookVerificationError):
        verify_standard_webhook(headers=headers, body=_BODY, secret=_SECRET, now=_TS)


def test_svix_non_utf8_body_verifies_over_bytes():
    body = b"\xff\xfe binary body"  # invalid UTF-8 — must not crash
    headers = _svix_headers(body=body)
    verify_standard_webhook(headers=headers, body=body, secret=_SECRET, now=_TS)


def test_svix_missing_header_fails():
    with pytest.raises(WebhookVerificationError):
        verify_standard_webhook(headers={}, body=_BODY, secret=_SECRET, now=_TS)


# ── Linear hex verifier ──────────────────────────────────────────────────────


def _hex_sig(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_linear_valid_hex_passes():
    verify_hmac_hex(header_sig=_hex_sig("lin-secret", _BODY), body=_BODY, secret="lin-secret")


def test_linear_tampered_fails():
    with pytest.raises(WebhookVerificationError):
        verify_hmac_hex(header_sig=_hex_sig("lin-secret", _BODY), body=_BODY + b"!", secret="lin-secret")


def test_linear_wrong_secret_fails():
    with pytest.raises(WebhookVerificationError):
        verify_hmac_hex(header_sig=_hex_sig("other", _BODY), body=_BODY, secret="lin-secret")


def test_linear_missing_signature_header_fails():
    for bad in (None, ""):
        with pytest.raises(WebhookVerificationError):
            verify_hmac_hex(header_sig=bad, body=_BODY, secret="lin-secret")


# ── Dedup cache ──────────────────────────────────────────────────────────────


def test_dedup_first_seen_then_duplicate():
    cache = DeliveryDedupCache()
    assert cache.is_duplicate("fathom", "id-1") is False
    cache.mark_seen("fathom", "id-1")
    assert cache.is_duplicate("fathom", "id-1") is True


def test_dedup_ttl_expiry_with_injected_clock():
    t = {"now": 1000.0}
    cache = DeliveryDedupCache(ttl_seconds=10, clock=lambda: t["now"])
    cache.mark_seen("fathom", "id-1")
    assert cache.is_duplicate("fathom", "id-1") is True
    t["now"] += 11
    assert cache.is_duplicate("fathom", "id-1") is False


def test_dedup_partition_isolation_and_bounds():
    cache = DeliveryDedupCache(max_entries=2)
    cache.mark_seen("linear", "a")
    cache.mark_seen("linear", "b")
    cache.mark_seen("linear", "c")  # evicts "a" (oldest) — bound holds
    assert cache.is_duplicate("linear", "a") is False
    assert cache.is_duplicate("linear", "c") is True
    # A different partition is isolated.
    assert cache.is_duplicate("linear", "c", partition="other") is False
