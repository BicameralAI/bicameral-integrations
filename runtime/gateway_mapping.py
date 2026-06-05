# SPDX-License-Identifier: MIT
"""Map an ``AdapterEmission`` to the gateway v1 ``IngestRequest`` (ADR-0012).

The wire contract is pinned in ``runtime/schemas/ingest_request_v1.schema.json``
(vendored from ``bicameral-bot:protocol/schemas/v1/``). The three required fields
(``title``, ``description``, ``source``) are floored to a non-empty value.
Dimensional confidence (``ConfidenceSurface``) is deliberately **NOT** collapsed
into the v1 scalar ``confidence`` (SG-2026-06-02-B) — each evidence item carries
only its excerpt; the gateway/daemon owns the judgment. The decision ``level``
is the daemon's call, so it is omitted.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission


def _first_excerpt(emission: AdapterEmission) -> str:
    for ev in emission.evidence:
        text = (ev.excerpt or "").strip()
        if text:
            return text
    return ""


def _source(emission: AdapterEmission) -> str:
    """A non-empty portable source identifier (URI preferred, else source:ref)."""
    for ev in emission.evidence:
        url = (ev.source_ref.url or "").strip()
        if url:
            return url
    for ev in emission.evidence:
        ref = (ev.source_ref.ref or "").strip()
        if ref:
            return f"{emission.source_id}:{ref}"
    return emission.source_id


def emission_to_ingest_request(emission: AdapterEmission) -> dict:
    """Map an ``AdapterEmission`` into a v1 ``IngestRequest`` dict."""
    title = emission.title.strip() or _first_excerpt(emission) or emission.source_id
    description = (
        emission.body.strip()
        or emission.title.strip()
        or _first_excerpt(emission)
        or emission.source_id
    )
    return {
        "title": title,
        "description": description,
        "source": _source(emission),
        "source_type": emission.source_id,
        "evidence": [{"excerpt": ev.excerpt} for ev in emission.evidence],
    }
