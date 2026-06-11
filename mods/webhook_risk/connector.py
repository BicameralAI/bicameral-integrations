# SPDX-License-Identifier: MIT
"""webhook_risk mod — advisory webhook-safety signals (ADR-0013).

EM-safe (ADR-0007/0008): reads immutable ``AdapterEmission`` evidence and returns advisory
artifacts only — it never accepts a webhook event, executes a mutation, or sends a notification.
Pure function over the input list (no I/O): signals come only from the emission text.

Deterministic detection (lowercased contiguous-substring match, NOT a parser):

- **webhook context** — the text references a webhook handling surface (``webhook``, a provider
  signature header, ``svix``, ``hmac``). Always annotated (the change touches webhook safety).
- **named risk** — the text additionally names a concrete webhook risk (``replay``, ``spoof``,
  ``unverified``, ``bypass``, ``missing signature``, ``no dedup``): routes to security review.

Absence-of-a-mention is deliberately NOT treated as a risk (a change can verify without saying
so) — only an explicitly named risk routes. No webhook context → NO output.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from ..contract import ModEmission

_OUTPUTS = frozenset({"advisory_governance_result", "routing_hint", "source_evidence_annotation"})

_WEBHOOK_TERMS = (
    "webhook", "x-hub-signature", "x-slack-signature", "x-notion-signature",
    "x-pagerduty-signature", "svix", "hmac signature",
)
_RISK_TERMS = (
    "replay", "spoof", "unverified", "bypass signature", "missing signature",
    "no signature", "no dedup", "without verification", "skip verification", "forged",
)


def _text(emission: AdapterEmission) -> str:
    parts = [emission.title, emission.body]
    parts.extend(ev.excerpt for ev in emission.evidence)
    return " ".join(p for p in parts if isinstance(p, str)).lower()


def _emissions_for(emission: AdapterEmission) -> list[ModEmission]:
    text = _text(emission)
    if not any(t in text for t in _WEBHOOK_TERMS):
        return []
    src = (emission.source_id or "unknown").strip() or "unknown"
    risks = [t for t in _RISK_TERMS if t in text]
    out: list[ModEmission] = [
        ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
            kind="source_evidence_annotation",
            message=f"emission touches webhook handling ({src})")),
    ]
    if risks:
        joined = ", ".join(risks)
        out.append(ModEmission("advisory_governance_result", advisory=AdvisoryResult(
            kind="advisory_governance_result",
            message=f"webhook risk named ({joined}) — verify signature + replay protection",
            metadata={"risks": joined, "source": emission.source_id})))
        out.append(ModEmission("routing_hint", routing_hint=RoutingHint(
            role="security",
            reason=f"webhook risk in {src}: {joined}", priority="high")))
    return out


class WebhookRiskMod:
    """EM-safe advisory mod surfacing webhook-safety signals."""

    id = "webhook-risk"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for emission in emissions:
            out.extend(_emissions_for(emission))
        return out


__all__ = ["WebhookRiskMod"]
