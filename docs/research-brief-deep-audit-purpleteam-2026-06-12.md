# Research Brief — deep-audit full purple-team pass (9 un-red-teamed connectors + 4 mods)

**Date**: 2026-06-12
**Analyst**: The Qor-logic Analyst (deep-audit recon; multi-agent purple-team workflow `w53y58tat`)
**Target**: the 9 flip-ready connectors NOT covered by the 2026-06-11 purple-team (#94–#102) — cursor, copilot, servicenow, granola, mcp_registry, github, jira, slack, notion — plus the 4 advisory mods and their NEW surfaces.
**Method**: 44 agents — 8 red attack classes (SSRF/credential-egress, parse-robustness, replay/dedup, PII-on-wire, descriptor over-claim, host-injection, mod-chokepoint, contract-vs-fixture) fanned over each target, **each finding adversarially blue-verified against source** before a per-target verdict. 26 findings raised, **24 confirmed real** (2 refuted: GitHub `CONFIG-DESCRIPTOR-007`, slack `WEBHOOK-VERIFY-003`).

---

## Executive Summary

The connector/mod **cores are sound** — no forged-ingest, no broken HMAC, no fail-open. But the audit found **three BLOCKED targets** on real defects this repo's own doctrine warns about:

1. **copilot** + **granola** (HIGH) — their `build_*_spec` are the only credentialed operator-`base_url` builders that **omit `_require_https_endpoint`**. A tampered/fat-fingered `base_url` sends the `read:org` GitHub PAT / `grn_` Bearer (PII-dense transcripts) to **any host — incl. `http://` cleartext and `169.254.169.254` cloud-metadata** — on the first request, upstream of every no-follow / 200-only / redaction defense. Same root, one-line fix each.
2. **notion** (HIGH) — `parse_page` is fed the **raw webhook envelope**, so `source_ref.ref` captures the ephemeral **event UUID** instead of the page `entity.id`; every live delivery yields a degenerate Observation (title = event UUID, no url/author/timestamp). **Masked by a fabricated full-page fixture** (`webhook_page.json`) — the repo's own "fixture-proven ≠ contract-correct" failure class (SG drift). Plus a **future-dated** `wire_gate` ("verified live 2026-06-12" while today is 2026-06-11).

The other six targets are **approved-with-fixes** (no critical/high): a recurring **non-string-scalar `.strip()`/`redact()` crash** (medium, 6 connectors — a single hostile/malformed provider row aborts the whole batch), plus shared lows.

**None block the current flip-ready (NOT-Live) state** — all blockers are "before the Live flip." Remediation is sequenced below by severity.

## Per-target verdicts

| Target | Verdict | Confirmed gaps (severity) |
|---|---|---|
| **copilot** | 🔴 BLOCKED | `base_url` no host-pin → PAT SSRF/cleartext/metadata (**HIGH×2**, one root); non-string `date` crash (med); shared lows |
| **granola** | 🔴 BLOCKED | `base_url` no host-pin → `grn_` Bearer + transcript SSRF (**HIGH**); descriptor over-claims a guard it lacks (med); shared lows |
| **notion** | 🔴 BLOCKED | `ref` = event UUID not `entity.id` (**HIGH**); webhook parses a full-page shape Notion never sends (med); id-less replay (med); non-string id crash (med); future-dated wire_gate (med); shared lows |
| **cursor** | 🟡 approved-with-fixes | non-string `day` crash (med); shared lows |
| **servicenow** | 🟡 approved-with-fixes | `instance` injection-validated but not private/metadata-IP denylisted (low); shared lows |
| **mcp_registry** | 🟡 approved-with-fixes | non-string `name/desc` crash (med); descriptor claims "PII-free" but emits attacker free-text with **no `redact()`** (med); shared lows |
| **github** | 🟡 approved-with-fixes | empty/absent `X-GitHub-Delivery` bypasses dedup, no body-hash fallback (med); non-string title/body crash (med); shared lows |
| **jira** | 🟡 approved-with-fixes | 3 shared lows only (HMAC path sound) |
| **slack** | 🟡 approved-with-fixes | non-string `text` crash (med); author not opaque-id-validated (info); shared lows |
| **mods** | 🟡 approved-with-fixes | output screen joins wire fields into one blob vs per-leaf input screen (info, latent PII-1 regression); author preserved to chokepoint (low); shared lows |

## Cross-cutting roots (one fix closes many)

1. **Host-pin gap** — `runtime/poll_specs.py`. `build_copilot_spec` (:132) + `build_granola_spec` (:166) call **no** `_require_https_endpoint`; `build_devin_spec` (:118) passes `allow=None`; `build_anthropic_admin_spec`/`build_openai_admin_spec` also unpinned; `_require_bare_host` (servicenow, :44) admits `169.254.169.254` / `metadata.google.internal`. → **Cycle 1**.
2. **Non-string-scalar crash** — `(x.get(k) or "").strip()` / `redact(non-str)` raise `AttributeError`/`TypeError` and the **un-guarded `deliver_poll` loop** (`runtime/delivery.py:73-80`) propagates it, aborting the whole batch. Affects cursor/copilot/mcp_registry/github/slack/notion. One `try/except` backstop in `deliver_poll` protects all 26; per-connector str-guards harden the leaves. → **Cycle 2**.
3. **notion webhook contract** — envelope-vs-full-page parse mismatch (`ref`/title), id-less replay, non-string id crash, future-dated gate. → **Cycle 3**.
4. **mcp_registry descriptor falsity + github replay** (mediums). → **Cycle 4**.
5. **Shared lows** — NANP-only `_PHONE_RE` (`adapter/core/redaction.py:25`) leaks international phone past redact() and the catalog screen; presence-only `instructions[].ref` validator (`scripts/validate_connector_config.py:113`) accepts refs to non-existent `auth.md (Verification)` sections; mod output screen joins-not-per-leaf (`mods/contract.py:227`); linear/fathom keep real-name `author`. → **Cycle 5**.

## Blueprint alignment

| Claim | Finding | Status |
|---|---|---|
| All credentialed poll builders pin/validate the endpoint host | copilot/granola/anthropic_admin/openai_admin do NOT; devin half-pins (scheme only) | **DRIFT** → Cycle 1 |
| Connectors fail-closed (skip) a malformed untrusted row, not crash the batch | non-string scalar in 6 connectors aborts the whole `deliver_poll` batch | **DRIFT** → Cycle 2 |
| notion webhook emits a page-identified Observation | emits the event-UUID-identified, content-empty Observation; full-page fixture masks it | **DRIFT (HIGH)** → Cycle 3 |
| mcp_registry is "PII-free by construction" | emits attacker-publishable registry free-text with no redact(); screen catches only secret/PHI/PAN | **DRIFT** → Cycle 4 |
| `redact()` scrubs "phone" | scrubs only NANP 3-3-4; international phone passes | **DRIFT (low)** → Cycle 5 |

## Recommendations (sequenced governed fix cycles; each modular-commit → PR → merge-if-green → tag @jinhongkuan)

1. **Cycle 1 (HIGH):** host-pin every credentialed `build_*_spec` + private/metadata-IP denylist + red-team gates. Closes copilot + granola BLOCKERs and devin/servicenow/anthropic/openai lows. **Confidence: high** (one-line fix each, exact host per each connector's verified contract).
2. **Cycle 2 (medium):** `deliver_poll` log-and-skip backstop + per-connector str-guards + regressions.
3. **Cycle 3 (HIGH, notion-specific):** `parse_event(entity.id)`, real-envelope fixture, body-hash dedup, corrected wire_gate date, descriptor correction.
4. **Cycle 4 (medium):** mcp_registry redact-and-pass + descriptor truth; github body-hash dedup fallback.
5. **Cycle 5 (low):** broaden `_PHONE_RE`; resolution-checked `ref` validator + add `## Verification` headings; mod per-leaf output screen; drop linear/fathom author.

## Updated Knowledge (Shadow Genome)

- **SG-2026-06-12-B** — *the host-pin must be applied at EVERY credentialed `build_*_spec`, not connector-by-connector.* The 2026-06-11 purple-team pinned cursor + linear; the same author left copilot/granola/anthropic/openai/devin unpinned. A per-connector fix invites exactly this asymmetry. Lesson: when a defense is added to a shared surface, sweep ALL siblings in the same pass and add a structural gate ("every credentialed `build_*_spec` invokes `_require_https_endpoint`").
- **SG-2026-06-12-C** — *fixture-proven ≠ contract-correct, re-confirmed (notion).* A hand-authored full-page fixture made `test_notion_webhook` green while the live webhook contract (a thin `{id, type, entity:{id}}` envelope) was never exercised. Replace synthetic fixtures with the real provider envelope before claiming a webhook path verified. (Pairs with SG-2026-06-12-A: verify-before-cite per connector per cycle.)

---

_Recon complete. 24 confirmed real gaps; 3 BLOCKED targets; remediation begins with the Cycle 1 host-pin HIGH blockers. Findings are advisory — remediation decisions remain with the Governor; the Review Boundary holds (no Live flip without operator secrets + live network, ADR-0012)._
