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


_GH_TOKEN = "ghp_0123456789abcdefghijklmnopqrstuvwxyz"  # fake; ghp_ + 36 chars


def test_validate_rejects_secret_in_evidence_excerpt():
    ev = SourceEvidence(source_ref=_ref(), excerpt=f"api key {_GH_TOKEN}")
    with pytest.raises(EmissionContractError) as exc:
        validate_emissions([_emission(evidence=(ev,))])
    assert str(exc.value).startswith("sensitive_data:")


def test_validate_rejects_secret_in_body():
    with pytest.raises(EmissionContractError) as exc:
        validate_emissions([_emission(body=f"deploy with {_GH_TOKEN}")])
    assert "sensitive_data:secret" in str(exc.value)


def test_validate_error_does_not_leak_raw_secret():
    ev = SourceEvidence(source_ref=_ref(), excerpt=f"api key {_GH_TOKEN}")
    with pytest.raises(EmissionContractError) as exc:
        validate_emissions([_emission(evidence=(ev,))])
    assert _GH_TOKEN not in str(exc.value)


def test_normalize_rejects_secret_bearing_observation():
    # The screen must fire through the full normalize() seam, not only direct validation.
    obs = Observation(source_ref=_ref(), excerpt=f"token {_GH_TOKEN}")
    with pytest.raises(EmissionContractError) as exc:
        normalize([obs], adapter_version="github/0.1.0")
    assert str(exc.value).startswith("sensitive_data:")


_GHP = "ghp_0123456789abcdefghijklmnopqrstuvwxyz"  # fake github-PAT shape


def _emission_with_ref(ref: str = "o/r#1", url: str = "https://github.com/o/r/pull/1") -> AdapterEmission:
    ev = SourceEvidence(
        source_ref=SourceRef(source_id="github", ref=ref, url=url, kind="x"),
        excerpt="we will use postgres",
        author="a",
    )
    return _emission(evidence=(ev,))


def test_secret_in_source_url_is_rejected():
    # #52: a secret embedded in source_ref.url is HARD-rejected (otherwise forwarded as gateway `source`).
    em = _emission_with_ref(url=f"https://x-access-token:{_GHP}@github.com/o/r")
    with pytest.raises(EmissionContractError):
        validate_emissions([em])


def test_secret_in_source_ref_is_rejected():
    with pytest.raises(EmissionContractError):
        validate_emissions([_emission_with_ref(ref=f"token-{_GHP}")])


def test_clean_realistic_url_and_ref_still_pass():
    # advisory: realistic high-risk-shaped url/ref that flow through the live harness must NOT false-positive.
    for ref, url in [
        ("o/r#92", "https://github.com/o/r/pull/92"),
        ("ENG-1", "https://example.atlassian.net/browse/ENG-1"),
        (
            "1AbcDEFghIJKlmNOpqRStuVWxyz0123456789ABCDEF",
            "https://docs.google.com/document/d/1AbcDEFghIJKlmNOpqRStuVWxyz0123456789ABCDEF",
        ),
    ]:
        em = _emission_with_ref(ref=ref, url=url)
        assert validate_emissions([em]) == [em]


def test_secret_in_source_id_is_rejected():
    # #52 (extended): source_id reaches the wire as source_type — must be screened.
    with pytest.raises(EmissionContractError):
        validate_emissions([_emission(source_id=_GHP)])


def test_zero_width_excerpt_rejected():
    # #61: a zero-width-only excerpt is visually blank and must be rejected.
    for blank in ("​", "﻿ ", "‎‏"):
        ev = SourceEvidence(source_ref=_ref(), excerpt=blank)
        with pytest.raises(EmissionContractError):
            validate_emissions([_emission(evidence=(ev,))])


def test_visible_excerpt_still_accepted():
    # #61: real text (incl. CJK, emoji, punctuation, padded) must still pass.
    for good in ("hello", " x ", "café", "日本語", "🚀 ship it", "!!!"):
        ev = SourceEvidence(source_ref=_ref(), excerpt=good)
        assert validate_emissions([_emission(evidence=(ev,))])


