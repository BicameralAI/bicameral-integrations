# SPDX-License-Identifier: MIT
"""Behavioral tests for GitHubConnector webhook verify + dedup (X-Hub-Signature-256)."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from adapter.core.webhook_security import DeliveryDedupCache
from connectors.github.connector import GitHubConnector

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "webhook_pr.json"
_SECRET = "gh-webhook-secret"


def _body() -> bytes:
    return json.dumps(json.loads(_FIXTURE.read_text(encoding="utf-8"))).encode("utf-8")


def _sig(body: bytes) -> str:
    return "sha256=" + hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _headers(body: bytes, delivery: str = "d-1") -> dict[str, str]:
    return {"X-Hub-Signature-256": _sig(body), "X-GitHub-Delivery": delivery}


def test_verify_true_for_valid_signature():
    body = _body()
    assert GitHubConnector(secret=_SECRET).verify(headers=_headers(body), body=body) is True


def test_verify_false_for_tampered_body():
    body = _body()
    assert GitHubConnector(secret=_SECRET).verify(headers=_headers(body), body=body + b" ") is False


def test_verify_false_for_missing_header():
    body = _body()
    assert GitHubConnector(secret=_SECRET).verify(headers={}, body=body) is False


def test_normalize_event_unwraps_envelope_number():
    # The PR number lives at the envelope top level; the unwrap must inject it.
    body = _body()
    out = GitHubConnector(secret=_SECRET).normalize_event(headers=_headers(body), body=body)
    assert len(out) == 1
    assert out[0].source_ref.source_id == "github"
    assert out[0].source_ref.ref == "example-org/example-repo#92"


def test_normalize_event_rejects_bad_signature():
    body = _body()
    conn = GitHubConnector(secret=_SECRET)
    assert conn.normalize_event(headers={"X-Hub-Signature-256": "sha256=bad"}, body=body) == []


def test_normalize_event_dedup_second_delivery_returns_empty():
    body = _body()
    conn = GitHubConnector(secret=_SECRET, dedup=DeliveryDedupCache())
    assert len(conn.normalize_event(headers=_headers(body), body=body)) == 1
    assert conn.normalize_event(headers=_headers(body), body=body) == []
