# SPDX-License-Identifier: MIT
"""notification_scope_risk mod — surface broad/unscoped broadcast-notification language (ADR-0013).

Advisory (ADR-0007/0008): scans evidence text for over-broad broadcast-notification vocabulary
(``@channel``, ``notify all``, ``company-wide``, ``all-hands``, …) and surfaces the matched terms so a
reviewer checks the *blast radius* of a notification before it ships. It annotates, asks, and routes; it
never blocks or approves. **Complements, never replaces** FX-SEC-001 — ``run_mod`` re-screens this mod's
output, so this surfaces the SCOPE WORD ("@channel"), never any secret value. Deterministic: terms are
matched (lowercased) over title + body + evidence excerpts via the shared :func:`matched_terms`
substring/word-boundary matcher, collected in declaration order. Pure, stdlib-only.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from .._signals import matched_terms, safe_id
from ..contract import ModEmission

_OUTPUTS = frozenset({"advisory_governance_result", "routing_hint", "suggested_review_question"})

# Over-broad broadcast vocab. All are phrases or carry @/hyphen ⇒ substring-matched by `matched_terms`.
# The bare token "broadcast" is intentionally EXCLUDED — too broad on its own to signal over-scope.
_BROADCAST_TERMS = (
    "@channel", "@everyone", "@here", "notify all", "email everyone", "mass email",
    "company-wide", "all-hands", "broadcast to all", "notify the whole", "blast to",
    "announce to all", "page everyone", "alert everyone",
)


def _matches(emission: AdapterEmission) -> list[str]:
    """Broadcast-scope terms found in title + body + evidence excerpts (lowercased, in order)."""
    text = " ".join([emission.title, emission.body, *(ev.excerpt for ev in emission.evidence)])
    return matched_terms(text, _BROADCAST_TERMS)


class NotificationScopeRiskMod:
    """Surface broad/unscoped broadcast-notification language so a reviewer checks blast radius."""

    id = "notification-scope-risk"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for em in emissions:
            found = _matches(em)
            if not found:
                continue
            joined = ", ".join(found)
            src = safe_id(em.source_id)
            out.append(ModEmission("advisory_governance_result", advisory=AdvisoryResult(
                kind="advisory_governance_result",
                message=f"evidence on {src} describes a broad/unscoped notification: {joined}",
                metadata={"signals": joined, "source": src})))
            out.append(ModEmission("routing_hint", routing_hint=RoutingHint(
                role="security",
                reason=f"over-broad notification scope in {src}: {joined}")))
            out.append(ModEmission("suggested_review_question", advisory=AdvisoryResult(
                kind="suggested_review_question",
                message=(
                    f"Is the '{joined}' notification scoped to the necessary recipients, "
                    "or is it over-broad?"))))
        return out


__all__ = ["NotificationScopeRiskMod"]
