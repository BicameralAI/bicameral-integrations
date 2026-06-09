# SPDX-License-Identifier: MIT
"""noisy_source_gate mod — suggest a manual gate for high-noise evidence sources (ADR-0013).

Advisory (ADR-0007/0008): for evidence from high-volume/low-signal sources (chat, meeting transcripts)
it suggests a manual review gate unless the operator has raised that source's trust. It **suggests**;
it never enforces. Reads `source_id`; emits a `routing_hint` + `advisory_governance_result`. The noisy
set is explicit config-as-code (not ML); a non-noisy source yields nothing. Pure, stdlib-only.
"""

from __future__ import annotations

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from ..contract import ModEmission

_OUTPUTS = frozenset({"routing_hint", "advisory_governance_result"})
# High-noise sources (chat + meeting transcripts) — explicit, conservative, extensible.
_NOISY_SOURCES = frozenset({"slack", "granola", "fathom"})


class NoisySourceGateMod:
    """Suggest a manual review gate for evidence from high-noise sources (advisory only)."""

    id = "noisy-source-gate"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for em in emissions:
            if em.source_id not in _NOISY_SOURCES:
                continue
            out.append(ModEmission("routing_hint", routing_hint=RoutingHint(
                role="reviewer", priority="low",
                reason=f"high-noise source {em.source_id!r} — suggest a manual review gate "
                       "unless this source's trust is raised")))
            out.append(ModEmission("advisory_governance_result", advisory=AdvisoryResult(
                kind="advisory_governance_result",
                message=f"evidence from high-noise source {em.source_id!r}; gate manually unless trust is raised",
                metadata={"source": em.source_id})))
        return out


__all__ = ["NoisySourceGateMod"]
