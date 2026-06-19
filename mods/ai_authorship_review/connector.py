# SPDX-License-Identifier: MIT
"""ai_authorship_review mod — route low-confidence AI-authored evidence to human/QA review.

Advisory (ADR-0007/0008): when evidence comes from an AI coding tool (aider/cursor/copilot/
claude_code/continue_dev/devin) AND carries low-confidence / unfinished-work markers
(``TODO``/``FIXME``/``untested``/``not sure``/``hallucination``/…), this mod surfaces an advisory,
routes the change to QA, and suggests a human-review question. It never blocks or approves — it
annotates and routes only.

Gate: fires ONLY when ``safe_id(source_id)`` is in the AI-coding source set; a non-AI source
produces no output. Then it requires at least one uncertainty marker (``matched_terms`` over
title+body+excerpts, lowercased, word-boundary for alphanumeric terms / substring for phrases).
Deterministic (sorted markers), pure, stdlib-only.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from .._signals import matched_terms, safe_id
from ..contract import ModEmission

_OUTPUTS = frozenset(
    {"advisory_governance_result", "routing_hint", "suggested_review_question"}
)

# AI coding tools whose authored evidence this mod gates on (safe_id-normalized).
_AI_SOURCES = frozenset(
    {"aider", "cursor", "copilot", "claude_code", "continue_dev", "devin"}
)

# Low-confidence / unfinished-work markers. Pure-alphanumeric terms word-boundary match
# (so "hallucination"/"hallucinated" are listed explicitly); space/hyphen phrases substring match.
_UNCERTAINTY = (
    "todo",
    "fixme",
    "untested",
    "placeholder",
    "unverified",
    "stub",
    "wip",
    "not sure",
    "i think",
    "might be",
    "best guess",
    "needs review",
    "double check",
    "double-check",
    "not tested",
    "hallucination",
    "hallucinated",
)


def _markers(emission: AdapterEmission) -> list[str]:
    """Sorted unique uncertainty markers found in title + body + evidence excerpts."""
    text = " ".join(
        [emission.title, emission.body, *(ev.excerpt for ev in emission.evidence)]
    )
    return sorted(set(matched_terms(text, _UNCERTAINTY)))


class AiAuthorshipReviewMod:
    """Route low-confidence AI-authored evidence to human/QA review (advisory only)."""

    id = "ai-authorship-review"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for em in emissions:
            src = safe_id(em.source_id)
            if src not in _AI_SOURCES:
                continue
            markers = _markers(em)
            if not markers:
                continue
            joined = ", ".join(markers)
            out.append(
                ModEmission(
                    "advisory_governance_result",
                    advisory=AdvisoryResult(
                        kind="advisory_governance_result",
                        message=(
                            f"AI-authored evidence from {src} carries "
                            f"low-confidence/unfinished markers: {joined}"
                        ),
                        metadata={"markers": joined, "source": src},
                    ),
                )
            )
            out.append(
                ModEmission(
                    "routing_hint",
                    routing_hint=RoutingHint(
                        role="qa",
                        reason=(
                            f"AI-authored evidence needs human review ({src}): {joined}"
                        ),
                    ),
                )
            )
            out.append(
                ModEmission(
                    "suggested_review_question",
                    advisory=AdvisoryResult(
                        kind="suggested_review_question",
                        message=(
                            f"Has the AI-authored change from {src} ({joined}) been "
                            "human-reviewed and tested before acceptance?"
                        ),
                    ),
                )
            )
        return out


__all__ = ["AiAuthorshipReviewMod"]
