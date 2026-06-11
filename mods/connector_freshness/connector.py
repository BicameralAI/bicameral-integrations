# SPDX-License-Identifier: MIT
"""connector_freshness mod — advisory provider-freshness signals (ADR-0013).

EM-safe (ADR-0007/0008): reads immutable ``AdapterEmission`` evidence and returns advisory
artifacts only — it never fetches a provider or expands a credential. Pure function over the
input list (no I/O): signals come only from the emission text.

Deterministic detection (lowercased contiguous-substring match):

- **deprecation / breaking change** — the text names a provider deprecation, sunset, EOL,
  breaking change, or API-version migration: routes to connector review (strong signal).
- **soft version mention** — the text references an API version without a break term: annotated
  only (too weak to route).

No freshness term → NO output.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from ..contract import ModEmission

_OUTPUTS = frozenset({"advisory_governance_result", "routing_hint", "source_evidence_annotation"})

# Strong: a provider change that can break a connector's assumptions -> route.
_BREAK_TERMS = (
    "deprecat", "sunset", "end of life", "end-of-life", "breaking change",
    "no longer supported", "will be removed", "retire", "migrate to v", "upgrade to v",
)
# Soft: an API-version mention with no break term -> annotate only.
_VERSION_TERMS = ("api version", "v1 ", "v2 ", "v3 ", "/v1/", "/v2/", "/v3/")


def _text(emission: AdapterEmission) -> str:
    parts = [emission.title, emission.body]
    parts.extend(ev.excerpt for ev in emission.evidence)
    return " ".join(p for p in parts if isinstance(p, str)).lower()


def _emissions_for(emission: AdapterEmission) -> list[ModEmission]:
    text = _text(emission)
    breaks = [t for t in _BREAK_TERMS if t in text]
    soft = [t for t in _VERSION_TERMS if t in text]
    if not breaks and not soft:
        return []
    src = (emission.source_id or "unknown").strip() or "unknown"
    if breaks:
        joined = ", ".join(breaks)
        return [
            ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
                kind="source_evidence_annotation",
                message=f"provider-freshness signal on {src}: {joined}")),
            ModEmission("advisory_governance_result", advisory=AdvisoryResult(
                kind="advisory_governance_result",
                message=f"provider change may stale a connector assumption ({joined}) — review references/auth",
                metadata={"terms": joined, "source": emission.source_id})),
            ModEmission("routing_hint", routing_hint=RoutingHint(
                role="connectors",
                reason=f"freshness review for {src}: {joined}", priority="normal")),
        ]
    return [
        ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
            kind="source_evidence_annotation",
            message=f"api-version mention on {src} (soft freshness signal)")),
    ]


class ConnectorFreshnessMod:
    """EM-safe advisory mod surfacing stale-provider-assumption signals."""

    id = "connector-freshness"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for emission in emissions:
            out.extend(_emissions_for(emission))
        return out


__all__ = ["ConnectorFreshnessMod"]
