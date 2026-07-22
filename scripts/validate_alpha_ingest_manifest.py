#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate the July-29 alpha ingest manifest (GH #258). Fail-closed.

Two layers, both fail-closed, mirroring ``validate_connector_config.py``:

1. **Structural** — the repo's stdlib JSON-Schema-subset checker driven by
   ``ingest/_schema/alpha-ingest-manifest.schema.json`` (closed: unknown fields
   and unknown state values fail).
2. **Semantic honesty** — the multi-axis conformance state cannot overstate
   evidence: ``component: proven`` requires ``real_capture: recorded``;
   ``real_capture: recorded`` requires the sanitized capture and its ledger to
   exist AND the committed sanitized digest to match the capture bytes;
   ``gateway: proven`` requires an existing gateway receipt path;
   ``terminal_bot: proven`` requires ``gateway: proven``;
   ``implementation: missing`` forces every downstream axis unproven/missing
   and requires the deferral to be documented in ``notes``;
   non-empty ``expected.*`` golden paths must resolve to repo files.

Exits non-zero on any failure.
"""

from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from validate_connector_config import _check  # reuse the fail-closed checker  # noqa: E402

_MANIFEST = _REPO / "ingest" / "alpha-ingest-manifest.json"
_SCHEMA = _REPO / "ingest" / "_schema" / "alpha-ingest-manifest.schema.json"


def _entry_label(entry: dict) -> str:
    return f"{entry.get('connector_id', '?')}/{entry.get('mode', '?')}"


def semantic_errors(manifest: dict) -> list[str]:
    errs: list[str] = []
    seen: set[tuple[str, str]] = set()
    for entry in manifest.get("entries", []):
        label = _entry_label(entry)
        key = (entry.get("connector_id", ""), entry.get("mode", ""))
        if key in seen:
            errs.append(f"{label}: duplicate connector/mode entry")
        seen.add(key)

        if not (_REPO / "connectors" / entry["connector_id"]).is_dir():
            errs.append(f"{label}: connector directory does not exist")

        state = entry["conformance_state"]
        capture = entry["real_capture"]

        if state["implementation"] == "missing":
            if state["real_capture"] != "missing" or state["component"] != "unproven":
                errs.append(
                    f"{label}: implementation missing forces real_capture=missing and component=unproven"
                )
            if state["gateway"] != "unproven" or state["terminal_bot"] != "unproven":
                errs.append(f"{label}: implementation missing forces gateway/terminal_bot unproven")
            if not entry.get("notes", "").strip():
                errs.append(f"{label}: implementation missing requires the deferral documented in notes")

        if state["real_capture"] == "recorded":
            path = _REPO / capture["path"]
            ledger = _REPO / capture["sanitization_ledger"]
            if not path.is_file():
                errs.append(f"{label}: recorded capture path missing: {capture['path']}")
            elif capture["sanitized_digest"] != "sha256:" + sha256(path.read_bytes()).hexdigest():
                errs.append(f"{label}: sanitized_digest does not match the committed capture bytes")
            if not ledger.is_file():
                errs.append(f"{label}: sanitization ledger missing: {capture['sanitization_ledger']}")
            if not capture["captured_at"].strip() or not capture["source_license_or_retention_note"].strip():
                errs.append(f"{label}: recorded capture requires captured_at and license/retention note")
        else:
            if state["component"] == "proven":
                errs.append(f"{label}: component cannot be proven without a recorded real capture")
            if not entry["capture_command"].strip() or not entry["required_credential_class"].strip():
                errs.append(
                    f"{label}: missing capture requires the exact capture_command and required_credential_class"
                )

        if state["gateway"] == "proven" and not (
            entry["expected"]["gateway_receipt"].strip()
            and (_REPO / entry["expected"]["gateway_receipt"]).is_file()
        ):
            errs.append(f"{label}: gateway proven requires an existing committed gateway receipt")
        if state["terminal_bot"] == "proven" and state["gateway"] != "proven":
            errs.append(f"{label}: terminal_bot cannot be proven while gateway is unproven")
        if state["human_acceptance"] == "accepted" and state["terminal_bot"] != "proven":
            errs.append(f"{label}: human acceptance cannot precede terminal Bot proof")

        for name, rel in entry["expected"].items():
            if rel.strip() and not (_REPO / rel).is_file():
                errs.append(f"{label}: expected.{name} path does not resolve: {rel}")
    return errs


def main() -> int:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    errs = _check(manifest, schema, "manifest")
    if not errs:
        errs = semantic_errors(manifest)
    if errs:
        print("alpha ingest manifest validation FAILED:", file=sys.stderr)
        for err in errs:
            print(f"- {err}", file=sys.stderr)
        return 1
    entries = manifest["entries"]
    recorded = sum(1 for e in entries if e["conformance_state"]["real_capture"] == "recorded")
    print(
        f"alpha ingest manifest OK: {len(entries)} routes, {recorded} recorded real capture(s), "
        "state axes honest (no collapsed verified boolean)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
