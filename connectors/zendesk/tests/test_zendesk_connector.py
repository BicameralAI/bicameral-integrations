# SPDX-License-Identifier: MIT
"""Behavioral tests for the Zendesk parse surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapter.core.capabilities import SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.pipeline import EmissionContractError, normalize
from connectors.zendesk.connector import ZendeskConnector, parse_ticket

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ticket_event.json"


def _event() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_parse_ticket_maps_subject_and_metadata():
    obs = parse_ticket(_event())
    assert obs.source_ref.source_id == "zendesk"
    assert obs.source_ref.ref == "4571"
    assert obs.excerpt.startswith("Login fails after password reset")  # subject preserved
    assert obs.title == "Login fails after password reset"
    assert obs.mode == SourceMode.WEBHOOK
    assert obs.metadata["status"] == "open"
    assert obs.metadata["priority"] == "high"
    assert obs.metadata["via"] == "web"


def test_requester_id_opaque_passes_redact_unchanged():
    # purple-team #170 (zd-1): a numeric requester id passes redact() byte-for-byte (opacity preserved).
    obs = parse_ticket(_event())
    assert obs.author == "9001"


def test_email_shaped_requester_id_is_redacted():
    # purple-team #170 (zd-1): a stray email/phone in requester_id is scrubbed — opacity enforced, not trusted.
    event = _event()
    event["detail"]["requester_id"] = "agent-jane@support.com"
    obs = parse_ticket(event)
    assert "jane@support.com" not in obs.author


def test_ticket_body_redacted_and_emitted():
    # Body (description) now emitted via redact-and-pass, with PII scrubbed.
    obs = parse_ticket(_event())
    assert "Customer cannot log in" in obs.excerpt  # body text emitted
    assert "user@example.com" not in obs.excerpt and "@" not in obs.excerpt
    assert "AKIAABCDEFGHIJKLMNOP" not in obs.excerpt
    assert "[redacted:email]" in obs.excerpt and "[redacted:secret]" in obs.excerpt


def test_raw_body_would_be_rejected_then_redacted_passes():
    # Companion non-vacuity: the RAW description trips FX-SEC-001 (secret) -> rejected;
    # the connector's redacted emission passes the same gate.
    raw = _event()["detail"]["description"]
    bad = Observation(source_ref=SourceRef(source_id="zendesk", ref="x"), excerpt=raw)
    with pytest.raises(EmissionContractError):
        normalize([bad], adapter_version="x")
    normalize(ZendeskConnector().observations(_event()), adapter_version="x")  # no raise


def test_subject_only_when_no_body():
    event = {"subject": "zen:ticket:8899", "detail": {"id": "8899", "subject": "Billing question"}}
    obs = parse_ticket(event)
    assert obs.excerpt == "Billing question"  # subject only when no description


def test_parse_ticket_id_from_subject_when_detail_id_missing():
    event = {"subject": "zen:ticket:8899", "detail": {"subject": "Billing question"}}
    obs = parse_ticket(event)
    assert obs.source_ref.ref == "8899"
    assert obs.excerpt == "Billing question"


def test_parse_ticket_floors_when_empty():
    obs = parse_ticket({})
    assert obs.source_ref.ref == "zendesk-ticket"
    assert obs.excerpt == "zendesk-ticket"  # non-empty floor (contract)


def test_parse_ticket_defends_wrong_types():
    # detail not a dict, fields wrong-typed -> floors, no crash (SG-I).
    obs = parse_ticket({"detail": ["nope"], "type": 7, "subject": None})
    assert obs.source_ref.ref == "zendesk-ticket"
    assert obs.excerpt == "zendesk-ticket"


def test_connector_observations_wraps_parse():
    out = ZendeskConnector().observations(_event())
    assert len(out) == 1 and out[0].source_ref.ref == "4571"
