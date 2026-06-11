# SPDX-License-Identifier: MIT
"""Behavior tests for the webhook_risk mod."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.contract import run_mod, validate_manifest
from mods.webhook_risk import WebhookRiskMod

_MOD_DIR = Path(__file__).resolve().parents[1]


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def _emission(body: str) -> AdapterEmission:
    ev = SourceEvidence(
        source_ref=SourceRef(source_id="github", ref="o/r#1", url="https://x/1", kind="pull_request"),
        excerpt=body, author="dev")
    return AdapterEmission(source_id="github", title="change", body=body, evidence=(ev,))


def test_manifest_acceptance():
    validate_manifest(_manifest(), WebhookRiskMod())


def test_no_webhook_context_no_output():
    assert WebhookRiskMod().evaluate([_emission("Refactor the auth handler")]) == []


def test_webhook_context_only_annotates():
    out = WebhookRiskMod().evaluate([_emission("Add a webhook receiver for events")])
    kinds = [e.output_type for e in out]
    assert kinds == ["source_evidence_annotation"]  # context but no named risk -> no route


def test_named_risk_routes_security():
    out = run_mod(WebhookRiskMod(), [_emission("webhook handler skips signature, replay possible")],
                  _manifest())
    route = [e for e in out if e.output_type == "routing_hint"]
    assert route and route[0].routing_hint is not None
    assert route[0].routing_hint.role == "security" and route[0].routing_hint.priority == "high"
