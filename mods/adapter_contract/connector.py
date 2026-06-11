# SPDX-License-Identifier: MIT
"""adapter_contract mod — advisory evidence-shape / contract-preservation signals (ADR-0013).

EM-safe (ADR-0007/0008): reads immutable ``AdapterEmission`` evidence and returns advisory
artifacts only — never writes, approves, resolves, blocks, or mutates. Pure function over the
input list (no I/O, no repo access): every signal is derived from the emission's OWN structure,
which is the one contract surface a mod can see.

Detected (deterministic):

- **lost provider pointer** — an evidence entry with NEITHER a ``source_ref.ref`` NOR a ``url``:
  the evidence cannot be tied back to its source artifact (the strongest contract breach → routes).
- **no evidence** — an emission carrying zero ``SourceEvidence`` (nothing reviewable).
- **blank excerpt** — an evidence entry with an empty excerpt (no reviewable content).

A well-formed emission (ref/url present, non-blank excerpt, ≥1 evidence) produces NO output —
silence is the default; this mod fires only on a genuine shape defect.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from .._signals import safe_id
from ..contract import ModEmission

_OUTPUTS = frozenset({"advisory_governance_result", "routing_hint", "source_evidence_annotation"})


def _s(value: object) -> str:
    """A stripped string for str inputs, else '' (defensive over Any-typed fields)."""
    return value.strip() if isinstance(value, str) else ""


def _contract_issues(emission: AdapterEmission) -> tuple[list[str], bool]:
    """Return (issue messages, routable) for one emission. ``routable`` is True when a load-bearing
    pointer is fully lost (no evidence, or evidence with neither ref nor url) — too weak to route
    on a blank-excerpt nit alone. Totality-safe: a non-tuple ``evidence`` or a None ``source_ref``
    is treated as a lost pointer, never a crash (mod purple-team crash_dos)."""
    issues: list[str] = []
    routable = False
    evidence = emission.evidence if isinstance(emission.evidence, (list, tuple)) else ()
    if not evidence:
        issues.append("emission carries zero SourceEvidence (no reviewable pointer)")
        routable = True
    for ev in evidence:
        sr = getattr(ev, "source_ref", None)
        if not (_s(getattr(sr, "ref", "")) or _s(getattr(sr, "url", ""))):
            # echo only the contract-clean id (mod purple-team pii_secret_output): a raw evidence
            # source_id could carry a generic name/email the FX-SEC-001 screen does not catch.
            issues.append(f"evidence has no locatable ref or url (source {safe_id(getattr(sr, 'source_id', ''))})")
            routable = True
        if not _s(getattr(ev, "excerpt", "")):
            issues.append("evidence excerpt is blank (no reviewable content)")
    return issues, routable


def _emissions_for(emission: AdapterEmission) -> list[ModEmission]:
    issues, routable = _contract_issues(emission)
    if not issues:
        return []
    joined = "; ".join(issues)
    src = safe_id(emission.source_id)
    out: list[ModEmission] = [
        ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
            kind="source_evidence_annotation",
            message=f"evidence-contract risk on {src}: {joined}")),
        ModEmission("advisory_governance_result", advisory=AdvisoryResult(
            kind="advisory_governance_result",
            message=f"adapter contract not fully preserved: {joined}", metadata={"issues": joined, "source": src})),
    ]
    if routable:
        out.append(ModEmission("routing_hint", routing_hint=RoutingHint(
            role="connectors",
            reason=f"evidence pointer missing on {src} — review the connector parse surface",
            priority="normal")))
    return out


class AdapterContractMod:
    """EM-safe advisory mod surfacing evidence-shape / contract-preservation defects."""

    id = "adapter-contract"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for emission in emissions:
            out.extend(_emissions_for(emission))
        return out


__all__ = ["AdapterContractMod"]
