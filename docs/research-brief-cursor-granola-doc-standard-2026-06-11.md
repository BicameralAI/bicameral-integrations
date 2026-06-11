# Research Brief — Cursor & Granola live-contract verification + documentation standard

**Date**: 2026-06-11
**Analyst**: The Qor-logic Analyst
**Target**: `connectors/cursor` + `connectors/granola` — verify the live API contracts (verify-before-cite) and establish the complete, accurate documentation standard before any go-live descriptor work.
**Sources (live, 2026-06-11)**: `cursor.com/docs/account/teams/admin-api`, `public-api.granola.ai` docs (via `docs.granola.ai`). Internal: `connectors/{cursor,granola}/{connector.py,auth.md,references.md}`, `runtime/poll_specs.py`.

---

## Executive Summary

**Cursor: contract VERIFIED live — clears its verification debt; descriptor-ready (L1).** The host, method, auth, body (incl. units + the 30-day cap), `data` envelope, and row fields all confirm; pagination is now resolved as **POST-body** `page`/`pageSize` with a response `pagination.hasNextPage`. The `poll_specs.py` "inferred/unverified" comments are STALE and should be reconciled. PII control (parse-time allowlist + opaque `userId` + `redact()` on free-text) is correct.

**Granola: DRIFT + a real PII gap — NOT descriptor-ready as-is (L2).** The live note identity field is **`owner` {name, email}**, but the connector reads a non-existent **`attendees`** field (would emit an empty/wrong author live). And the connector emits the **verbatim transcript with no `redact()`** plus a person's **name as `author`**, while FX-SEC-001 screens only secret/PHI/PAN — so generic names/emails in meeting speech reach the wire un-scrubbed. Granola needs **connector corrections** (re-point identity to `owner`; apply redact-and-pass to the transcript; stop emitting raw owner identity) before the descriptor, not just a config.json.

## Findings

### Cursor — VERIFIED (live 2026-06-11)

| Element | Live doc | Connector/auth.md | Status |
|---|---|---|---|
| Endpoint | `POST https://api.cursor.com/teams/daily-usage-data` | same (`auth.md:40`) | **MATCH** (host was "inferred" in `poll_specs.py:179` — now VERIFIED) |
| Auth | HTTP Basic, API key as username, empty password | same (`auth.md:9-11`) | **MATCH** |
| Body | `startDate`/`endDate` epoch **ms**, range ≤ **30 days**; `page`/`pageSize` optional | `{startDate,endDate}` epoch ms ≤30d (`auth.md:42`) | **MATCH** (+ page/pageSize now confirmed) |
| Envelope | top-level **`data`** array | `items=lambda page: page.get("data", [])` (`poll_specs.py:199`) | **MATCH** (comment "unverified envelope" is STALE) |
| Row fields | `userId, day, date, email, isActive`, usage + billing metrics, `mostUsedModel`, `clientVersion`; **no `name`** | allowlist reads metrics + `mostUsedModel` + opaque `userId`; never `email`/`name`/`clientVersion` | **MATCH** (PII control correct; `name` absence confirmed) |
| Pagination | response **`pagination.hasNextPage`** (+page/pageSize/totalPages); `page`/`pageSize` ride in the **POST body** | DEFERRED, "query-vs-body unclear, not wired" (`auth.md:45-50`) | **RESOLVED → body-based** (the open question is answered) |

Cursor residual: the pager is **not wired** (single request). For teams > 1 page this truncates. Now that the transport is verified (body-based `page`/`pageSize`, response `pagination.hasNextPage`), the build cycle can either wire a **body-page pager** or document `pageSize`-widening as the operator step. Not a go-live blocker; document it as a `wire_gate`.

### Granola — DRIFT (live 2026-06-11)

