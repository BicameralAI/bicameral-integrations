# Research Brief

**Date**: 2026-06-05
**Analyst**: The Qor-logic Analyst
**Target**: (1) a PII **redaction-and-pass** model for the adapter; (2) Devin v3 API + ServiceNow Table API — its first two consumers
**Scope**: How redaction composes with the FX-SEC-001 hard screen; the redact contract; the Devin / ServiceNow read surfaces and their PII shape.

---

## Executive Summary

The repo has long deferred a **PII redaction-and-pass** model (the gate for live Zendesk ticket bodies, Cursor per-developer attribution, and any free-text body). This brief designs it as a shared `adapter/core/redaction.py::redact(text)` primitive and grounds its **first two consumers** — Devin (agentic-session evidence) and ServiceNow (ITSM incidents) — both poll-only REST APIs with a safe metadata surface plus a PII-dense free-text body. The keystone finding: FX-SEC-001 (`_screen_sensitive`) is a **reject** gate over `secret/PHI/PAN`; the redactor must **scrub those same classes to placeholders so redacted text PASSES the hard gate** (redact-and-pass, not reject), **plus** scrub the generic PII FX-SEC-001 never detects (email, phone). No blocking blueprint drift.

## Findings

### Design: redaction-and-pass model (the keystone)
- **Existing screen** (`adapter/core/pipeline.py:53-67`): `_screen_sensitive` runs `detect_sensitive(title + body + excerpts)` and **raises `EmissionContractError` (HARD reject)** on any secret/PHI/PAN hit. It is the backstop and stays unchanged.
- **`detect_sensitive`** (`adapter/core/sensitive.py:111-128`) detects: **secret** (AWS/GitHub-PAT/Azure/PEM/JWT regexes), **phi** (label-adjacent `MRN:`/`patient_*:`/`dob:`/`ssn:`), **pan** (Luhn-valid, non-ID-preceded digit runs). It does **NOT** detect generic email or phone (SG-2026-06-05-A).
- **Redaction contract** — `redact(text) -> str`:
  1. Scrub the FX-SEC-001 catalog classes to placeholders (`[redacted:secret]` / `[redacted:phi]` / `[redacted:pan]`) by reusing the **same** `sensitive.py` patterns + PAN Luhn/label logic — so the redacted text contains none of them.
  2. Scrub generic PII FX-SEC-001 misses: **email** → `[redacted:email]`, **phone** → `[redacted:phone]`.
  - **Keystone invariant (must be tested):** `detect_sensitive(redact(text)) == []` for an adversarial corpus — i.e. redacted output always PASSES `_screen_sensitive`. This is what makes it "pass" instead of "reject".
  - **Policy:** redaction is **opt-in per connector** for free-text bodies; FX-SEC-001 remains the un-bypassable hard backstop for every emission (defense in depth — if the redactor ever misses a secret, the gate still rejects). Reject-vs-redact: structured/safe fields need no redaction; PII-dense free-text is redacted-then-passed.
  - **No reversibility / no key**: placeholders are irreversible (this is evidence text, not a data pipeline). Deterministic, stdlib `re` only.

### Interface: Devin v3 API (P1, catalog B9)
- **Endpoints**: `GET /v3/organizations/{org}/sessions` (list), `GET /v3/enterprise/sessions/{devin_id}/messages` (messages, cursor pagination, chronological). Base `https://api.devin.ai/v3/`. Source: [Devin Docs — API overview](https://docs.devin.ai/api-reference/overview), [list sessions](https://docs.devinenterprise.com/api-reference/v3/sessions/organizations-sessions).
- **Auth**: **Bearer** token — Service-User API key (`cog_…`, shown once; RBAC-scoped) or Personal Access Token ("coming soon").
- **Poll-only** (no webhooks). Read-only evidence = a session's goal/title, status, structured output, linked PRs, and message trail.
- **PII shape**: session **metadata** (id, status, title, linked PRs) is the safe surface; **message bodies are free-text** (may carry secrets/PII) → run through `redact()`.

### Interface: ServiceNow Table API (P2)
- **Endpoint**: `GET /api/now/table/incident?sysparm_fields=…&sysparm_limit=…&sysparm_offset=…`. Per-tenant instance URL. Source: [ServiceNow Table API](https://www.servicenow.com/docs/bundle/zurich-api-reference/page/integrate/inbound-rest/concept/c_TableAPI.html).
- **Auth**: Basic or OAuth; a dedicated integration user with `rest_service` + table-read roles.
- **Poll-only**. Read-only evidence = incident records.
- **PII shape**: safe surface = `number`, `short_description`, `state`, `priority`, `category`; PII-dense = `description` / `comments` / `caller_id` free-text → `short_description` is the primary excerpt; `description` run through `redact()` when included; `caller_id` (identity) dropped.

## Blueprint Alignment

| Blueprint claim | Actual finding | Status |
|---|---|---|
| Repeated deferral: "PII redaction-and-pass model" gates live Zendesk/CS + per-user surfaces | Designed here as `adapter/core/redaction.py`; composes with (does not replace) FX-SEC-001 | MATCH (closes the deferral) |
| Catalog: Devin P1, read-only v3 sessions API, poll, no webhooks; Desktop has no file artifact | Confirmed — Bearer `cog_` key, `/v3/.../sessions` + `/messages`, cursor poll | MATCH |
| Catalog: ServiceNow P2, ITSM Table API, poll-only, per-tenant | Confirmed — `GET /api/now/table/incident`, basic/OAuth, sysparm paging | MATCH |
| FX-SEC-001 is the data-leak standard (HARD reject, secret/PHI/PAN) | Unchanged; redactor scrubs the same classes so redacted text passes it | MATCH |

## Recommendations

1. **(HIGH) Build `adapter/core/redaction.py::redact(text)`** reusing `sensitive.py` patterns for the catalog classes + email/phone, with the tested invariant `detect_sensitive(redact(x)) == []`. Keep FX-SEC-001 as the un-bypassable backstop.
2. **(MED) Devin connector**: parse session metadata (status/title/linked PRs) as the excerpt; run any message-body text through `redact()`. `userId`/author identity handled conservatively.
3. **(MED) ServiceNow connector**: excerpt = `short_description` (+ `redact(description)` when present); drop `caller_id` identity. `number`→ref.
4. **(LOW) Follow-up**: retrofit Zendesk (ticket body) + Cursor (per-developer) to use `redact()` — separate cycle, out of scope here.

## Updated Knowledge

To `docs/SHADOW_GENOME.md`: the **redact-and-pass** model is the complement to FX-SEC-001's reject — `redact()` scrubs the catalog classes (so output passes `_screen_sensitive`) plus generic email/phone; the invariant `detect_sensitive(redact(x)) == []` is the safety contract; FX-SEC-001 stays the hard backstop (redaction never disables it).

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
