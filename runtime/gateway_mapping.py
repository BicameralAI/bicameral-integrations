# SPDX-License-Identifier: MIT
"""Map an ``AdapterEmission`` to the bot's v2 ``ExternalIngestEnvelope`` (#226; RFQ 4 / bot#218).

The wire contract is pinned in ``runtime/schemas/external_ingest_request_v2.schema.json``
(byte-exact vendored copy of ``bicameral-bot:protocol/schemas/v2/external-ingest-request.schema.json``,
schema commit ``5c24c60f``, bot HEAD ``22806ac2``; pin metadata in
``runtime/schemas/ingest_schema_pin.json``, gated by ``scripts/validate_ingest_schema_pin.py``).
The gateway *ignores* unknown non-forbidden top-level keys (no ``additionalProperties`` guard in
the schema; no ``deny_unknown_fields`` on the Rust type) — the EMITTER self-restricts to
schema-declared keys anyway (regression-locked), so an accidental extra field can never drift
toward the 403'd 18-name authority set.

Field classification (RFQ #42 / GH #198, carried into the v2 envelope — #226):

+----------------------------+----------------------------------+------------------------------+
| AdapterEmission field      | Envelope field                   | Classification               |
+----------------------------+----------------------------------+------------------------------+
| body (floored)             | content                          | SOURCE FACT                  |
| source_id                  | source_system                    | SOURCE FACT                  |
| evidence[].source_ref.url  | source_uri (redacted)            | SOURCE FACT (portable id)    |
| evidence[].excerpt         | evidence[].excerpt               | SOURCE FACT (screened)       |
| title (floored)            | candidate_hints[0].title         | HINT (non-authoritative)     |
| body (floored)             | candidate_hints[0].body          | HINT (non-authoritative)     |
| emission_type              | candidate_hints[0].labels[]      | HINT (lane hint)             |
| routing_hints              | candidate_hints[0].labels[]      | HINT (screened, advisory)    |
| advisories                 | candidate_hints[0].labels[]      | HINT (screened, advisory)    |
| provenance (#196)          | candidate_hints[0].labels[]      | HINT (delivery/verification) |
| confidence                 | (dropped)                        | HINT (not collapsed)         |
| metadata                   | (dropped)                        | DROPPED (unscreened)         |
| (absent)                   | candidate_hints[0].level         | BOT-OWNED (never sent)       |
| (absent)                   | content_hash                     | BOT-OWNED (daemon computes)  |
+----------------------------+----------------------------------+------------------------------+

``candidate_hints`` is the v2 schema's ONLY advisory-string surface, so every #198 hint and #196
provenance descriptor rides there as a label — signal for the daemon's projection, never authority
(bot ADR-0024; the daemon classifies ``level`` itself). Integrations never sends bot-owned
``level``, ``content_hash``, accepted evidence/candidate state, ``ActorContext``,
``SourceSnapshot``, ``BindingEvidence``, signoff, compliance, enforcement, or event-store fields.
Dimensional ``ConfidenceSurface`` is never collapsed to a scalar (SG-2026-06-02-B).
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
        "content_hash",
        "snapshot_content",
    }
)


def _first_excerpt(emission: AdapterEmission) -> str:
    for ev in emission.evidence:
        text = (ev.excerpt or "").strip()
        if text:
            return text
    return ""


def _source_uri(emission: AdapterEmission) -> str:
    """A non-empty portable provenance URI (URL preferred, else source:ref).

    The chosen url/ref is run through ``redact`` before it becomes the wire ``source_uri``:
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


def _hint_labels(emission: AdapterEmission) -> list[str]:
    """Non-authoritative lane/routing/advisory/provenance labels (screened via ``redact``).

    These are advisory hints the bot may use or ignore (#198 tags + #196 provenance,
    carried as ``candidate_hints[].labels`` — the v2 envelope's advisory-string surface).
    They never encode authority, accepted state, or bot-owned lifecycle.
    """
    labels: list[str] = []

    # emission_type as a lane hint (non-authoritative; bot decides actual lane)
    if emission.emission_type in _EMISSION_TYPES:
        labels.append(f"emission_type:{emission.emission_type}")

    # routing hints — role + priority; screened through redact
    for rh in emission.routing_hints:
        role = redact(rh.role).strip()
        if role:
            labels.append(f"routing:{role}:{rh.priority}")

    # advisories — kind only; screened through redact
    for adv in emission.advisories:
        kind = redact(adv.kind).strip()
        if kind:
            labels.append(f"advisory:{kind}")

    # provenance (#196) — delivery/verification descriptors + screened provider ids
    if emission.provenance is not None:
        labels.append(f"delivery:{emission.provenance.delivery_mode}")
        labels.append(f"verification:{emission.provenance.verification}")
        if emission.provenance.provider_event_id:
            labels.append(f"provider_event_id:{redact(emission.provenance.provider_event_id)}")
        if emission.provenance.provider_resource_id:
            labels.append(
                f"provider_resource_id:{redact(emission.provenance.provider_resource_id)}"
            )

    return labels


def emission_to_external_envelope(emission: AdapterEmission) -> dict:
    """Map an ``AdapterEmission`` into a v2 ``ExternalIngestEnvelope`` dict.

    Source facts (content, source_system, source_uri, evidence) are always mapped.
    Hints (title/body, emission_type lane, routing, advisories, provenance) ride as ONE
    advisory ``candidate_hints`` entry. Bot-owned fields (``level``, ``content_hash``)
    are never populated. Unscreened ``metadata`` is dropped. ``confidence`` is dropped
    (not collapsed to a scalar — SG-2026-06-02-B).
    """
    title = emission.title.strip() or _first_excerpt(emission) or emission.source_id
    content = (
        emission.body.strip()
        or emission.title.strip()
        or _first_excerpt(emission)
        or emission.source_id
    )
    hint: dict = {"title": title, "body": content}
    labels = _hint_labels(emission)
    if labels:
        hint["labels"] = labels
    return {
        "source_system": emission.source_id,
        "source_uri": _source_uri(emission),
        "content": content,
        "evidence": [{"excerpt": ev.excerpt} for ev in emission.evidence],
        "candidate_hints": [hint],
    }
