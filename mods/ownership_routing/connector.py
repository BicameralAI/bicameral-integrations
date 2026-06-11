# SPDX-License-Identifier: MIT
"""ownership_routing mod — advisory reviewer-lens / domain-ownership signals (ADR-0013).

EM-safe (ADR-0007/0008): reads immutable ``AdapterEmission`` evidence and returns advisory
artifacts only — it may SUGGEST a reviewer lens or owner, never assign a reviewer, require
approval, or override branch protection. Pure function over the input list (no I/O): fires only on
**change evidence** and keys off the change text.

Deterministic detection: map domain hints in the change text to a reviewer lens (security /
connectors / governance / ci / docs). Emits one ``owner_lens_hint`` + one ``routing_hint`` per
matched domain, plus a single annotation. No domain matched on a change → NO output.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from ..contract import ModEmission

_OUTPUTS = frozenset({"owner_lens_hint", "routing_hint", "source_evidence_annotation"})

_CHANGE_KINDS = frozenset({"pull_request", "issue", "merge_request"})

# Domain -> the substrings that imply that domain owns the change (ordered for stable output).
_DOMAINS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("security", ("security", "auth", "crypto", "redact", "sensitive", "vulnerability", "credential", "signature")),
    ("connectors", ("connector", "adapter", "webhook", "parse surface", "poll spec")),
    ("governance", ("governance", "ledger", "adr", "compliance", "policy", "trust tier")),
    ("ci", (".github/workflows", "ci pipeline", "scorecard", "sbom", "workflow yaml")),
    ("docs", ("readme", "documentation", "docs/", "changelog")),
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
    domains = [name for name, terms in _DOMAINS if any(t in text for t in terms)]
    if not domains:
        return []
    src = (emission.source_id or "unknown").strip() or "unknown"
    out: list[ModEmission] = [
        ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
            kind="source_evidence_annotation",
            message=f"change on {src} maps to owner lens(es): {', '.join(domains)}")),
    ]
    for domain in domains:
        out.append(ModEmission("owner_lens_hint", advisory=AdvisoryResult(
            kind="owner_lens_hint", message=f"review through the {domain} lens",
            metadata={"lens": domain, "source": emission.source_id})))
        out.append(ModEmission("routing_hint", routing_hint=RoutingHint(
            role=domain, reason=f"{domain}-owned change in {src}", priority="normal")))
    return out


class OwnershipRoutingMod:
    """EM-safe advisory mod suggesting reviewer lenses / domain ownership."""

    id = "ownership-routing"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for emission in emissions:
            out.extend(_emissions_for(emission))
        return out


__all__ = ["OwnershipRoutingMod"]
