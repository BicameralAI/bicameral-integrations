# SPDX-License-Identifier: MIT
"""Validate ADR-0020 redaction evaluation corpus and annotation integrity.

The gate is candidate-neutral and offline. It validates the accepted JSON Schemas,
manifest references, exact file digests, annotation identity, field paths, entity
spans, protected-value hashes, and deterministic manifest coverage.

Before the corpus exists, schema-only validation succeeds. Once any JSON record is
placed under ``tests/redaction_evaluation/corpus`` or ``expected``, a manifest is
mandatory. The default manifest discovery order supports the locations documented
by ADR-0020 while rejecting ambiguous duplicate manifests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from jsonschema.exceptions import SchemaError, ValidationError  # type: ignore[import-untyped]

_ROOT = Path(__file__).resolve().parents[1]
_REL_SCHEMA_DIR = Path("tests/redaction_evaluation/schema")
_REL_CORPUS_DIR = Path("tests/redaction_evaluation/corpus")
_REL_EXPECTED_DIR = Path("tests/redaction_evaluation/expected")
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_corpus_input(path: Path) -> Any:
    """Load one corpus input through the documented corpus conventions.

    Corpus inputs wrap the observation payload in an envelope and commit
    catalog-tripping values in the documented reversible form so no
    secret-shaped byte sequence exists in the tree. The corpus loader is
    the single source of truth for decoding; field paths then resolve
    against the observation payload, per the evaluation contract.
    """

    from tests.redaction_evaluation.corpus_loader import load_input_record

    record = load_input_record(path)
    observation = record.get("observation")
    return observation if isinstance(observation, dict) else record


_MANIFEST_CANDIDATES = (
    Path("artifacts/redaction-evaluation/corpus-manifest.json"),
    Path("tests/redaction_evaluation/corpus-manifest.json"),
)


class FieldPathError(ValueError):
    """Raised when an annotation field path is invalid or cannot be resolved."""


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant is forbidden: {value}")


def _load_json(path: Path, label: str, errors: list[str]) -> Any | None:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
        )
    except FileNotFoundError:
        errors.append(f"{label}: file not found: {path}")
    except UnicodeDecodeError:
        errors.append(f"{label}: file is not valid UTF-8: {path}")
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label}: file is not strict JSON: {path}")
    return None


def _sha256_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _sha256_canonical_value(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _json_location(error: ValidationError) -> str:
    location = "$"
    for part in error.absolute_path:
        location += f"[{part}]" if isinstance(part, int) else f".{part}"
    return location


def _schema_violations(
    validator: Draft202012Validator,
    instance: Any,
    label: str,
) -> list[str]:
    violations: list[str] = []
    ordered = sorted(
        validator.iter_errors(instance),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    for error in ordered:
        violations.append(
            f"{label}: schema violation at {_json_location(error)} "
            f"(validator={error.validator})"
        )
    return violations


def _duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def _repo_path(
    root: Path,
    raw_path: str,
    required_parent: Path,
    label: str,
    errors: list[str],
) -> Path | None:
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        errors.append(f"{label}: path must be repository-relative without '..': {raw_path}")
        return None

    root_resolved = root.resolve()
    parent_resolved = (root / required_parent).resolve()
    candidate = root / relative
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root_resolved):
        errors.append(f"{label}: path escapes repository root: {raw_path}")
        return None
    if not resolved.is_relative_to(parent_resolved):
        errors.append(
            f"{label}: path must remain beneath {required_parent.as_posix()}: {raw_path}"
        )
        return None
    return candidate


def _field_tokens(field_path: str) -> list[str | int]:
    if field_path == "$":
        return []

    index = 0
    if field_path.startswith("$"):
        index = 1
        if index < len(field_path) and field_path[index] == ".":
            index += 1

    tokens: list[str | int] = []
    expecting_component = True
    while index < len(field_path):
        char = field_path[index]
        if char == ".":
            if expecting_component:
                raise FieldPathError("empty field-path component")
            expecting_component = True
            index += 1
            continue

        if char == "[":
            close = field_path.find("]", index + 1)
            if close == -1:
                raise FieldPathError("unclosed list index")
            raw_index = field_path[index + 1 : close]
            if not raw_index.isdigit():
                raise FieldPathError("list index must be a non-negative integer")
            tokens.append(int(raw_index))
            expecting_component = False
            index = close + 1
            continue

        start = index
        while index < len(field_path) and field_path[index] not in ".[":
            index += 1
        key = field_path[start:index]
        if not key:
            raise FieldPathError("empty field-path key")
        tokens.append(key)
        expecting_component = False

    if expecting_component:
        raise FieldPathError("field path cannot end with a separator")
    return tokens


def _resolve_field(document: Any, field_path: str) -> Any:
    current = document
    for token in _field_tokens(field_path):
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                raise FieldPathError("list index does not resolve")
            current = current[token]
        else:
            if not isinstance(current, dict) or token not in current:
                raise FieldPathError("object key does not resolve")
            current = current[token]
    return current


def _discover_manifest(
    root: Path,
    explicit_manifest: Path | None,
    errors: list[str],
) -> Path | None:
    if explicit_manifest is not None:
        candidate = explicit_manifest
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root.resolve())
        except ValueError:
            errors.append("manifest path must remain beneath repository root")
            return None
        if not candidate.exists():
            errors.append(f"manifest file not found: {candidate}")
            return None
        return candidate

    existing = [root / path for path in _MANIFEST_CANDIDATES if (root / path).exists()]
    if len(existing) > 1:
        # The evidence layout mandated by the hosted validation contract keeps
        # a verified copy of the source manifest under the artifact directory
        # and byte-compares the pair. Identical copies are therefore not an
        # ambiguity; only DIVERGENT duplicates are rejected.
        contents = {path: path.read_bytes() for path in existing}
        if len(set(contents.values())) > 1:
            errors.append(
                "corpus manifests diverge; regenerate the artifact copy of: "
                + ", ".join(path.relative_to(root).as_posix() for path in existing)
            )
            return None
        return existing[-1]
    return existing[0] if existing else None


def _validate_expected_record(
    input_document: Any,
    expected: dict[str, Any],
    record_id: str,
    label: str,
) -> list[str]:
    errors: list[str] = []
    if expected.get("record_id") != record_id:
        errors.append(f"{label}: record_id does not match manifest record {record_id!r}")

    entities = expected.get("expected_entities", [])
    entity_ids = [entity.get("entity_id", "") for entity in entities if isinstance(entity, dict)]
    for duplicate in _duplicates(entity_ids):
        errors.append(f"{label}: duplicate entity_id: {duplicate}")

    span_keys: list[str] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        entity_id = entity.get("entity_id", "<unknown>")
        field_path = entity.get("field_path")
        start = entity.get("start")
        end = entity.get("end")
        if not isinstance(field_path, str):
            continue
        try:
            value = _resolve_field(input_document, field_path)
        except FieldPathError:
            errors.append(f"{label}: entity {entity_id} field path does not resolve: {field_path}")
            continue
        if not isinstance(value, str):
            errors.append(f"{label}: entity {entity_id} field path must resolve to a string")
            continue
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if start >= end:
            errors.append(f"{label}: entity {entity_id} must satisfy start < end")
        elif end > len(value):
            errors.append(
                f"{label}: entity {entity_id} span exceeds resolved string length"
            )
        span_keys.append(
            f"{field_path}:{start}:{end}:{entity.get('category')}:{entity.get('subtype')}"
        )
    for duplicate in _duplicates(span_keys):
        errors.append(f"{label}: duplicate expected entity span: {duplicate}")

    protected_fields = expected.get("protected_fields", [])
    protected_paths = [
        item.get("field_path", "") for item in protected_fields if isinstance(item, dict)
    ]
    for duplicate in _duplicates(protected_paths):
        errors.append(f"{label}: duplicate protected field path: {duplicate}")
    for protected in protected_fields:
        if not isinstance(protected, dict):
            continue
        field_path = protected.get("field_path")
        if not isinstance(field_path, str):
            continue
        try:
            value = _resolve_field(input_document, field_path)
        except FieldPathError:
            errors.append(f"{label}: protected field path does not resolve: {field_path}")
            continue
        actual = _sha256_canonical_value(value)
        if actual != protected.get("expected_value_sha256"):
            errors.append(f"{label}: protected field hash mismatch: {field_path}")

    assertions = expected.get("preservation_assertions", [])
    assertion_ids = [
        item.get("assertion_id", "") for item in assertions if isinstance(item, dict)
    ]
    for duplicate in _duplicates(assertion_ids):
        errors.append(f"{label}: duplicate preservation assertion_id: {duplicate}")
    for assertion in assertions:
        if not isinstance(assertion, dict):
            continue
        assertion_id = assertion.get("assertion_id", "<unknown>")
        field_path = assertion.get("field_path")
        substring = assertion.get("required_substring")
        if not isinstance(field_path, str) or not isinstance(substring, str):
            continue
        try:
            value = _resolve_field(input_document, field_path)
        except FieldPathError:
            errors.append(
                f"{label}: preservation assertion {assertion_id} path does not resolve: "
                f"{field_path}"
            )
            continue
        if not isinstance(value, str):
            errors.append(
                f"{label}: preservation assertion {assertion_id} path must resolve to a string"
            )
        elif substring not in value:
            errors.append(
                f"{label}: preservation assertion {assertion_id} substring is absent "
                "from the input field"
            )
    return errors


def validate_repository(
    root: Path = _ROOT,
    explicit_manifest: Path | None = None,
) -> list[str]:
    """Return deterministic, value-free validation errors for a repository tree."""

    root = root.resolve()
    errors: list[str] = []
    schema_dir = root / _REL_SCHEMA_DIR
    manifest_schema_path = schema_dir / "corpus-manifest.schema.json"
    expected_schema_path = schema_dir / "expected-record.schema.json"

    manifest_schema = _load_json(manifest_schema_path, "manifest schema", errors)
    expected_schema = _load_json(expected_schema_path, "expected schema", errors)
    if not isinstance(manifest_schema, dict) or not isinstance(expected_schema, dict):
        return sorted(errors)

    for label, schema in (
        ("manifest schema", manifest_schema),
        ("expected schema", expected_schema),
    ):
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError:
            errors.append(f"{label}: invalid Draft 2020-12 schema")

    if errors:
        return sorted(errors)

    manifest_validator = Draft202012Validator(manifest_schema)
    expected_validator = Draft202012Validator(expected_schema)
    manifest_path = _discover_manifest(root, explicit_manifest, errors)

    corpus_root = root / _REL_CORPUS_DIR
    expected_root = root / _REL_EXPECTED_DIR
    actual_inputs = {
        path.relative_to(root).as_posix()
        for path in corpus_root.rglob("*.json")
        if path.is_file()
    } if corpus_root.exists() else set()
    actual_expected = {
        path.relative_to(root).as_posix()
        for path in expected_root.rglob("*.json")
        if path.is_file()
    } if expected_root.exists() else set()

    if manifest_path is None:
        if actual_inputs or actual_expected:
            errors.append("corpus or expected JSON files exist but no corpus manifest was found")
        return sorted(errors)

    manifest = _load_json(manifest_path, "corpus manifest", errors)
    if not isinstance(manifest, dict):
        return sorted(errors)
    errors.extend(_schema_violations(manifest_validator, manifest, "corpus manifest"))
    if errors:
        return sorted(errors)

    records = manifest["records"]
    record_ids = [record["record_id"] for record in records]
    input_paths = [record["input_path"] for record in records]
    expected_paths = [record["expected_path"] for record in records]
    for duplicate in _duplicates(record_ids):
        errors.append(f"corpus manifest: duplicate record_id: {duplicate}")
    for duplicate in _duplicates(input_paths):
        errors.append(f"corpus manifest: duplicate input_path: {duplicate}")
    for duplicate in _duplicates(expected_paths):
        errors.append(f"corpus manifest: duplicate expected_path: {duplicate}")
    if record_ids != sorted(record_ids):
        errors.append("corpus manifest: records must be sorted by record_id")

    listed_inputs: set[str] = set()
    listed_expected: set[str] = set()
    for record in records:
        record_id = record["record_id"]
        label = f"record {record_id}"
        input_path = _repo_path(
            root,
            record["input_path"],
            _REL_CORPUS_DIR,
            f"{label} input",
            errors,
        )
        expected_path = _repo_path(
            root,
            record["expected_path"],
            _REL_EXPECTED_DIR,
            f"{label} expected",
            errors,
        )
        if input_path is None or expected_path is None:
            continue
        listed_inputs.add(input_path.relative_to(root).as_posix())
        listed_expected.add(expected_path.relative_to(root).as_posix())
        if not input_path.is_file():
            errors.append(f"{label}: input file not found: {record['input_path']}")
            continue
        if not expected_path.is_file():
            errors.append(f"{label}: expected file not found: {record['expected_path']}")
            continue
        if _sha256_file(input_path) != record["input_sha256"]:
            errors.append(f"{label}: input SHA-256 mismatch")
        if _sha256_file(expected_path) != record["expected_sha256"]:
            errors.append(f"{label}: expected SHA-256 mismatch")

        try:
            input_document = _load_corpus_input(input_path)
        except (OSError, ValueError, KeyError) as error:
            errors.append(f"{label} input: cannot load corpus input: {error}")
            input_document = None
        expected_document = _load_json(expected_path, f"{label} expected", errors)
        if input_document is None or not isinstance(expected_document, dict):
            continue
        expected_errors = _schema_violations(
            expected_validator,
            expected_document,
            f"{label} expected",
        )
        errors.extend(expected_errors)
        if not expected_errors:
            errors.extend(
                _validate_expected_record(
                    input_document,
                    expected_document,
                    record_id,
                    f"{label} expected",
                )
            )

    for path in sorted(actual_inputs - listed_inputs):
        errors.append(f"unlisted corpus JSON file: {path}")
    for path in sorted(listed_inputs - actual_inputs):
        if (root / path).exists():
            errors.append(f"listed input path is not a regular JSON file: {path}")
    for path in sorted(actual_expected - listed_expected):
        errors.append(f"unlisted expected JSON file: {path}")
    for path in sorted(listed_expected - actual_expected):
        if (root / path).exists():
            errors.append(f"listed expected path is not a regular JSON file: {path}")

    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=_ROOT,
        help="repository root (defaults to the current checkout)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="explicit repository-relative corpus manifest path",
    )
    args = parser.parse_args(argv)

    errors = validate_repository(args.root, args.manifest)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        print(
            f"\n{len(errors)} redaction evaluation contract error(s).",
            file=sys.stderr,
        )
        return 1

    print("OK: redaction evaluation schemas and available corpus artifacts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
