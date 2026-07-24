#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Operator-run Linear GraphQL live-wire verification (GH #258, D7).

connectors/linear/auth.md marks the exact Issue field set, ``orderBy:
updatedAt`` behavior, pagination envelope, and rate-limit shape as
**UNVERIFIED until a live response** (wire-gate). This command executes the
documented query against the real Linear API with an operator-supplied key and
reports what was actually observed, so the auth.md "Observed" section can be
updated from EVIDENCE rather than by copying provider documentation.

    LINEAR_API_KEY=<key> python scripts/linear_live_wire.py \
        --capture-out ingest/captures/linear-graphql_poll/raw.json

The raw response is written for the sanitize step (never commit it raw); the
verification report prints to stdout with no credential material.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_API = "https://api.linear.app/graphql"
_QUERY = """query Issues($first: Int!, $after: String) {
  issues(first: $first, after: $after, orderBy: updatedAt) {
    nodes { id identifier title description url updatedAt state { name } }
    pageInfo { hasNextPage endCursor }
  }
}"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-out", required=True)
    parser.add_argument("--first", type=int, default=5)
    args = parser.parse_args()

    key = os.environ.get("LINEAR_API_KEY", "")
    if not key:
        print("LINEAR_API_KEY is empty; refusing to run", file=sys.stderr)
        return 1

    request = urllib.request.Request(
        _API,
        data=json.dumps({"query": _QUERY, "variables": {"first": args.first, "after": None}}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": key},
        method="POST",
    )
    observed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        # Scheme is the pinned https constant _API; no file:/custom schemes reachable.
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
            status = response.status
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - live path
        status = exc.code
        body = json.loads(exc.read().decode("utf-8") or "{}")

    findings: dict[str, object] = {"observed_at": observed_at, "http_status": status}
    if "errors" in body:
        codes = [
            str(((err.get("extensions") or {}).get("code")) or err.get("message", ""))
            for err in body["errors"]
        ]
        findings["errors_array_present"] = True
        findings["error_codes"] = codes
        findings["ratelimited_shape_confirmed"] = any(code == "RATELIMITED" for code in codes)
        print(json.dumps(findings, indent=2))
        print("wire-gate NOT satisfied by an error response; retry within limits", file=sys.stderr)
        return 1

    issues = body.get("data", {}).get("issues", {})
    nodes = issues.get("nodes", [])
    page = issues.get("pageInfo", {})
    expected_fields = {"id", "identifier", "title", "description", "url", "updatedAt", "state"}
    node_fields = set(nodes[0]) if nodes else set()
    timestamps = [str(n.get("updatedAt", "")) for n in nodes]
    findings.update(
        {
            "queried_field_set_returned": sorted(node_fields),
            "expected_fields_all_present": expected_fields <= node_fields,
            "auth_header_accepted": True,
            "pagination_envelope": sorted(page),
            "pagination_envelope_matches": {"hasNextPage", "endCursor"} <= set(page),
            "order_by_updated_at_descending_observed": timestamps == sorted(timestamps, reverse=True),
            "node_count": len(nodes),
            "dedup_identity_field_present": all(bool(n.get("id")) for n in nodes),
        }
    )
    out = Path(args.capture_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(findings, indent=2))
    print(
        f"raw response written to {out} (NEVER commit raw; run scripts/capture_sanitize.py next).\n"
        "Update connectors/linear/auth.md 'Observed' with these findings + this date; "
        "webhook signature/timestamp verification still needs a live signed delivery."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
