# SPDX-License-Identifier: MIT
"""Fail-open heuristic evaluation shared by every integration adapter.

Provider-specific parsers may attach structured advisory signals to
``Observation.metadata['advisory_signals']``. The universal adapter validates and
promotes those signals, adds cross-provider signals, and preserves the original
evidence unchanged. Heuristics never create candidate or Decision authority.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Iterable

from .emissions import AdapterEmission, AdvisoryResult

_SCHEMA_VERSION = 1
_ALLOWED_SCOPES = frozenset({"integration", "universal"})
_ALLOWED_CONFIDENCE = frozenset({"low", "medium", "high"})
_ALLOWED_EFFECTS = frozenset({"annotate", "rank_lower", "route"})
_STATUS_ONLY = frozenset({"lgtm", "approved", "done", "fixed", "closed"})
_TOKEN_RE = re.compile(r"[^a-z0-9._-]+")


def _token(value: object) -> str:
    text = str(value or "").strip().lower()
    return _TOKEN_RE.sub("_", text).strip("_")


def _advisory(
    *,
    code: str,
    scope: str,
    basis: str,
    confidence: str,
    recommended_effect: str,
    explanation: str,
) -> AdvisoryResult:
    return AdvisoryResult(
        kind=code,
        message=explanation,
        metadata={
            "scope": scope,
            "basis": basis,
            "confidence": confidence,
            "recommended_effect": recommended_effect,
            "schema_version": _SCHEMA_VERSION,
        },
    )


def _schema_error(reason: str) -> AdvisoryResult:
    """Return a diagnostic advisory instead of dropping otherwise valid evidence."""
    return _advisory(
        code="heuristic_schema_error",
        scope="universal",
        basis=reason,
        confidence="high",
        recommended_effect="annotate",
        explanation="An integration heuristic signal was malformed; evidence was preserved.",
    )


def _integration_advisories(metadata: dict[str, Any]) -> list[AdvisoryResult]:
    raw = metadata.get("advisory_signals", ())
    if raw in (None, "", (), []):
        return []
    if not isinstance(raw, (list, tuple)):
        return [_schema_error("advisory_signals_not_sequence")]

    out: list[AdvisoryResult] = []
    for item in raw:
        if not isinstance(item, dict):
            out.append(_schema_error("advisory_signal_not_object"))
            continue
        code = _token(item.get("code"))
        scope = _token(item.get("scope") or "integration")
        basis = _token(item.get("basis"))
        confidence = _token(item.get("confidence") or "medium")
        effect = _token(item.get("recommended_effect") or "annotate")
        explanation = str(item.get("explanation") or "Integration-specific advisory signal.")
        version = item.get("schema_version", _SCHEMA_VERSION)
        if not code:
            out.append(_schema_error("advisory_code_missing"))
            continue
        if scope not in _ALLOWED_SCOPES:
            out.append(_schema_error("advisory_scope_invalid"))
            continue
        if confidence not in _ALLOWED_CONFIDENCE:
            out.append(_schema_error("advisory_confidence_invalid"))
            continue
        if effect not in _ALLOWED_EFFECTS:
            out.append(_schema_error("advisory_effect_invalid"))
            continue
        if version != _SCHEMA_VERSION:
            out.append(_schema_error("advisory_schema_version_invalid"))
            continue
        out.append(
            _advisory(
                code=code,
                scope=scope,
                basis=basis or "integration_rule",
                confidence=confidence,
                recommended_effect=effect,
                explanation=explanation,
            )
        )
    return out


def _universal_advisories(emission: AdapterEmission) -> list[AdvisoryResult]:
    metadata = emission.metadata if isinstance(emission.metadata, dict) else {}
    authors = [ev.author.strip().lower() for ev in emission.evidence if ev.author.strip()]
    actor_type = str(metadata.get("actor_type", "")).strip().lower()
    body = emission.body.strip().lower()
    out: list[AdvisoryResult] = []

    if actor_type == "bot" or any(author.endswith("[bot]") for author in authors):
        out.append(
            _advisory(
                code="bot_authored",
                scope="universal",
                basis="provider_actor_type_or_author_suffix",
                confidence="high",
                recommended_effect="annotate",
                explanation="The source was authored by an automation identity.",
            )
        )

    if any("dependabot" in author or "renovate" in author for author in authors):
        out.append(
            _advisory(
                code="dependency_automation",
                scope="universal",
                basis="known_dependency_automation_identity",
                confidence="high",
                recommended_effect="rank_lower",
                explanation="The source was produced by dependency automation.",
            )
        )

    if body in _STATUS_ONLY:
        out.append(
            _advisory(
                code="status_only",
                scope="universal",
                basis="exact_status_vocabulary",
                confidence="high",
                recommended_effect="rank_lower",
                explanation="The source body contains only a bounded status phrase.",
            )
        )

    if body.startswith("<!--") or "issue template" in body:
        out.append(
            _advisory(
                code="template_dominant",
                scope="universal",
                basis="template_marker",
                confidence="medium",
                recommended_effect="rank_lower",
                explanation="Template or boilerplate markers dominate the captured source.",
            )
        )

    if bool(metadata.get("duplicate_delivery")):
        out.append(
            _advisory(
                code="duplicate_delivery",
                scope="universal",
                basis="connector_delivery_identity",
                confidence="high",
                recommended_effect="annotate",
                explanation="The connector identified this delivery as a replay or duplicate.",
            )
        )

    if bool(metadata.get("generated_sync_event")):
        out.append(
            _advisory(
                code="generated_sync_event",
                scope="universal",
                basis="connector_sync_marker",
                confidence="high",
                recommended_effect="rank_lower",
                explanation="The source represents a generated synchronization event.",
            )
        )

    if bool(metadata.get("stale_source")):
        out.append(
            _advisory(
                code="stale_source",
                scope="universal",
                basis="connector_freshness_marker",
                confidence="high",
                recommended_effect="route",
                explanation="The connector marked the source as stale.",
            )
        )

    if str(metadata.get("source_trust", "")).strip().lower() == "low":
        out.append(
            _advisory(
                code="low_source_trust",
                scope="universal",
                basis="connector_source_trust_marker",
                confidence="medium",
                recommended_effect="route",
                explanation="The connector marked the source trust posture as low.",
            )
        )

    return out


def _dedupe(advisories: Iterable[AdvisoryResult]) -> tuple[AdvisoryResult, ...]:
    out: list[AdvisoryResult] = []
    seen: set[tuple[str, str]] = set()
    for advisory in advisories:
        scope = str(advisory.metadata.get("scope", "")) if isinstance(advisory.metadata, dict) else ""
        key = (advisory.kind, scope)
        if key in seen:
            continue
        seen.add(key)
        out.append(advisory)
    return tuple(out)


def evaluate_fail_open(emission: AdapterEmission) -> AdapterEmission:
    """Attach source-aware and universal advisories without changing evidence.

    Provider-specific signals take precedence over a universal signal with the
    same code. Malformed heuristic metadata becomes a diagnostic advisory rather
    than suppressing the source.
    """
    integration = _integration_advisories(emission.metadata)
    provider_codes = {advisory.kind for advisory in integration}
    universal = [
        advisory
        for advisory in _universal_advisories(emission)
        if advisory.kind not in provider_codes
    ]
    advisories = _dedupe((*emission.advisories, *integration, *universal))
    return replace(emission, advisories=advisories)
