# SPDX-License-Identifier: MIT
"""Cross-repo conformance: to_sdk_evidence output ⟷ the vendored SDK Evidence schema (#212-B).

The schema (``runtime/schemas/sdk_evidence_v0.schema.json``) is a VENDORED, commit-pinned mirror of
the bicameral-sdk evidence/provenance TypeScript contract (GH #7). Integrations fails first on drift:
if the SDK shape changes, the pin + these assertions catch it before a live consumer does. Structural
validation against the schema's ``required``/``enum`` (house pattern, dependency-light — mirrors
``test_gateway_mapping``), not a third-party validator.
"""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.capabilities import SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.pipeline import normalize
from adapter.core.sdk_evidence import (
    SDK_EVIDENCE_PIN_COMMIT,
    emission_to_sdk_evidence,
    to_sdk_evidence,
)

_SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "schemas" / "sdk_evidence_v0.schema.json").read_text(
        encoding="utf-8"
    )
)
_DEFS = _SCHEMA["definitions"]


def _assert_object(obj: dict, spec: dict) -> None:
    """Every ``required`` key present with the right primitive type; ``enum`` honoured; nested
    ``$ref`` objects recursed. Covers the shapes this mapping actually emits."""
    for key in spec.get("required", []):
        assert key in obj, f"missing required {key!r}"
    for key, value in obj.items():
        prop = spec["properties"].get(key)
        assert prop is not None, f"unexpected key {key!r} not in schema"
        if "$ref" in prop:
            _assert_object(value, _DEFS[prop["$ref"].rsplit("/", 1)[-1]])
        elif prop.get("type") == "string":
            assert isinstance(value, str)
            if "enum" in prop:
                assert value in prop["enum"], f"{key}={value!r} not in {prop['enum']}"
        elif prop.get("type") == "array":
            assert isinstance(value, list)


def _conforms(evidence: dict) -> None:
    _assert_object(evidence, _SCHEMA)


def _obs(mode: SourceMode = SourceMode.WEBHOOK) -> Observation:
    ref = SourceRef(source_id="linear", ref="PLAT-1", url="https://linear.app/x/PLAT-1", kind="issue")
    return Observation(source_ref=ref, excerpt="a clean decision", mode=mode, timestamp="2026-06-02T00:00:00Z")


def test_pin_commit_recorded():
    assert len(SDK_EVIDENCE_PIN_COMMIT) == 40  # a full git SHA — the vendored-schema pin


def test_to_sdk_evidence_conforms_to_vendored_schema():
    ev = to_sdk_evidence(_obs(), adapter_version="linear/0.1.0")
    _conforms(ev)
    assert ev["status"] == "raw"  # enum-locked
    assert ev["provenance"]["capturedBy"]["actorType"] == "connector"  # enum-locked


def test_emission_evidence_conforms_to_vendored_schema():
    for ev in emission_to_sdk_evidence(normalize([_obs()], adapter_version="linear/0.1.0")[0]):
        _conforms(ev)


def test_active_and_passive_modes_conform():
    for mode in (SourceMode.ACTIVE, SourceMode.PASSIVE):
        _conforms(to_sdk_evidence(_obs(mode), adapter_version="v"))
