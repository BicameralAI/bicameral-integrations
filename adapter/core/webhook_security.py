"""Webhook signature verification + delivery dedup (provider-neutral primitives).

Two verification schemes and a replay-dedup cache, ported in discipline from
``bicameral-mcp`` (``webhooks/github.py`` + ``webhooks/dedup.py``):

- ``verify_standard_webhook`` — Standard Webhooks / Svix (Fathom): HMAC-SHA256
  over the bytes ``id.timestamp.body`` with a ``whsec_``-base64 key, base64
  signature, space-delimited ``v1,<b64>`` list (key rotation), timestamp
  tolerance.
- ``verify_hmac_hex`` — plain hex HMAC-SHA256 over the raw body (Linear's
  ``Linear-Signature``).
- ``DeliveryDedupCache`` — bounded partitioned LRU + TTL replay cache.

Fail-closed discipline: every failure mode — missing/empty secret, missing or
malformed header, non-numeric timestamp, stale timestamp, mismatch — raises
``WebhookVerificationError`` (the single type a connector maps to ``verify``
== False). Comparisons are constant-time (``hmac.compare_digest``). Callers
verify BEFORE parsing the body and dedup only AFTER verifying.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import threading
import time
from collections import OrderedDict


class WebhookVerificationError(Exception):
    """Webhook verification failed. A connector maps this to ``verify() -> False``."""


def header_value(headers: dict[str, str], name: str) -> str | None:
    """Case-insensitive header lookup (HTTP header names are case-insensitive)."""
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def _parse_svix_headers(headers: dict[str, str]) -> tuple[str, int, str]:
    """Return (id, timestamp:int, signature-header) or raise (fail-closed)."""
    wid = header_value(headers, "webhook-id")
    wts = header_value(headers, "webhook-timestamp")
    wsig = header_value(headers, "webhook-signature")
    if not wid or not wts or not wsig:
        raise WebhookVerificationError("missing webhook-id/timestamp/signature header")
    try:
        ts = int(wts)
    except (TypeError, ValueError) as exc:
        raise WebhookVerificationError(f"non-numeric webhook-timestamp: {wts!r}") from exc
    return wid, ts, wsig


def _svix_expected_sig(key: bytes, wid: str, ts: int, body: bytes) -> str:
    """base64(HMAC-SHA256(key, b"id.timestamp.body")) — signed content is bytes."""
    signed = wid.encode("utf-8") + b"." + str(ts).encode("ascii") + b"." + body
    return base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode("ascii")


def verify_standard_webhook(
    *,
    headers: dict[str, str],
    body: bytes,
    secret: str,
    now: float | None = None,
    tolerance_s: int = 300,
) -> None:
    """Verify a Standard Webhooks / Svix signature, or raise ``WebhookVerificationError``."""
    if not secret or not secret.startswith("whsec_"):
        raise WebhookVerificationError("missing or malformed webhook secret")
    try:
        key = base64.b64decode(secret[len("whsec_") :], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise WebhookVerificationError("webhook secret is not valid base64") from exc
    wid, ts, sig_header = _parse_svix_headers(headers)
    clock = time.time() if now is None else now
    if abs(clock - ts) > tolerance_s:
        raise WebhookVerificationError("webhook-timestamp outside tolerance")
    expected = _svix_expected_sig(key, wid, ts, body)
    for part in sig_header.split(" "):
        _, _, candidate = part.partition(",")
        if candidate and hmac.compare_digest(candidate, expected):
            return
    raise WebhookVerificationError("no matching signature")


def verify_hmac_hex(*, header_sig: str | None, body: bytes, secret: str) -> None:
    """Verify a hex HMAC-SHA256 over the raw body, or raise ``WebhookVerificationError``."""
    if not secret:
        raise WebhookVerificationError("no webhook secret configured")
    if not isinstance(header_sig, str) or not header_sig:
        raise WebhookVerificationError("missing signature header")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(header_sig, expected):
        raise WebhookVerificationError("signature mismatch")


def verify_hmac_hex_multi(*, header_sig: str | None, body: bytes, secret: str) -> None:
    """Verify a comma-separated ``v1=<hex>`` HMAC-SHA256 set (key rotation), or raise.

    PagerDuty's ``X-PagerDuty-Signature`` sends a digest under every active
    signing secret during rotation: ``v1=<hex>,v1=<hex>``. Accept if ANY ``v1=``
    candidate matches (constant-time); fail-closed on every other path. The
    expected digest is always a 64-char hexdigest, so a bare ``v1=`` (empty
    candidate) can never match.
    """
    if not secret:
        raise WebhookVerificationError("no webhook secret configured")
    if not isinstance(header_sig, str) or not header_sig:
        raise WebhookVerificationError("missing signature header")
    candidates = [
        part.strip()[3:] for part in header_sig.split(",") if part.strip().startswith("v1=")
    ]
    if not candidates:
        raise WebhookVerificationError("no v1= signature candidate")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(candidate, expected) for candidate in candidates):
        raise WebhookVerificationError("no matching signature")


class DeliveryDedupCache:
    """Bounded, partitioned LRU + TTL cache for webhook delivery dedup.

    One bucket per ``(source, partition)``: oldest entry dropped past
    ``max_entries``; entries older than ``ttl_seconds`` are not hits; the
    least-recently-written bucket is dropped past ``max_partitions``. The
    ``clock`` is injectable for deterministic TTL tests. Ported from
    ``bicameral-mcp/webhooks/dedup.py``.
    """

    def __init__(
        self,
        *,
        max_entries: int = 1000,
        max_partitions: int = 512,
        ttl_seconds: int = 86400,
        clock=time.time,
    ) -> None:
        self._max = max_entries
        self._max_partitions = max_partitions
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets: OrderedDict[tuple[str, str | None], OrderedDict[str, float]] = OrderedDict()

    def is_duplicate(self, source: str, delivery_id: str, *, partition: str | None = None) -> bool:
        if not delivery_id:
            return False
        with self._lock:
            bucket = self._buckets.get((source, partition))
            if bucket is None:
                return False
            entry = bucket.get(delivery_id)
            if entry is None:
                return False
            if self._clock() - entry > self._ttl:
                bucket.pop(delivery_id, None)
                return False
            return True

    def mark_seen(self, source: str, delivery_id: str, *, partition: str | None = None) -> None:
        if not delivery_id:
            return
        key = (source, partition)
        now = self._clock()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = OrderedDict()
                self._buckets[key] = bucket
                while len(self._buckets) > self._max_partitions:
                    self._buckets.popitem(last=False)
            else:
                self._buckets.move_to_end(key)
            bucket[delivery_id] = now
            bucket.move_to_end(delivery_id)
            while len(bucket) > self._max:
                bucket.popitem(last=False)
