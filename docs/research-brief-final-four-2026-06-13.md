# Research Brief — anthropic_admin + openai_admin + continue_dev + confluence flip-ready (the remainder)

**Date**: 2026-06-13
**Analyst**: The Qor-logic Analyst
**Target**: the final four Future-Development connectors — `anthropic_admin`, `openai_admin`, `continue_dev`,
`confluence` — the remainder that takes the catalog to **26 / 26 flip-ready**.
**Method**: verify-before-cite (SG-2026-06-12-A) — each provider contract re-verified live; flip-ready gap +
PII review per connector; explicit doc-standard assessment.

---

## Executive Summary

**Zero contract drift.** Two are **PII-free / identity-dropped by construction** (descriptor-only); two emit raw
provider free text and need the established redact-and-pass parity. One descriptor-honesty nuance: **Confluence
Cloud has no signable webhook**, so its flip-ready descriptor offers the verifiable poll, not an unverifiable
webhook.

| Connector | Contract drift | Code hardening | Descriptor | Effort |
|---|---|---|---|---|
| **anthropic_admin** | none (usage API re-verified live) | none — PII-free aggregate by construction | new | low (descriptor-only) |
| **openai_admin** | none (audit_logs re-verified live) | none — actor identity already dropped + redacted | new | low (descriptor-only) |
| **continue_dev** | none (shape re-confirmed; field detail pinned) | redact-and-pass excerpt (F1) + redact author/userId (F2) | new | medium |
| **confluence** | none (Cloud has no signature) | redact-and-pass body+title (F1); active+passive poll only (F2) | new | medium |

## Contract Verification (verify-before-cite, SG-2026-06-12-A)

