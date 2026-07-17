# SPDX-License-Identifier: MIT
"""Reusable cross-seam conformance tracing for alpha ingest recordings.

Provider acquisition tests supply sanitized provider captures and their parsed
``Observation`` values. This module records exact checkpoints and a human-readable
phase model showing what data exists before and after each transformation. The
same phase records can drive tests, golden outputs, and Mermaid lifecycle diagrams.
"""

from __future__ import annotations

import html
from collections.abc import Iterable, Mapping
from typing import Any

from adapter.core.emissions import AdapterEmission, AdvisoryResult
from adapter.core.observations import Observation
from adapter.core.pipeline import normalize

from .gateway_mapping import emission_to_external_envelope


def observation_checkpoint(observation: Observation) -> dict[str, Any]:
    return {
        "source_ref": {
            "source_id": observation.source_ref.source_id,
            "ref": observation.source_ref.ref,
            "url": observation.source_ref.url,
            "kind": observation.source_ref.kind,
        },
        "excerpt": observation.excerpt,
        "mode": observation.mode.value,
        "title": observation.title,
        "author": observation.author,
        "timestamp": observation.timestamp,
        "provider_event_id": observation.provider_event_id,
        "provider_resource_id": observation.provider_resource_id,
        "evidence_id": observation.evidence_id,
        "evidence_metadata": observation.evidence_metadata,
        "metadata": observation.metadata,
    }


def advisory_checkpoint(advisory: AdvisoryResult) -> dict[str, Any]:
    return {
        "code": advisory.kind,
        "message": advisory.message,
        "metadata": advisory.metadata,
    }


def emission_checkpoint(emission: AdapterEmission) -> dict[str, Any]:
    provenance = None
    if emission.provenance is not None:
        provenance = {
            "delivery_mode": emission.provenance.delivery_mode,
            "verification": emission.provenance.verification,
            "provider_event_id": emission.provenance.provider_event_id,
            "provider_resource_id": emission.provenance.provider_resource_id,
        }
    return {
        "source_id": emission.source_id,
        "title": emission.title,
        "body": emission.body,
        "emission_type": emission.emission_type,
        "adapter_version": emission.adapter_version,
        "evidence": [
            {
                "source_ref": {
                    "source_id": evidence.source_ref.source_id,
                    "ref": evidence.source_ref.ref,
                    "url": evidence.source_ref.url,
                    "kind": evidence.source_ref.kind,
                },
                "excerpt": evidence.excerpt,
                "author": evidence.author,
                "timestamp": evidence.timestamp,
                "evidence_id": evidence.evidence_id,
                "metadata": evidence.metadata,
            }
            for evidence in emission.evidence
        ],
        "advisories": [advisory_checkpoint(advisory) for advisory in emission.advisories],
        "provenance": provenance,
        "metadata": emission.metadata,
    }


