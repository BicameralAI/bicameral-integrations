# SPDX-License-Identifier: MIT
"""Tests for the machine-checkable ingest lifecycle phase contract."""

from __future__ import annotations

import pytest

from adapter.core.capabilities import SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from runtime.ingest_conformance import trace_ingest
from runtime.ingest_phase_contract import PhaseTraceContractError, validate_phase_trace


_REQUIRED = (
    "provider_capture",
    "observation",
    "adapter_emission",
    "external_envelope",
    "delivery_state",
)


def _valid_trace() -> dict:
    observation = Observation(
        source_ref=SourceRef(
            source_id="github",
            ref="BicameralAI/example#issues/7:comment:9",
            url="https://github.com/BicameralAI/example/issues/7#issuecomment-9",
            kind="issue_comment",
        ),
        excerpt="Decision: preserve evidence.",
        title="Ingest decision",
        mode=SourceMode.WEBHOOK,
        provider_event_id="delivery-9",
        provider_resource_id="issue_comment:9",
        evidence_id="github:comment:9:v1",
    )
    return trace_ingest(
        [observation],
        adapter_version="github/0.1.0",
        source_capture={
            "action": "created",
            "repository": {"full_name": "BicameralAI/example"},
            "issue": {"number": 7},
            "comment": {"body": "Decision: preserve evidence."},
        },
        delivery_result={
            "status": 201,
            "cursor_verdict": "advance",
            "cursor": {"last_provider_event_id": "delivery-9"},
        },
    )[0]


def test_real_trace_satisfies_complete_integrations_phase_contract() -> None:
    phases = validate_phase_trace(_valid_trace(), required_phase_ids=_REQUIRED)

    assert [phase["id"] for phase in phases] == list(_REQUIRED)
    assert all(phase["data"] for phase in phases)
    assert all(phase["display"] for phase in phases)


def test_missing_required_phase_fails() -> None:
    trace = _valid_trace()
    trace["phases"] = trace["phases"][:-1]

    with pytest.raises(PhaseTraceContractError, match="missing_required_phases:delivery_state"):
        validate_phase_trace(trace, required_phase_ids=_REQUIRED)


def test_duplicate_phase_id_fails() -> None:
    trace = _valid_trace()
    trace["phases"][1]["id"] = trace["phases"][0]["id"]

    with pytest.raises(PhaseTraceContractError, match="duplicate_phase_id"):
        validate_phase_trace(trace)


def test_phase_requires_concrete_data() -> None:
    trace = _valid_trace()
    trace["phases"][1]["data"] = {}

    with pytest.raises(PhaseTraceContractError, match="phase_observation_data_required"):
        validate_phase_trace(trace)


def test_phase_requires_function_and_gate() -> None:
    trace = _valid_trace()
    trace["phases"][2]["function"] = ""

    with pytest.raises(PhaseTraceContractError, match="phase_adapter_emission_function_required"):
        validate_phase_trace(trace)

    trace = _valid_trace()
    trace["phases"][2]["transformation"]["gate"] = ""
    with pytest.raises(PhaseTraceContractError, match="phase_adapter_emission_gate_required"):
        validate_phase_trace(trace)


def test_transformation_lists_require_nonempty_strings() -> None:
    trace = _valid_trace()
    trace["phases"][3]["transformation"]["removed"] = [""]

    with pytest.raises(
        PhaseTraceContractError,
        match="phase_external_envelope_removed_items_must_be_nonempty_strings",
    ):
        validate_phase_trace(trace)
