# SPDX-License-Identifier: MIT
"""source_trust_calibration mod — advisory source-trust signals (ADR-0013).

EM-safe (ADR-0007/0008): reads immutable ``AdapterEmission`` evidence and returns advisory
artifacts only — it never changes a canonical trust tier or promotes evidence to a decision.
Pure function over the input list (no I/O): it weighs the provenance an emission actually
carries and suggests keeping a weakly-provenanced source advisory / under manual review.

Trust-weakening signals (deterministic):

- **no actor identity** — an attributable-kind evidence (PR / issue / message / page / comment /
  meeting) with a blank ``author``: nobody to attribute the change to.
- **unknown schema** — an evidence entry with no declared ``source_ref.kind``.
- **public / no-auth source** — a source whose data is attacker-publishable (e.g. the public MCP
  registry): keep advisory regardless of content.
- **already-advisory emission_type** — ``hint`` / ``advisory`` emissions are low-trust by construction.

A normally-attributable, well-identified emission produces NO output.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from .._signals import safe_id
from ..contract import ModEmission

_OUTPUTS = frozenset({"advisory_governance_result", "routing_hint", "source_evidence_annotation"})

# Kinds where a human actor is normally attributable — a blank author is then a real gap. Covers the
# kinds the connectors actually emit (mod purple-team false_negative: commit/merge_request/ticket/
# document/transcript/session/incident/finding were missing). Machine-emitted kinds (usage_metrics,
# audit_event, vulnerability, mcp_server) are deliberately EXCLUDED — a blank author there is expected.
_ATTRIBUTABLE_KINDS = frozenset({
    "pull_request", "merge_request", "issue", "message", "page", "comment", "meeting",
    "commit", "ticket", "document", "transcript", "session", "incident", "finding",
})
# Sources whose payloads are public / attacker-publishable (no credential gates the content).
_PUBLIC_SOURCES = frozenset({"mcp_registry"})
_LOW_TRUST_TYPES = frozenset({"hint", "advisory"})


def _s(value: object) -> str:
    """A stripped string for str inputs, else ''."""
    return value.strip() if isinstance(value, str) else ""


def _trust_signals(emission: AdapterEmission) -> list[str]:
    """Provenance-weakening signals for one emission (empty list = well-provenanced). Totality-safe:
    a None/odd evidence, source_ref, or non-str kind never crashes (mod purple-team crash_dos)."""
    signals: list[str] = []
    if _s(emission.source_id) in _PUBLIC_SOURCES:
        signals.append(f"{_s(emission.source_id)} is a public/no-auth source (attacker-publishable content)")
    if emission.emission_type in _LOW_TRUST_TYPES:
        signals.append(f"emission_type '{emission.emission_type}' is advisory by construction")
    for ev in (emission.evidence or ()):
        kind = getattr(getattr(ev, "source_ref", None), "kind", None)
        kind = kind if isinstance(kind, str) else ""
        if kind in _ATTRIBUTABLE_KINDS and not _s(getattr(ev, "author", "")):
            signals.append(f"no actor identity on {kind} evidence")
        if not kind:
            signals.append("evidence has no declared kind (unknown schema)")
    return signals


def _emissions_for(emission: AdapterEmission) -> list[ModEmission]:
    signals = _trust_signals(emission)
    if not signals:
        return []
    joined = "; ".join(signals)
    src = safe_id(emission.source_id)
    return [
        ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
            kind="source_evidence_annotation",
            message=f"source-trust note on {src}: {joined}")),
        ModEmission("advisory_governance_result", advisory=AdvisoryResult(
            kind="advisory_governance_result",
            message=f"weak provenance on {src} — keep advisory / manual review: {joined}",
            metadata={"signals": joined, "source": src})),
        ModEmission("routing_hint", routing_hint=RoutingHint(
            role="review",
            reason=f"calibrate source trust for {src} (weak provenance): {joined}",
            priority="normal")),
    ]


class SourceTrustCalibrationMod:
    """EM-safe advisory mod surfacing source-provenance / trust-calibration signals."""

    id = "source-trust-calibration"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for emission in emissions:
            out.extend(_emissions_for(emission))
        return out


__all__ = ["SourceTrustCalibrationMod"]
