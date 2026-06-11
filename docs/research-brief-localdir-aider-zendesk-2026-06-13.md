# Research Brief — local_directory + aider + zendesk flip-ready

**Date**: 2026-06-13
**Analyst**: The Qor-logic Analyst
**Target**: the next three connectors queued for the live/flip-ready hardening lane —
`local_directory`, `aider`, `zendesk` — assessed against the FX-CFG-001 descriptor contract +
the flip-ready PII/security standard set by the linear/google_drive/fathom/claude_code exemplars.
**Method**: verify-before-cite (SG-2026-06-12-A) — every provider/source contract re-verified against
its live/local source before assessment; flip-ready gap analysis against the FX-CFG-001 standard;
PII/identity/security review of each `connector.py` parse surface.

---

## Executive Summary

All three connectors are **Beta, end-to-end harness-proven, and missing only the FX-CFG-001 descriptor
half** (`config.json` + generated `SETUP.md`) — the same gap fathom/claude_code closed. The provider
contracts are **clean — zero drift**: Zendesk's webhook signature and Aider's git-attribution behavior
both re-verified against live docs and match the built code exactly; local_directory has no external API
(local filesystem). The flip work is therefore descriptor authoring + **redaction parity hardening** on
the two connectors that currently emit raw free text, plus one design call to surface (aider author name).

| Connector | Contract drift | Code hardening needed | Descriptor | Net flip effort |
|---|---|---|---|---|
| **local_directory** | none (local FS) | **redact-and-pass** content + stem (F1/F2) | new | medium |
| **aider** | none (verified) | **redact-and-pass** commit subject (F3); document author-name retention (F4) | new | low-medium |
| **zendesk** | none (verified) | none (already redact-and-pass + HMAC verify + dedup) | new | low (descriptor-only) |

## Contract Verification (verify-before-cite, SG-2026-06-12-A)

