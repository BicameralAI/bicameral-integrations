# SPDX-License-Identifier: MIT
"""data_classification mod — flag confidentiality/PII-bearing evidence for restricted handling (ADR-0013).

Advisory (ADR-0007/0008): classifies an emission's DATA sensitivity AFTER the FX-SEC-001 producer
screen (and any connector redact-and-pass) have run — so it never sees a raw secret/PHI/PAN. Instead it
flags two residual sensitivity signals a reviewer should route on:
  - explicit confidentiality MARKERS in the text (confidential / internal-only / proprietary / nda / …);
  - REDACTION PLACEHOLDERS (``[redacted:...]``) — proof the source carried PII/secret that was scrubbed,
    so the surrounding context is still sensitive.
On a signal it annotates + routes to restricted review; it never blocks, approves, or mutates evidence.
Emit-on-signal: unremarkable/general evidence yields no annotation. Deterministic (sorted markers),
whole-word, stdlib-only. (Source-TRUST tiering is a sibling concern — source_trust_calibration.)
"""

from __future__ import annotations

import re

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from ..contract import ModEmission

_OUTPUTS = frozenset({"advisory_governance_result", "routing_hint", "source_evidence_annotation"})

_MARKERS = (
    "confidential", "internal only", "internal-only", "proprietary", "nda",
    "do not share", "do not distribute", "restricted", "classified", "privileged",
)
_MARKER_RE = re.compile(r"(?i)\b(" + "|".join(m.replace(" ", r"\s+") for m in _MARKERS) + r")\b")
_REDACTION_RE = re.compile(r"\[redacted:[a-z]+\]")


def _text(emission: AdapterEmission) -> str:
    return " ".join([emission.title, emission.body, *(ev.excerpt for ev in emission.evidence)])


def _signals(text: str) -> list[str]:
    """Sorted confidentiality markers (whitespace-normalized) + a ``redacted-pii`` flag when a
    redaction placeholder is present. Empty list ⇒ general/unremarkable (no annotation)."""
    signals = sorted({re.sub(r"\s+", " ", m.lower()) for m in _MARKER_RE.findall(text)})
    if _REDACTION_RE.search(text):
        signals.append("redacted-pii")
    return signals


class DataClassificationMod:
    """Flag confidentiality/PII-bearing evidence for restricted review (advisory only)."""

    id = "data-classification"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for em in emissions:
            signals = _signals(_text(em))
            if not signals:
                continue  # general / unremarkable — emit nothing
            joined = ", ".join(signals)
            eids = tuple(sorted({ev.source_ref.ref for ev in em.evidence if ev.source_ref.ref}))
            out.append(ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
                kind="source_evidence_annotation",
                message=f"data classification: RESTRICTED ({joined})",
                evidence_ids=eids,
                metadata={"classification": "restricted", "signals": joined})))
            out.append(ModEmission("routing_hint", routing_hint=RoutingHint(
                role="restricted-review", reason=f"restricted-classified evidence ({joined})")))
            out.append(ModEmission("advisory_governance_result", advisory=AdvisoryResult(
                kind="advisory_governance_result",
                message=f"evidence classified RESTRICTED -> route to restricted review ({joined})",
                metadata={"classification": "restricted"})))
        return out


__all__ = ["DataClassificationMod"]
