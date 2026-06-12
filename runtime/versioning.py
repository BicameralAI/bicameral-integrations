# SPDX-License-Identifier: MIT
"""Derive the per-connector emission ``adapter_version`` from the descriptor (single source).

The connector ``version`` lives in `connectors/<id>/config.json` (the FX-CFG-001 descriptor, the
single source the operator + UI consume). The emission's ``adapter_version`` provenance string —
what a downstream gateway consumer sees — should carry that same per-connector version, not a
generic constant or a hand-maintained literal that drifts (the `continue/0.1.0`-vs-`continue_dev`
class). This reads the descriptor once per id (cached) and returns ``"<source_id>/<version>"``,
falling back to ``"<source_id>/<VERSION_BASELINE>"`` if the descriptor is missing/unreadable
(fail-soft — provenance must never crash the emission path). Stdlib-only.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_VERSION_BASELINE = "0.1.0"


@lru_cache(maxsize=None)
def adapter_version_for(source_id: str) -> str:
    """``"<source_id>/<descriptor version>"`` — the per-connector emission version (single source)."""
    version = _VERSION_BASELINE
    path = _REPO / "connectors" / source_id / "config.json"
    try:
        descriptor = json.loads(path.read_text(encoding="utf-8"))
        v = descriptor.get("version")
        if isinstance(v, str) and v:
            version = v
    except (OSError, ValueError):  # missing / unreadable / bad JSON -> fall back, never crash emit
        pass
    return f"{source_id}/{version}"
