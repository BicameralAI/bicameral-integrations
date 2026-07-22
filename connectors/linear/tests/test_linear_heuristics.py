# SPDX-License-Identifier: MIT
"""Linear-specific heuristic signals through the universal adapter seam."""

from __future__ import annotations

from adapter.core.pipeline import normalize
from connectors.linear.connector import parse_event
from runtime.gateway_mapping import emission_to_external_envelope


def _update_event() -> dict:
    return {
        "action": "update",
        "type": "Issue",
        "actor": {"type": "oauth_client", "name": "ignored"},
        "createdAt": "2026-07-17T06:00:00Z",
        "data": {
            "id": "issue-1",
            "identifier": "ENG-1",
            "title": "Keep the evidence",
            "description": "This source remains ingested despite administrative noise.",
            "url": "https://linear.app/acme/issue/ENG-1",
        },
        "updatedFrom": {"stateId": "old-state", "assigneeId": "old-user"},
        "webhookId": "linear-delivery-1",
        "organizationId": "org-acme",
    }


def test_linear_signals_are_source_aware_and_fail_open() -> None:
    observation = parse_event(_update_event())
    emission = normalize([observation], adapter_version="linear/0.1.0")[0]

    assert emission.body == observation.excerpt
    assert emission.evidence[0].excerpt == observation.excerpt
    assert [advisory.kind for advisory in emission.advisories] == [
        "generated_sync_event",
        "administrative_only",
    ]
    assert all(advisory.metadata["scope"] == "integration" for advisory in emission.advisories)

    labels = emission_to_external_envelope(emission)["candidate_hints"][0]["labels"]
    assert any(label.startswith("advisory_v1:generated_sync_event:integration:") for label in labels)
    assert any(label.startswith("advisory_v1:administrative_only:integration:") for label in labels)


def test_linear_human_content_without_noise_signals_stays_clean() -> None:
    event = _update_event()
    event["action"] = "create"
    event["actor"] = {"type": "user", "name": "ignored"}
    event["updatedFrom"] = {}

    emission = normalize([parse_event(event)], adapter_version="linear/0.1.0")[0]

    assert emission.advisories == ()
    assert emission.evidence[0].excerpt == event["data"]["description"]
