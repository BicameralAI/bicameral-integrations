# SPDX-License-Identifier: MIT
"""Mod execution contract (ADR-0013) — the manifest-enforced, EM-safe runner.

A mod is an **advisory post-processor** over adapter emissions (ADR-0007/0008): it reads
immutable evidence and returns advisory artifacts only. The EM-safe boundary is enforced
mostly *by construction* —

- evidence is immutable (``AdapterEmission``/``SourceEvidence`` are frozen) ⇒ a mod cannot
  delete or mutate source evidence;
- a mod's only output channel is *returning* ``ModEmission`` artifacts ⇒ it has no method to
  write a canonical decision, approve signoff, resolve compliance, create a blocking result,
  or bypass policy (none are representable).

``run_mod`` adds the rest: an **outputs allowlist** (a mod may emit only its manifest-declared
output types), **manifest⟷code consistency** (id/version/outputs mirror the governance
manifest), **no opaque confidence score** (dimensional ``ConfidenceSurface`` only), and the
**FX-SEC-001 sensitive screen** over every wire-bound artifact field (a mod that *finds* a
secret must not surface it in cleartext — the runner is the single chokepoint all mods pass).
Stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint
from adapter.core.pipeline import validate_emissions
from adapter.core.sensitive import detect_sensitive

from ._manifest import Manifest, ModManifestError, load_manifest

# The six advisory output kinds an EM-safe mod may emit (ADR-0007). Only `routing_hint`
# maps to RoutingHint; every other kind is an AdvisoryResult whose `kind` == the output_type.
_KNOWN_OUTPUTS = frozenset({
    "source_evidence_annotation",
    "dependency_signal",
    "advisory_governance_result",
    "owner_lens_hint",
    "suggested_review_question",
    "routing_hint",
})

# The full ADR-0007 forbidden-action baseline every manifest must declare (⊇).
_EM_SAFE_FORBIDDEN = frozenset({
    "write_canonical_decision",
    "approve_signoff",
    "resolve_compliance",
    "create_blocking_ci_result",
    "bypass_governance_policy",
    "mutate_source_evidence",
    "collapse_confidence_score",
})

# Substrings that mark a metadata key as an opaque numeric confidence/score (ADR-0007).
# Matched as substrings (so `confidence_score`, `risk_score`, `match_probability` all trip)
# and walked into nested dicts/lists — the structural guard against score-smuggling. It is a
# guard, not a proof no numeric signal exists: the real guarantee is that AdvisoryResult has
# no first-class scalar score field, so a dimensional ConfidenceSurface is the only channel.
_SCORE_TOKENS = ("confidence", "score", "probability", "likelihood")


class ModContractError(ValueError):
    """Raised when a mod or its emission violates the EM-safe execution contract."""


@dataclass(frozen=True)
class ModEmission:
    """One advisory artifact a mod produced, tagged with its declared ``output_type``.

    ``__post_init__`` binds the tag to the artifact: exactly one of ``advisory`` /
    ``routing_hint`` is populated, and ``output_type == 'routing_hint'`` iff a ``RoutingHint``
    is carried (every other type carries an ``AdvisoryResult`` whose ``kind`` matches). This
    makes an advisory-masquerading-as-routing_hint structurally impossible.
    """

    output_type: str
    advisory: AdvisoryResult | None = None
    routing_hint: RoutingHint | None = None

    def __post_init__(self) -> None:
        populated = [a for a in (self.advisory, self.routing_hint) if a is not None]
        if len(populated) != 1:
            raise ModContractError(
                f"ModEmission {self.output_type!r} must carry exactly one artifact"
            )
        if self.output_type == "routing_hint":
            if self.routing_hint is None:
                raise ModContractError("output_type 'routing_hint' requires a RoutingHint")
        elif self.advisory is None:
            raise ModContractError(f"output_type {self.output_type!r} requires an AdvisoryResult")
        elif self.advisory.kind != self.output_type:
            raise ModContractError(
                f"advisory.kind {self.advisory.kind!r} != output_type {self.output_type!r}"
            )


@runtime_checkable
class Mod(Protocol):
    """An EM-safe advisory mod. Reads immutable evidence; returns advisory artifacts only.

    ``id``/``version``/``outputs`` mirror the mod's ``manifest.yaml`` (verified by
    ``validate_manifest``). ``id`` is the canonical hyphenated form (e.g. ``dependency-risk``).
    """

    id: str
    version: str
    outputs: frozenset[str]

    def evaluate(self, emissions: list[AdapterEmission]) -> list[ModEmission]: ...


def validate_manifest(manifest: Manifest, mod: Mod) -> None:
    """Enforce manifest⟷code consistency + the EM-safe forbidden baseline. Fail-closed."""
    if mod.id != manifest.id:
        raise ModContractError(f"mod.id {mod.id!r} != manifest.id {manifest.id!r}")
    if mod.version != manifest.version:
        raise ModContractError(f"mod.version {mod.version!r} != manifest.version {manifest.version!r}")
    if frozenset(mod.outputs) != manifest.outputs:
        raise ModContractError(f"{mod.id}: code outputs {set(mod.outputs)} != manifest {set(manifest.outputs)}")
    unknown = manifest.outputs - _KNOWN_OUTPUTS
    if unknown:
        raise ModContractError(f"{mod.id}: unknown output types {unknown}")
    missing = _EM_SAFE_FORBIDDEN - manifest.forbidden_actions
    if missing:
        raise ModContractError(f"{mod.id}: manifest forbidden_actions missing EM-safe baseline {missing}")


def _flatten_strings(value: object) -> list[str]:
    """All string leaves AND dict keys of a (possibly nested) metadata value, for the
    sensitive screen. Walks dict keys+values, lists/tuples/sets so a secret nested in
    metadata (or smuggled into a KEY) cannot escape; non-str scalars are stringified (a
    custom ``__str__`` or ``bytes`` can't dodge the screen). Behaviourally identical to
    ``adapter.core.pipeline._metadata_strings`` (intentional duplication — change both)."""
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        out: list[str] = []
        for key, sub in value.items():
            out.extend(_flatten_strings(key))
            out.extend(_flatten_strings(sub))
        return out
    if isinstance(value, (list, tuple, set)):
        return [s for item in value for s in _flatten_strings(item)]
    return [] if value is None else [str(value)]


def _wire_text(emission: ModEmission) -> list[str]:
    """Every wire-bound free-text field of a mod artifact (for the sensitive screen).
    ``priority`` is excluded by design — it is a closed ``Literal``, not free text."""
    parts: list[str] = []
    adv, rh = emission.advisory, emission.routing_hint
    if adv is not None:
        parts.append(adv.message)
        parts.extend(adv.evidence_ids)
        parts.extend(_flatten_strings(adv.metadata))
    if rh is not None:
        parts.extend([rh.reason, rh.role])
    return [p for p in parts if p]


def _score_like(key: str) -> bool:
    return any(tok in key.lower() for tok in _SCORE_TOKENS)


def _is_score(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _opaque_scores(meta: dict[str, object], *, tainted: bool) -> list[str]:
    """Keys of opaque numeric scores in ``meta``. A numeric leaf is opaque when its own key or
    any ancestor key is score-like (so ``{"scores": {"overall": 0.9}}`` is caught — the parent
    names the score). Walks nested dicts and dicts inside lists; ``bool`` is a flag, not a score."""
    found: list[str] = []
    for key, value in meta.items():
        here = tainted or _score_like(key)
        if isinstance(value, dict):
            found.extend(_opaque_scores(value, tainted=here))
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, dict):
                    found.extend(_opaque_scores(item, tainted=here))
                elif here and _is_score(item):
                    found.append(key)
        elif here and _is_score(value):
            found.append(key)
    return found


def _reject_opaque_score(emission: ModEmission) -> None:
    """Reject a numeric confidence/score in metadata (ADR-0007: no opaque score — use the
    dimensional ``ConfidenceSurface``). Matches score-like key substrings + ancestor taint."""
    adv = emission.advisory
    if adv is None:
        return
    hits = _opaque_scores(adv.metadata, tainted=False)
    if hits:
        raise ModContractError(
            f"{emission.output_type}: opaque numeric score in metadata ({hits[0]!r}) "
            "forbidden — use a ConfidenceSurface"
        )


def run_mod(
    mod: Mod, emissions: list[AdapterEmission], manifest: Manifest
) -> list[ModEmission]:
    """Run a mod under its manifest, EM-safe + FX-SEC-001 enforced. Fail-closed.

    Re-screens the **input** emissions (``validate_emissions``) before ``evaluate`` sees them —
    a defensive boundary mirroring ``GatewaySink.emit``: a hand-built emission carrying a secret
    in ``metadata`` (now preserved through ``normalize``, ADR-0014) must not reach a mod raw.
    Then validates the manifest⟷code contract, runs ``mod.evaluate``, and for every produced
    artifact enforces: ``output_type`` is manifest-declared; no opaque confidence score; and
    no secret/PHI/PAN in any wire-bound field (a hit HARD-rejects — a mod must never surface a
    secret it detected in cleartext). Returns the validated, screened artifacts. The runner
    writes nothing canonical — it hands advisory artifacts to its caller (operator runtime).
    """
    validate_emissions(emissions)  # input boundary: fail-closed on secret-bearing/invalid input
    validate_manifest(manifest, mod)
    results = list(mod.evaluate(emissions))
    for emission in results:
        if emission.output_type not in mod.outputs:
            raise ModContractError(
                f"{mod.id}: undeclared output_type {emission.output_type!r}"
            )
        _reject_opaque_score(emission)
        hits = detect_sensitive(" ".join(_wire_text(emission)))
        if hits:
            raise ModContractError(
                f"{mod.id}: mod output carries sensitive data ({hits[0].cls}) — refused"
            )
    return results


__all__ = [
    "Mod",
    "ModEmission",
    "ModContractError",
    "validate_manifest",
    "run_mod",
    "Manifest",
    "ModManifestError",
    "load_manifest",
]
