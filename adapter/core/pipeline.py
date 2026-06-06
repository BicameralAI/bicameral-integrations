"""Universal adapter pipeline: normalize observations and validate emissions."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .emissions import AdapterEmission, SourceEvidence
from .observations import Observation
from .sensitive import detect_sensitive

_SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_EMISSION_TYPES = frozenset({"candidate", "evidence", "hint", "advisory"})


class EmissionContractError(ValueError):
    """Raised when an emission violates the ADR-0005 neutral-contract rules."""


def validate_emissions(emissions: Iterable[AdapterEmission]) -> list[AdapterEmission]:
    """Enforce the ADR-0005 emission contract before mods or the bot-gateway
    bridge consume the emissions.

    Per emission: stable ``source_id`` (``[A-Za-z0-9._-]+``); at least one
    ``SourceEvidence`` carrying a non-empty excerpt (evidence preserved); a
    recorded non-empty ``adapter_version``; ``emission_type`` within the
    non-authoritative set; and ``confidence`` either absent or a dimensional
    ``ConfidenceSurface`` (never a single opaque score).

    Returns the validated list; raises ``EmissionContractError`` on the first
    violation.
    """
    validated = list(emissions)
    for emission in validated:
        if not _SOURCE_ID_RE.match(emission.source_id):
            raise EmissionContractError(f"source_id_invalid: {emission.source_id!r}")
        if not emission.evidence:
            raise EmissionContractError("evidence_required: emission has no evidence")
        if any(not ev.excerpt.strip() for ev in emission.evidence):
            raise EmissionContractError("evidence_excerpt_blank")
        if not emission.adapter_version.strip():
            raise EmissionContractError("adapter_version_required")
        if emission.emission_type not in _EMISSION_TYPES:
            raise EmissionContractError(
                f"emission_type_invalid: {emission.emission_type!r}"
            )
        if emission.confidence is not None and not emission.confidence.dimensions:
            raise EmissionContractError("confidence_not_dimensional")
        _screen_sensitive(emission)
    return validated


def _screen_sensitive(emission: AdapterEmission) -> None:
    """Reject an emission carrying a secret / PHI / PAN. mcp parity: sensitive
    data is a HARD gate — never forwarded to the gateway. The scanned content covers
    EVERY wire-bound field: ``title``/``body``/``excerpt`` plus ``source_id`` (→ wire
    ``source_type``) and each evidence ``source_ref.url``/``ref``/``source_id`` (a secret
    in a provider URL/ref/id is otherwise forwarded as the gateway ``source`` — #52).
    The raised detail uses the redacted excerpt, so a raw value cannot leak (#53).
    """
    parts = [emission.title, emission.body, emission.source_id]
    for ev in emission.evidence:
        parts.extend([ev.excerpt, ev.source_ref.url, ev.source_ref.ref, ev.source_ref.source_id])
    hits = detect_sensitive(" ".join(p for p in parts if p))
    if hits:
        hit = hits[0]
        raise EmissionContractError(
            f"sensitive_data:{hit.cls} (pattern={hit.pattern_id}, "
            f"excerpt={hit.match_excerpt!r}, catalog=v1)"
        )


def normalize(
    observations: Iterable[Observation], *, adapter_version: str
) -> list[AdapterEmission]:
    """Universal normalization seam: provider-neutral Observations into
    reviewable AdapterEmissions.

    The single shared normalizer every connector feeds (ADR-0004); provider
    parsing stays in connectors. Emissions bridge downstream to the
    bicameral-bot gateway (not MCP). Output is contract-validated before return.
    """
    emissions = [_emission_from(obs, adapter_version) for obs in observations]
    return validate_emissions(emissions)


def _emission_from(obs: Observation, adapter_version: str) -> AdapterEmission:
    """Build one AdapterEmission from an Observation, preserving its evidence."""
    evidence = SourceEvidence(
        source_ref=obs.source_ref,
        excerpt=obs.excerpt,
        author=obs.author,
        timestamp=obs.timestamp,
    )
    return AdapterEmission(
        source_id=obs.source_ref.source_id,
        title=obs.title,
        body=obs.excerpt,
        evidence=(evidence,),
        emission_type="candidate",
        adapter_version=adapter_version,
    )