| Element | Live doc | Connector | Status |
|---|---|---|---|
| Host/endpoint | `GET https://public-api.granola.ai/v1/notes` (+ `/{id}`), `?include=transcript` | same | **MATCH** |
| Auth | `Authorization: Bearer grn_…` | Bearer (`auth.md:9-10`) | **MATCH** (+ `grn_` prefix is new detail for the descriptor's `validation` regex) |
| Envelope | top-level **`notes`** array | `items=…page.get("notes")` (`poll_specs.py:146`) | **MATCH** |
| Pagination | cursor **`cursor`** + **`hasMore`**, cursor via query param | `PageToken(next_param="cursor", token_field="cursor", has_more_field="hasMore")` | **MATCH** |
| Watermark | `created_after` (ISO 8601) query param | same (`auth.md:10`) | **MATCH** |
| **Identity field** | note carries **`owner` {name, email}** (and `title`, `summary`, `transcript`) — **no `attendees`** in the documented note shape | `parse_transcript` reads **`item.get("attendees")`** → `author=attendees[0].name` (`connector.py:18-26,57`) | **DRIFT (HIGH)** — author would be empty/wrong against the live API; identity is `owner` |
| Transcript item | `{speaker:{source,diarization_label}, text}` — speaker is an **object**, anonymized to source/label | `_join_transcript` reads `utt["text"]` only; comment says `{speaker, text}` (scalar) | MATCH on behavior (text-only); comment slightly off |
| PII guidance | **none** in the docs | — | connector must own PII |

## Blueprint / scope alignment

| Scope claim (scope-golive-batch-verified4) | Live finding | Status |
|---|---|---|
| cursor "VERIFICATION DEBT — host inferred, body+envelope unverified" | All verified live; `poll_specs.py` comments are stale, `auth.md` was correct | **RESOLVED** — cursor is descriptor-ready (L1) |
| cursor pagination "deferred, query-vs-body unclear" | Confirmed **body-based** (`page`/`pageSize`; response `pagination.hasNextPage`) | RESOLVED — wire or document |
| granola "L1, confirm redaction posture" | granola is **L2**: identity-field DRIFT (`owner` not `attendees`) + transcript emitted with **no redact-and-pass** + owner name as `author` | **DRIFT** — needs connector fix, not just a descriptor |

## Recommendations (updates the go-live batch scope)

1. **Cursor → proceed to descriptor (L1).** Credential `cursor` (api_key, Basic username); runtime `base_url` (pin host `api.cursor.com`), `body` (date range, epoch-ms, ≤30d). Reconcile the stale `poll_specs.py:179-199` comments to "verified 2026-06-11" and either wire a body-page pager or record `pageSize`-widening as a `wire_gate`. PII posture: parse-time allowlist + opaque `userId` (accurate). **Confidence: high.**
2. **Granola → connector correction FIRST, then descriptor (L2).** In the build cycle's implement: (a) re-point identity to **`owner.name`** (verify whether `attendees` ever appears; default to `owner`); (b) apply **`redact()` (redact-and-pass)** to the transcript excerpt so spoken emails/phones are scrubbed (FX-SEC-001 won't catch them); (c) do **not** emit raw `owner.name`/`email` as `author` — either drop identity (PII-safe, like the active Linear path) or redact it. Then author the descriptor with an accurate `data.pii_posture` (verbatim transcript; redact-and-pass; no raw attendee identity). **This is a parse/PII change → audit at L2.** **Confidence: high.**
3. **Do NOT ship granola on the original "verified-4 L1 batch" assumption.** Sequence: cursor + servicenow + copilot proceed as L1 descriptors; granola gets its connector-correction sub-cycle (L2) then its descriptor. **Confidence: high.**
4. Bump both `references.md`/`auth.md` to "verified 2026-06-11" with the corrected facts (done in this research per the doc-standard ask).

## Updated Knowledge (Shadow Genome)

- **SG-2026-06-11-D** — Granola note identity is `owner {name,email}`, not `attendees`; and transcript is emitted verbatim with no redact-and-pass while a person's name rides as `author`. A meeting-content connector is PII-dense and FX-SEC-001 (secret/PHI/PAN only) is NOT a sufficient backstop — apply `redact()` and don't emit raw attendee identity. Reinforces SG-2026-06-05-D (cursor allowlist) + SG-2026-06-11-A (verify the live host/version, not the recorded claim).

---

_Research complete. Findings advisory — implementation decisions remain with the Governor. Verify-before-cite caught one connector (cursor) ready and one (granola) carrying drift + a PII gap that would otherwise have shipped in a descriptor._
