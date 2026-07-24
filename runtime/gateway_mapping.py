# SPDX-License-Identifier: MIT
"""Map an ``AdapterEmission`` to the bot's v2 ``ExternalIngestEnvelope``.

The mapping is authority-stripped. Source facts, screened advisory features, and
a value-free redaction receipt may cross the boundary; candidate level, content
hashes, accepted state, actor authority, signoff, compliance, bindings, and
event-store fields remain Bot-owned.
"""

from __future__ import annotations

import re
from typing import Any

from adapter.core.emissions import AdapterEmission
from adapter.core.redaction import redact

_EMISSION_TYPES = frozenset({"candidate", "evidence", "hint", "advisory"})
_LABEL_TOKEN_RE = re.compile(r"[^a-z0-9._-]+")
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
    """Return a non-empty portable provenance URI."""
    for ev in emission.evidence:
        url = (ev.source_ref.url or "").strip()
        if url:
            return redact(url)
    for ev in emission.evidence:
        ref = (ev.source_ref.ref or "").strip()
        if ref:
            return f"{emission.source_id}:{redact(ref)}"
    return emission.source_id


def _label_token(value: object, *, fallback: str = "unknown") -> str:
    text = redact(str(value or "")).strip().lower()
    token = _LABEL_TOKEN_RE.sub("_", text).strip("_")
    return (token or fallback)[:120]


def _hint_labels(emission: AdapterEmission) -> list[str]:
    """Return screened, non-authoritative lane, routing, advisory, and provenance labels."""
    labels: list[str] = []

    if emission.emission_type in _EMISSION_TYPES:
        labels.append(f"emission_type:{emission.emission_type}")

    for hint in emission.routing_hints:
        role = _label_token(hint.role)
        labels.append(f"routing:{role}:{hint.priority}")

    for advisory in emission.advisories:
        kind = _label_token(advisory.kind)
        labels.append(f"advisory:{kind}")
        metadata = advisory.metadata if isinstance(advisory.metadata, dict) else {}
        version = metadata.get("schema_version", 1)
        scope = _label_token(metadata.get("scope"), fallback="universal")
        confidence = _label_token(metadata.get("confidence"), fallback="unknown")
        effect = _label_token(metadata.get("recommended_effect"), fallback="annotate")
        basis = _label_token(metadata.get("basis"), fallback="unspecified")
        labels.append(
            f"advisory_v{version}:{kind}:{scope}:{confidence}:{effect}:{basis}"
        )

    if emission.provenance is not None:
        labels.append(f"delivery:{emission.provenance.delivery_mode}")
        labels.append(f"verification:{emission.provenance.verification}")
        if emission.provenance.provider_event_id:
            labels.append(
                f"provider_event_id:{redact(emission.provenance.provider_event_id)}"
            )
        if emission.provenance.provider_resource_id:
            labels.append(
                "provider_resource_id:"
                f"{redact(emission.provenance.provider_resource_id)}"
            )

    receipt = emission.metadata.get("redaction_receipt")
    if isinstance(receipt, dict):
        labels.append(f"redaction:v{receipt.get('schema_version', 'unknown')}")
        labels.append(f"redaction_ruleset:{_label_token(receipt.get('ruleset_id'))}")

    return labels


def emission_to_external_envelope(emission: AdapterEmission) -> dict[str, Any]:
    """Map one validated emission into the authority-stripped external envelope.

    The envelope preserves sanitized source content and evidence. Advisory signals
    remain projection features, never candidate instructions or lifecycle authority.
    The optional redaction receipt contains only ruleset identity, digests, category
    counts, actions, and completion metadata. It never contains removed values.
    """
    title = emission.title.strip() or _first_excerpt(emission) or emission.source_id
    content = (
        emission.body.strip()
        or emission.title.strip()
        or _first_excerpt(emission)
        or emission.source_id
    )
    hint: dict[str, Any] = {"title": title, "body": content}
    labels = _hint_labels(emission)
    if labels:
        hint["labels"] = labels
    envelope: dict[str, Any] = {
        "source_system": emission.source_id,
        "source_uri": _source_uri(emission),
        "content": content,
        "evidence": [{"excerpt": ev.excerpt} for ev in emission.evidence],
        "candidate_hints": [hint],
    }
    receipt = emission.metadata.get("redaction_receipt")
    if isinstance(receipt, dict):
        envelope["redaction_receipt"] = dict(receipt)
    return envelope
