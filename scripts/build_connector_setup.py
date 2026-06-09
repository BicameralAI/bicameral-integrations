#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate per-connector backend how-to docs (SETUP.md) from each config.json (FX-CFG-001).

Renders a deterministic operator runbook from one descriptor — prerequisites, credentials (where to get
each + the config key + the per-credential ``BICAMERAL_<KEY>`` env var), the backend-config stanza, webhook
setup, the exact ``runtime.cli`` commands, data/permissions, and go-live. **No secret values** (descriptors
hold none — only keys/steps/scopes). Deterministic: fields are accessed by EXPLICIT name (lists preserve
order), so a reordered config.json cannot reorder the doc. Written via ``write_bytes`` (LF on every OS) so
the validator's byte-exact freshness check is cross-OS stable. Stdlib-only.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_CONNECTORS = _REPO / "connectors"


def _credential(c: dict) -> list[str]:
    env = "BICAMERAL_" + c["key"].upper()
    req = "required" if c.get("required") else "optional"
    out = [f"### `{c['key']}` — {c['label']} ({c['type']}, {req})"]
    if c.get("header"):
        out.append(f"- Wire format: `{c['header']}`")
    if c.get("modes"):
        out.append("- Serves run mode(s): " + ", ".join(f"`{m}`" for m in c["modes"]))
    if c.get("scopes"):
        out.append("- OAuth scopes: " + ", ".join(f"`{s}`" for s in c["scopes"]))
    if c.get("refresh_owner"):
        oversight = " (token exchange/refresh needs operator oversight)" if c.get("wiring_oversight") else ""
        out.append(f"- Refresh owner: **{c['refresh_owner']}**{oversight}")
    if c["type"] == "webhook_secret":
        out.append("- **Note:** webhook-*receive* path only — **NOT** consumed by `runtime.cli run` "
                   "(the active fetch uses the API credential).")
    out.append(f"- Supply via config key `{c['key']}` **or** env `{env}` (env wins when set).")
    obtain = c.get("obtain") or {}
    if obtain.get("url"):
        out.append(f"- Where to get it: {obtain['url']}")
    out += [f"  - {step}" for step in obtain.get("steps", [])]
    return out + [""]


def _local_stanza(d: dict) -> str:
    secrets = {c["key"]: f"<{c['label']}>" for c in d.get("credentials", [])}
    runtime = {}
    for rc in d.get("runtime_config", []):
        runtime[rc["key"]] = rc["default"] if "default" in rc else f"<{rc['label']}>"
    block: dict = {"enabled": True, "secrets": secrets}
    if runtime:
        block["runtime"] = runtime
    return json.dumps({"connectors": {d["id"]: block}}, indent=2)


def _runtime_table(d: dict) -> list[str]:
    rows = d.get("runtime_config", [])
    if not rows:
        return []
    out = ["", "Runtime config:", "", "| key | required | default | description |", "|---|---|---|---|"]
    for rc in rows:
        default = rc["default"] if "default" in rc else "—"
        out.append(f"| `{rc['key']}` | {bool(rc.get('required'))} | {default} | {rc['description']} |")
    return out + [""]


def _webhook(d: dict) -> list[str]:
    wh = d.get("webhook")
    if not wh:
        return []
    out = ["## Webhook setup", "", f"- Signature scheme: {wh['signature_scheme']} (header `{wh['header']}`)."]
    if wh.get("events"):
        out.append("- Events: " + ", ".join(f"`{e}`" for e in wh["events"]))
    recv = wh.get("receiver") or {}
    if recv:
        out.append(f"- {recv.get('label', 'Receiver URL')} — **you provision this inbound URL** "
                   f"(provisioned_by: {recv.get('provisioned_by', 'operator')}) and register it at the provider.")
    out += [f"  - {step}" for step in (wh.get("setup") or {}).get("steps", [])]
    return out + [""]


def _run_section(d: dict) -> list[str]:
    cid = d["id"]
    has_doc = any(rc["key"] == "document_id" for rc in d.get("runtime_config", []))
    run = f"python -m runtime.cli run {cid}" + (" --document-id <a Google Doc id>" if has_doc else "")
    return [
        "## Run it (headless — no UI)", "", "```bash",
        "python -m runtime.cli list",
        run + "                 # fetch -> print screened emissions",
        f"python -m runtime.cli run-mods {cid} --mods dependency_risk",
        f"python -m runtime.cli run {cid} --sink gateway   # real POST (go-live; default-gated)",
        "```", "",
        "`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).",
        "",
    ]


def build_setup(d: dict) -> str:
    """Deterministic markdown backend runbook for one connector descriptor."""
    lines = [
        "<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->",
        f"# {d['name']} — backend setup", "", d.get("description", ""), "",
        f"- **id** `{d['id']}` · **category** {d['category']} · **trust tier** {d['trust_tier']}",
        f"- **status** {d['status']} · **available** {d['available']} · **modes** {', '.join(d['modes'])}", "",
        "See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general "
        "backend model (config, secrets, the runner, go-live, troubleshooting).", "",
        "## Credentials", "",
    ]
    for c in d.get("credentials", []):
        lines += _credential(c)
    lines += ["## Backend config", "",
              "Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real "
              "values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):", "",
              "```json", _local_stanza(d), "```"]
    lines += _runtime_table(d)
    lines += _webhook(d)
    lines += _run_section(d)
    lines += ["## Data & permissions", "",
              f"- Emits: {', '.join(d['data']['emits'])}",
              f"- PII posture: {d['data']['pii_posture']}", ""]
    gates = d.get("wire_gates", [])
    lines += ["## Go-live", "", f"Readiness: {d.get('live_readiness', '—')}", ""]
    lines += [f"- Gate: {g}" for g in gates] + ([""] if gates else [])
    lines += ["## References", ""]
    lines += [f"- {r['kind']}: {r['url']}" for r in d.get("references", [])]
    return "\n".join(lines) + "\n"


def main() -> int:
    count = 0
    for path in sorted(_CONNECTORS.glob("*/config.json")):
        descriptor = json.loads(path.read_text(encoding="utf-8"))
        (path.parent / "SETUP.md").write_bytes(build_setup(descriptor).encode("utf-8"))
        count += 1
    print(f"wrote {count} SETUP.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