def test_oversized_source_id_rejected():
    # #61: a degenerate long source_id (regex-valid) must not reach the wire as source_type.
    with pytest.raises(EmissionContractError):
        validate_emissions([_emission(source_id="a" * 200)])
    assert validate_emissions([_emission(source_id="github")])  # normal still passes


# --- ADR-0014: connector metadata preserved through normalize + screened per-leaf ---

_AKIA = "AKIAIOSFODNN7EXAMPLE"  # fake AWS access key (matches \bAKIA[0-9A-Z]{16}\b)
_PAN = "4111111111111111"  # Luhn-valid test PAN


class _Stringy:
    """A non-str scalar whose ``__str__`` carries a secret (must be screened)."""

    def __str__(self) -> str:
        return f"leaked {_AKIA}"


def test_normalize_preserves_metadata():
    # FX-ADP-001: Observation.metadata survives normalize into emission.metadata,
    # nested-intact, as a DEFENSIVE COPY (not the same object).
    md = {"severity": "HIGH", "packages": "requests", "nested": {"k": "v"}}
    obs = Observation(source_ref=_ref(), excerpt="vuln summary", metadata=md)
    out = normalize([obs], adapter_version="osv/0.1.0")
    assert out[0].metadata == md
    assert out[0].metadata is not md  # defensive copy


def test_clean_metadata_passes_unchanged():
    # Non-vacuous companion: structured, nested, container-bearing clean metadata passes.
    md = {"severity": "HIGH", "packages": ["requests", "urllib3"], "nested": {"k": "v"}}
    em = _emission(metadata=md)
    assert validate_emissions([em]) == [em]


def test_secret_in_metadata_flat_value_rejected():
    with pytest.raises(EmissionContractError) as exc:
        validate_emissions([_emission(metadata={"note": f"key {_AKIA}"})])
    assert str(exc.value).startswith("sensitive_data:")


def test_secret_in_metadata_nested_value_rejected():
    # nested inside a list-of-dicts — proves the recursion screens deep leaves.
    md = {"signals": [{"detail": f"found {_AKIA}"}]}
    with pytest.raises(EmissionContractError) as exc:
        validate_emissions([_emission(metadata=md)])
    assert str(exc.value).startswith("sensitive_data:")


def test_secret_in_metadata_key_rejected():
    # a secret in a KEY (not value) must not escape — keys are scanned too.
    with pytest.raises(EmissionContractError) as exc:
        validate_emissions([_emission(metadata={_AKIA: "v"})])
    assert str(exc.value).startswith("sensitive_data:")


def test_secret_in_metadata_non_str_scalar_rejected():
    # a non-str scalar is stringified before screening (malicious __str__ can't dodge).
    with pytest.raises(EmissionContractError) as exc:
        validate_emissions([_emission(metadata={"obj": _Stringy()})])
    assert str(exc.value).startswith("sensitive_data:")


def test_secret_in_metadata_tuple_and_set_rejected():
    for container in ({"t": (f"x {_AKIA}",)}, {"s": {f"y {_AKIA}"}}):
        with pytest.raises(EmissionContractError) as exc:
            validate_emissions([_emission(metadata=container)])
        assert str(exc.value).startswith("sensitive_data:")


def test_metadata_per_leaf_no_false_adjacency():
    # per-leaf scan: an id-label in one leaf must NOT suppress a PAN in a DIFFERENT leaf
    # (a single-join screen would fabricate _is_id_preceded suppression → false negative).
    md = {"a": "order_id:", "b": _PAN}
    with pytest.raises(EmissionContractError) as exc:
        validate_emissions([_emission(metadata=md)])
    assert str(exc.value).startswith("sensitive_data:")


def test_metadata_id_labeled_pan_within_one_leaf_passes():
    # legitimate within-leaf suppression is preserved: an order_id-labelled run is NOT a PAN.
    em = _emission(metadata={"x": f"order_id: {_PAN}"})
    assert validate_emissions([em]) == [em]
