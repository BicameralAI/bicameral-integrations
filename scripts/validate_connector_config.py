#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate every connector's config.json against the descriptor contract (FX-CFG-001).

Runs as a standalone CI step in THIS repo (NOT wired into the cross-repo-portable
``governance_gate.py``). Three layers, all fail-closed:

1. **Structural** — a small stdlib JSON-Schema checker driven by
   ``connectors/_schema/connector-config.schema.json``. It supports the subset the schema uses
   (``type`` / ``properties`` / ``required`` / ``enum`` / ``items`` / ``additionalProperties:false``)
   and is **fail-closed**: unknown keys are rejected at every object level (the ``mods/_manifest.py``
   discipline). It is NOT a full JSON-Schema engine — that limit is the stated boundary (ADR-0015).
2. **Semantic / code drift-guard** — ``id`` == folder name == the connector's ``source_id``; the
   declared ``modes`` ⊆ the connector's ``capabilities.modes`` (resolved by ``importlib`` of just the
   connector module, in a fail-closed ``try/except`` — connectors MUST be import-side-effect-free,
   ADR-0012); a webhook block iff a ``webhook`` mode; ``instructions[].ref`` required for
   ``open_url``/``register_webhook``/``configure`` (anti-fabrication — a provider click-path must cite
   its verified source).
3. **Index freshness** — the committed ``connectors/index.json`` equals a fresh aggregation.

