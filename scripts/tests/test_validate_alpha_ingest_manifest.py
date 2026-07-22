# SPDX-License-Identifier: MIT
"""Fail-closed behavior of the alpha ingest manifest validator (GH #258)."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO / "scripts") not in sys.path:  # the validator does a flat scripts-dir import
    sys.path.insert(0, str(_REPO / "scripts"))
_SPEC = importlib.util.spec_from_file_location(
    "validate_alpha_ingest_manifest", _REPO / "scripts" / "validate_alpha_ingest_manifest.py"
)
assert _SPEC and _SPEC.loader
validator = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("validate_alpha_ingest_manifest", validator)
_SPEC.loader.exec_module(validator)

_MANIFEST = json.loads((_REPO / "ingest" / "alpha-ingest-manifest.json").read_text(encoding="utf-8"))
_SCHEMA = json.loads(
    (_REPO / "ingest" / "_schema" / "alpha-ingest-manifest.schema.json").read_text(encoding="utf-8")
)


def _entry(connector: str) -> dict:
    manifest = copy.deepcopy(_MANIFEST)
    return manifest, next(e for e in manifest["entries"] if e["connector_id"] == connector)


def test_committed_manifest_is_structurally_and_semantically_valid() -> None:
    assert validator._check(_MANIFEST, _SCHEMA, "manifest") == []
    assert validator.semantic_errors(_MANIFEST) == []


def test_unknown_field_fails_closed() -> None:
    manifest = copy.deepcopy(_MANIFEST)
    manifest["entries"][0]["verified"] = True
    errs = validator._check(manifest, _SCHEMA, "manifest")
    assert any("verified" in e for e in errs)


def test_unknown_state_value_fails_closed() -> None:
    manifest = copy.deepcopy(_MANIFEST)
    manifest["entries"][0]["conformance_state"]["component"] = "kinda-proven"
    errs = validator._check(manifest, _SCHEMA, "manifest")
    assert any("kinda-proven" in e for e in errs)


def test_component_proven_requires_recorded_capture() -> None:
    manifest, entry = _entry("github")
    entry["conformance_state"]["component"] = "proven"
    errs = validator.semantic_errors(manifest)
    assert any("component cannot be proven" in e for e in errs)


def test_recorded_capture_digest_must_match_bytes() -> None:
    manifest, entry = _entry("local_directory")
    entry["real_capture"]["sanitized_digest"] = "sha256:" + "0" * 64
    errs = validator.semantic_errors(manifest)
    assert any("does not match the committed capture bytes" in e for e in errs)


def test_gateway_proven_requires_committed_receipt() -> None:
    manifest, entry = _entry("local_directory")
    entry["conformance_state"]["gateway"] = "proven"
    errs = validator.semantic_errors(manifest)
    assert any("gateway proven requires" in e for e in errs)


def test_terminal_bot_requires_gateway_and_acceptance_requires_terminal() -> None:
    manifest, entry = _entry("local_directory")
    entry["conformance_state"]["terminal_bot"] = "proven"
    errs = validator.semantic_errors(manifest)
    assert any("terminal_bot cannot be proven" in e for e in errs)

    manifest, entry = _entry("local_directory")
    entry["conformance_state"]["human_acceptance"] = "accepted"
    errs = validator.semantic_errors(manifest)
    assert any("human acceptance cannot precede" in e for e in errs)


def test_missing_implementation_requires_documented_deferral() -> None:
    manifest, entry = _entry("github")
    missing = next(e for e in manifest["entries"] if e["conformance_state"]["implementation"] == "missing")
    missing["notes"] = ""
    errs = validator.semantic_errors(manifest)
    assert any("requires the deferral documented" in e for e in errs)


def test_missing_capture_requires_command_and_credential_class() -> None:
    manifest, entry = _entry("github")
    entry["capture_command"] = ""
    errs = validator.semantic_errors(manifest)
    assert any("capture_command" in e for e in errs)