### zendesk — webhook signature: VERIFIED, no drift
- **Live source**: [developer.zendesk.com/documentation/webhooks/verifying](https://developer.zendesk.com/documentation/webhooks/verifying/) confirms
  `signature = base64(HMAC-SHA256(signing_secret, TIMESTAMP + BODY))`; headers
  `x-zendesk-webhook-signature` + `x-zendesk-webhook-signature-timestamp`; constant-time compare;
  signing secret is per-webhook (a static test secret applies pre-creation).
- **As built**: `adapter/core/webhook_security.py:208-212` — `signed = timestamp.encode() + body`,
  `base64.b64encode(HMAC-SHA256)`, `hmac.compare_digest`, fail-closed on missing secret/signature/timestamp.
  `connectors/zendesk/connector.py:125-136` wires both headers. **MATCH.** No replay window documented
  → dedup (envelope `id` → `detail.id` → body-hash fallback, `connector.py:138-156`) is the only replay guard, correctly.

### aider — git attribution: VERIFIED, no drift
- **Live source**: [aider.chat/docs/git.html](https://aider.chat/docs/git.html) — by default `(aider)` is
  appended to **both** the git author and committer name when aider authored the change; **committer-only**
  when aider merely commits pre-existing dirty files; `--attribute-co-authored-by` is **opt-in** and adds a
  `Co-authored-by:` trailer. Flags: `--no-attribute-author`, `--no-attribute-committer`,
  `--attribute-co-authored-by`, `--attribute-commit-message-{author,committer}`.
- **As built**: `connectors/aider/connector.py:32-45` `_attributed_by` resolves author → committer →
  co-author trailer, in that precedence. **MATCH** the documented default + opt-in surface. references.md accurate.

### local_directory — local filesystem: no external contract to drift
- No provider API/webhook. Parse contract is the `{path, content, modified, source_type_label}` shape
  ported from `bicameral-mcp events/sources/local_directory.py`. The ref is `local-{sha256(path)[:16]}`
  (`connector.py:23-29`) — opaque, so the operator's filesystem layout never enters the ledger. ✓

## Flip-Ready Gap & Findings (file:line)

### local_directory
- **Gap**: no `connectors/local_directory/config.json` / `SETUP.md`.
- **F1 — pii_on_wire (medium)** — `connector.py:39,46` `parse_file` emits the **full file content as the
  excerpt with NO redaction**; references.md:31 admits "full file content emitted as excerpt … FX-SEC-001 is
  the guard." FX-SEC-001 hard-rejects only secret/PHI/PAN — **email/phone/names in a dropped file pass to the
  wire**. The exemplars (fathom/zendesk) redact-and-pass free text. Redaction is non-destructive (scrubs only
  secret/PHI/PAN + email + phone), so it is pure upside here. **Fix**: `excerpt = redact(content) or stem`.
- **F2 — pii_on_wire (low)** — `connector.py:41,47` `title = stem` (the filename) is emitted raw; a filename
  can itself carry PII (`jane.doe-severance.md`). **Fix**: redact the stem (`title = redact(stem)`).
- **Sound**: path sha256-tokenization (no layout leak), `isinstance` poll guard (`connector.py:64`). Keep.

### aider
- **Gap**: no `connectors/aider/config.json` / `SETUP.md`.
- **F3 — pii_on_wire (low-medium)** — `connector.py:57,59,64` the commit **subject is emitted un-redacted**
  into both excerpt and title. Developers paste tokens/emails into commit messages; FX-SEC-001 catches
  secret/PAN but not email/phone. **Fix**: redact-and-pass the subject (`subject = redact(_subject_line(...))`),
  keeping the `hash`/`"aider-commit"` floor un-redacted (an opaque hash must not be mangled by the phone regex —
  the same floor-not-redacted discipline claude_code uses).
- **F4 — identity_minimization (DESIGN CALL — document, do NOT strip)** — `connector.py:65`
  `author=str(record.get("author_name"))` emits the **real committer name** (e.g. `"Jane Dev (aider)"`).
  Unlike fathom/claude_code, which drop human names because the name is incidental, **aider's entire purpose is
  git provenance** — *which human ran the AI tool* is the evidence, at trust tier T0. Stripping it would gut the
  connector. The connector reads only `author_name` (a name), **not** `author_email`, so no contact handle leaks.
  **Action**: retain, and state the retention honestly in `data.pii_posture` as an intentional provenance choice
  (the opposite of the fathom/claude_code name-drop, by design). This is the key operator-facing decision.

### zendesk
- **Gap**: no `connectors/zendesk/config.json` / `SETUP.md` — **the only gap**.
- **Already correct** (no code change): redact-and-pass on subject **and** body (`connector.py:69-71`);
  `author=detail.requester_id` (`connector.py:83`) is an **opaque numeric id — not a name or email** (a
  deliberate identity-minimization choice worth documenting); comment threads + attachments excluded (first
  `description` only); HMAC verify + dedup as verified above. `_nested`/`_text` already type-guard wire drift.

## Recommended Descriptor Shapes (for /qor-auto-dev-1)

- **local_directory** — `modes:["passive"]`, `credentials:[]` (no network secret; host FS permissions),
  optional `runtime_config` for the watched-directory path + extension allow-list + size cap (operator runtime),
  `data.emits:["planning"]`, `pii_posture`: redact-and-pass content + stem (post-F1/F2) with FX-SEC-001 backstop,
  `instructions`: `configure` (set watched dir, ref → auth.md) + `verify`. `status:"live-ready"`, `available:true`.
- **aider** — `modes:["passive"]`, `credentials:[]` (T0 git import), `data.emits:["commit"]`,
  `pii_posture`: subject redact-and-passed (post-F3); **author name RETAINED as intentional provenance** (F4);
  `instructions`: `configure` (point at the git repo/working copy, ref → auth.md) + `verify`.
- **zendesk** — `modes:["webhook","active"]`; `credentials`: `zendesk_webhook` (`webhook_secret`, `modes:["webhook"]`)
  + the deferred active-poll credential (`oauth2`/`api_key`, `modes:["active"]`, `wiring_oversight:true`);
  `webhook` block (`signature_scheme` = base64 HMAC-SHA256 over `timestamp+body`, `header:"X-Zendesk-Webhook-Signature"`,
  setup + operator-provisioned receiver); `data.emits:["ticket"]`, `pii_posture`: redact-and-pass subject+body +
  requester_id-opaque + comments/attachments excluded; `instructions`: `register_webhook` + `paste_secret` + `verify`.

## Recommendations (one /qor-auto-dev-1 cycle per connector, then a /qor-deep-audit purple-team)

1. **local_directory** — add redact-and-pass (F1/F2), author `config.json`, regen `SETUP.md`+`index.json`,
   correct references.md PII line, regression tests (email/phone-in-content scrubbed; PII-in-filename scrubbed).
2. **aider** — add redact-and-pass on the subject (F3), author `config.json` documenting author-name retention (F4),
   regen, regression tests (token-in-commit-subject scrubbed; hash floor un-mangled; author name preserved).
3. **zendesk** — descriptor-only: author `config.json` (webhook+active), regen; no parse change expected.
4. After all three substantiate → **/qor-deep-audit purple-team** (red→blue→verdict) across parse_robustness,
   pii_on_wire, identity_minimization, webhook_replay/signature (zendesk), descriptor_accuracy, em_safe_contract,
   plus **path-traversal/symlink** for local_directory; remediate in governed cycles; tag @jinhongkuan.

## Updated Knowledge (Shadow Genome)

- **SG-2026-06-13-A** — *a local/passive connector that emits raw operator-supplied content needs redact-and-pass
  parity even with no network boundary.* The absence of a wire/provider boundary is not the absence of a PII
  boundary: FX-SEC-001 backstops only secret/PHI/PAN, so email/phone/names in operator-dropped files (or a
  filename) reach the evidence stream unredacted. Apply the same redact-and-pass the network connectors use to any
  free-text excerpt regardless of transport.
- **SG-2026-06-13-B** — *for a provenance connector, the human identity IS the evidence — do not blanket-apply the
  name-drop.* identity-minimization (fathom/claude_code drop real names) is correct when the name is incidental, but
  wrong when the connector exists to attribute work to a person (aider git author). The discipline is per-connector:
  decide whether the name is signal or noise, retain-and-document when signal, drop when noise — never reflexively.

---

_Research complete. Zero contract drift across all three; flip work is descriptor authoring + redaction-parity
hardening on local_directory + aider (zendesk is descriptor-only). Findings are advisory — implementation
decisions remain with the Governor. EM-safe + read-only boundary + ADR-0012 hold._
