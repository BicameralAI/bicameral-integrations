# SPDX-License-Identifier: MIT
"""Map an ``AdapterEmission`` to the gateway v1 ``IngestRequest`` (ADR-0012).

The wire contract is pinned in ``runtime/schemas/ingest_request_v1.schema.json``
(vendored from ``bicameral-bot:protocol/schemas/v1/``). The three required fields
(``title``, ``description``, ``source``) are floored to a non-empty value.
Dimensional confidence (``ConfidenceSurface``) is deliberately **NOT** collapsed
into the v1 scalar ``confidence`` (SG-2026-06-02-B) — each evidence item carries
only its excerpt; the gateway/daemon owns the judgment. The decision ``level``
is the daemon's call, so it is omitted.

Field classification (RFQ #42, PR #69, GH #198):

+---------------------------+-------------------+------------------------------+
| AdapterEmission field     | Envelope field    | Classification               |
+---------------------------+-------------------+------------------------------+
| title                     | title (floored)   | SOURCE FACT                  |
| body                      | description       | SOURCE FACT                  |
| evidence[].source_ref.url | source            | SOURCE FACT (portable id)    |
| source_id                 | source_type       | SOURCE FACT                  |
| evidence[].excerpt        | evidence[].excerpt| SOURCE FACT (screened)       |
| emission_type             | label + tags[]    | HINT (non-authoritative)     |
| routing_hints             | tags[]            | HINT (screened, advisory)    |
| advisories                | tags[]            | HINT (screened, advisory)    |
| confidence                | (dropped)         | HINT (not collapsed)         |
| metadata                  | (dropped)         | DROPPED (unscreened)         |
| (absent)                  | level             | BOT-OWNED (never sent)       |
| (absent)                  | snapshot_content  | BOT-OWNED (never sent)       |
+---------------------------+-------------------+------------------------------+

Integrations never sends bot-owned ``level``, accepted evidence/candidate state,
``ActorContext``, ``SourceSnapshot``, ``BindingEvidence``, signoff, compliance,
enforcement, or event-store fields.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission
from adapter.core.redaction import redact

# Emission-type values the adapter contract permits (pipeline._EMISSION_TYPES).
_EMISSION_TYPES = frozenset({"candidate", "evidence", "hint", "advisory"})

# Fields the bot owns — integrations must never populate these in the envelope.
BOT_OWNED_FIELDS: frozenset[str] = frozenset(
    {
        "level",
        "snapshot_content",
    }
)


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


def _hint_tags(emission: AdapterEmission) -> list[str]:
    """Non-authoritative lane/routing/advisory tags (screened via ``redact``).

    These are advisory hints the bot may use or ignore. They never encode
    authority, accepted state, or bot-owned lifecycle.
    """
    tags: list[str] = []

    # emission_type as a lane hint (non-authoritative; bot decides actual lane)
    if emission.emission_type in _EMISSION_TYPES:
        tags.append(f"emission_type:{emission.emission_type}")

    # routing hints — role + priority; screened through redact
    for rh in emission.routing_hints:
        role = redact(rh.role).strip()
        if role:
            tags.append(f"routing:{role}:{rh.priority}")

    # advisories — kind only; screened through redact
    for adv in emission.advisories:
        kind = redact(adv.kind).strip()
        if kind:
            tags.append(f"advisory:{kind}")

    return tags


def emission_to_ingest_request(emission: AdapterEmission) -> dict:
    """Map an ``AdapterEmission`` into a v1 ``IngestRequest`` dict.

    Source facts (title, description, source, source_type, evidence) are always
    mapped. Hints (emission_type, routing, advisories) are mapped to ``label``
    and ``tags`` as non-authoritative advisory data. Bot-owned fields (``level``,
    ``snapshot_content``) are never populated. Unscreened ``metadata`` is dropped.
    ``confidence`` is dropped (not collapsed to a scalar — SG-2026-06-02-B).
    """
    title = emission.title.strip() or _first_excerpt(emission) or emission.source_id
    description = (
        emission.body.strip()
        or emission.title.strip()
        or _first_excerpt(emission)
        or emission.source_id
    )

    tags = _hint_tags(emission)

    payload: dict = {
        # --- source facts ---
        "title": title,
        "description": description,
        "source": _source(emission),
        "source_type": emission.source_id,
        "evidence": [{"excerpt": ev.excerpt} for ev in emission.evidence],
    }

    # --- hints (non-authoritative) ---
    if emission.emission_type in _EMISSION_TYPES:
        payload["label"] = f"emission_type:{emission.emission_type}"
    if tags:
        payload["tags"] = tags

    # --- explicitly absent: bot-owned fields ---
    # level, snapshot_content are NEVER set (bot's call).
    # metadata is NEVER forwarded (unscreened — FX-SEC-001).
    # confidence is NEVER collapsed to a scalar (SG-2026-06-02-B).

    return payload
