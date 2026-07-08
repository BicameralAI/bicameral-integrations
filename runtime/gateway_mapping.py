# SPDX-License-Identifier: MIT
"""Map an ``AdapterEmission`` to the bot's v2 ``ExternalIngestEnvelope`` (#226; RFQ 4 / bot#218).

The wire contract is pinned in ``runtime/schemas/external_ingest_request_v2.schema.json``
(byte-exact vendored copy of ``bicameral-bot:protocol/schemas/v2/external-ingest-request.schema.json``,
schema commit ``5c24c60f``, bot HEAD ``22806ac2``). The gateway *ignores* unknown non-forbidden
top-level keys (no ``additionalProperties`` guard in the schema; no ``deny_unknown_fields`` on the
Rust type) — the EMITTER self-restricts to schema-declared keys anyway (regression-locked), so an
accidental extra field can never drift toward the 403'd authority set. Deliberately minimal:
required ``content`` / ``source_system`` / ``source_uri``; ``evidence[]`` excerpts; exactly ONE advisory
``candidate_hints[]`` entry preserving the legacy title/description signal (hints are *signal*,
never authority — bot ADR-0024; the daemon classifies ``level`` itself). ``content_hash`` and
per-evidence spans/confidence are omitted — the daemon computes/floors them, and dimensional
``ConfidenceSurface`` is never collapsed to a scalar (SG-2026-06-02-B). No authority field is ever
emitted (the gateway 403s 18 forbidden names — regression-locked in the tests).
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


def emission_to_external_envelope(emission: AdapterEmission) -> dict:
    """Map an ``AdapterEmission`` into a v2 ``ExternalIngestEnvelope`` dict."""
    title = emission.title.strip() or _first_excerpt(emission) or emission.source_id
    content = (
        emission.body.strip()
        or emission.title.strip()
        or _first_excerpt(emission)
        or emission.source_id
    )
    return {
        "source_system": emission.source_id,
        "source_uri": _source_uri(emission),
        "content": content,
        "evidence": [{"excerpt": ev.excerpt} for ev in emission.evidence],
        "candidate_hints": [{"title": title, "body": content}],
    }