### anthropic_admin — Usage & Cost Admin API: VERIFIED live, no drift
- **Live source**: [docs.anthropic.com/en/api/usage-cost-api](https://docs.anthropic.com/en/api/usage-cost-api).
  `GET /v1/organizations/usage_report/messages`, **`x-api-key` Admin key (`sk-ant-admin…`)**; response carries
  `uncached_input_tokens`, **`cache_creation` (nested ephemeral cache types)**, `cache_read_input_tokens`,
  `output_tokens`, by model/workspace/service_tier. **MATCHES** `parse_usage` exactly, including the nested
  `cache_creation.ephemeral_*` summation (the connector's specific claim — confirmed). New detail for the
  descriptor `validation`: the admin-key prefix is `sk-ant-admin`.

### openai_admin — audit_logs API: VERIFIED live, no drift
- **Live source**: [platform.openai.com/docs/api-reference/audit-logs](https://platform.openai.com/docs/api-reference/audit-logs/list).
  `GET https://api.openai.com/v1/organization/audit_logs`, **`Authorization: Bearer` Admin key**; events carry
  `{id, type, effective_at, project, actor, …}`. **MATCHES** `parse_audit_log`; the connector reads only the
  non-PII `type`/`project`/`actor.type`/`effective_at` and NEVER the actor email/id/ip.

### confluence — Cloud webhook signature: VERIFIED ABSENT (the descriptor-honesty crux)
- **Live source**: Atlassian docs — the `X-Hub-Signature` HMAC-SHA256 webhook scheme is documented **only for
  Confluence Data Center / Server** (confirmed across DC 7.18–10.2); there is **no Confluence Cloud payload
  signature**. The connector's deferral of webhook verification for Cloud is **honest**. The Cloud REST content
  shape `{id, type, title, body.storage.value, _links.{base, webui}}` matches `parse_content`. No drift.

### continue_dev — dev-data schema: re-confirmed shape; field detail pinned (provenance recorded)
- **Live source**: [docs.continue.dev development-data](https://docs.continue.dev/customize/deep-dives/development-data)
  confirms the **schema-versioned event JSON blob** (sent to an HTTP sink / written as local JSONL) but **defers
  the field-level schema to the Continue source** (SG-2026-06-13-D pattern — the doc renders the high-level shape,
  not the field list). The `eventName` base field + `prompt`/`completion`/`level:noCode` were pinned against
  docs/source 2026-06-08; the connector handles the documented schema churn defensively (`eventName`/`name`
  fallback, `schema` version, non-string-field tolerance). No drift on the confirmed surface; field detail is a
  recorded provenance limitation, not a fresh re-verify.

## Flip-Ready Gap & Findings (file:line)

### anthropic_admin — clean (descriptor-only)
- **Gap**: no `config.json`/`SETUP.md`. `parse_usage` synthesizes a **PII-free aggregate** excerpt from numeric
  token totals + distinct model names; the opaque `workspace_id`/`api_key_id` are **not surfaced**; no `author`;
  no provider free text. **No redaction needed** (the copilot/cursor "PII-free by construction" class). Just the
  descriptor.

### openai_admin — clean (descriptor-only)
- **Gap**: no `config.json`/`SETUP.md`. `parse_audit_log` **drops actor identity** (email/id/ip NEVER read; only
  the allowlisted non-PII `actor.type`) and passes the synthesized excerpt through `redact()` defensively. Just
  the descriptor.

### continue_dev
- **Gap**: no `config.json`/`SETUP.md`.
- **F1 — pii_on_wire (medium)** — `connector.py:29-34,51` the excerpt is the first of `prompt`/`completion`/
  `content`/`message` emitted **raw**. These are developer-AI interaction texts (a prompt can carry code with
  secrets/emails). Fix: redact-and-pass the excerpt (`redact()`, the claude_code/aider standard); keep the
  `continue {name}` floor.
- **F2 — pii_on_wire (low)** — `connector.py:54` `author = userId` emitted raw; redact it defensively (an opaque
  id passes `redact()` unchanged, an email-shaped userId is scrubbed — the zendesk requester_id treatment).

### confluence
- **Gap**: no `config.json`/`SETUP.md`.
- **F1 — pii_on_wire (medium)** — `connector.py:56-57,65` the excerpt is the flattened storage body + title,
  emitted **raw**. Confluence pages are PII-dense (internal docs, names, emails). Fix: redact-and-pass the
  flattened body + title (the jira/github standard). No `author` surfaced (good).
- **F2 — descriptor_accuracy (the honesty nuance)** — the connector's `capabilities` include WEBHOOK (for Data
  Center), but **Confluence Cloud cannot sign its webhooks**, and the connector ships no `verify()`. The
  flip-ready descriptor must declare **`modes:["active","passive"]`** (the authenticated REST poll — Connect-JWT /
  email+API-token), **NOT webhook**, and record in `wire_gates` that the Cloud webhook is unverifiable (the
  capability remains for a future Data-Center signature path). Capabilities ⊇ descriptor-modes; the gap is the
  unverifiable mode, disclosed (SG-2026-06-14-B).

## Recommended Descriptor Shapes (for /qor-auto-dev-1)

- **anthropic_admin** — `modes:["active"]`; credential `anthropic_admin` (`api_key`, header `x-api-key` +
  `anthropic-version`, `validation: ^sk-ant-admin`); `runtime_config` date range + host pin; `data.emits:
  ["usage_metrics"]`, pii_posture PII-free aggregate; `open_url`+`paste_secret`+`verify`.
- **openai_admin** — `modes:["active"]`; credential `openai_admin` (`api_key`, `Authorization: Bearer` admin
  key); `data.emits:["audit_event"]`, pii_posture identity-dropped + redacted; `open_url`+`paste_secret`+`verify`.
- **continue_dev** — `modes:["passive"]`, `credentials:[]` (local JSONL file import); `runtime_config` dev-data
  path + the `level:noCode` lever note; `data.emits:["development_data"]`, pii_posture redact-and-pass excerpt +
  redact userId; `configure`+`verify`.
- **confluence** — `modes:["active","passive"]` (NO webhook); credential `confluence` (`api_key` / Basic
  email+API-token, or Connect JWT — per auth.md); `runtime_config` base URL/space filter + host pin
  (`*.atlassian.net`); `data.emits:["page"]`, pii_posture redact-and-pass body+title; `open_url`+`paste_secret`+
  `configure`+`verify`.

## Recommendations (one /qor-auto-dev-1 cycle per connector, then a /qor-deep-audit purple-team)

1. **anthropic_admin / openai_admin** — descriptor-only (PII-free / identity-dropped); author config.json, regen,
   explicit doc-standard attestation, a regression test re-asserting the PII-free / identity-dropped posture.
2. **continue_dev** — redact-and-pass excerpt (F1) + redact userId (F2), author config.json, regen, attestation,
   regression tests (secret/email in a prompt scrubbed; opaque userId passes, email-shaped scrubbed).
3. **confluence** — redact-and-pass body+title (F1), author config.json with `modes:["active","passive"]` (F2 —
   no unverifiable webhook), regen, attestation, regression tests (email/secret in a page body scrubbed).
4. After all four substantiate → **/qor-deep-audit purple-team** (red→blue→verdict; verify impact vs the real
   gateway serializer, SG-2026-06-13-C), then remediate; tag @jinhongkuan. **This completes 26 / 26 flip-ready.**

## Updated Knowledge (Shadow Genome)

- **SG-2026-06-14-B** — *a connector whose capabilities include an UNVERIFIABLE mode must declare in its FX-CFG-001
  descriptor only the verifiable subset.* Confluence's `capabilities` include WEBHOOK (Data-Center HMAC), but
  Confluence **Cloud** publishes no payload signature, and the connector ships no `verify()`. Offering that
  webhook as flip-ready would invite an operator to wire an unauthenticated inbound path. The descriptor declares
  `["active","passive"]` (the authenticated poll) and records the unverifiable webhook as a disclosed gap;
  capabilities ⊇ descriptor-modes by design. Pairs with SG-2026-06-13-D (record what you could not verify).

---

_Research complete. Zero contract drift across all four; two descriptor-only (PII-free / identity-dropped), two
need redact-and-pass parity, and confluence offers only its verifiable poll. Completing these four reaches
26 / 26 flip-ready. Findings advisory — decisions remain with the Governor. EM-safe + read-only + ADR-0012 hold._
