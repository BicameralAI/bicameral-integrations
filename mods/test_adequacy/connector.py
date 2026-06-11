# SPDX-License-Identifier: MIT
"""test_adequacy mod — advisory test-gap signals (ADR-0013).

EM-safe (ADR-0007/0008): reads immutable ``AdapterEmission`` evidence and returns advisory
artifacts only — it never marks a PR blocking or sufficient. Pure function over the input list
(no I/O): fires only on **change evidence** and keys off the change text.

Deterministic detection: a change whose text indicates a behavior/code change
(fix/feature/refactor/bug/migration/endpoint/parser) but mentions NO test signal
(test/spec/fixture/coverage/assert). Routes review + asks the test-gap question. A change that
already references tests, or that is not a behavior change, → NO output.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from ..contract import ModEmission

_OUTPUTS = frozenset({
    "advisory_governance_result", "routing_hint",
    "source_evidence_annotation", "suggested_review_question",
})

_CHANGE_KINDS = frozenset({"pull_request", "issue", "merge_request"})

# Markers that the change alters behavior (so a test should accompany it).
_BEHAVIOR_TERMS = (
    "fix", "bug", "feature", "refactor", "migration", "endpoint", "parser",
    "handler", "validation", "logic", "regression", "behavior",
)
# Any of these implies tests were considered -> not a gap.
_TEST_TERMS = ("test", "spec", "fixture", "coverage", "assert", "pytest", "unit test")


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
    behavior = [t for t in _BEHAVIOR_TERMS if t in text]
    if not behavior or any(t in text for t in _TEST_TERMS):
        return []  # not a behavior change, or tests already referenced
    src = (emission.source_id or "unknown").strip() or "unknown"
    joined = ", ".join(behavior)
    return [
        ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
            kind="source_evidence_annotation",
            message=f"behavior change on {src} ({joined}) with no test signal in the text")),
        ModEmission("advisory_governance_result", advisory=AdvisoryResult(
            kind="advisory_governance_result",
            message=f"possible test gap — behavior change ({joined}) names no test/fixture",
            metadata={"behavior": joined, "source": emission.source_id})),
        ModEmission("routing_hint", routing_hint=RoutingHint(
            role="review", reason=f"test-adequacy review for {src}: {joined}", priority="normal")),
        ModEmission("suggested_review_question", advisory=AdvisoryResult(
            kind="suggested_review_question",
            message=f"Does this {joined} change add or update a test that exercises the new behavior?")),
    ]


class TestAdequacyMod:
    """EM-safe advisory mod surfacing behavior-change-without-tests signals."""

    id = "test-adequacy"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for emission in emissions:
            out.extend(_emissions_for(emission))
        return out


__all__ = ["TestAdequacyMod"]
