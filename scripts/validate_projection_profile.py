#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate every connector's projection.json against the projection-profile contract.

Runs as a standalone CI step in THIS repo (NOT wired into the cross-repo-portable
``governance_gate.py``). Three layers, all fail-closed:

1. **Structural** — a small stdlib JSON-Schema checker driven by
   ``connectors/_schema/projection-profile.schema.json``. It supports the subset the
   schema uses (``type`` / ``properties`` / ``required`` / ``enum`` / ``items`` /
   ``additionalProperties:false``) and is **fail-closed**: unknown keys are rejected
   at every object level (the ADR-0015 validator discipline). It is NOT a full
   JSON-Schema engine — that limit is the stated boundary.
2. **Semantic / drift-guard** — ``profile_id`` prefix == ``target_system``; the
   ``target_system`` inside the profile == the connector folder name; ``profile_id``
   embeds the ``target_surface``; ``required_canonical_ref`` and ``required_receipt``
   must both be ``true`` for all profiles (anti-drift, ADR-0019 §5).
3. **Authority-free discipline** — no profile may contain any field whose name matches
   authority / permission / approval / eligibility / canonical-mutation vocabulary
   (fail-closed by construction). The schema ``additionalProperties: false`` is the
   structural guard; this layer is the semantic double-check on field *values* and
   *allowed/forbidden field names*.

Exits non-zero on any failure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_CONNECTORS = _REPO / "connectors"
_SCHEMA = _CONNECTORS / "_schema" / "projection-profile.schema.json"

_PY_TYPE = {"object": dict, "array": list, "string": str, "boolean": bool}

# Authority / permission / approval / eligibility vocabulary that must never
# appear in allowed_fields or forbidden_fields values (the integrations authority
# boundary, ADR-0019 §4). The schema forbids adding new top-level fields
# (additionalProperties: false); this set guards the *content* of allowed/forbidden
# field lists against accidentally declaring authority-bearing target fields.
_AUTHORITY_FIELD_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)permission"),
    re.compile(r"(?i)approval"),
    re.compile(r"(?i)eligib"),
    re.compile(r"(?i)authori"),
    re.compile(r"(?i)canonical[_-]?mut"),
    re.compile(r"(?i)secret"),
    re.compile(r"(?i)credential"),
    re.compile(r"(?i)token"),
    re.compile(r"(?i)password"),
    re.compile(r"(?i)policy"),
]

_PROFILE_ID_RE = re.compile(
    r"^(?P<target>[a-z][a-z0-9_]*)\.(?P<surface>[a-z][a-z0-9_]*)\.(?P<kind>[a-z][a-z0-9_]*)\.v(?P<version>[1-9]\d*)$"
)


def _type_ok(value: object, kind: str) -> bool:
    """True if ``value`` matches the schema ``type``."""
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _PY_TYPE[kind])


def _check(value: object, schema: dict, path: str) -> list[str]:
    """Recursive fail-closed structural check over the schema subset."""
    errs: list[str] = []
    kind = schema.get("type")
    if isinstance(kind, str) and not _type_ok(value, kind):
        return [f"{path}: expected {kind}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: {value!r} not in {schema['enum']}")
    if kind == "object" and isinstance(value, dict):
        props = schema.get("properties", {})
        assert isinstance(props, dict)
        for req in schema.get("required", []):
            if req not in value:
                errs.append(f"{path}: missing required key {req!r}")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errs.append(f"{path}: unknown key {key!r} (fail-closed)")
        for key, sub in value.items():
            if key in props:
                sub_schema = props[key]
                assert isinstance(sub_schema, dict)
                errs.extend(_check(sub, sub_schema, f"{path}.{key}"))
    if kind == "array" and isinstance(value, list) and "items" in schema:
        items_schema = schema["items"]
        assert isinstance(items_schema, dict)
        for i, item in enumerate(value):
            errs.extend(_check(item, items_schema, f"{path}[{i}]"))
    return errs


def _authority_field_check(
    fields: list[str], field_list_name: str, profile_id: str
) -> list[str]:
    """Reject any field name that matches authority/permission/approval vocabulary."""
    errs: list[str] = []
    for field in fields:
        for pattern in _AUTHORITY_FIELD_PATTERNS:
            if pattern.search(field):
                errs.append(
                    f"{profile_id}: {field_list_name} contains authority/permission/secret "
                    f"field {field!r} (forbidden by ADR-0019 §4)"
                )
                break
    return errs


