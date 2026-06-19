# SPDX-License-Identifier: MIT
"""policy_exemption_audit mod — advisory policy-exemption/waiver/accepted-risk claims (ADR-0013).

EM-safe (ADR-0007/0008): reads immutable ``AdapterEmission`` evidence and returns advisory
artifacts only — it surfaces evidence that CLAIMS a policy exemption/waiver/accepted-risk so a
policy owner can RE-APPROVE it; it never blocks CI, approves, or resolves compliance. Pure
function over the input list (no I/O).

Distinct from ``authority_boundary`` by design: that mod owns authority-crossing ACTIONS
(auto-merge / bypass-governance / deploy-without-review); this mod owns EXEMPTION CLAIMS
(exempt / waiver / accepted-risk / wontfix / suppress-finding). The vocabularies do not
overlap, so an authority-phrase-only change does not fire here.

Deterministic detection: word-boundary-match a single alnum token (``exempt``/``waiver``/…),
substring-match a phrase (``accepted risk``/``policy exception``/…) over title + body + evidence
excerpts (lowercased). Fires on >=1 match; routes a POLICY review and asks a re-approval
question. No exemption term -> NO output.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from .._signals import matched_terms, safe_id
from ..contract import ModEmission

_OUTPUTS = frozenset({
    "advisory_governance_result", "routing_hint", "suggested_review_question",
})

# Exemption-CLAIM vocabulary (distinct from authority_boundary's action vocab). Single alnum
# tokens word-boundary-match; multi-word / punctuated phrases substring-match (SG-2026-06-12-E).
_EXEMPTION_TERMS = (
    "exempt", "exemption", "waiver", "waived", "grandfathered",
    "accepted risk", "risk accepted", "policy exception", "exception granted",
    "wontfix", "won't fix", "will not fix", "suppress finding", "suppressed finding",
    "ignore rule", "ignore finding", "override approved", "temporary exception",
    "compliance exception",
)


def _text(emission: AdapterEmission) -> str:
    parts = [emission.title, emission.body]
    parts.extend(ev.excerpt for ev in (emission.evidence or ()))  # totality: tolerate None evidence
    return " ".join(p for p in parts if isinstance(p, str)).lower()


def _emissions_for(emission: AdapterEmission) -> list[ModEmission]:
    hits = matched_terms(_text(emission), _EXEMPTION_TERMS)
    if not hits:
        return []
    src = safe_id(emission.source_id)
    joined = ", ".join(hits)
    return [
        ModEmission("advisory_governance_result", advisory=AdvisoryResult(
            kind="advisory_governance_result",
            message=f"evidence on {src} claims a policy exemption/waiver: {joined}",
            metadata={"terms": joined, "source": src})),
        ModEmission("routing_hint", routing_hint=RoutingHint(
            role="policy", reason=f"policy-exemption claim in {src}: {joined}", priority="high")),
        ModEmission("suggested_review_question", advisory=AdvisoryResult(
            kind="suggested_review_question",
            message=(
                f"Has the '{joined}' exemption been explicitly re-approved by a policy owner "
                "with an audit record and expiry?"))),
    ]


class PolicyExemptionAuditMod:
    """EM-safe advisory mod surfacing policy-exemption/waiver/accepted-risk CLAIMS for re-approval."""

    id = "policy-exemption-audit"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for emission in emissions:
            out.extend(_emissions_for(emission))
        return out


__all__ = ["PolicyExemptionAuditMod"]
