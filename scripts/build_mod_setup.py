#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate per-mod how-to docs (SETUP.md) from each mod config.json.

The EM-safe-mod parity of ``build_connector_setup.py``. A mod has NO credentials and NO live
network — so its runbook is "what it reads, what it advises, what it can NEVER do, how to enable
it, optional knobs." Deterministic: fields are accessed by EXPLICIT name (lists preserve order).
Written via ``write_bytes`` (LF on every OS) so the validator's byte-exact freshness check is
cross-OS stable. Stdlib-only.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_MODS = _REPO / "mods"


def _config_table(en: dict) -> list[str]:
    rows = en.get("config", [])
    if not rows:
        return ["_No operator knobs — enable/disable only._", ""]
    out = ["", "| key | required | default | description |", "|---|---|---|---|"]
    for rc in rows:
        default = rc["default"] if "default" in rc else "—"
        out.append(f"| `{rc['key']}` | {bool(rc.get('required'))} | {default} | {rc['description']} |")
    return out + [""]


def build_setup(d: dict) -> str:
    """Deterministic markdown runbook for one mod descriptor."""
    en = d.get("enablement", {})
    lines = [
        "<!-- GENERATED from config.json — do not edit; run scripts/build_mod_setup.py -->",
        f"# {d['name']} — mod setup", "", d.get("description", ""), "",
        f"- **id** `{d['id']}` · **manifest** `{d['manifest_id']}` · **family** {d['family']} · **version** {d['version']}",
        f"- **advisory only** (non-authoritative; ADR-0008) · **default enabled** {en.get('default_enabled')} "
        f"· **trust-gated** {en.get('trust_gated')}", "",
        "See [mods/README.md](README.md) for the general mod model + the mod safety contract.", "",
        "## Advises on", "", d.get("advises_on", ""), "",
        "## Reads (evidence consumed)", "",
    ]
    lines += [f"- {c}" for c in d.get("consumes", [])]
    lines += ["", "## Emits (advisory artifacts only)", ""]
    lines += [f"- `{e}`" for e in d.get("emits", [])]
    lines += ["", "## Can NEVER do (EM-safe boundary)", "",
              "This mod is non-authoritative by construction — it may surface a concern, never act on it:"]
    lines += [f"- `{a}`" for a in d.get("em_safe", {}).get("forbidden_actions", [])]
    lines += ["", "## Enable it (headless — no UI)", "", "```bash",
              f"python -m runtime.cli run-mods <connector> --mods {d['id']}",
              "```", "", "Operator knobs:"]
    lines += _config_table(en)
    lines += ["## Requirements", ""]
    lines += [f"- {r}" for r in d.get("requirements", [])]
    lines += ["", "## References", ""]
    lines += [f"- {r['kind']}: {r['url']}" for r in d.get("references", [])]
    return "\n".join(lines) + "\n"


def main() -> int:
    count = 0
    for path in sorted(_MODS.glob("*/config.json")):
        descriptor = json.loads(path.read_text(encoding="utf-8"))
        (path.parent / "SETUP.md").write_bytes(build_setup(descriptor).encode("utf-8"))
        count += 1
    print(f"wrote {count} mod SETUP.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
