# SPDX-License-Identifier: MIT
"""Behavior tests for the Linear connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.capabilities import SourceMode
from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.linear.connector import LinearConnector, parse_event, parse_issue_node

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "issue_created.json"


def _event() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads_as_issue_create_event():
    event = _event()
    assert event["action"] == "create"
    assert event["type"] == "Issue"
    assert event["data"]["identifier"] == "PLAT-204"


def test_parse_builds_title_from_identifier_and_title():
    obs = parse_event(_event())
    assert obs.title.startswith("PLAT-204")
    assert "advisory locks" in obs.title


def test_parse_uses_description_as_excerpt():
    obs = parse_event(_event())
    assert obs.excerpt == _event()["data"]["description"]


def test_parse_falls_back_to_title_when_description_empty():
    event = _event()
    event["data"]["description"] = ""
    obs = parse_event(event)
    assert obs.excerpt == event["data"]["title"]


def test_parse_sets_source_ref_and_kind():
    obs = parse_event(_event())
    assert obs.source_ref.source_id == "linear"
    assert obs.source_ref.ref == "PLAT-204"
    assert obs.source_ref.kind == "issue"
    assert obs.source_ref.url == "https://linear.app/acme/issue/PLAT-204"
    assert obs.author == ""  # actor.name (real-name PII) dropped — SG-2026-06-11-D (deep-audit)


def test_parse_preserves_action_and_type_in_metadata():
    obs = parse_event(_event())
    assert obs.metadata["action"] == "create"
    assert obs.metadata["type"] == "Issue"
    assert obs.metadata["organization_id"] == "org_acme"


def test_end_to_end_normalizes_to_emission():
    event = _event()
    out = normalize(
        LinearConnector().observations(event), adapter_version="linear/0.1.0"
    )
    assert len(out) == 1
    emission = out[0]
    assert isinstance(emission, AdapterEmission)
    assert emission.source_id == "linear"
    assert emission.title.startswith("PLAT-204")
    assert emission.evidence[0].excerpt == event["data"]["description"]


def _fixture(name: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_observations_emits_for_issue_create():
    # Positive control: a valid Issue create still yields exactly one Observation.
    assert len(LinearConnector().observations(_event())) == 1


def test_observations_skips_non_issue_event():
    # A1: a Comment webhook (no identifier/title/description) must NOT emit an empty Observation.
    assert LinearConnector().observations(_fixture("comment_event.json")) == []


def test_observations_skips_remove_action():
    # A2: a delete must NOT surface a now-removed issue as live evidence.
    assert LinearConnector().observations(_fixture("issue_removed.json")) == []


def test_observations_skips_issue_without_identifier():
    # A3: an Issue event lacking `data.identifier` fails the boundary invariant.
    event = {"type": "Issue", "action": "create", "data": {"title": "no id here"}}
    assert LinearConnector().observations(event) == []


def test_parse_issue_node():
    # GraphQL active-fetch path: an Issue node → Observation (distinct from the webhook envelope).
    node = {
        "identifier": "ENG-7", "title": "Refactor poller", "description": "make it cursor-aware",
        "url": "https://linear.app/acme/issue/ENG-7", "updatedAt": "2026-06-02T10:00:00Z",
        "state": {"name": "In Progress"},
        "assignee": {"name": "Alice", "email": "alice@example.com"},  # MUST NOT be surfaced
    }
    obs = parse_issue_node(node)
    assert obs.title.startswith("ENG-7")
    assert obs.excerpt == "make it cursor-aware"
    assert obs.source_ref.kind == "issue"
    assert obs.mode == SourceMode.ACTIVE
    # PII guard: no assignee identity in any surfaced field.
    blob = f"{obs.title} {obs.excerpt} {obs.author} {obs.metadata}"
    assert "alice" not in blob.lower() and "example.com" not in blob
