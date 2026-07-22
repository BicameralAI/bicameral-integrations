# SPDX-License-Identifier: MIT
"""Universal adapter pipeline: normalize observations and validate emissions."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from .capabilities import SourceMode
from .emissions import (
    AdapterEmission,
    AdvisoryResult,
    ProviderProvenance,
    RoutingHint,
    SourceEvidence,
    SourceRef,
)
from .heuristics import evaluate_fail_open
from .observations import Observation
from .redaction import redact
from .redaction_receipt import guarded_sanitize_observation
from .sensitive import detect_sensitive

_DELIVERY_MODE: dict[SourceMode, str] = {
    SourceMode.WEBHOOK: "webhook",
    SourceMode.ACTIVE: "poll",
    SourceMode.PASSIVE: "active-fetch",
    SourceMode.DISCOVERY: "poll",
}

_SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_MAX_SOURCE_ID = 128
_EMISSION_TYPES = frozenset({"candidate", "evidence", "hint", "advisory"})


class EmissionContractError(ValueError):
    """Raised when an emission violates the ADR-0005 neutral-contract rules."""


def _is_blank(text: str) -> bool:
    """True when text has no visible character."""
    return not any(not c.isspace() and unicodedata.category(c) != "Cf" for c in text)


def _require_str(value: object, label: str) -> str:
    """Require a string at the shared wire boundary."""
    if not isinstance(value, str):
        raise EmissionContractError(f"{label}_not_str: {type(value).__name__}")
    return value


def _assert_emission_types(emission: AdapterEmission) -> None:
    """Runtime type guard for every field consumed by validation or wire mapping."""
    _require_str(emission.source_id, "source_id")
    _require_str(emission.emission_type, "emission_type")
    _require_str(emission.adapter_version, "adapter_version")
    _require_str(emission.title, "title")
    _require_str(emission.body, "body")
    if not isinstance(emission.metadata, dict):
        raise EmissionContractError(f"metadata_not_dict: {type(emission.metadata).__name__}")
    if not isinstance(emission.evidence, (list, tuple)):
        raise EmissionContractError(
            f"evidence_not_sequence: {type(emission.evidence).__name__}"
        )
    for ev in emission.evidence:
        if not isinstance(ev, SourceEvidence):
            raise EmissionContractError(f"evidence_item_invalid: {type(ev).__name__}")
        if not isinstance(ev.source_ref, SourceRef):
            raise EmissionContractError(
                f"source_ref_invalid: {type(ev.source_ref).__name__}"
            )
        _require_str(ev.excerpt, "excerpt")
        _require_str(ev.author, "author")
        _require_str(ev.timestamp, "timestamp")
        _require_str(ev.evidence_id, "evidence_id")
        if not isinstance(ev.metadata, dict):
            raise EmissionContractError(
                f"evidence_metadata_not_dict: {type(ev.metadata).__name__}"
            )
        _require_str(ev.source_ref.url, "source_ref.url")
        _require_str(ev.source_ref.ref, "source_ref.ref")
        _require_str(ev.source_ref.source_id, "source_ref.source_id")
        _require_str(ev.source_ref.kind, "source_ref.kind")
    if not isinstance(emission.routing_hints, (list, tuple)):
        raise EmissionContractError(
            f"routing_hints_not_sequence: {type(emission.routing_hints).__name__}"
        )
    for hint in emission.routing_hints:
        if not isinstance(hint, RoutingHint):
            raise EmissionContractError(f"routing_hint_invalid: {type(hint).__name__}")
        _require_str(hint.role, "routing_hint.role")
        _require_str(hint.reason, "routing_hint.reason")
        _require_str(hint.priority, "routing_hint.priority")
    if not isinstance(emission.advisories, (list, tuple)):
        raise EmissionContractError(
            f"advisories_not_sequence: {type(emission.advisories).__name__}"
        )
    for advisory in emission.advisories:
        if not isinstance(advisory, AdvisoryResult):
            raise EmissionContractError(f"advisory_invalid: {type(advisory).__name__}")
        _require_str(advisory.kind, "advisory.kind")
        _require_str(advisory.message, "advisory.message")
        if not isinstance(advisory.metadata, dict):
            raise EmissionContractError(
                f"advisory_metadata_not_dict: {type(advisory.metadata).__name__}"
            )
    if emission.provenance is not None:
        if not isinstance(emission.provenance, ProviderProvenance):
            raise EmissionContractError(
                f"provenance_invalid: {type(emission.provenance).__name__}"
            )
        _require_str(emission.provenance.delivery_mode, "provenance.delivery_mode")
        _require_str(emission.provenance.verification, "provenance.verification")
        _require_str(emission.provenance.provider_event_id, "provenance.provider_event_id")
        _require_str(
            emission.provenance.provider_resource_id,
            "provenance.provider_resource_id",
        )


def validate_emissions(emissions: Iterable[AdapterEmission]) -> list[AdapterEmission]:
    """Enforce the neutral emission contract before mods or gateway delivery."""
    validated = list(emissions)
    for emission in validated:
        _assert_emission_types(emission)
        if not _SOURCE_ID_RE.match(emission.source_id):
            raise EmissionContractError(f"source_id_invalid: {emission.source_id!r}")
        if len(emission.source_id) > _MAX_SOURCE_ID:
            raise EmissionContractError("source_id_too_long")
        if not emission.evidence:
            raise EmissionContractError("evidence_required: emission has no evidence")
        if any(_is_blank(ev.excerpt) for ev in emission.evidence):
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


def _metadata_strings(value: object) -> list[str]:
    """Return every string leaf and dict key from nested metadata."""
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        out: list[str] = []
        for key, sub in value.items():
            out.extend(_metadata_strings(key))
            out.extend(_metadata_strings(sub))
        return out
    if isinstance(value, (list, tuple, set)):
        return [s for item in value for s in _metadata_strings(item)]
    return [] if value is None else [str(value)]


def _screen_sensitive(emission: AdapterEmission) -> None:
    """Reject any wire- or mod-bound field carrying configured sensitive data."""
    core = [emission.title, emission.body, emission.source_id]
    for ev in emission.evidence:
        core.extend(
            [
                ev.excerpt,
                ev.source_ref.url,
                ev.source_ref.ref,
                ev.source_ref.source_id,
                ev.source_ref.kind,
                ev.author,
                ev.timestamp,
                ev.evidence_id,
            ]
        )
    for hint in emission.routing_hints:
        core.extend([hint.role, hint.reason, hint.priority])
    for advisory in emission.advisories:
        core.extend([advisory.kind, advisory.message])
    if emission.provenance is not None:
        core.extend(
            [
                emission.provenance.delivery_mode,
                emission.provenance.verification,
                emission.provenance.provider_event_id,
                emission.provenance.provider_resource_id,
            ]
        )

    units = [part for part in core if part]
    units.extend(_metadata_strings(emission.metadata))
    for ev in emission.evidence:
        units.extend(_metadata_strings(ev.metadata))
    for advisory in emission.advisories:
        units.extend(_metadata_strings(advisory.metadata))

    for unit in units:
        hits = detect_sensitive(unit)
        if hits:
            hit = hits[0]
            raise EmissionContractError(
                f"sensitive_data:{hit.cls} (pattern={hit.pattern_id}, "
                f"excerpt={hit.match_excerpt!r}, catalog=v1)"
            )


def normalize(
    observations: Iterable[Observation], *, adapter_version: str
) -> list[AdapterEmission]:
    """Normalize every provider-neutral Observation through one mandatory seam.

    The universal sequence is:

    ``verified Observation -> required redaction -> AdapterEmission -> fail-open heuristics -> validation``.

    Provider-specific parsers may add structured advisory inputs, but they may
    not bypass shared redaction, normalization, or preserve raw sensitive data.
    """
    emissions: list[AdapterEmission] = []
    for observation in observations:
        sanitized, receipt = guarded_sanitize_observation(observation)
        emission = _emission_from(sanitized, adapter_version)
        emission.metadata["redaction_receipt"] = receipt
        emissions.append(evaluate_fail_open(emission))
    return validate_emissions(emissions)


def _provenance_from(obs: Observation) -> ProviderProvenance:
    """Derive non-authoritative provider provenance from an Observation."""
    mode = _DELIVERY_MODE.get(obs.mode, "poll")
    verification = "signed" if obs.mode == SourceMode.WEBHOOK else "unsigned"
    resource = obs.provider_resource_id or obs.source_ref.ref
    resource_id = redact(resource) if resource else ""
    event_id = redact(obs.provider_event_id) if obs.provider_event_id else ""
    return ProviderProvenance(
        delivery_mode=mode,  # type: ignore[arg-type]
        verification=verification,  # type: ignore[arg-type]
        provider_event_id=event_id,
        provider_resource_id=resource_id,
    )


def _emission_from(obs: Observation, adapter_version: str) -> AdapterEmission:
    """Build one evidence emission while preserving recorded source identity."""
    evidence = SourceEvidence(
        source_ref=obs.source_ref,
        excerpt=obs.excerpt,
        author=obs.author,
        timestamp=obs.timestamp,
        evidence_id=obs.evidence_id,
        metadata=dict(obs.evidence_metadata),
    )
    return AdapterEmission(
        source_id=obs.source_ref.source_id,
        title=obs.title,
        body=obs.excerpt,
        evidence=(evidence,),
        emission_type="evidence",
        adapter_version=adapter_version,
        provenance=_provenance_from(obs),
        metadata=dict(obs.metadata),
    )
