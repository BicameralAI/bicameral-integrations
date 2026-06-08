# SPDX-License-Identifier: MIT
"""dependency_risk mod — advisory dependency-risk signals over adapter emissions (ADR-0013).

The reference EM-safe mod (ADR-0007/0008): reads immutable ``AdapterEmission`` evidence and returns
advisory artifacts only — it never writes a canonical decision, approves, resolves, or blocks. Two
deterministic, stdlib-only detection paths:

- **vulnerability path** — OSV-style evidence (``source_ref.kind == "vulnerability"``): emits a
  ``dependency_signal`` naming the affected packages + a security ``routing_hint`` + a
  ``source_evidence_annotation``, built from the connector ``metadata`` preserved through ``normalize``
  (ADR-0014: ``packages``/``severity``/``aliases``).
- **manifest-mention path** — any emission with NO vulnerability evidence whose text references a
  dependency-manifest filename: a low-confidence ``dependency_signal`` + annotation, NO routing
  (too weak to route).

Pure function over the input list (no I/O, no mutation). Every output passes ``run_mod``'s
outputs-allowlist + opaque-score + FX-SEC-001 screen.
"""

from __future__ import annotations

from typing import Literal

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint

from ..contract import ModEmission

_OUTPUTS = frozenset({"dependency_signal", "routing_hint", "source_evidence_annotation"})

# Dependency-manifest filenames, matched as CONTIGUOUS substrings of lowercased text (the ``.`` is a
# literal char, not a regex) — deterministic, NOT a semver/diff parser.
_MANIFEST_TOKENS = (
    "requirements.txt", "pyproject.toml", "package.json", "package-lock.json", "yarn.lock",
    "go.mod", "cargo.toml", "gemfile", "pom.xml", "build.gradle", "poetry.lock",
)

_ALIAS_PREFIXES = ("CVE-", "GHSA-")  # a real catalogued-vuln id → high-priority routing


def _s(value: object) -> str:
    """A stripped string for str inputs, else '' (metadata values are ``Any``)."""
    return value.strip() if isinstance(value, str) else ""


def _has_catalogued_alias(aliases: str) -> bool:
    """True iff any comma-separated alias token is a CVE/GHSA id (honest priority gate — we do
    NOT parse the CVSS vector into a band)."""
    return any(tok.strip().upper().startswith(_ALIAS_PREFIXES) for tok in aliases.split(","))


def _vuln_emissions(emission: AdapterEmission) -> list[ModEmission]:
    """Signals for EACH vulnerability-kind evidence entry (``evidence`` is a tuple; iterate all).
    ``packages``/``severity``/``aliases`` are emission-level metadata (OSV is 1-obs→1-emission→
    1-evidence today), so each evidence's signals share them — correct for the current model."""
    md = emission.metadata
    packages = _s(md.get("packages")) or "unspecified package(s)"
    severity, aliases = _s(md.get("severity")), _s(md.get("aliases"))
    priority: Literal["low", "normal", "high"] = "high" if _has_catalogued_alias(aliases) else "normal"
    out: list[ModEmission] = []
    for ev in emission.evidence:
        if ev.source_ref.kind != "vulnerability":
            continue
        ref = ev.source_ref.ref or "unknown-vuln"
        meta = {"packages": packages, "severity": severity, "aliases": aliases, "vuln": ref}
        out.append(ModEmission("dependency_signal", advisory=AdvisoryResult(
            kind="dependency_signal", message=f"Dependency vulnerability {ref} affects {packages}",
            evidence_ids=(ref,), metadata=meta)))
        out.append(ModEmission("routing_hint", routing_hint=RoutingHint(
            role="security", reason=f"dependency vulnerability {ref} in {packages}", priority=priority)))
        out.append(ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
            kind="source_evidence_annotation",
            message=f"evidence is a dependency vulnerability advisory ({ref})", evidence_ids=(ref,))))
    return out


def _manifest_emissions(emission: AdapterEmission) -> list[ModEmission]:
    """Low-confidence signal when an emission's text references a dependency manifest. No routing,
    no provider id surfaced (``evidence_ids=()`` — a PR/MR ref is user-controlled)."""
    low = f"{emission.title} {emission.body}".lower()
    found = [tok for tok in _MANIFEST_TOKENS if tok in low]
    if not found:
        return []
    joined = ", ".join(found)
    return [
        ModEmission("dependency_signal", advisory=AdvisoryResult(
            kind="dependency_signal",
            message=f"dependency manifest referenced ({joined}) — review the change",
            metadata={"manifests": joined, "source": emission.source_id})),
        ModEmission("source_evidence_annotation", advisory=AdvisoryResult(
            kind="source_evidence_annotation",
            message=f"emission references a dependency manifest ({joined})")),
    ]


class DependencyRiskMod:
    """EM-safe advisory mod surfacing dependency vulnerabilities + manifest-change signals."""

    id = "dependency-risk"
    version = "0.1.0"
    outputs = _OUTPUTS

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]:
        out: list[ModEmission] = []
        for emission in emissions:
            # vuln path takes precedence; manifest path only when no vulnerability evidence.
            out.extend(_vuln_emissions(emission) or _manifest_emissions(emission))
        return out


__all__ = ["DependencyRiskMod"]
