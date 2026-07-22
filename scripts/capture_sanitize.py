#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Sanitize a real provider capture and write its sanitization ledger (GH #258/#260).

Raw provider data is NEVER committed. This tool takes a raw provider-format
payload obtained through the real acquisition boundary, applies the
deterministic redaction engine to every string leaf, proves that structural
parsing/identity/dedup/timestamp fields survived, and writes:

- ``capture.json`` — ``{payload, capture_meta}`` with the SANITIZED payload;
- ``sanitization-ledger.json`` — provider/mode, capture date, provider schema
  version, original-content SHA-256 (the only, irreversible representation of
  the original bytes), sanitized-content SHA-256, redaction categories+counts,
  the structural-preservation proof, and the source license/retention note.

For ``local_directory`` the tool can PERFORM the real acquisition itself
(``--acquire-local-file``): an operator-run read of an actual file on disk is
the connector's genuine passive-import boundary. Every other connector's raw
capture must be obtained with that provider's credentials (commands documented
in ``ingest/alpha-ingest-manifest.json``) and passed via ``--input``.

Synthetic fixtures must NOT be fed through this tool to fake a real capture:
the ledger records acquisition provenance and the manifest state stays
``missing`` until a genuine capture exists.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from adapter.core.redaction import redact  # noqa: E402
from adapter.core.redaction_receipt import ENGINE, ENGINE_VERSION, RULESET_DIGEST, RULESET_ID  # noqa: E402

_PLACEHOLDERS = {
    "[redacted:email]": "pii",
    "[redacted:phone]": "pii",
    "[redacted:secret]": "secret",
    "[redacted:phi]": "phi",
    "[redacted:pan]": "pan",
}


def _sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _category_counts(before: str, after: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token, category in _PLACEHOLDERS.items():
        delta = after.count(token) - before.count(token)
        if delta > 0:
            counts[category] = counts.get(category, 0) + delta
    return counts


def _structural_proof(connector: str, raw: dict[str, Any], sanitized: dict[str, Any]) -> dict[str, Any]:
    """Prove sanitization preserved parsing, identity, dedup, timestamp, and
    version fields by parsing BOTH payloads and comparing structural facts."""
    if connector == "local_directory":
        from connectors.local_directory.connector import parse_file

        a, b = parse_file(raw), parse_file(sanitized)
        fields = {
            "ref": (a.source_ref.ref, b.source_ref.ref),
            "source_id": (a.source_ref.source_id, b.source_ref.source_id),
            "timestamp": (a.timestamp, b.timestamp),
            "mode": (str(a.mode), str(b.mode)),
        }
    elif connector == "github":
        from connectors.github.connector import parse_pull_request

        a, b = parse_pull_request(raw), parse_pull_request(sanitized)
        fields = {
            "ref": (a.source_ref.ref, b.source_ref.ref),
            "timestamp": (a.timestamp, b.timestamp),
            "mode": (str(a.mode), str(b.mode)),
        }
    elif connector == "linear":
        from connectors.linear.connector import parse_event

        a, b = parse_event(raw), parse_event(sanitized)
        fields = {
            "ref": (a.source_ref.ref, b.source_ref.ref),
            "timestamp": (a.timestamp, b.timestamp),
            "mode": (str(a.mode), str(b.mode)),
        }
    elif connector == "google_drive":
        from connectors.google_drive.connector import parse_document

        a, b = parse_document(raw), parse_document(sanitized)
        fields = {
            "ref": (a.source_ref.ref, b.source_ref.ref),
            "mode": (str(a.mode), str(b.mode)),
        }
    else:
        raise SystemExit(f"unknown connector for structural proof: {connector}")
    return {
        "method": "parse-both-and-compare",
        "fields": {name: {"raw": pair[0], "sanitized": pair[1]} for name, pair in fields.items()},
        "preserved": all(pair[0] == pair[1] for pair in fields.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connector", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--input", help="Raw provider-format JSON payload (never committed)")
    parser.add_argument(
        "--acquire-local-file",
        help="local_directory only: perform the real passive-import acquisition of this file",
    )
    parser.add_argument("--scan-root", default="", help="local_directory scan root recorded for scope checks")
    parser.add_argument("--provider-schema-version", required=True)
    parser.add_argument("--license-note", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--capture-meta", default="{}", help="JSON object merged into capture_meta")
    args = parser.parse_args()

    if args.acquire_local_file:
        if args.connector != "local_directory":
            raise SystemExit("--acquire-local-file is the local_directory passive-import boundary only")
        source = Path(args.acquire_local_file)
        stat = source.stat()
        raw: dict[str, Any] = {
            "path": source.as_posix(),
            "content": source.read_text(encoding="utf-8"),
            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }
        acquisition = f"operator-run local file read of {source.as_posix()}"
    elif args.input:
        raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
        acquisition = f"operator-supplied raw capture {Path(args.input).name} (obtained with provider credentials)"
    else:
        raise SystemExit("supply --input or --acquire-local-file")

    raw_bytes = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sanitized = _sanitize(raw)
    sanitized_payload_bytes = json.dumps(sanitized, sort_keys=True, separators=(",", ":")).encode("utf-8")

    proof = _structural_proof(args.connector, raw, sanitized)
    if not proof["preserved"]:
        raise SystemExit("sanitization changed structural fields; capture rejected (fail closed)")

    counts = _category_counts(
        json.dumps(raw, sort_keys=True), json.dumps(sanitized, sort_keys=True)
    )
    captured_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    capture_meta = {"acquisition": acquisition, "captured_at": captured_at}
    capture_meta.update(json.loads(args.capture_meta))
    if args.scan_root:
        capture_meta["scan_root"] = args.scan_root
    capture_doc = {"payload": sanitized, "capture_meta": capture_meta}
    capture_path = out_dir / "capture.json"
    capture_path.write_text(json.dumps(capture_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    ledger = {
        "provider": args.connector,
        "mode": args.mode,
        "captured_at": captured_at,
        "provider_schema_version": args.provider_schema_version,
        "acquisition": acquisition,
        "original_content_sha256": "sha256:" + sha256(raw_bytes).hexdigest(),
        "original_retention": "raw bytes discarded after sanitization; the digest above is the only, irreversible representation",
        "sanitized_content_sha256": "sha256:"
        + sha256(capture_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "sanitized_payload_sha256": "sha256:" + sha256(sanitized_payload_bytes).hexdigest(),
        "redaction": {
            "engine": ENGINE,
            "engine_version": ENGINE_VERSION,
            "ruleset_id": RULESET_ID,
            "ruleset_digest": RULESET_DIGEST,
            "categories": counts,
        },
        "structural_fields_proof": proof,
        "source_license_or_retention_note": args.license_note,
    }
    (out_dir / "sanitization-ledger.json").write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"sanitized capture written: {capture_path}")
    print(f"sanitized capture digest: {ledger['sanitized_content_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