Exits non-zero on any failure.
"""

from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path

from build_connector_index import build_index, render
from build_connector_setup import build_setup

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:  # CLI: sys.path[0] is scripts/, not repo root — make `connectors` importable
    sys.path.insert(0, str(_REPO))
_CONNECTORS = _REPO / "connectors"
_SCHEMA = _CONNECTORS / "_schema" / "connector-config.schema.json"
_INDEX = _CONNECTORS / "index.json"

_REF_REQUIRED_ACTIONS = frozenset({"open_url", "register_webhook", "configure"})
_PY_TYPE = {"object": dict, "array": list, "string": str, "boolean": bool}
_REF_RE = re.compile(r"^(?P<path>[^()]+?)(?:\s*\((?P<section>[^()]+)\))?$")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(?P<text>.+?)\s*$")


def _resolve_ref(folder: str, ref: str) -> str | None:
    """Resolution-check an instructions[].ref (anti-fabrication, deep-audit): the cited file must
    exist under the repo, and a ``(Section)`` label — when present — must match an existing markdown
    heading (fail-closed). Hardens the gate from presence-only; returns an error string or None."""
    match = _REF_RE.match(ref.strip())
    if not match:
        return f"{folder}: instructions ref {ref!r} is malformed"
    rel = (match.group("path") or "").strip()
    target = _REPO / rel
    if not target.is_file():
        return f"{folder}: instructions ref path {rel!r} does not resolve to a repo file"
    section = (match.group("section") or "").strip()
    if section:
        headings = [
            m.group("text").lower()
            for line in target.read_text(encoding="utf-8").splitlines()
            if (m := _HEADING_RE.match(line))
        ]
        if not any(section.lower() in h for h in headings):
            return f"{folder}: instructions ref cites section {section!r} but no matching heading in {rel}"
    return None


def _type_ok(value: object, kind: str) -> bool:
    """True if ``value`` matches the schema ``type`` (bool is NOT int/number; null only via absent type)."""
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _PY_TYPE[kind])


def _check(value: object, schema: dict, path: str) -> list[str]:
    """Recursive fail-closed structural check over the schema subset used by the contract."""
    errs: list[str] = []
    kind = schema.get("type")
    if kind and not _type_ok(value, kind):
        return [f"{path}: expected {kind}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: {value!r} not in {schema['enum']}")
    if kind == "object" and isinstance(value, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in value:
                errs.append(f"{path}: missing required key {req!r}")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errs.append(f"{path}: unknown key {key!r} (fail-closed)")
        for key, sub in value.items():
            if key in props:
                errs.extend(_check(sub, props[key], f"{path}.{key}"))
    if kind == "array" and isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errs.extend(_check(item, schema["items"], f"{path}[{i}]"))
    return errs


def _connector_class(connector_id: str):
    """Import the connector module and return the class carrying source_id + capabilities."""
    module = importlib.import_module(f"connectors.{connector_id}.connector")
    for obj in vars(module).values():
        if isinstance(obj, type) and hasattr(obj, "source_id") and hasattr(obj, "capabilities"):
            return obj
    raise LookupError(f"no connector class with source_id+capabilities in connectors.{connector_id}")


def _semantic(descriptor: dict, folder: str) -> list[str]:
    """id/source_id/modes drift-guard + webhook-mode coherence + conditional instruction refs."""
    errs: list[str] = []
    cid = descriptor.get("id")
    if cid != folder:
        errs.append(f"id {cid!r} != folder {folder!r}")
    try:
        cls = _connector_class(folder)
    except Exception as exc:  # fail-closed: a broken/side-effecting import is a hard failure
        return errs + [f"connector import failed for {folder!r}: {type(exc).__name__}"]
    if cid != getattr(cls, "source_id", None):
        errs.append(f"id {cid!r} != connector.source_id {getattr(cls, 'source_id', None)!r}")
    cap_modes = {str(m) for m in cls.capabilities.modes}
    declared = set(descriptor.get("modes", []))
    extra = declared - cap_modes
    if extra:
        errs.append(f"{folder}: modes {extra} not in capabilities {cap_modes}")
    has_webhook_mode = "webhook" in declared
    if has_webhook_mode != ("webhook" in descriptor):
        errs.append(f"{folder}: webhook block {'required' if has_webhook_mode else 'unexpected'} for declared modes")
    for c in descriptor.get("credentials", []):  # FX-RUNTIME-005: a credential serving a mode the connector
        cred_extra = set(c.get("modes") or []) - declared  # doesn't declare is dead → latent silent under-require
        if cred_extra:
            errs.append(f"{folder}: credential {c.get('key')!r} modes {cred_extra} not in connector modes {declared}")
    for i, step in enumerate(descriptor.get("instructions", [])):
        if not isinstance(step, dict):  # _check already flags the type; never throw here (return errors)
            continue
        if step.get("action") in _REF_REQUIRED_ACTIONS:
            ref = step.get("ref")
            if not ref:
                errs.append(f"{folder}: instructions[{i}] action {step['action']!r} requires a 'ref' (anti-fabrication)")
            elif (err := _resolve_ref(folder, ref)) is not None:
                errs.append(err)
    return errs


def validate_descriptor(path: Path, schema: dict) -> list[str]:
    """Structural + semantic errors for one config.json (empty list = valid)."""
    try:
        descriptor = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return [f"{path}: unparseable JSON ({exc})"]
    return _check(descriptor, schema, path.stem) + _semantic(descriptor, path.parent.name)


def validate_all(connectors_dir: Path = _CONNECTORS) -> dict[str, list[str]]:
    """Validate every connectors/*/config.json + the index freshness. Path -> errors."""
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    report: dict[str, list[str]] = {}
    for path in sorted(connectors_dir.glob("*/config.json")):
        errs = validate_descriptor(path, schema)
        if errs:
            report[str(path.relative_to(_REPO))] = errs
    fresh = render(build_index(connectors_dir)).encode("utf-8")
    committed = _INDEX.read_bytes() if _INDEX.exists() else b""  # byte-exact: catches CRLF drift too
    if fresh != committed:
        report["connectors/index.json"] = ["stale — run scripts/build_connector_index.py"]
    for path in sorted(connectors_dir.glob("*/config.json")):  # only config.json-bearing connectors
        setup = path.parent / "SETUP.md"
        fresh_setup = build_setup(json.loads(path.read_text(encoding="utf-8"))).encode("utf-8")
        have = setup.read_bytes() if setup.exists() else b""  # missing -> b"" -> mismatch, fail-closed
        if fresh_setup != have:
            report[str(setup.relative_to(_REPO))] = ["stale/missing — run scripts/build_connector_setup.py"]
    return report


def main() -> int:
    if not _CONNECTORS.exists():
        print("no connectors/ — skip")
        return 0
    report = validate_all()
    if not report:
        print("connector-config: OK (descriptors valid + index fresh)")
        return 0
    for path, errs in report.items():
        for err in errs:
            print(f"FAIL {path}: {err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