def _short(value: object, *, limit: int = 100) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _advisory_codes(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    codes: list[str] = []
    for item in raw:
        if isinstance(item, Mapping):
            code = str(item.get("code", "")).strip()
            if code:
                codes.append(code)
    return codes


def _capture_display(capture: Mapping[str, Any]) -> list[str]:
    action = str(capture.get("action", "")).strip()
    repository = capture.get("repository")
    repository_name = ""
    if isinstance(repository, Mapping):
        repository_name = str(repository.get("full_name", "")).strip()
    issue = capture.get("issue")
    issue_number = ""
    if isinstance(issue, Mapping):
        issue_number = str(issue.get("number", "")).strip()
    comment = capture.get("comment")
    body = ""
    if isinstance(comment, Mapping):
        body = str(comment.get("body", ""))
    elif isinstance(issue, Mapping):
        body = str(issue.get("body", ""))
    display = []
    if action:
        display.append(f"action: {action}")
    if repository_name:
        display.append(f"repository: {repository_name}")
    if issue_number:
        display.append(f"issue: #{issue_number}")
    if body:
        display.append(f"body: {_short(body)}")
    return display or ["sanitized provider payload"]


def _phase_records(
    *,
    observation: Observation,
    emission: AdapterEmission,
    envelope: dict[str, Any],
    source_capture: Mapping[str, Any] | None,
    delivery_result: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    observation_data = observation_checkpoint(observation)
    emission_data = emission_checkpoint(emission)
    integration_codes = _advisory_codes(observation.metadata.get("advisory_signals"))
    emission_codes = [item["code"] for item in emission_data["advisories"]]
    universal_codes = [code for code in emission_codes if code not in integration_codes]
    provenance = emission_data.get("provenance") or {}
    hints = envelope.get("candidate_hints")
    labels: list[str] = []
    if isinstance(hints, list) and hints and isinstance(hints[0], Mapping):
        raw_labels = hints[0].get("labels", [])
        if isinstance(raw_labels, list):
            labels = [str(label) for label in raw_labels]

    phases: list[dict[str, Any]] = []
    if source_capture is not None:
        phases.append(
            {
                "id": "provider_capture",
                "title": "Sanitized provider capture",
                "function": "provider transport and acquisition gate",
                "data": dict(source_capture),
                "display": _capture_display(source_capture),
                "transformation": {
                    "preserved": ["provider payload bytes for replay and signature verification"],
                    "added": ["capture digest and acquisition context outside this payload"],
                    "removed": ["secrets and direct identifiers during sanitization"],
                    "gate": "authentication, signature, source scope, payload, and binary limits",
                },
            }
        )

    phases.extend(
        [
            {
                "id": "observation",
                "title": "Provider-neutral Observation",
                "function": "provider parser plus integration-specific heuristics",
                "data": observation_data,
                "display": [
                    f"source: {observation.source_ref.source_id}/{observation.source_ref.kind}",
                    f"excerpt: {_short(observation.excerpt)}",
                    f"mode: {observation.mode.value}",
                    "integration signals: " + (", ".join(integration_codes) or "none"),
                ],
                "transformation": {
                    "preserved": ["bounded source text", "provider timestamp", "canonical source URL"],
                    "added": [
                        "stable SourceRef",
                        "provider event and resource identities",
                        "evidence identity",
                        "source-aware advisory signals",
                    ],
                    "removed": ["provider-only fields not admitted to the neutral contract"],
                    "gate": "provider schema and required stable identifiers",
                },
            },
            {
                "id": "adapter_emission",
                "title": "Validated AdapterEmission",
                "function": "adapter.core.pipeline.normalize",
                "data": emission_data,
                "display": [
                    f"emission_type: {emission.emission_type}",
                    f"body: {_short(emission.body)}",
                    "integration advisories: " + (", ".join(integration_codes) or "none"),
                    "universal advisories: " + (", ".join(universal_codes) or "none"),
                    "provenance: "
                    f"{provenance.get('delivery_mode', '')}/{provenance.get('verification', '')}",
                ],
                "transformation": {
                    "preserved": [
                        "source evidence text",
                        "SourceRef",
                        "evidence identity and metadata",
                        "provider delivery identities",
                    ],
                    "added": [
                        "adapter version",
                        "validated provenance",
                        "universal advisory signals",
                        "contract validation result",
                    ],
                    "removed": ["nothing for relevance or noise reasons"],
                    "gate": "neutral emission contract and sensitive-data screen",
                },
            },
            {
                "id": "external_envelope",
                "title": "ExternalIngestEnvelope",
                "function": "runtime.gateway_mapping.emission_to_external_envelope",
                "data": envelope,
                "display": [
                    f"source_system: {envelope.get('source_system', '')}",
                    f"content: {_short(envelope.get('content', ''))}",
                    f"evidence excerpts: {len(envelope.get('evidence', []))}",
                    f"wire labels: {len(labels)}",
                ],
                "transformation": {
                    "preserved": ["source system", "portable source URI", "content", "evidence excerpts"],
                    "added": ["screened advisory and provenance labels"],
                    "removed": [
                        "connector metadata",
                        "evidence metadata and evidence_id",
                        "dimensional confidence surface",
                        "all Bot-owned authority fields",
                    ],
                    "gate": "authority stripping and external-ingest schema",
                },
            },
        ]
    )

    if delivery_result is not None:
        phases.append(
            {
                "id": "delivery_state",
                "title": "Gateway delivery and connector state",
                "function": "GatewaySink plus connector cursor policy",
                "data": dict(delivery_result),
                "display": [
                    f"status: {delivery_result.get('status', '')}",
                    f"cursor verdict: {delivery_result.get('cursor_verdict', '')}",
                    f"cursor: {_short(delivery_result.get('cursor', {}))}",
                ],
                "transformation": {
                    "preserved": ["the exact ExternalIngestEnvelope sent to Bot"],
                    "added": ["delivery receipt", "retry or terminal outcome", "durable connector cursor"],
                    "removed": ["nothing from the delivered evidence"],
                    "gate": "cursor advances only after HTTP 201",
                },
            }
        )
    return phases


def render_mermaid_trace(trace: Mapping[str, Any]) -> str:
    """Render one phase trace as a data-bearing Mermaid flowchart."""
    raw_phases = trace.get("phases")
    if not isinstance(raw_phases, list) or not raw_phases:
        raise ValueError("trace_has_no_phases")

    lines = ["flowchart LR"]
    previous_id = ""
    for index, raw_phase in enumerate(raw_phases):
        if not isinstance(raw_phase, Mapping):
            raise ValueError("trace_phase_invalid")
        phase_id = f"P{index}"
        title = html.escape(str(raw_phase.get("title", phase_id)))
        function = html.escape(str(raw_phase.get("function", "")))
        display_raw = raw_phase.get("display", [])
        display = [html.escape(str(item)) for item in display_raw] if isinstance(display_raw, list) else []
        label_lines = [f"<b>{title}</b>", function, *display]
        label = "<br/>".join(item for item in label_lines if item)
        lines.append(f'    {phase_id}["{label}"]')
        if previous_id:
            transformation = raw_phase.get("transformation", {})
            added: list[str] = []
            removed: list[str] = []
            if isinstance(transformation, Mapping):
                added_raw = transformation.get("added", [])
                removed_raw = transformation.get("removed", [])
                if isinstance(added_raw, list):
                    added = [str(item) for item in added_raw]
                if isinstance(removed_raw, list):
                    removed = [str(item) for item in removed_raw]
            edge_parts = []
            if added:
                edge_parts.append("adds: " + _short(", ".join(added), limit=72))
            if removed:
                edge_parts.append("drops: " + _short(", ".join(removed), limit=72))
            edge_label = html.escape("; ".join(edge_parts) or "transforms")
            lines.append(f'    {previous_id} -->|"{edge_label}"| {phase_id}')
        previous_id = phase_id
    return "\n".join(lines)


def trace_ingest(
    observations: Iterable[Observation],
    *,
    adapter_version: str,
    source_capture: Mapping[str, Any] | None = None,
    delivery_result: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Record exact universal checkpoints and human-readable phase changes.

    Evidence is asserted unchanged between Observation and AdapterEmission. A
    heuristic implementation that mutates or removes evidence therefore fails the
    conformance run instead of quietly improving its dashboard statistics.
    """
    captured = list(observations)
    emissions = normalize(captured, adapter_version=adapter_version)
    if len(captured) != len(emissions):
        raise AssertionError("conformance_count_mismatch")

    traces: list[dict[str, Any]] = []
    for observation, emission in zip(captured, emissions, strict=True):
        if not emission.evidence or emission.evidence[0].excerpt != observation.excerpt:
            raise AssertionError("heuristic_or_normalization_content_loss")
        envelope = emission_to_external_envelope(emission)
        traces.append(
            {
                "observation": observation_checkpoint(observation),
                "emission": emission_checkpoint(emission),
                "external_ingest_envelope": envelope,
                "phases": _phase_records(
                    observation=observation,
                    emission=emission,
                    envelope=envelope,
                    source_capture=source_capture,
                    delivery_result=delivery_result,
                ),
            }
        )
    return traces
