# SPDX-License-Identifier: MIT
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Callable

from scripts.validate_redaction_evaluation_contract import (
    _sha256_canonical_value,
    validate_repository,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_SOURCE = _REPO_ROOT / "tests" / "redaction_evaluation" / "schema"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _build_root(tmp_path: Path, *, populated: bool = True) -> Path:
    root = tmp_path / "repo"
    schema_target = root / "tests" / "redaction_evaluation" / "schema"
    shutil.copytree(_SCHEMA_SOURCE, schema_target)
    if not populated:
        return root

    input_path = (
        root
        / "tests"
        / "redaction_evaluation"
        / "corpus"
        / "decision-with-person-email-001.json"
    )
    expected_path = (
        root
        / "tests"
        / "redaction_evaluation"
        / "expected"
        / "decision-with-person-email-001.json"
    )
    input_document = {
        "provider_event_id": "evt-001",
        "excerpt": "Alice approved keeping the event store local. Email alice@example.test.",
    }
    _write_json(input_path, input_document)
    expected_document = {
        "schema_version": 1,
        "record_id": "decision-with-person-email-001",
        "expected_entities": [
            {
                "entity_id": "entity-person-001",
                "category": "pii",
                "subtype": "person",
                "field_path": "excerpt",
                "start": 0,
                "end": 5,
                "replacement": "[redacted:person]",
                "mandatory": False,
            },
            {
                "entity_id": "entity-email-001",
                "category": "pii",
                "subtype": "email",
                "field_path": "excerpt",
                "start": 53,
                "end": 71,
                "replacement": "[redacted:email]",
                "mandatory": False,
            },
        ],
        "protected_fields": [
            {
                "field_path": "provider_event_id",
                "expected_value_sha256": _sha256_canonical_value("evt-001"),
            }
        ],
        "preservation_assertions": [
            {
                "assertion_id": "decision-clause-001",
                "field_path": "excerpt",
                "required_substring": "approved keeping the event store local",
            }
        ],
        "expected_outcome": "sanitized",
        "expected_failure_reason": None,
    }
    _write_json(expected_path, expected_document)

    manifest_path = root / "artifacts" / "redaction-evaluation" / "corpus-manifest.json"
    manifest = {
        "schema_version": 1,
        "corpus_id": "bicameral-redaction-evaluation-v1",
        "description": "Synthetic evaluation records",
        "records": [
            {
                "record_id": "decision-with-person-email-001",
                "source_shape": "observation",
                "input_path": input_path.relative_to(root).as_posix(),
                "expected_path": expected_path.relative_to(root).as_posix(),
                "classes": ["positive_detection", "decision_preservation"],
                "input_sha256": _file_digest(input_path),
                "expected_sha256": _file_digest(expected_path),
            }
        ],
    }
    _write_json(manifest_path, manifest)
    return root


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_path(root: Path) -> Path:
    return root / "artifacts" / "redaction-evaluation" / "corpus-manifest.json"


def _expected_path(root: Path) -> Path:
    return (
        root
        / "tests"
        / "redaction_evaluation"
        / "expected"
        / "decision-with-person-email-001.json"
    )


def _rewrite_expected(root: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    expected_path = _expected_path(root)
    expected = _load(expected_path)
    mutate(expected)
    _write_json(expected_path, expected)
    manifest_path = _manifest_path(root)
    manifest = _load(manifest_path)
    manifest["records"][0]["expected_sha256"] = _file_digest(expected_path)
    _write_json(manifest_path, manifest)


def test_schema_only_state_is_valid(tmp_path: Path) -> None:
    root = _build_root(tmp_path, populated=False)
    assert validate_repository(root) == []


def test_populated_contract_is_valid(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    assert validate_repository(root) == []


def test_manifest_schema_violation_is_rejected(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    manifest_path = _manifest_path(root)
    manifest = _load(manifest_path)
    manifest["unexpected"] = True
    _write_json(manifest_path, manifest)

    errors = validate_repository(root)
    assert any("corpus manifest: schema violation" in error for error in errors)


def test_digest_drift_is_rejected(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    input_path = (
        root
        / "tests"
        / "redaction_evaluation"
        / "corpus"
        / "decision-with-person-email-001.json"
    )
    input_path.write_text(input_path.read_text(encoding="utf-8") + " ", encoding="utf-8")

    assert any("input SHA-256 mismatch" in error for error in validate_repository(root))


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    manifest_path = _manifest_path(root)
    manifest = _load(manifest_path)
    manifest["records"][0]["input_path"] = "tests/redaction_evaluation/corpus/../expected/x.json"
    _write_json(manifest_path, manifest)

    errors = validate_repository(root)
    assert any("schema violation" in error or "without '..'" in error for error in errors)


def test_duplicate_record_ids_are_rejected(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    manifest_path = _manifest_path(root)
    manifest = _load(manifest_path)
    manifest["records"].append(dict(manifest["records"][0]))
    _write_json(manifest_path, manifest)

    assert any("duplicate record_id" in error for error in validate_repository(root))


def test_missing_and_unlisted_files_are_rejected(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    _expected_path(root).unlink()
    unlisted = root / "tests" / "redaction_evaluation" / "corpus" / "unlisted.json"
    _write_json(unlisted, {"safe": True})

    errors = validate_repository(root)
    assert any("expected file not found" in error for error in errors)
    assert any("unlisted corpus JSON file" in error for error in errors)


def test_record_id_mismatch_is_rejected(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    _rewrite_expected(root, lambda expected: expected.__setitem__("record_id", "other-record"))

    assert any("record_id does not match" in error for error in validate_repository(root))


def test_unresolved_entity_path_is_rejected(tmp_path: Path) -> None:
    root = _build_root(tmp_path)

    def mutate(expected: dict[str, Any]) -> None:
        expected["expected_entities"][0]["field_path"] = "missing.path"

    _rewrite_expected(root, mutate)
    assert any("field path does not resolve" in error for error in validate_repository(root))


def test_invalid_entity_span_is_rejected(tmp_path: Path) -> None:
    root = _build_root(tmp_path)

    def mutate(expected: dict[str, Any]) -> None:
        expected["expected_entities"][0]["start"] = 5
        expected["expected_entities"][0]["end"] = 5

    _rewrite_expected(root, mutate)
    assert any("must satisfy start < end" in error for error in validate_repository(root))


def test_protected_field_hash_drift_is_rejected(tmp_path: Path) -> None:
    root = _build_root(tmp_path)

    def mutate(expected: dict[str, Any]) -> None:
        expected["protected_fields"][0]["expected_value_sha256"] = "sha256:" + "0" * 64

    _rewrite_expected(root, mutate)
    assert any("protected field hash mismatch" in error for error in validate_repository(root))


def test_corpus_files_without_manifest_are_rejected(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    _manifest_path(root).unlink()

    assert any("no corpus manifest" in error for error in validate_repository(root))
