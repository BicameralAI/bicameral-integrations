# SPDX-License-Identifier: MIT
"""decision_drift mod — advisory decision-conflict signals (ADR-0013).

EM-safe (ADR-0007/0008): reads immutable ``AdapterEmission`` evidence and returns advisory
artifacts only — it never supersedes, approves, rejects, or writes a decision record. Pure
function over the input list (no I/O). Unlike the PR-review family it is NOT gated to change
evidence: per its scope a ticket or meeting note can imply an unrecorded/conflicting decision.

Deterministic detection: the text names a decision-conflict cue (ADR / decision record /
trust tier paired with supersede / contradict / overrides / no-longer-matches / conflicts-with /
unrecorded decision). Routes GOVERNANCE review + asks whether the decision record needs an update.
No conflict cue → NO output.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from .._signals import matched_terms, safe_id
from ..contract import ModEmission

_OUTPUTS = frozenset({
    "advisory_governance_result", "routing_hint",
    "source_evidence_annotation", "suggested_review_question",
})

# A decision anchor must co-occur with a conflict cue for a drift signal (both required). 'adr' is
# word-boundary-matched (SG-2026-06-12-E: no longer fires inside 'quadratic'/'cadre'); the cues are
# DECISION-SPECIFIC phrasings (mod purple-team false_positive: bare 'overrides'/'reverses'/'out of
# date' collide with ordinary engineering prose) + expanded vocab (false_negative).
_DECISION_ANCHORS = (
    "adr", "decision record", "recorded decision", "trust tier", "governance decision",
    "architecture decision", "design decision",
)
_CONFLICT_CUES = (
    "supersede", "supersedes", "superseded", "contradicts the decision", "no longer matches",
    "conflicts with the decision", "stale decision", "unrecorded decision", "deviates from the decision",
    "reverses the decision", "overrides the decision", "obsolete", "rescinded", "revoked",
    "no longer follow", "no longer following", "changed direction", "should not follow",
)


def _text(emission: AdapterEmission) -> str:
    parts = [emission.title, emission.body]
    parts.extend(ev.excerpt for ev in (emission.evidence or ()))  # totality: tolerate None evidence
    return " ".join(p for p in parts if isinstance(p, str)).lower()


def _emissions_for(emission: AdapterEmission) -> list[ModEmission]:
    text = _text(emission)
    anchors = matched_terms(text, _DECISION_ANCHORS)
    cues = matched_terms(text, _CONFLICT_CUES)
    if not (anchors and cues):  # need BOTH a decision anchor and a conflict cue
        return []
    src = safe_id(emission.source_id)
    joined = ", ".join(cues)
    return [
        ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
            kind="source_evidence_annotation",
            message=f"possible decision drift on {src}: {', '.join(anchors)} + {joined}")),
        ModEmission("advisory_governance_result", advisory=AdvisoryResult(
            kind="advisory_governance_result",
            message=f"evidence may conflict with a recorded decision ({joined}) — review the decision record",
            metadata={"anchors": ", ".join(anchors), "cues": joined, "source": src})),
        ModEmission("routing_hint", routing_hint=RoutingHint(
            role="governance", reason=f"decision drift in {src}: {joined}", priority="normal")),
        ModEmission("suggested_review_question", advisory=AdvisoryResult(
            kind="suggested_review_question",
            message=f"Does the recorded decision need an update or a superseding ADR given this ({joined})?")),
    ]


class DecisionDriftMod:
    """EM-safe advisory mod surfacing evidence that may conflict with recorded decisions."""

    id = "decision-drift"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for emission in emissions:
            out.extend(_emissions_for(emission))
        return out


__all__ = ["DecisionDriftMod"]
