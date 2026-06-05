# SPDX-License-Identifier: MIT
"""Unit tests for the OpenAI Admin connector (audit events; actor identity dropped)."""

from __future__ import annotations

import json
from pathlib import Path

from connectors.openai_admin.connector import parse_audit_log

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_audit_log_maps_event():
    obs = parse_audit_log(_load("audit_event.json"))
    assert obs.source_ref.ref == "audit_log-abc123"
    assert obs.source_ref.kind == "audit_event"
    assert "project.created" in obs.excerpt
    assert "Acme Reviewer" in obs.excerpt
    assert "via session" in obs.excerpt  # non-PII actor type surfaced


def test_actor_identity_dropped():
    # Fixture carries actor email + ip_address; both must appear NOWHERE (sole control).
    event = _load("audit_event.json")
    assert event["actor"]["session"]["user"]["email"] == "owner@example.com"  # input has PII
    assert event["actor"]["session"]["ip_address"] == "203.0.113.7"
    obs = parse_audit_log(event)
    haystack = " ".join(
        [obs.excerpt, obs.title, obs.author, obs.source_ref.ref, json.dumps(obs.metadata)]
    )
    assert "owner@example.com" not in haystack and "@" not in haystack
    assert "203.0.113.7" not in haystack  # IP dropped (redact does NOT scrub IPv4)
    assert "user_01" not in haystack


def test_blank_event_floors():
    obs = parse_audit_log({})
    assert obs.source_ref.ref == "openai-audit-event"
    assert obs.excerpt  # non-blank ("OpenAI audit event via unknown")
    assert "via unknown" in obs.excerpt
