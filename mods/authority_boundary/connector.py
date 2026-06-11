# SPDX-License-Identifier: MIT
"""authority_boundary mod — advisory authority/canonical-state-crossing signals (ADR-0013).

EM-safe (ADR-0007/0008): reads immutable ``AdapterEmission`` evidence and returns advisory
artifacts only — it can RAISE a boundary risk and route review, but never blocks CI or enforces
policy. Pure function over the input list (no I/O): fires only on **change evidence** and keys off
the change text.

Deterministic detection: a change that names an authority-crossing action — writing a canonical
decision, auto-approve/signoff, merge/deploy/delete without review, credential-scope expansion,
shell execution, or production mutation. Routes GOVERNANCE review + asks a boundary question.
No authority term on a change → NO output.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from ..contract import ModEmission

_OUTPUTS = frozenset({
    "advisory_governance_result", "routing_hint",
    "source_evidence_annotation", "suggested_review_question",
})

_CHANGE_KINDS = frozenset({"pull_request", "issue", "merge_request"})

_AUTHORITY_TERMS = (
    "auto-approve", "auto approve", "auto-merge", "auto merge", "signoff", "sign-off",
    "write canonical", "canonical decision", "resolve compliance", "bypass governance",
    "bypass policy", "skip review", "without review", "force merge", "force push",
    "deploy to production", "prod deploy", "delete production", "credential scope",
    "expand scope", "shell execution", "run shell", "rm -rf", "grant admin",
)


def _is_change(emission: AdapterEmission) -> bool:
    return any(ev.source_ref.kind in _CHANGE_KINDS for ev in emission.evidence)


def _text(emission: AdapterEmission) -> str:
    parts = [emission.title, emission.body]
    parts.extend(ev.excerpt for ev in emission.evidence)
    return " ".join(p for p in parts if isinstance(p, str)).lower()


def _emissions_for(emission: AdapterEmission) -> list[ModEmission]:
    if not _is_change(emission):
        return []
    text = _text(emission)
    hits = [t for t in _AUTHORITY_TERMS if t in text]
    if not hits:
        return []
    src = (emission.source_id or "unknown").strip() or "unknown"
    joined = ", ".join(hits)
    return [
        ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
            kind="source_evidence_annotation",
            message=f"change on {src} names an authority-crossing action: {joined}")),
        ModEmission("advisory_governance_result", advisory=AdvisoryResult(
            kind="advisory_governance_result",
            message=f"possible authority-boundary crossing ({joined}) — confirm human review + policy gate",
            metadata={"terms": joined, "source": emission.source_id})),
        ModEmission("routing_hint", routing_hint=RoutingHint(
            role="governance", reason=f"authority-boundary risk in {src}: {joined}", priority="high")),
        ModEmission("suggested_review_question", advisory=AdvisoryResult(
            kind="suggested_review_question",
            message=f"Is the '{joined}' path gated by explicit human approval, actor identity, and an audit record?")),
    ]


class AuthorityBoundaryMod:
    """EM-safe advisory mod surfacing authority/canonical-state-crossing signals."""

    id = "authority-boundary"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for emission in emissions:
            out.extend(_emissions_for(emission))
        return out


__all__ = ["AuthorityBoundaryMod"]
