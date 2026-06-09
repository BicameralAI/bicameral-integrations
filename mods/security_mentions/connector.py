# SPDX-License-Identifier: MIT
"""security_mentions mod — surface security-relevant mentions in evidence (ADR-0013).

Advisory (ADR-0007/0008): scans evidence text for security keywords (auth/token/secret/…) and surfaces
the *mentions* so a reviewer sees the security surface of a change at a glance. It annotates and routes;
it never blocks or approves. **Complements, never replaces** FX-SEC-001 — the producer screen (and
`run_mod`'s input re-screen) already removed any real secret, so this surfaces the WORD ("token"), never
a secret value; `run_mod` also re-screens this mod's output. Whole-word (``\b<kw>\b``), case-insensitive,
deterministic (sorted matches). Pure, stdlib-only.
"""

from __future__ import annotations

import re

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from ..contract import ModEmission

_OUTPUTS = frozenset({"advisory_governance_result", "routing_hint", "source_evidence_annotation"})
_KEYWORDS = (
    "auth", "token", "secret", "credential", "password", "oauth", "webhook", "signature",
    "vulnerability", "cve", "encryption", "tls", "certificate", "rbac", "permission",
    "privilege", "exploit",
)
_PATTERN = re.compile(r"\b(" + "|".join(_KEYWORDS) + r")\b", re.IGNORECASE)


def _matches(emission: AdapterEmission) -> list[str]:
    """Sorted unique security keywords found (whole-word) in title + body + evidence excerpts."""
    text = " ".join([emission.title, emission.body, *(ev.excerpt for ev in emission.evidence)])
    return sorted({m.lower() for m in _PATTERN.findall(text)})


class SecurityMentionsMod:
    """Surface security-relevant mentions (auth/token/secret/…) in evidence (advisory only)."""

    id = "security-mentions"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for em in emissions:
            found = _matches(em)
            if not found:
                continue
            joined = ", ".join(found)
            out.append(ModEmission("advisory_governance_result", advisory=AdvisoryResult(
                kind="advisory_governance_result",
                message=f"security-relevant mentions: {joined}", metadata={"keywords": joined})))
            out.append(ModEmission("routing_hint", routing_hint=RoutingHint(
                role="security", reason=f"security mentions in evidence ({joined})")))
            out.append(ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
                kind="source_evidence_annotation",
                message=f"evidence mentions security topics: {joined}")))
        return out


__all__ = ["SecurityMentionsMod"]
