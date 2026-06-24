# SPDX-License-Identifier: MIT
"""Ingest schema drift gate — validates vendored IngestRequest schema integrity (#195).

Checks performed (all offline, no live credentials):

1. **Content-hash integrity**: the SHA-256 of the vendored schema file matches
   the ``content_sha256`` recorded in the pin metadata file.
2. **Pin metadata completeness**: upstream_repo, upstream_commit (40-char SHA),
   upstream_path, local_path, and content_sha256 are all present and non-empty.
3. **Structural smoke-test**: the vendored schema is valid JSON, declares the
   expected ``required`` fields (title, description, source), and defines
   ``IngestEvidenceItem``.
4. **Golden-fixture schema conformance**: every golden conformance fixture's
   ``expected_ingest_request`` satisfies the vendored schema structurally.

Exit 0 on success, exit 1 on any drift/integrity failure. Designed to run in CI
as a contract gate that fails integrations on stale mapping/schema incompatibility.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_PATH = _ROOT / "runtime" / "schemas" / "ingest_request_v1.schema.json"
_PIN_PATH = _ROOT / "runtime" / "schemas" / "ingest_schema_pin.json"
_FIXTURES_DIR = _ROOT / "runtime" / "tests" / "fixtures" / "ingest_conformance"

_REQUIRED_PIN_KEYS = (
    "upstream_repo",
    "upstream_commit",
    "upstream_path",
    "local_path",
    "content_sha256",
)


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)


def _check_pin_metadata(pin: dict) -> list[str]:
    errors: list[str] = []
    for key in _REQUIRED_PIN_KEYS:
        val = pin.get(key)
        if not val or not isinstance(val, str):
            errors.append(f"pin metadata missing or empty: {key!r}")
    commit = pin.get("upstream_commit", "")
    if len(commit) != 40:
        errors.append(f"upstream_commit must be a 40-char SHA, got {len(commit)} chars")
    return errors


def _check_content_hash(pin: dict) -> list[str]:
    if not _SCHEMA_PATH.exists():
        return [f"vendored schema not found: {_SCHEMA_PATH}"]
    actual = hashlib.sha256(_SCHEMA_PATH.read_bytes()).hexdigest()
    expected = pin.get("content_sha256", "")
    if actual != expected:
        return [
            f"content hash mismatch: vendored schema SHA-256 is {actual}, "
            f"pin records {expected}. Re-pin after schema update."
        ]
    return []


def _check_schema_structure(schema: dict) -> list[str]:
    errors: list[str] = []
    required = schema.get("required", [])
    for field in ("title", "description", "source"):
        if field not in required:
            errors.append(f"schema missing required field: {field!r}")
    defs = schema.get("definitions", {})
    if "IngestEvidenceItem" not in defs:
        errors.append("schema missing definition: IngestEvidenceItem")
    return errors


def _check_fixture_conformance(schema: dict) -> list[str]:
    errors: list[str] = []
    if not _FIXTURES_DIR.exists():
        errors.append(f"fixtures directory not found: {_FIXTURES_DIR}")
        return errors
    fixtures = sorted(_FIXTURES_DIR.glob("*.json"))
    if not fixtures:
        errors.append("no golden conformance fixtures found")
        return errors
    required_keys = set(schema.get("required", []))
    evidence_required = set(
        schema.get("definitions", {}).get("IngestEvidenceItem", {}).get("required", [])
    )
    for path in fixtures:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        expected = fixture.get("expected_ingest_request", {})
        for key in required_keys:
            val = expected.get(key)
            if not isinstance(val, str) or not val:
                errors.append(
                    f"{path.name}: expected_ingest_request missing required {key!r}"
                )
        for i, item in enumerate(expected.get("evidence", [])):
            for key in evidence_required:
                if key not in item or not isinstance(item[key], str):
                    errors.append(
                        f"{path.name}: evidence[{i}] missing required {key!r}"
                    )
    return errors


def main() -> int:
    all_errors: list[str] = []

    # Load pin metadata
    if not _PIN_PATH.exists():
        _fail(f"pin metadata not found: {_PIN_PATH}")
        return 1
    pin = json.loads(_PIN_PATH.read_text(encoding="utf-8"))
    all_errors.extend(_check_pin_metadata(pin))

    # Content hash
    all_errors.extend(_check_content_hash(pin))

    # Schema structure
    if not _SCHEMA_PATH.exists():
        _fail(f"vendored schema not found: {_SCHEMA_PATH}")
        return 1
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    all_errors.extend(_check_schema_structure(schema))

    # Golden fixture conformance
    all_errors.extend(_check_fixture_conformance(schema))

    if all_errors:
        for err in all_errors:
            _fail(err)
        print(
            f"\n{len(all_errors)} ingest schema drift error(s). "
            "See runtime/schemas/ingest_schema_pin.json and the vendored schema.",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: ingest schema pin verified (upstream {pin['upstream_commit'][:12]}…, "
        f"{len(list(_FIXTURES_DIR.glob('*.json')))} golden fixtures conformant)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
