"""Behavior tests for the universal adapter pipeline (normalize + validate)."""

from __future__ import annotations

import pytest

from adapter.core.capabilities import SourceMode
from adapter.core.emissions import (
    AdapterEmission,
    ConfidenceSurface,
    SourceEvidence,
    SourceRef,
)
from adapter.core.observations import Observation
from adapter.core.pipeline import (
    EmissionContractError,
    normalize,
    validate_emissions,
)


def _ref() -> SourceRef:
    return SourceRef(
        source_id="github",
        ref="o/r#1",
        url="https://github.com/o/r/pull/1",
        kind="pull_request",
    )


def _evidence() -> SourceEvidence:
    return SourceEvidence(
        source_ref=_ref(), excerpt="we will use postgres", author="alice"
    )


def _emission(**overrides: object) -> AdapterEmission:
    base: dict = dict(
        source_id="github",
        title="Adopt Postgres",
        body="we will use postgres",
        evidence=(_evidence(),),
        emission_type="candidate",
        adapter_version="github/0.1.0",
    )
    base.update(overrides)
    return AdapterEmission(**base)  # type: ignore[arg-type]


def test_validate_accepts_wellformed_emission():
    em = _emission()
    assert validate_emissions([em]) == [em]


def test_validate_rejects_missing_evidence():
    with pytest.raises(EmissionContractError):
        validate_emissions([_emission(evidence=())])


def test_validate_rejects_blank_evidence_excerpt():
    blank = SourceEvidence(source_ref=_ref(), excerpt="   ")
    with pytest.raises(EmissionContractError):
        validate_emissions([_emission(evidence=(blank,))])


def test_validate_rejects_empty_source_id():
    with pytest.raises(EmissionContractError):
        validate_emissions([_emission(source_id="")])


def test_validate_rejects_unknown_emission_type():
    with pytest.raises(EmissionContractError):
        validate_emissions([_emission(emission_type="decision")])


def test_validate_rejects_empty_adapter_version():
    with pytest.raises(EmissionContractError):
        validate_emissions([_emission(adapter_version="")])


def test_validate_rejects_scalar_confidence():
    # A ConfidenceSurface with no named dimensions is an opaque score → rejected.
    with pytest.raises(EmissionContractError):
        validate_emissions([_emission(confidence=ConfidenceSurface(dimensions={}))])


def test_normalize_preserves_excerpt_and_version():
    obs = Observation(
        source_ref=_ref(),
        excerpt="we will use postgres",
        title="Adopt Postgres",
        mode=SourceMode.ACTIVE,
    )
    out = normalize([obs], adapter_version="a/1.2.3")
    assert len(out) == 1
    assert out[0].evidence[0].excerpt == "we will use postgres"
    assert out[0].adapter_version == "a/1.2.3"


def test_normalize_maps_source_id_from_ref():
    obs = Observation(source_ref=_ref(), excerpt="x")
    out = normalize([obs], adapter_version="a/1")
    assert out[0].source_id == "github"