def _semantic(profile: dict, connector_folder: str) -> list[str]:
    """Drift-guard: profile_id format, target == folder, canonical-ref/receipt enforcement."""
    errs: list[str] = []
    pid = profile.get("profile_id", "")
    assert isinstance(pid, str)
    target = profile.get("target_system", "")
    assert isinstance(target, str)
    surface = profile.get("target_surface", "")
    assert isinstance(surface, str)

    # profile_id format
    m = _PROFILE_ID_RE.match(pid)
    if not m:
        errs.append(
            f"{pid}: profile_id must match <target>.<surface>.<kind>.v<N> "
            f"(e.g. linear.issue.summary.v1)"
        )
    else:
        # profile_id prefix must match target_system
        if m.group("target") != target:
            errs.append(
                f"{pid}: profile_id target prefix {m.group('target')!r} != target_system {target!r}"
            )
        # profile_id surface must match target_surface
        if m.group("surface") != surface:
            errs.append(
                f"{pid}: profile_id surface {m.group('surface')!r} != target_surface {surface!r}"
            )

    # target_system must match connector folder
    if target != connector_folder:
        errs.append(
            f"{pid}: target_system {target!r} != connector folder {connector_folder!r}"
        )

    # required_canonical_ref must be true (ADR-0019 §5.2)
    if profile.get("required_canonical_ref") is not True:
        errs.append(f"{pid}: required_canonical_ref must be true (ADR-0019 anti-drift)")

    # required_receipt must be true for all mutating profiles (ADR-0019 §5.3)
    if profile.get("required_receipt") is not True:
        errs.append(
            f"{pid}: required_receipt must be true (ADR-0019 receipt enforcement)"
        )

    # Authority-free field discipline on allowed_fields and forbidden_fields
    allowed = profile.get("allowed_fields", [])
    forbidden = profile.get("forbidden_fields", [])
    assert isinstance(allowed, list)
    assert isinstance(forbidden, list)
    errs.extend(_authority_field_check(allowed, "allowed_fields", pid))
    errs.extend(_authority_field_check(forbidden, "forbidden_fields", pid))

    # allowed and forbidden must not overlap
    overlap = set(allowed) & set(forbidden)
    if overlap:
        errs.append(
            f"{pid}: allowed_fields and forbidden_fields overlap: {sorted(overlap)}"
        )

    return errs


def validate_projection(path: Path, schema: dict) -> list[str]:
    """Structural + semantic errors for one projection.json (empty list = valid)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return [f"{path}: unparseable JSON ({exc})"]
    if not isinstance(data, list):
        return [f"{path}: top-level must be an array of projection profiles"]
    errs: list[str] = []
    folder = path.parent.name
    for i, profile in enumerate(data):
        if not isinstance(profile, dict):
            errs.append(f"{path}[{i}]: expected object, got {type(profile).__name__}")
            continue
        errs.extend(_check(profile, schema, f"{path.stem}[{i}]"))
        errs.extend(_semantic(profile, folder))
    if not data:
        errs.append(f"{path}: projection.json must contain at least one profile")
    return errs


def validate_all(connectors_dir: Path = _CONNECTORS) -> dict[str, list[str]]:
    """Validate every connectors/*/projection.json. Path -> errors."""
    schema_raw = _SCHEMA.read_text(encoding="utf-8")
    schema: dict = json.loads(schema_raw)
    report: dict[str, list[str]] = {}
    for path in sorted(connectors_dir.glob("*/projection.json")):
        errs = validate_projection(path, schema)
        if errs:
            report[str(path.relative_to(_REPO))] = errs
    return report


def main() -> int:
    if not _CONNECTORS.exists():
        print("no connectors/ — skip")
        return 0
    projections = list(_CONNECTORS.glob("*/projection.json"))
    if not projections:
        print("no projection.json files found — skip")
        return 0
    report = validate_all()
    if not report:
        print(f"projection-profile: OK ({len(projections)} file(s) valid)")
        return 0
    for path, errs in report.items():
        for err in errs:
            print(f"FAIL {path}: {err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
