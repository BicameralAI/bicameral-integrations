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

from .._signals import any_match, is_change_evidence, matched_terms, safe_id
from ..contract import ModEmission

_OUTPUTS = frozenset({
    "advisory_governance_result", "routing_hint",
    "source_evidence_annotation", "suggested_review_question",
})

# Markers that the change alters behavior (so a test should accompany it). Full-word inflections,
# word-boundary-matched (SG-2026-06-12-E: 'fix' no longer fires on 'prefix'); vocab expanded
# (mod purple-team false_negative). _TEST_TERMS likewise — critically 'test' must NOT fire on
# 'latest'/'contest' (the medium that was suppressing real test-gap signals).
_BEHAVIOR_TERMS = (
    "fix", "fixes", "fixed", "bug", "bugs", "feature", "refactor", "refactored", "migration",
    "migrations", "endpoint", "parser", "handler", "validation", "logic", "regression", "behavior",
    "patch", "patched", "rewrite", "rewrote", "optimize", "optimized", "implement", "hotfix",
)
# Any of these implies tests were considered -> not a gap.
_TEST_TERMS = (
    "test", "tests", "tested", "testing", "spec", "specs", "fixture", "fixtures",
    "coverage", "assert", "asserts", "pytest", "unit test",
)


def _text(emission: AdapterEmission) -> str:
    parts = [emission.title, emission.body]
    parts.extend(ev.excerpt for ev in (emission.evidence or ()))  # totality: tolerate None evidence
    return " ".join(p for p in parts if isinstance(p, str)).lower()


def _emissions_for(emission: AdapterEmission) -> list[ModEmission]:
    if not is_change_evidence(emission):
        return []
    text = _text(emission)
    behavior = matched_terms(text, _BEHAVIOR_TERMS)
    if not behavior or any_match(text, _TEST_TERMS):
        return []  # not a behavior change, or tests already referenced
    src = safe_id(emission.source_id)
    joined = ", ".join(behavior)
    return [
        ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
            kind="source_evidence_annotation",
            message=f"behavior change on {src} ({joined}) with no test signal in the text")),
        ModEmission("advisory_governance_result", advisory=AdvisoryResult(
            kind="advisory_governance_result",
            message=f"possible test gap — behavior change ({joined}) names no test/fixture",
            metadata={"behavior": joined, "source": src})),
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
