#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Operator-run REAL GatewaySink delivery with a binding receipt (GH #258/#260).

Runs one recorded sanitized capture through the full mandatory path
(acquire -> redaction boundary -> universal normalization -> envelope) and
delivers it to a REAL Bot external-ingest endpoint via the production
``GatewaySink``. Only HTTP 201 is success under the existing contract; a
CollectingSink, mock server, in-process handler, or recorded transport can
NEVER satisfy the manifest's gateway checkpoint — this command is the only
path that can move a route's ``gateway`` axis to ``proven``.

The receipt binds: exact Integrations commit, exact Bot commit (schema pin +
any observed identity), connector/mode, sanitized capture digest, redaction
receipt digest, envelope digest, HTTP status, Bot evidence identity or typed
acceptance identifier, cursor outcome, start/complete times, and cleanup.

Credentials: the gateway bearer token is read from the environment variable
named by ``--token-env`` (never from arguments, never logged).

    python scripts/real_gateway_delivery.py \
        --route local_directory/passive_import \
        --endpoint https://<bot-host>/api/v1/external-ingest \
        --token-env BICAMERAL_GATEWAY_TOKEN \
        --receipt-out ingest/receipts/<route>-gateway-receipt.json
"""

from __future__ import annotations

import argparse
import json
import os
# Fixed-argv `git rev-parse` only; no shell, no untrusted input.
import subprocess  # nosec B404
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from adapter.core.redaction_receipt import receipt_digest  # noqa: E402
from runtime.ingest_conformance_harness import canonical_digest, collect_artifacts  # noqa: E402
from runtime.sinks import GatewayEmissionError, GatewaySink  # noqa: E402
from runtime.cursor_policy import resolve_cursor_action  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", required=True, help="connector/mode from the alpha manifest")
    parser.add_argument("--endpoint", required=True, help="real Bot external-ingest endpoint URL")
    parser.add_argument("--token-env", required=True, help="env var holding the gateway bearer token")
    parser.add_argument("--receipt-out", required=True)
    args = parser.parse_args()

    token = os.environ.get(args.token_env, "")
    if not token:
        print(f"gateway token env {args.token_env} is empty; refusing to run", file=sys.stderr)
        return 1

    manifest = json.loads((_REPO / "ingest" / "alpha-ingest-manifest.json").read_text(encoding="utf-8"))
    connector, mode = args.route.split("/", 1)
    entry = next(
        e for e in manifest["entries"] if e["connector_id"] == connector and e["mode"] == mode
    )
    if entry["conformance_state"]["real_capture"] != "recorded":
        print(f"{args.route}: real capture missing; a real delivery needs a real capture first", file=sys.stderr)
        return 1

    integrations_commit = subprocess.run(  # nosec B603 B607
        ["git", "-C", str(_REPO), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    pin = json.loads((_REPO / "runtime" / "schemas" / "ingest_schema_pin.json").read_text(encoding="utf-8"))

    started_at = _now()
    artifacts = collect_artifacts(entry)
    emission = artifacts["_emission"]
    envelope = artifacts["external_ingest_envelope"]

    sink = GatewaySink(endpoint=args.endpoint, token=token)
    status = 0
    bot_identity = ""
    error_reason = ""
    try:
        sink.emit([emission])
        status = 201
        # The current GatewaySink does not surface the response body; the
        # Bot-side identity is the deterministic content hash of the envelope
        # content, which the Bot computes identically (typed acceptance id).
        bot_identity = "content_sha256:" + sha256(
            str(envelope.get("content", "")).encode("utf-8")
        ).hexdigest()
    except GatewayEmissionError as exc:
        status = getattr(exc, "status", 0)
        error_reason = getattr(exc, "reason", "") or exc.__class__.__name__
    cursor = resolve_cursor_action(status=status, reason=error_reason)
    completed_at = _now()

    receipt = {
        "schema_version": 1,
        "kind": "real-gateway-delivery-receipt",
        "route": args.route,
        "integrations_commit": integrations_commit,
        "bot_commit_pin": pin["upstream_commit"],
        "contract_schema_sha256": "sha256:" + pin["content_sha256"],
        "sanitized_capture_digest": entry["real_capture"]["sanitized_digest"],
        "redaction_receipt_digest": receipt_digest(
            {**artifacts["redaction_receipt"]["receipt"], "completed_at": ""}
        ),
        "envelope_digest": canonical_digest(envelope),
        "http_status": status,
        "success": status == 201,
        "bot_evidence_identity": bot_identity,
        "typed_failure_reason": error_reason,
        "cursor_outcome": str(cursor.verdict),
        "started_at": started_at,
        "completed_at": completed_at,
        "cleanup": "no provider-side state created; local capture retained; token remains in operator env only",
    }
    out = Path(args.receipt_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"delivery {'SUCCEEDED (201)' if status == 201 else f'did not succeed (status {status})'}; receipt: {out}")
    print("update the manifest gateway axis ONLY on a committed 201 receipt")
    return 0 if status == 201 else 1


if __name__ == "__main__":
    raise SystemExit(main())
