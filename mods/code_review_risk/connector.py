# SPDX-License-Identifier: MIT
"""code_review_risk mod — advisory PR-level review-risk signals (ADR-0013).

EM-safe (ADR-0007/0008): reads immutable ``AdapterEmission`` evidence and returns advisory
artifacts only — it never approves, requests changes, posts a comment, or merges. Pure function
over the input list (no I/O): it only fires on **change evidence** (a pull_request / issue /
merge_request) and keys off the change text.

Deterministic detection (lowercased contiguous-substring match):

- **high blast radius** — the text names a risky area (migration/schema, auth/token/credential,
  CI workflow, Dockerfile, secret/key path, a declared breaking change). Routes review + asks a
  grounded review question. No risky area named on a change → NO output.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from .._signals import any_match, is_change_evidence, safe_id
from ..contract import ModEmission

_OUTPUTS = frozenset({
    "advisory_governance_result", "routing_hint",
    "source_evidence_annotation", "suggested_review_question",
})

# Risky areas, grouped so the review question can name the category that tripped. Alphanumeric terms
# are word-boundary-matched (SG-2026-06-12-E: 'auth' no longer fires on 'author'); phrase/path terms
# match as substrings. Full-word inflections + security vocab (mod purple-team false_negative).
_RISK_AREAS = {
    "schema/migration": ("migration", "migrations", "alter table", "drop table", "schema change", "ddl"),
    "auth": ("auth", "authentication", "authorization", "login", "token", "credential", "credentials",
             "oauth", "session", "password", "cve", "xss", "csrf", "injection", "rce", "sqli", "exploit"),
    "ci/workflow": (".github/workflows", "workflow", "workflows", "ci pipeline", "release pipeline"),
    "container/infra": ("dockerfile", "kubernetes", "terraform", "helm chart"),
    "secrets": ("secret", "secrets", "api key", "private key", "signing key"),
    "breaking": ("breaking change", "breaking changes", "backward incompat", "remove endpoint", "drop support"),
}


def _text(emission: AdapterEmission) -> str:
    parts = [emission.title, emission.body]
    parts.extend(ev.excerpt for ev in (emission.evidence or ()))  # totality: tolerate None evidence
    return " ".join(p for p in parts if isinstance(p, str)).lower()


def _emissions_for(emission: AdapterEmission) -> list[ModEmission]:
    if not is_change_evidence(emission):
        return []
    text = _text(emission)
    areas = [name for name, terms in _RISK_AREAS.items() if any_match(text, terms)]
    if not areas:
        return []
    src = safe_id(emission.source_id)
    joined = ", ".join(areas)
    return [
        ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
            kind="source_evidence_annotation",
            message=f"change on {src} touches high-risk area(s): {joined}")),
        ModEmission("advisory_governance_result", advisory=AdvisoryResult(
            kind="advisory_governance_result",
            message=f"PR-level review risk ({joined}) — review blast radius before merge",
            metadata={"areas": joined, "source": src})),
        ModEmission("routing_hint", routing_hint=RoutingHint(
            role="review", reason=f"high-risk change area(s) in {src}: {joined}", priority="high")),
        ModEmission("suggested_review_question", advisory=AdvisoryResult(
            kind="suggested_review_question",
            message=f"Does this change to {joined} have a tested rollback and a clear blast-radius bound?")),
    ]


class CodeReviewRiskMod:
    """EM-safe advisory mod surfacing PR-level review-risk signals."""

    id = "code-review-risk"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for emission in emissions:
            out.extend(_emissions_for(emission))
        return out


__all__ = ["CodeReviewRiskMod"]
