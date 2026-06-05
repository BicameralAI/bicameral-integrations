# SPDX-License-Identifier: MIT
"""Behavioral tests for the Zendesk parse surface."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.capabilities import SourceMode
from connectors.zendesk.connector import ZendeskConnector, parse_ticket

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ticket_event.json"


def _event() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_parse_ticket_maps_subject_and_metadata():
    obs = parse_ticket(_event())
    assert obs.source_ref.source_id == "zendesk"
    assert obs.source_ref.ref == "4571"
    assert obs.excerpt == "Login fails after password reset"
    assert obs.title == "Login fails after password reset"
    assert obs.mode == SourceMode.WEBHOOK
    assert obs.metadata["status"] == "open"
    assert obs.metadata["priority"] == "high"
    assert obs.metadata["via"] == "web"


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
