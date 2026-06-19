# SPDX-License-Identifier: MIT
"""cross_system_reference mod — surface cross-system linkage in evidence (ADR-0013).

Advisory (ADR-0007/0008): scans an emission's evidence text for markers of an external system
OTHER than the emission's own ``source_id``, so a reviewer can reconcile the two systems (e.g. a
Linear emission whose body links a github.com PR). It annotates and routes; it never blocks or
approves. A self-reference (a github emission mentioning github.com) is NOT cross-system and is
skipped. Marker matching is deterministic (sorted foreign systems), case-insensitive, via
``matched_terms`` (word-boundary for alnum markers, substring for punctuated ones). Pure, stdlib-only.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from .._signals import matched_terms, safe_id
from ..contract import ModEmission

_OUTPUTS = frozenset({"routing_hint", "source_evidence_annotation", "suggested_review_question"})

# system name -> contiguous text markers that indicate a reference to that external system.
_SYSTEM_MARKERS: dict[str, tuple[str, ...]] = {
    "github": ("github.com", "gh-"),
    "gitlab": ("gitlab.com",),
    "linear": ("linear.app",),
    "jira": ("atlassian.net", "jira"),
    "notion": ("notion.so",),
    "slack": ("slack.com", "@slack"),
    "sentry": ("sentry.io",),
    "pagerduty": ("pagerduty.com", "pagerduty"),
    "zendesk": ("zendesk.com", "zendesk"),
    "confluence": ("confluence",),
}


def _foreign_systems(emission: AdapterEmission) -> list[str]:
    """Sorted external systems referenced in evidence text whose name != the emission's own
    ``source_id`` (self-reference skipped). Scans title + body + evidence excerpts, lowercased."""
    own = safe_id(emission.source_id).lower()
    text = " ".join([emission.title, emission.body, *(ev.excerpt for ev in emission.evidence)])
    found: set[str] = set()
    for system, markers in _SYSTEM_MARKERS.items():
        if system == own:
            continue
        if matched_terms(text, markers):
            found.add(system)
    return sorted(found)


class CrossSystemReferenceMod:
    """Surface when an emission's evidence references a different external system (advisory only)."""

    id = "cross-system-reference"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for em in emissions:
            foreign = _foreign_systems(em)
            if not foreign:
                continue
            src = safe_id(em.source_id)
            joined = ", ".join(foreign)
            out.append(ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
                kind="source_evidence_annotation",
                message=f"evidence on {src} references other system(s): {joined}",
                metadata={"foreign_systems": joined})))
            out.append(ModEmission("suggested_review_question", advisory=AdvisoryResult(
                kind="suggested_review_question",
                message=(f"Does the reference to {joined} stay in sync with the {src} item, "
                         "or need manual reconciliation?"),
                metadata={"foreign_systems": joined})))
            out.append(ModEmission("routing_hint", routing_hint=RoutingHint(
                role="integrations", reason=f"cross-system reference in {src}: {joined}")))
        return out


__all__ = ["CrossSystemReferenceMod"]
