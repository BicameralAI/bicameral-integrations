# SPDX-License-Identifier: MIT
"""Reusable cross-seam conformance tracing for alpha ingest recordings.

Provider acquisition tests supply real, sanitized ``Observation`` values. This
module records the universal checkpoints from Observation through normalized
emission, fail-open advisories, and authority-stripped gateway envelope.
"""

from __future__ import annotations

from typing import Any, Iterable

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


def trace_ingest(
    observations: Iterable[Observation], *, adapter_version: str
) -> list[dict[str, Any]]:
    """Record exact universal checkpoints for a provider capture.

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
        traces.append(
            {
                "observation": observation_checkpoint(observation),
                "emission": emission_checkpoint(emission),
                "external_ingest_envelope": emission_to_external_envelope(emission),
            }
        )
    return traces
