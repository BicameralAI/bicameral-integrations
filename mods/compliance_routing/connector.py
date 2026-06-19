# SPDX-License-Identifier: MIT
"""compliance_routing mod — route evidence naming a regulatory framework to compliance (ADR-0013).

EM-safe (ADR-0007/0008): reads immutable ``AdapterEmission`` evidence and returns advisory
artifacts only — it surfaces evidence that NAMES a regulatory/compliance framework (HIPAA,
GDPR, PCI DSS, SOC 2, ...) and routes it to a compliance reviewer so the regulated scope is
weighed before a change lands; it never blocks CI, approves, or resolves compliance. Pure
function over the input list (no I/O).

Distinct from ``data_classification`` by design: that mod owns confidentiality MARKERS
(confidential / internal-only / nda) and ``[redacted]`` PII placeholders; this mod owns
NAMED REGULATORY FRAMEWORKS (the obligation, not the sensitivity tier) and routes to
compliance. The vocabularies do not overlap, so a confidentiality-marker-only change does
not fire here.

Deterministic detection: word-boundary-match a single alnum token (``hipaa``/``gdpr``/...),
substring-match a phrase (``pci dss``/``soc 2``/``data subject``/...) over title + body +
evidence excerpts (lowercased), via ``mods._signals.matched_terms``. Fires on >=1 match;
routes a COMPLIANCE review and asks a control-owner question. No framework term -> NO output.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from .._signals import matched_terms, safe_id
from ..contract import ModEmission

_OUTPUTS = frozenset({
    "advisory_governance_result", "routing_hint", "suggested_review_question",
})

# Named-regulatory-framework vocabulary (distinct from data_classification's confidentiality
# markers). Single alnum tokens word-boundary-match (so "sox" does not fire on "soxhlet");
# multi-word / punctuated phrases substring-match (SG-2026-06-12-E).
_COMPLIANCE_TERMS = (
    "hipaa", "gdpr", "pci", "pci dss", "soc 2", "soc2", "ccpa", "sox", "ferpa", "glba",
    "fedramp", "iso 27001", "nist", "data subject", "right to be forgotten",
    "data retention", "breach notification", "regulatory", "audit evidence",
    "compliance requirement",
)


def _text(emission: AdapterEmission) -> str:
    parts = [emission.title, emission.body]
    parts.extend(ev.excerpt for ev in (emission.evidence or ()))  # totality: tolerate None evidence
    return " ".join(p for p in parts if isinstance(p, str)).lower()


def _emissions_for(emission: AdapterEmission) -> list[ModEmission]:
    hits = matched_terms(_text(emission), _COMPLIANCE_TERMS)
    if not hits:
        return []
    src = safe_id(emission.source_id)
    joined = ", ".join(hits)
    return [
        ModEmission("advisory_governance_result", advisory=AdvisoryResult(
            kind="advisory_governance_result",
            message=f"evidence on {src} touches regulated scope: {joined}",
            metadata={"frameworks": joined, "source": src})),
        ModEmission("routing_hint", routing_hint=RoutingHint(
            role="compliance",
            reason=f"regulatory framework named in {src}: {joined}", priority="high")),
        ModEmission("suggested_review_question", advisory=AdvisoryResult(
            kind="suggested_review_question",
            message=(
                f"Does the {joined} obligation have a documented control owner and "
                "evidence trail for this change?"))),
    ]


class ComplianceRoutingMod:
    """EM-safe advisory mod routing evidence that names a regulatory framework to compliance."""

    id = "compliance-routing"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for emission in emissions:
            out.extend(_emissions_for(emission))
        return out


__all__ = ["ComplianceRoutingMod"]
