# SPDX-License-Identifier: MIT
"""Contract tests for the candidate-neutral redaction evaluation corpus.

Two validation layers:

1. Schema validation with ``jsonschema`` when it is installed (skipped with a
   reason otherwise).
2. A dependency-free structural layer that always runs: manifest shape,
   digest pinning, expected-record shape, span resolution against the
   de-obfuscated inputs, protected-field digests, preservation assertions,
   and a committed-byte scan with the repository's own sensitive catalog
   (which proves the obfuscation scheme kept secret-shaped tokens out of
   repository bytes).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[1]
MANIFEST_PATH = BASE / "corpus-manifest.json"
SCHEMA_DIR = BASE / "schema"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_LOADER = _load_module("_eval_corpus_loader", BASE / "corpus_loader.py")
_SENSITIVE = _load_module(
    "_eval_sensitive", REPO_ROOT / "adapter" / "core" / "sensitive.py"
)

SOURCE_SHAPES = {
    "github_webhook",
    "github_poll",
    "linear_webhook",
    "linear_graphql",
    "local_directory",
    "bounded_document_fetch",
    "observation",
    "adapter_emission",
    "external_ingest_envelope",
    "plain_text",
    "failure_fixture",
}
CLASSES = {
    "positive_detection",
    "negative_control",
    "decision_preservation",
    "structural_identity",
    "nested_metadata",
    "mixed_entities",
    "overlapping_entities",
    "malformed_input",
    "oversized_payload",
    "unsupported_binary",
    "sensitive_metadata_key",
    "backend_unavailable",
    "backend_invalid_configuration",
    "backend_crash",
    "backend_timeout",
    "concurrency_timeout_storm",
    "malformed_backend_findings",
    "nondeterminism_probe",
}
CATEGORIES = {"secret", "credential", "pii", "phi", "prohibited_content"}
OUTCOMES = {"sanitized", "unchanged", "failed_closed"}

ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REASON_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
REPLACEMENT_RE = re.compile(r"^\[redacted:[a-z0-9._-]+\]$")
FIELD_PATH_RE = re.compile(r"^[A-Za-z0-9_.$\[\]-]+$")

EXPECTED_KEYS = {
    "schema_version",
    "record_id",
    "expected_entities",
    "protected_fields",
    "preservation_assertions",
    "expected_outcome",
    "expected_failure_reason",
}
ENTITY_KEYS = {
    "entity_id",
    "category",
    "subtype",
    "field_path",
    "start",
    "end",
    "replacement",
    "mandatory",
}
MANIFEST_RECORD_KEYS = {
    "record_id",
    "source_shape",
    "input_path",
    "expected_path",
    "classes",
    "input_sha256",
    "expected_sha256",
}


def _sha256_label(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    loaded = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="module")
def entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return list(_LOADER.iter_manifest(MANIFEST_PATH))


def _read_json(repo_relative: str) -> Any:
    return json.loads((REPO_ROOT / repo_relative).read_text(encoding="utf-8"))


def test_manifest_and_expected_validate_with_jsonschema(
    manifest: dict[str, Any], entries: list[dict[str, Any]]
) -> None:
    jsonschema = pytest.importorskip(
        "jsonschema",
        reason="jsonschema not installed; the structural fallback tests below "
        "still enforce the contract",
    )
    manifest_schema = json.loads(
        (SCHEMA_DIR / "corpus-manifest.schema.json").read_text(encoding="utf-8")
    )
    expected_schema = json.loads(
        (SCHEMA_DIR / "expected-record.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(manifest, manifest_schema)
    for entry in entries:
        jsonschema.validate(_read_json(entry["expected_path"]), expected_schema)


def test_manifest_structure_and_digest_pinning(
    manifest: dict[str, Any], entries: list[dict[str, Any]]
) -> None:
    assert set(manifest.keys()) == {"schema_version", "corpus_id", "description", "records"}
    assert manifest["schema_version"] == 1
    assert manifest["corpus_id"] == "bicameral-redaction-evaluation-v1"
    assert ID_RE.match(manifest["corpus_id"])
    assert isinstance(manifest["description"], str)
    assert 1 <= len(manifest["description"]) <= 512
    assert entries, "manifest must contain records"

    record_ids = [entry["record_id"] for entry in entries]
    assert record_ids == sorted(record_ids), "manifest records must be record_id-sorted"
    assert len(set(record_ids)) == len(record_ids), "record ids must be unique"

    for entry in entries:
        assert set(entry.keys()) == MANIFEST_RECORD_KEYS, entry.get("record_id")
        rid = entry["record_id"]
        assert ID_RE.match(rid), rid
        assert len(rid) <= 160
        assert entry["source_shape"] in SOURCE_SHAPES, rid
        classes = entry["classes"]
        assert isinstance(classes, list) and classes, rid
        assert len(set(classes)) == len(classes), rid
        assert all(cls in CLASSES for cls in classes), rid
        for key in ("input_path", "expected_path"):
            path_value = entry[key]
            assert isinstance(path_value, str) and path_value.endswith(".json"), rid
            assert not path_value.startswith("/"), rid
            assert ".." not in path_value.split("/"), rid
            file_path = REPO_ROOT / path_value
            assert file_path.is_file(), f"{rid}: missing {path_value}"
        assert SHA_RE.match(entry["input_sha256"]), rid
        assert SHA_RE.match(entry["expected_sha256"]), rid
        input_bytes = (REPO_ROOT / entry["input_path"]).read_bytes()
        expected_bytes = (REPO_ROOT / entry["expected_path"]).read_bytes()
        assert _sha256_label(input_bytes) == entry["input_sha256"], f"{rid}: input drift"
        assert (
            _sha256_label(expected_bytes) == entry["expected_sha256"]
        ), f"{rid}: expected drift"


def test_expected_records_structural(entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        rid = entry["record_id"]
        expected = _read_json(entry["expected_path"])
        assert isinstance(expected, dict), rid
        assert set(expected.keys()) == EXPECTED_KEYS, rid
        assert expected["schema_version"] == 1, rid
        assert expected["record_id"] == rid, rid
        assert expected["expected_outcome"] in OUTCOMES, rid

        reason = expected["expected_failure_reason"]
        if expected["expected_outcome"] == "failed_closed":
            assert isinstance(reason, str) and REASON_RE.match(reason), rid
            assert 1 <= len(reason) <= 160, rid
        else:
            assert reason is None, rid

        entity_ids = set()
        for entity in expected["expected_entities"]:
            assert set(entity.keys()) == ENTITY_KEYS, rid
            assert ID_RE.match(entity["entity_id"]), rid
            entity_ids.add(entity["entity_id"])
            assert entity["category"] in CATEGORIES, rid
            assert ID_RE.match(entity["subtype"]), rid
            assert 1 <= len(entity["subtype"]) <= 96, rid
            assert FIELD_PATH_RE.match(entity["field_path"]), rid
            assert 1 <= len(entity["field_path"]) <= 256, rid
            assert _is_strict_int(entity["start"]) and entity["start"] >= 0, rid
            assert _is_strict_int(entity["end"]) and entity["end"] >= 1, rid
            assert REPLACEMENT_RE.match(entity["replacement"]), rid
            assert 1 <= len(entity["replacement"]) <= 128, rid
            assert isinstance(entity["mandatory"], bool), rid
        assert len(entity_ids) == len(expected["expected_entities"]), rid

        for protected in expected["protected_fields"]:
            assert set(protected.keys()) == {"field_path", "expected_value_sha256"}, rid
            assert FIELD_PATH_RE.match(protected["field_path"]), rid
            assert SHA_RE.match(protected["expected_value_sha256"]), rid

        for assertion in expected["preservation_assertions"]:
            assert set(assertion.keys()) == {
                "assertion_id",
                "field_path",
                "required_substring",
            }, rid
            assert ID_RE.match(assertion["assertion_id"]), rid
            assert FIELD_PATH_RE.match(assertion["field_path"]), rid
            substring = assertion["required_substring"]
            assert isinstance(substring, str) and 1 <= len(substring) <= 512, rid


def test_input_records_match_manifest(entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        rid = entry["record_id"]
        record = _LOADER.load_input_record(REPO_ROOT / entry["input_path"])
        assert record["record_id"] == rid, rid
        assert record["source_shape"] == entry["source_shape"], rid
        assert isinstance(record["observation"], dict), rid


def test_entity_spans_resolve_after_deobfuscation(entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        rid = entry["record_id"]
        expected = _read_json(entry["expected_path"])
        record = _LOADER.load_input_record(REPO_ROOT / entry["input_path"])
        observation = record["observation"]
        for entity in expected["expected_entities"]:
            path = entity["field_path"]
            text = _LOADER.resolve_field_path(observation, path)
            assert isinstance(text, str), f"{rid}: {path} is not a string"
            start, end = entity["start"], entity["end"]
            assert 0 <= start < end <= len(text), f"{rid}: bad span {start}:{end} at {path}"


def test_protected_fields_pin_input_values(entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        rid = entry["record_id"]
        expected = _read_json(entry["expected_path"])
        record = _LOADER.load_input_record(REPO_ROOT / entry["input_path"])
        observation = record["observation"]
        for protected in expected["protected_fields"]:
            path = protected["field_path"]
            value = _LOADER.resolve_field_path(observation, path)
            assert isinstance(value, str), f"{rid}: protected {path} is not a string"
            assert (
                _sha256_label(value.encode("utf-8")) == protected["expected_value_sha256"]
            ), f"{rid}: protected-field digest mismatch at {path}"


def test_preservation_assertions_present_and_disjoint(
    entries: list[dict[str, Any]],
) -> None:
    for entry in entries:
        rid = entry["record_id"]
        expected = _read_json(entry["expected_path"])
        record = _LOADER.load_input_record(REPO_ROOT / entry["input_path"])
        observation = record["observation"]
        for assertion in expected["preservation_assertions"]:
            path = assertion["field_path"]
            substring = assertion["required_substring"]
            text = _LOADER.resolve_field_path(observation, path)
            assert isinstance(text, str), f"{rid}: preservation field {path} not a string"
            spans = [
                (entity["start"], entity["end"])
                for entity in expected["expected_entities"]
                if entity["field_path"] == path
            ]
            found_disjoint = False
            offset = text.find(substring)
            assert offset != -1, f"{rid}: preservation substring absent at {path}"
            while offset != -1:
                candidate_end = offset + len(substring)
                if all(
                    not (offset < end and start < candidate_end) for start, end in spans
                ):
                    found_disjoint = True
                    break
                offset = text.find(substring, offset + 1)
            assert found_disjoint, (
                f"{rid}: preservation substring overlaps an entity span at {path}"
            )


def test_committed_bytes_carry_no_secret_shaped_tokens() -> None:
    """Prove the obfuscation scheme: repository bytes never trip the catalog."""
    scanned = 0
    for path in sorted(BASE.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts:
            continue
        if path.suffix not in {".py", ".json", ".md"}:
            continue
        text = path.read_bytes().decode("utf-8")
        hits = _SENSITIVE.detect_sensitive(text)
        assert not hits, (
            f"committed file trips the sensitive catalog: {path.name}: "
            f"{[(hit.cls, hit.pattern_id) for hit in hits]}"
        )
        scanned += 1
    assert scanned > 0
