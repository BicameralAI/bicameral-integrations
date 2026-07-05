# SPDX-License-Identifier: MIT
"""Cross-repo ingest conformance: golden AdapterEmission -> IngestRequest fixtures (#195).

Each JSON fixture under ``fixtures/ingest_conformance/`` encodes a realistic
``AdapterEmission`` and the exact ``IngestRequest`` the gateway mapping must
produce. The fixtures lock the emission-to-ingest contract so integrations
fails first on mapping drift — no live provider or bot credentials required.

The schema pin file (``runtime/schemas/ingest_schema_pin.json``) records the
upstream bot commit; the drift gate (``scripts/validate_ingest_schema_pin.py``)
verifies the vendored schema content hash has not diverged from the pin.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from runtime.gateway_mapping import emission_to_ingest_request

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "ingest_conformance"
_SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "schemas"
        / "ingest_request_v1.schema.json"
    ).read_text(encoding="utf-8")
)
_PIN = json.loads(
    (
        Path(__file__).resolve().parents[1] / "schemas" / "ingest_schema_pin.json"
    ).read_text(encoding="utf-8")
)


def _load_fixtures() -> list[tuple[str, dict]]:
    """Return (fixture_name, fixture_dict) pairs for parametrization."""
    fixtures: list[tuple[str, dict]] = []
    for path in sorted(_FIXTURES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        fixtures.append((path.stem, data))
    return fixtures


def _emission_from_fixture(raw: dict) -> AdapterEmission:
    """Reconstruct an ``AdapterEmission`` from the JSON fixture representation."""
    evidence_items: list[SourceEvidence] = []
    for ev_raw in raw["evidence"]:
        ref_raw = ev_raw["source_ref"]
        ref = SourceRef(
            source_id=ref_raw["source_id"],
            ref=ref_raw["ref"],
            url=ref_raw.get("url", ""),
            kind=ref_raw.get("kind", ""),
        )
        evidence_items.append(
            SourceEvidence(
                source_ref=ref,
                excerpt=ev_raw["excerpt"],
                author=ev_raw.get("author", ""),
                timestamp=ev_raw.get("timestamp", ""),
                evidence_id=ev_raw.get("evidence_id", ""),
                metadata=ev_raw.get("metadata", {}),
            )
        )
    return AdapterEmission(
        source_id=raw["source_id"],
        title=raw["title"],
        body=raw["body"],
        evidence=tuple(evidence_items),
        emission_type=raw.get("emission_type", "candidate"),
        adapter_version=raw.get("adapter_version", "0.1.0"),
    )


def _assert_schema_conforms(payload: dict) -> None:
    """Structural validation against the vendored IngestRequest schema (house pattern)."""
    for key in _SCHEMA["required"]:
        assert key in payload and isinstance(payload[key], str) and payload[key], (
            f"required field {key!r} missing or empty"
        )
    assert isinstance(payload.get("evidence"), list), "evidence must be a list"
    item_required = _SCHEMA["definitions"]["IngestEvidenceItem"]["required"]
    for item in payload["evidence"]:
        for k in item_required:
            assert k in item and isinstance(item[k], str), (
                f"evidence item missing required {k!r}"
            )


_FIXTURE_CASES = _load_fixtures()


@pytest.mark.parametrize(
    "name,fixture", _FIXTURE_CASES, ids=[c[0] for c in _FIXTURE_CASES]
)
def test_golden_fixture_matches_expected_output(name: str, fixture: dict) -> None:
    """Each golden fixture's emission maps to exactly the expected IngestRequest."""
    emission = _emission_from_fixture(fixture["emission"])
    actual = emission_to_ingest_request(emission)
    expected = fixture["expected_ingest_request"]
    assert actual == expected, (
        f"fixture {name!r}: mapping output differs from golden expectation"
    )


@pytest.mark.parametrize(
    "name,fixture", _FIXTURE_CASES, ids=[c[0] for c in _FIXTURE_CASES]
)
def test_golden_fixture_conforms_to_schema(name: str, fixture: dict) -> None:
    """Each golden fixture's mapped output satisfies the vendored v1 schema."""
    emission = _emission_from_fixture(fixture["emission"])
    payload = emission_to_ingest_request(emission)
    _assert_schema_conforms(payload)


def test_pin_commit_is_recorded() -> None:
    """The schema pin file records a 40-char upstream commit SHA."""
    assert len(_PIN["upstream_commit"]) == 40, "pin must record a full git SHA"


def test_pin_content_hash_matches_vendored_schema() -> None:
    """The content_sha256 in the pin file matches the actual vendored schema file."""
    import hashlib

    schema_path = (
        Path(__file__).resolve().parents[1]
        / "schemas"
        / "ingest_request_v1.schema.json"
    )
    actual_hash = hashlib.sha256(schema_path.read_bytes()).hexdigest()
    assert actual_hash == _PIN["content_sha256"], (
        f"vendored schema content hash ({actual_hash}) does not match pin "
        f"({_PIN['content_sha256']}); re-pin after updating the schema"
    )


def test_at_least_one_fixture_exists() -> None:
    """Guard: the fixture directory must contain at least one golden fixture."""
    assert len(_FIXTURE_CASES) > 0, "no golden fixtures found"
