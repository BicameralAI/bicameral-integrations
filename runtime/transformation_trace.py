# SPDX-License-Identifier: MIT
"""Canonical cross-repository transformation-trace projection for ingest.

The universal ingest path already emits concrete phase records. This module
projects those records into ``bicameral.transformation-trace/v1`` without
changing acquisition, normalization, heuristic, or delivery behavior.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

TRACE_SCHEMA = "bicameral.transformation-trace/v1"
TRACE_SET_SCHEMA = "bicameral.transformation-trace-set/v1"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

_PHASE_CONTRACTS = {
    "PHASE-01-PROVIDER-ACQUISITION": "bicameral.provider-capture/v1",
    "PHASE-04-OBSERVATION": "bicameral.observation/v1",
    "PHASE-05-PROVIDER-ADVISORIES": "bicameral.ingress-advisory/v1",
    "PHASE-06-UNIVERSAL-NORMALIZATION": "bicameral.adapter-emission/v1",
    "PHASE-07-UNIVERSAL-ADVISORIES": "bicameral.ingress-advisory/v1",
    "PHASE-08-GATEWAY-MAPPING": "bicameral.external-ingest-envelope/v2",
    "PHASE-08-GATEWAY-DELIVERY": "bicameral.gateway-delivery-receipt/v1",
}


class TransformationTraceContractError(ValueError):
    """A canonical transformation trace is incomplete or internally inconsistent."""


@dataclass(frozen=True)
class TransformationTraceContext:
    """Immutable execution context supplied by the conformance or runtime caller."""

    journey_id: str
    trace_id: str
    component_revision: str
    occurred_at: str
    contract_fingerprints: Mapping[str, str]
    attempt: int = 1
    correlation_ids: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        _required_text(self.journey_id, "journey_id")
        _required_text(self.trace_id, "trace_id")
        if not _SHA_RE.fullmatch(self.component_revision):
            raise TransformationTraceContractError("component_revision_must_be_full_sha")
        _required_text(self.occurred_at, "occurred_at")
        if self.attempt < 1:
            raise TransformationTraceContractError("attempt_must_be_positive")
        for contract_id in set(_PHASE_CONTRACTS.values()):
            fingerprint = self.contract_fingerprints.get(contract_id)
            if not isinstance(fingerprint, str) or not _DIGEST_RE.fullmatch(fingerprint):
                raise TransformationTraceContractError(
                    f"contract_fingerprint_required:{contract_id}"
                )
        for key, value in self.correlation_ids.items():
            _required_text(key, "correlation_id_key")
            _required_text(value, f"correlation_id:{key}")


def canonical_digest(value: object) -> str:
    """Return a SHA-256 digest over deterministic UTF-8 JSON serialization."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TransformationTraceContractError(f"{label}_required")
    return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TransformationTraceContractError(f"{label}_must_be_object")
    return cast(Mapping[str, Any], value)


def _phase_by_id(trace: Mapping[str, Any], phase_id: str) -> Mapping[str, Any] | None:
    raw_phases = trace.get("phases")
    if not isinstance(raw_phases, list):
        raise TransformationTraceContractError("phases_required")
    for raw_phase in raw_phases:
        if isinstance(raw_phase, Mapping) and raw_phase.get("id") == phase_id:
            return cast(Mapping[str, Any], raw_phase)
    return None


def _copy(value: object) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _copy_object(value: object) -> dict[str, Any]:
    copied = _copy(value)
    if not isinstance(copied, dict):
        raise TransformationTraceContractError("copied_value_must_be_object")
    return cast(dict[str, Any], copied)


