#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Aggregate every mod's config.json into a single committed index for the mcp UI.

The EM-safe-mod parity of ``build_connector_index.py``. Emits ``mods/index.json`` =
``{"mods": {<id>: <descriptor>, ...}}`` sorted by id. Deterministic (sort_keys + indent +
trailing newline) so the validator's freshness check (regenerate == committed) is a stable
drift guard. Stdlib-only.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_MODS = _REPO / "mods"
_INDEX = _MODS / "index.json"


def build_index(mods_dir: Path = _MODS) -> dict:
    """Read every ``mods/*/config.json`` into one id-keyed index dict."""
    out: dict[str, dict] = {}
    for path in sorted(mods_dir.glob("*/config.json")):
        descriptor = json.loads(path.read_text(encoding="utf-8"))
        out[descriptor["id"]] = descriptor
    return {"mods": out}


def render(index: dict) -> str:
    """Canonical JSON text (deterministic) for the committed index."""
    return json.dumps(index, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    # write_bytes (NOT write_text) so the LF from render() is preserved verbatim on every OS.
    _INDEX.write_bytes(render(build_index()).encode("utf-8"))
    print(f"wrote {_INDEX.relative_to(_REPO)} ({len(build_index()['mods'])} mods)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
