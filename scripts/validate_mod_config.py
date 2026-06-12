#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate every mod's config.json against the mod descriptor contract (the EM-safe-mod parity
of FX-CFG-001). Runs as a standalone CI step in THIS repo. Three layers, all fail-closed:

1. **Structural** — the same stdlib JSON-Schema subset checker the connector validator uses
   (``_check``), driven by ``mods/_schema/mod-descriptor.schema.json``; fail-closed (unknown keys
   rejected at every object level).
2. **Semantic / manifest tie** — ``id`` == folder name; and the UI descriptor must AGREE with the
   ENFORCED ``manifest.yaml`` (parsed by the fail-closed ``mods._manifest`` loader): ``manifest_id``
   / ``version`` / ``name`` match, ``emits`` == manifest ``outputs``, and **``em_safe.forbidden_actions``
   == manifest ``forbidden_actions``** (so the UI's trust-disclosure surface can never under/over-state
   the boundary the code contract enforces).
3. **Index + SETUP freshness** — the committed ``mods/index.json`` and each ``SETUP.md`` equal a fresh
   regeneration (byte-exact; catches CRLF drift too).

Exits non-zero on any failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO / "scripts"))
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from build_mod_index import build_index, render  # noqa: E402
from build_mod_setup import build_setup  # noqa: E402
from product_meta import PRODUCT_CHANNEL  # noqa: E402
from validate_connector_config import _check  # noqa: E402 — reuse the schema-subset checker

from mods._manifest import ModManifestError, load_manifest  # noqa: E402

_MODS = _REPO / "mods"
_SCHEMA = _MODS / "_schema" / "mod-descriptor.schema.json"
_INDEX = _MODS / "index.json"


def _semantic(descriptor: dict, folder: str) -> list[str]:
    """id == folder + the UI descriptor must agree with the enforced manifest.yaml."""
    errs: list[str] = []
    if descriptor.get("id") != folder:
        errs.append(f"id {descriptor.get('id')!r} != folder {folder!r}")
    if descriptor.get("channel") != PRODUCT_CHANNEL:  # uniform product channel (single source)
        errs.append(f"{folder}: channel {descriptor.get('channel')!r} != product channel {PRODUCT_CHANNEL!r}")
    manifest_path = _MODS / folder / "manifest.yaml"
    try:
        manifest = load_manifest(manifest_path)
    except (ModManifestError, OSError) as exc:  # fail-closed: a missing/broken manifest is a hard failure
        return errs + [f"{folder}: manifest load failed: {type(exc).__name__}"]
    if descriptor.get("manifest_id") != manifest.id:
        errs.append(f"{folder}: manifest_id {descriptor.get('manifest_id')!r} != manifest.id {manifest.id!r}")
    if descriptor.get("version") != manifest.version:
        errs.append(f"{folder}: version {descriptor.get('version')!r} != manifest.version {manifest.version!r}")
    if descriptor.get("name") != manifest.name:
        errs.append(f"{folder}: name {descriptor.get('name')!r} != manifest.name {manifest.name!r}")
    if set(descriptor.get("emits", [])) != set(manifest.outputs):
        errs.append(f"{folder}: emits {set(descriptor.get('emits', []))} != manifest outputs {set(manifest.outputs)}")
    fa = set((descriptor.get("em_safe") or {}).get("forbidden_actions", []))
    if fa != set(manifest.forbidden_actions):
        errs.append(f"{folder}: em_safe.forbidden_actions {fa} != manifest forbidden_actions {set(manifest.forbidden_actions)}")
    return errs


def validate_descriptor(path: Path, schema: dict) -> list[str]:
    """Structural + semantic errors for one mod config.json (empty list = valid)."""
    try:
        descriptor = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return [f"{path}: unparseable JSON ({exc})"]
    return _check(descriptor, schema, path.stem) + _semantic(descriptor, path.parent.name)


def validate_all(mods_dir: Path = _MODS) -> dict[str, list[str]]:
    """Validate every mods/*/config.json + the index + SETUP freshness. Path -> errors."""
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    report: dict[str, list[str]] = {}
    for path in sorted(mods_dir.glob("*/config.json")):
        errs = validate_descriptor(path, schema)
        if errs:
            report[str(path.relative_to(_REPO))] = errs
    fresh = render(build_index(mods_dir)).encode("utf-8")
    committed = _INDEX.read_bytes() if _INDEX.exists() else b""
    if fresh != committed:
        report["mods/index.json"] = ["stale — run scripts/build_mod_index.py"]
    for path in sorted(mods_dir.glob("*/config.json")):
        setup = path.parent / "SETUP.md"
        fresh_setup = build_setup(json.loads(path.read_text(encoding="utf-8"))).encode("utf-8")
        have = setup.read_bytes() if setup.exists() else b""
        if fresh_setup != have:
            report[str(setup.relative_to(_REPO))] = ["stale/missing — run scripts/build_mod_setup.py"]
    return report


def main() -> int:
    if not _MODS.exists():
        print("no mods/ — skip")
        return 0
    report = validate_all()
    if not report:
        print("mod-config: OK (descriptors valid + manifest-consistent + index fresh)")
        return 0
    for path, errs in report.items():
        for err in errs:
            print(f"FAIL {path}: {err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
