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

from ..contract import ModEmission

_OUTPUTS = frozenset({
    "advisory_governance_result", "routing_hint",
    "source_evidence_annotation", "suggested_review_question",
})

# A decision anchor must co-occur with a conflict verb for a drift signal (both required).
_DECISION_ANCHORS = ("adr", "decision record", "recorded decision", "trust tier", "governance decision")
_CONFLICT_CUES = (
    "supersede", "contradict", "overrides", "no longer matches", "conflicts with",
    "out of date", "stale decision", "unrecorded decision", "reverses", "deviates from",
)


def _text(emission: AdapterEmission) -> str:
    parts = [emission.title, emission.body]
    parts.extend(ev.excerpt for ev in emission.evidence)
    return " ".join(p for p in parts if isinstance(p, str)).lower()


def _emissions_for(emission: AdapterEmission) -> list[ModEmission]:
    text = _text(emission)
    anchors = [a for a in _DECISION_ANCHORS if a in text]
    cues = [c for c in _CONFLICT_CUES if c in text]
    if not (anchors and cues):  # need BOTH a decision anchor and a conflict cue
        return []
    src = (emission.source_id or "unknown").strip() or "unknown"
    joined = ", ".join(cues)
    return [
        ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
            kind="source_evidence_annotation",
            message=f"possible decision drift on {src}: {', '.join(anchors)} + {joined}")),
        ModEmission("advisory_governance_result", advisory=AdvisoryResult(
            kind="advisory_governance_result",
            message=f"evidence may conflict with a recorded decision ({joined}) — review the decision record",
            metadata={"anchors": ", ".join(anchors), "cues": joined, "source": emission.source_id})),
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
