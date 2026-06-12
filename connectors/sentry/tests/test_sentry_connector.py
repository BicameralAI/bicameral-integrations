# SPDX-License-Identifier: MIT
"""Behavior tests for the Sentry connector and end-to-end normalization."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from adapter.core.webhook_security import DeliveryDedupCache
from connectors.sentry.connector import SentryConnector, parse_issue

_SECRET = "client-secret"


def _signed(payload: dict) -> tuple[dict, bytes]:
    body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {"Sentry-Hook-Signature": sig}, body

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "issue_event.json"


def _event() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads():
    assert _event()["action"] == "created"


def test_parse_unwraps_data_issue():
    obs = parse_issue(_event())
    assert obs.excerpt.startswith("TypeError: NoneType")
    assert obs.source_ref.source_id == "sentry"
    assert obs.source_ref.ref == "4571234567"
    assert obs.source_ref.url.endswith("/issues/4571234567/")
    assert obs.timestamp == "2026-06-03T11:22:33.000000Z"
    assert obs.metadata["action"] == "created"
    assert obs.metadata["level"] == "error"
    assert obs.metadata["short_id"] == "EXAMPLE-PROJECT-7Q"


def test_excerpt_falls_back_culprit_then_short_then_id():
    assert parse_issue({"data": {"issue": {"id": "1", "culprit": "mod.fn"}}}).excerpt == "mod.fn"
    assert parse_issue({"data": {"issue": {"id": "1", "shortId": "P-9"}}}).excerpt == "P-9"


def test_accepts_bare_issue_object():
    obs = parse_issue({"id": "9", "title": "boom"})
    assert obs.excerpt == "boom" and obs.source_ref.ref == "9"


def test_title_and_culprit_redact_and_passed():
    # F1 (medium): the exception message + culprit are redact-and-passed (error messages embed PII/secrets).
    issue = {
        "id": "55",
        "title": "OperationalError: could not connect for user ops@corp.com",
        "culprit": "db.connect(AKIAIOSFODNN7EXAMPLE)",
        "shortId": "PROJ-9",
    }
    obs = parse_issue({"data": {"issue": issue}})
    assert "ops@corp.com" not in obs.title
    assert "ops@corp.com" not in obs.excerpt
    assert "AKIAIOSFODNN7EXAMPLE" not in parse_issue({"data": {"issue": {"id": "1", "culprit": issue["culprit"]}}}).excerpt


def test_opaque_id_floor_not_redacted():
    # The shortId/id floor is opaque — survives when title+culprit are empty.
    obs = parse_issue({"data": {"issue": {"id": "4571234567", "shortId": "PROJ-9"}}})
    assert obs.excerpt == "PROJ-9"
    assert obs.source_ref.ref == "4571234567"


def test_floors_excerpt_when_empty():
    obs = parse_issue({})
    assert obs.excerpt == "sentry-issue" and obs.source_ref.ref == "sentry-issue"
    out = normalize([obs], adapter_version="sentry/0.1.0")
    assert out[0].evidence[0].excerpt.strip()


def test_wrong_typed_title_culprit_do_not_crash():
    # Non-string title/culprit (a truthy int/list) must not crash on .strip().
    obs = parse_issue({"data": {"issue": {"id": "1", "title": 7, "culprit": ["x"]}}})
    assert obs.excerpt == "1"  # falls through to id floor
    out = normalize([obs], adapter_version="sentry/0.1.0")
    assert out[0].source_id == "sentry" and out[0].evidence[0].excerpt.strip()


def test_end_to_end_normalizes():
    out = normalize(SentryConnector().observations(_event()), adapter_version="sentry/0.1.0")
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission) and out[0].source_id == "sentry"


def test_verify_true_on_signed_false_on_tampered():
    c = SentryConnector(secret=_SECRET)
    headers, body = _signed(_event())
    assert c.verify(headers=headers, body=body) is True
    assert c.verify(headers=headers, body=body + b" ") is False          # tampered body
    assert c.verify(headers={}, body=body) is False                      # missing header
    assert SentryConnector(secret="").verify(headers=headers, body=body) is False  # no secret


def test_normalize_event_rejects_bad_sig_and_dedups():
    headers, body = _signed(_event())
    dedup = DeliveryDedupCache()
    c = SentryConnector(secret=_SECRET, dedup=dedup)
    assert c.normalize_event(headers={"Request-ID": "d1"} | headers, body=body)  # 1st: parsed
    # same delivery id again -> deduped to []
    assert c.normalize_event(headers={"Request-ID": "d1"} | headers, body=body) == []
    # bad signature -> []
    assert c.normalize_event(headers={"Sentry-Hook-Signature": "bad"}, body=body) == []


def test_normalize_event_rejects_non_object_json_and_verify_survives_bad_args():
    c = SentryConnector(secret=_SECRET)
    headers, body = _signed([1, 2])  # validly-signed, but JSON is a list not an object
    assert c.normalize_event(headers=headers, body=body) == []
    # caller-contract violations fail closed, not crash
    assert c.verify(headers=None, body=body) is False  # type: ignore[arg-type]
    assert c.verify(headers=headers, body="notbytes") is False  # type: ignore[arg-type]


def test_normalize_event_processes_when_no_delivery_id():
    # No Request-ID and an empty-id payload -> best-effort dedup must NOT drop it.
    payload = {"data": {"issue": {"title": "boom"}}}
    headers, body = _signed(payload)
    c = SentryConnector(secret=_SECRET, dedup=DeliveryDedupCache())
    out = c.normalize_event(headers=headers, body=body)
    assert len(out) == 1 and out[0].excerpt == "boom"
