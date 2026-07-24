#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regenerate golden checkpoint artifacts for alpha manifest entries (GH #258).

Uses the SAME construction path as the conformance harness
(``runtime.ingest_conformance_harness.collect_artifacts``), so goldens cannot
drift from harness semantics. Only entries whose ``real_capture`` is
``recorded`` produce goldens; missing captures cannot be faked into a matrix.

Run after an intentional contract change, then review the golden diff:

    python scripts/generate_alpha_goldens.py [connector/mode ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from runtime.ingest_conformance_harness import collect_artifacts  # noqa: E402

_MANIFEST = _REPO / "ingest" / "alpha-ingest-manifest.json"


def main() -> int:
    selected = set(sys.argv[1:])
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    written = 0
    for entry in manifest["entries"]:
        route = f"{entry['connector_id']}/{entry['mode']}"
        if selected and route not in selected:
            continue
        if entry["conformance_state"]["real_capture"] != "recorded":
            print(f"skip {route}: real capture missing (goldens are never synthesized)")
            continue
        artifacts = collect_artifacts(entry)
        for golden_key, rel in entry["expected"].items():
            if golden_key == "gateway_receipt" or not rel.strip():
                continue
            target = _REPO / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(artifacts[golden_key], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            written += 1
        print(f"regenerated {route}")
    print(f"{written} golden file(s) written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
