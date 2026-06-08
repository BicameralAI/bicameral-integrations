#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Aggregate every connector's config.json into a single committed index for the mcp UI.

Emits ``connectors/index.json`` = ``{"connectors": {<id>: <descriptor>, ...}}`` sorted by id.
Deterministic (sort_keys + indent + trailing newline) so the validator's freshness check
(regenerate == committed) is a stable drift guard. Stdlib-only.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_CONNECTORS = _REPO / "connectors"
_INDEX = _CONNECTORS / "index.json"


def build_index(connectors_dir: Path = _CONNECTORS) -> dict:
    """Read every ``connectors/*/config.json`` into one id-keyed index dict."""
    out: dict[str, dict] = {}
    for path in sorted(connectors_dir.glob("*/config.json")):
        descriptor = json.loads(path.read_text(encoding="utf-8"))
        out[descriptor["id"]] = descriptor
    return {"connectors": out}


def render(index: dict) -> str:
    """Canonical JSON text (deterministic) for the committed index."""
    return json.dumps(index, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    # write_bytes (NOT write_text) so the LF from render() is preserved verbatim on every OS —
    # write_text translates \n -> os.linesep (CRLF on Windows), breaking the byte-determinism claim.
    _INDEX.write_bytes(render(build_index()).encode("utf-8"))
    print(f"wrote {_INDEX.relative_to(_REPO)} ({len(build_index()['connectors'])} connectors)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