def _advisories(
    emission: Mapping[str, Any],
    *,
    scope: str,
) -> list[Mapping[str, Any]]:
    raw = emission.get("advisories")
    if not isinstance(raw, list):
        return []
    output: list[Mapping[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        typed_item = cast(Mapping[str, Any], item)
        metadata = typed_item.get("metadata")
        item_scope = metadata.get("scope") if isinstance(metadata, Mapping) else None
        if item_scope == scope:
            output.append(typed_item)
    return output


def _delta_items(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    return [
        {"path": "/", "reason": item.strip()}
        for item in raw
        if isinstance(item, str) and item.strip()
    ]


def _legacy_delta(phase: Mapping[str, Any]) -> dict[str, list[dict[str, str]]]:
    transformation = phase.get("transformation")
    source = cast(Mapping[str, Any], transformation) if isinstance(transformation, Mapping) else {}
    return {
        "preserved": _delta_items(source.get("preserved")),
        "added": _delta_items(source.get("added")),
        "transformed": _delta_items(source.get("transformed")),
        "removed": _delta_items(source.get("removed")),
        "redacted": _delta_items(source.get("redacted")),
    }


def _advisory_records(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in items:
        metadata = item.get("metadata")
        details = cast(Mapping[str, Any], metadata) if isinstance(metadata, Mapping) else {}
        records.append(
            {
                "advisory_id": str(item.get("code") or item.get("kind") or "unknown"),
                "result": "signal",
                "score": None,
                "authority": "none",
                "failure_mode": "fail_open",
                "scope": details.get("scope", "unknown"),
                "confidence": details.get("confidence", "unknown"),
                "recommended_effect": details.get("recommended_effect", "annotate"),
                "basis": details.get("basis", "unspecified"),
            }
        )
    return records


def _record(
    *,
    context: TransformationTraceContext,
    phase_id: str,
    function: str,
    input_schema: str,
    input_data: object,
    output_schema: str,
    output_data: object,
    delta: Mapping[str, Any],
    hard_gates: Sequence[Mapping[str, Any]] = (),
    advisories: Sequence[Mapping[str, Any]] = (),
    persistence: Mapping[str, Any] | None = None,
    authority_before: str,
    authority_after: str,
    authority_transition: str,
    receipt_status: str = "completed",
    reason_codes: Sequence[str] = (),
    retryable: bool = False,
) -> dict[str, Any]:
    contract_id = _PHASE_CONTRACTS[phase_id]
    persistence_value: Mapping[str, Any] = persistence or {
        "plane": "none",
        "operation": "none",
        "artifact_id": None,
        "digest": None,
        "locator": None,
    }
    return {
        "schema": TRACE_SCHEMA,
        "journey_id": context.journey_id,
        "trace_id": context.trace_id,
        "phase_id": phase_id,
        "occurred_at": context.occurred_at,
        "component": {
            "id": "ELM-INTEGRATIONS",
            "repository": "BicameralAI/bicameral-integrations",
            "revision": context.component_revision,
            "function": function,
        },
        "contract": {
            "id": contract_id,
            "semantic_fingerprint": context.contract_fingerprints[contract_id],
        },
        "input": {
            "schema": input_schema,
            "digest": canonical_digest(input_data),
            "data": _copy(input_data),
        },
        "output": {
            "schema": output_schema,
            "digest": canonical_digest(output_data),
            "data": _copy(output_data),
        },
        "delta": _copy(delta),
        "evaluation": {
            "hard_gates": _copy(list(hard_gates)),
            "advisories": _copy(list(advisories)),
        },
        "persistence": _copy(persistence_value),
        "authority": {
            "before": authority_before,
            "after": authority_after,
            "transition": authority_transition,
            "canonical": False,
        },
        "timing": {
            "started_at": context.occurred_at,
            "completed_at": context.occurred_at,
            "duration_ms": 0,
            "attempt": context.attempt,
        },
        "receipt": {
            "status": receipt_status,
            "reason_codes": list(reason_codes),
            "retryable": retryable,
            "correlation_ids": dict(context.correlation_ids),
        },
    }


def project_ingest_transformation_trace(
    trace: Mapping[str, Any],
    *,
    context: TransformationTraceContext,
) -> dict[str, Any]:
    """Project a PR #255 ingest trace into the accepted cross-repository contract."""

    context.validate()
    observation = _mapping(trace.get("observation"), "observation")
    emission = _mapping(trace.get("emission"), "emission")
    envelope = _mapping(trace.get("external_ingest_envelope"), "external_ingest_envelope")

    capture_phase = _phase_by_id(trace, "provider_capture")
    observation_phase = _phase_by_id(trace, "observation")
    emission_phase = _phase_by_id(trace, "adapter_emission")
    envelope_phase = _phase_by_id(trace, "external_envelope")
    delivery_phase = _phase_by_id(trace, "delivery_state")

    missing: list[str] = []
    if observation_phase is None:
        missing.append("observation")
    if emission_phase is None:
        missing.append("adapter_emission")
    if envelope_phase is None:
        missing.append("external_envelope")
    if missing:
        raise TransformationTraceContractError(
            "missing_required_legacy_phases:" + ",".join(missing)
        )
    assert observation_phase is not None
    assert emission_phase is not None
    assert envelope_phase is not None

    records: list[dict[str, Any]] = []
    state: object = {}

    if capture_phase is not None:
        capture = _mapping(capture_phase.get("data"), "provider_capture_data")
        records.append(
            _record(
                context=context,
                phase_id="PHASE-01-PROVIDER-ACQUISITION",
                function=str(capture_phase.get("function") or "provider_acquisition.capture"),
                input_schema="provider-specific/capture",
                input_data=capture,
                output_schema="bicameral.provider-capture/v1",
                output_data=capture,
                delta=_legacy_delta(capture_phase),
                hard_gates=(
                    {
                        "gate_id": "GATE-PROVIDER-ACQUISITION",
                        "result": "pass",
                        "reason_code": "CAPTURE_ACCEPTED",
                        "evidence": [],
                    },
                ),
                authority_before="external_evidence",
                authority_after="external_evidence",
                authority_transition="none",
            )
        )
        state = capture

    records.append(
        _record(
            context=context,
            phase_id="PHASE-04-OBSERVATION",
            function=str(observation_phase.get("function") or "provider_parser.observe"),
            input_schema=(
                "bicameral.provider-capture/v1" if capture_phase else "provider-specific/capture"
            ),
            input_data=state,
            output_schema="bicameral.observation/v1",
            output_data=observation,
            delta=_legacy_delta(observation_phase),
            hard_gates=(
                {
                    "gate_id": "GATE-OBSERVATION-CONTRACT",
                    "result": "pass",
                    "reason_code": "OBSERVATION_VALID",
                    "evidence": [],
                },
            ),
            authority_before="external_evidence",
            authority_after="normalized_evidence",
            authority_transition="normalize",
        )
    )
    state = observation

    provider_advisories = _advisories(emission, scope="integration")
    provider_state = _copy_object(observation)
    provider_state["advisories"] = _copy(provider_advisories)
    records.append(
        _record(
            context=context,
            phase_id="PHASE-05-PROVIDER-ADVISORIES",
            function="adapter.core.heuristics.evaluate_provider_signals",
            input_schema="bicameral.observation/v1",
            input_data=state,
            output_schema="bicameral.observation-with-advisories/v1",
            output_data=provider_state,
            delta={
                "preserved": [{"path": "/", "reason": "observation preserved"}],
                "added": [{"path": "/advisories", "reason": "provider-aware signals"}],
                "transformed": [],
                "removed": [],
                "redacted": [],
            },
            advisories=_advisory_records(provider_advisories),
            authority_before="normalized_evidence",
            authority_after="normalized_evidence",
            authority_transition="annotate",
        )
    )
    state = provider_state

    integration_only_emission = _copy_object(emission)
    integration_only_emission["advisories"] = _copy(provider_advisories)
    records.append(
        _record(
            context=context,
            phase_id="PHASE-06-UNIVERSAL-NORMALIZATION",
            function=str(emission_phase.get("function") or "adapter.core.pipeline.normalize"),
            input_schema="bicameral.observation-with-advisories/v1",
            input_data=state,
            output_schema="bicameral.adapter-emission/v1",
            output_data=integration_only_emission,
            delta=_legacy_delta(emission_phase),
            hard_gates=(
                {
                    "gate_id": "GATE-ADAPTER-EMISSION-CONTRACT",
                    "result": "pass",
                    "reason_code": "EMISSION_VALID",
                    "evidence": [],
                },
            ),
            authority_before="normalized_evidence",
            authority_after="normalized_evidence",
            authority_transition="normalize",
        )
    )
    state = integration_only_emission

    universal_advisories = _advisories(emission, scope="universal")
    records.append(
        _record(
            context=context,
            phase_id="PHASE-07-UNIVERSAL-ADVISORIES",
            function="adapter.core.heuristics.evaluate_fail_open",
            input_schema="bicameral.adapter-emission/v1",
            input_data=state,
            output_schema="bicameral.adapter-emission/v1",
            output_data=emission,
            delta={
                "preserved": [{"path": "/", "reason": "emission evidence preserved"}],
                "added": [
                    {"path": "/advisories", "reason": "universal fail-open signals"}
                ],
                "transformed": [],
                "removed": [],
                "redacted": [],
            },
            advisories=_advisory_records(universal_advisories),
            authority_before="normalized_evidence",
            authority_after="normalized_evidence",
            authority_transition="annotate",
        )
    )
    state = emission

    records.append(
        _record(
            context=context,
            phase_id="PHASE-08-GATEWAY-MAPPING",
            function=str(
                envelope_phase.get("function")
                or "runtime.gateway_mapping.emission_to_external_envelope"
            ),
            input_schema="bicameral.adapter-emission/v1",
            input_data=state,
            output_schema="bicameral.external-ingest-envelope/v2",
            output_data=envelope,
            delta=_legacy_delta(envelope_phase),
            hard_gates=(
                {
                    "gate_id": "GATE-AUTHORITY-STRIPPING",
                    "result": "pass",
                    "reason_code": "ENVELOPE_NON_AUTHORITATIVE",
                    "evidence": [],
                },
            ),
            authority_before="normalized_evidence",
            authority_after="normalized_evidence",
            authority_transition="wire_projection",
        )
    )
    state = envelope

    if delivery_phase is not None:
        delivery = _mapping(delivery_phase.get("data"), "delivery_state_data")
        status = delivery.get("status")
        completed = status == 201 or status == "accepted"
        cursor_advanced = delivery.get("cursor_verdict") == "advance"
        records.append(
            _record(
                context=context,
                phase_id="PHASE-08-GATEWAY-DELIVERY",
                function=str(delivery_phase.get("function") or "GatewaySink.deliver"),
                input_schema="bicameral.external-ingest-envelope/v2",
                input_data=state,
                output_schema="bicameral.gateway-delivery-receipt/v1",
                output_data=delivery,
                delta=_legacy_delta(delivery_phase),
                hard_gates=(
                    {
                        "gate_id": "GATE-GATEWAY-DELIVERY",
                        "result": "pass" if completed else "fail",
                        "reason_code": "HTTP_201" if completed else "DELIVERY_NOT_ACCEPTED",
                        "evidence": [],
                    },
                ),
                persistence={
                    "plane": "local_work" if cursor_advanced else "none",
                    "operation": "update" if cursor_advanced else "none",
                    "artifact_id": "connector_cursor" if cursor_advanced else None,
                    "digest": canonical_digest(delivery.get("cursor", {}))
                    if cursor_advanced
                    else None,
                    "locator": None,
                },
                authority_before="normalized_evidence",
                authority_after="normalized_evidence",
                authority_transition="deliver",
                receipt_status="completed" if completed else "failed",
                reason_codes=("HTTP_201",) if completed else ("DELIVERY_NOT_ACCEPTED",),
                retryable=not completed,
            )
        )

    result = {
        "schema": TRACE_SET_SCHEMA,
        "journey_id": context.journey_id,
        "trace_id": context.trace_id,
        "records": records,
    }
    validate_transformation_trace_set(result)
    return result


def validate_transformation_trace_set(trace_set: Mapping[str, Any]) -> None:
    """Fail closed on malformed records, digest breaks, or authority escalation."""

    if trace_set.get("schema") != TRACE_SET_SCHEMA:
        raise TransformationTraceContractError("trace_set_schema_invalid")
    journey_id = _required_text(trace_set.get("journey_id"), "journey_id")
    trace_id = _required_text(trace_set.get("trace_id"), "trace_id")
    raw_records = trace_set.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        raise TransformationTraceContractError("trace_records_required")

    previous_output_digest: str | None = None
    seen_phase_ids: set[str] = set()
    for index, raw_record in enumerate(raw_records):
        record = _mapping(raw_record, f"record_{index}")
        if record.get("schema") != TRACE_SCHEMA:
            raise TransformationTraceContractError(f"record_{index}_schema_invalid")
        if record.get("journey_id") != journey_id or record.get("trace_id") != trace_id:
            raise TransformationTraceContractError(f"record_{index}_identity_mismatch")
        phase_id = _required_text(record.get("phase_id"), f"record_{index}_phase_id")
        if phase_id in seen_phase_ids:
            raise TransformationTraceContractError(f"duplicate_phase_id:{phase_id}")
        seen_phase_ids.add(phase_id)

        component = _mapping(record.get("component"), f"record_{index}_component")
        revision = component.get("revision")
        if not isinstance(revision, str) or not _SHA_RE.fullmatch(revision):
            raise TransformationTraceContractError(f"record_{index}_revision_invalid")
        contract = _mapping(record.get("contract"), f"record_{index}_contract")
        if contract.get("id") != _PHASE_CONTRACTS.get(phase_id):
            raise TransformationTraceContractError(f"record_{index}_contract_id_invalid")
        fingerprint = contract.get("semantic_fingerprint")
        if not isinstance(fingerprint, str) or not _DIGEST_RE.fullmatch(fingerprint):
            raise TransformationTraceContractError(f"record_{index}_fingerprint_invalid")

        input_value = _mapping(record.get("input"), f"record_{index}_input")
        output_value = _mapping(record.get("output"), f"record_{index}_output")
        if input_value.get("digest") != canonical_digest(input_value.get("data")):
            raise TransformationTraceContractError(f"record_{index}_input_digest_invalid")
        if output_value.get("digest") != canonical_digest(output_value.get("data")):
            raise TransformationTraceContractError(f"record_{index}_output_digest_invalid")
        if previous_output_digest is not None and input_value.get("digest") != previous_output_digest:
            raise TransformationTraceContractError(f"record_{index}_digest_chain_broken")
        previous_output_digest = str(output_value.get("digest"))

        authority = _mapping(record.get("authority"), f"record_{index}_authority")
        if authority.get("canonical") is not False:
            raise TransformationTraceContractError(
                f"record_{index}_integrations_cannot_create_canonical_authority"
            )
        _mapping(record.get("persistence"), f"record_{index}_persistence")
        _mapping(record.get("timing"), f"record_{index}_timing")
        _mapping(record.get("receipt"), f"record_{index}_receipt")
