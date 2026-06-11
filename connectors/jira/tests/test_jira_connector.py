# SPDX-License-Identifier: MIT
"""Behavior tests for the Jira connector and end-to-end normalization."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from adapter.core.webhook_security import DeliveryDedupCache
from connectors.jira.connector import JiraConnector, parse_issue

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "issue_created.json"
_SECRET = "jira-webhook-secret"


def _event() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _signed(payload: dict) -> tuple[dict, bytes]:
    body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature": "sha256=" + sig}, body


def test_fixture_loads():
    assert _event()["webhookEvent"] == "jira:issue_created"


def test_parse_maps_summary_key_metadata():
    obs = parse_issue(_event())
    assert obs.excerpt == "Checkout button unresponsive on mobile"
    assert obs.title == obs.excerpt
    assert obs.source_ref.source_id == "jira"
    assert obs.source_ref.ref == "PROJ-123"
    assert obs.source_ref.url.endswith("/issue/10002")
    assert obs.author == ""  # actor displayName (a real name) dropped, PII-safe (SG-2026-06-11-D)
    assert obs.timestamp == "2026-06-04T00:05:00.000+0000"
    assert obs.metadata["status"] == "To Do"
    assert obs.metadata["issuetype"] == "Bug"
    assert obs.metadata["project"] == "PROJ"


def test_summary_redacted_and_pass():
    # the summary is free-text -> redact-and-pass scrubs an embedded email; non-PII text survives.
    ev = {"issue": {"key": "K-9", "fields": {"summary": "Reopen for bob@corp.com per ticket"}}}
    obs = parse_issue(ev)
    assert "bob@corp.com" not in obs.excerpt
    assert "Reopen for" in obs.excerpt


def test_excerpt_never_uses_adf_description():
    # description is an ADF object — excerpt must be summary, never the ADF dict.
    ev = {"issue": {"key": "K-1", "fields": {"summary": "S", "description": {"type": "doc"}}}}
    assert parse_issue(ev).excerpt == "S"
    # no summary -> key floor (NOT the ADF description)
    ev2 = {"issue": {"key": "K-2", "fields": {"description": {"type": "doc"}}}}
    assert parse_issue(ev2).excerpt == "K-2"


def test_floor_and_wrong_typed_fields_do_not_crash():
    assert parse_issue({}).excerpt == "jira-issue"
    assert parse_issue({"issue": [1, 2]}).excerpt == "jira-issue"  # issue non-dict
    assert parse_issue({"issue": {"key": "K", "fields": None}}).excerpt == "K"  # fields null
    assert parse_issue({"issue": {"key": "K", "fields": {"status": "notadict"}}}).metadata["status"] == ""
    assert parse_issue({"issue": {"key": "K"}, "user": "notadict"}).author == ""
    int_ts = parse_issue({"issue": {"key": "K"}, "timestamp": 1717459200000})
    assert int_ts.timestamp == "1717459200000"


def test_whitespace_key_floors_excerpt_not_blank():
    # whitespace-only key/id is truthy but must NOT yield a blank excerpt.
    obs = parse_issue({"issue": {"key": "   ", "id": "   ", "fields": {}}})
    assert obs.excerpt == "jira-issue" and obs.source_ref.ref == "jira-issue"
    out = normalize([obs], adapter_version="jira/0.1.0")
    assert out[0].evidence[0].excerpt.strip()


def test_verify_true_on_signed_false_on_tampered():
    c = JiraConnector(secret=_SECRET)
    headers, body = _signed(_event())
    assert c.verify(headers=headers, body=body) is True
    # raw hex without the sha256= prefix also verifies
    bare = {"X-Hub-Signature": headers["X-Hub-Signature"][len("sha256="):]}
    assert c.verify(headers=bare, body=body) is True
    assert c.verify(headers=headers, body=body + b" ") is False        # tampered
    assert c.verify(headers={"X-Hub-Signature": "sha256="}, body=body) is False  # empty candidate
    assert c.verify(headers={}, body=body) is False                    # missing header
    assert JiraConnector(secret="").verify(headers=headers, body=body) is False  # no secret
    assert c.verify(headers=["notadict"], body=body) is False  # type: ignore[arg-type]  # non-dict headers fail closed


def test_normalize_event_rejects_bad_sig_dedups_processes_no_id():
    headers, body = _signed(_event())
    dedup = DeliveryDedupCache()
    c = JiraConnector(secret=_SECRET, dedup=dedup)
    h = {"X-Atlassian-Webhook-Identifier": "d-1"} | headers
    assert c.normalize_event(headers=h, body=body)            # 1st parsed
    assert c.normalize_event(headers=h, body=body) == []      # deduped
    assert c.normalize_event(headers={"X-Hub-Signature": "sha256=bad"}, body=body) == []
    # no delivery id derivable: falls back to issue.id from the body; still processes
    out = c.normalize_event(headers=headers, body=body)
    assert len(out) == 1 and out[0].source_ref.ref == "PROJ-123"


def test_end_to_end_normalizes():
    out = normalize(JiraConnector().observations(_event()), adapter_version="jira/0.1.0")
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission) and out[0].source_id == "jira"
