# SPDX-License-Identifier: MIT
"""Unit tests for the ServiceNow connector (incident parse + redaction; caller dropped)."""

from __future__ import annotations

import json
from pathlib import Path

from connectors.servicenow.connector import parse_incident

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_incident_maps_metadata():
    obs = parse_incident(_load("incident.json"))
    assert obs.source_ref.ref == "INC0012345"
    assert obs.source_ref.kind == "incident"
    assert "SSO login fails" in obs.excerpt
    assert "state=2" in obs.excerpt and "priority=3" in obs.excerpt


def test_description_secret_and_email_redacted():
    obs = parse_incident(_load("incident.json"))
    assert "AKIAABCDEFGHIJKLMNOP" not in obs.excerpt
    assert "admin@example.com" not in obs.excerpt
    assert "[redacted:secret]" in obs.excerpt and "[redacted:email]" in obs.excerpt


def test_caller_identity_dropped():
    # The fixture carries caller_id with a name + email; it must appear nowhere.
    record = _load("incident.json")
    assert "jane.doe@example.com" in record["caller_id"]  # input has the PII
    obs = parse_incident(record)
    haystack = " ".join(
        [obs.excerpt, obs.title, obs.author, obs.source_ref.ref, json.dumps(obs.metadata)]
    )
    assert "Jane Doe" not in haystack
    assert "jane.doe@example.com" not in haystack


def test_blank_incident_floors():
    obs = parse_incident({})
    assert obs.source_ref.ref == "servicenow-incident"
    assert obs.excerpt == "servicenow-incident"  # floored, non-blank


def test_parse_incident_defends_nonstr_fields():
    # #56: non-str fields must not crash .strip().
    obs = parse_incident({"short_description": 123, "state": ["x"], "priority": {"p": 1}, "number": 5})
    assert obs.source_ref.source_id == "servicenow"
    assert obs.source_ref.ref == "servicenow-incident"  # non-str number floored
