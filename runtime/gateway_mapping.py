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
from adapter.core.redaction import redact


def _first_excerpt(emission: AdapterEmission) -> str:
    for ev in emission.evidence:
        text = (ev.excerpt or "").strip()
        if text:
            return text
    return ""


def _source(emission: AdapterEmission) -> str:
    """A non-empty portable source identifier (URI preferred, else source:ref).

    The chosen url/ref is run through ``redact`` before it becomes the wire ``source``:
    the FX-SEC-001 catalog screen has no email/phone pattern, so generic PII embedded in a
    provider artifact URL/ref (e.g. a Devin ``pr_url`` fragment) would otherwise reach the
    gateway un-scrubbed — the same redact-and-pass that already protects title/excerpt
    (purple-team PII-4/GATEWAY-1, 2026-06-11). Scheme/host/path of a real URL are PII-free
    and survive redaction unchanged."""
    for ev in emission.evidence:
        url = (ev.source_ref.url or "").strip()
        if url:
            return redact(url)
    for ev in emission.evidence:
        ref = (ev.source_ref.ref or "").strip()
        if ref:
            return f"{emission.source_id}:{redact(ref)}"
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
