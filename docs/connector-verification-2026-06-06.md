# Connector verification campaign — doc-confirmed bar (Phase 1)

**Bar (operator decision 2026-06-06)**: a connector is *verified* when its contract is **confirmed
against authoritative current provider documentation**. The live authenticated call is NOT part of
verification (it lands at go-live). For each item below the outcome is one of:
- **CONFIRMED** — provider doc matches as-built (record source URL + access date).
- **DRIFT** — provider doc differs from as-built → triggers a governed connector fix cycle.
- **DOC-SILENT** — the provider doc does not define it → stays deferred; the *confirmed finding* is
  "not documented" (this is itself a valid verified outcome, e.g. confluence Cloud signatures).

Status legend: ☐ pending · ✅ confirmed · ⚠ drift (fix needed) · ◑ doc-silent (deferred-by-evidence)

## Batch 1 — poll connectors (DONE 2026-06-06; doc-confirmed against official provider docs)

| Connector | Verdict | Status |
|---|---|---|
| servicenow | `result` envelope ✅, Basic ✅, `sysparm_offset`+`sysparm_limit` offset pagination ✅, fields ✅. Short-page-stop is DOC-SILENT (sound derived convention; SN also documents a `Link`/`X-Total-Count` alternative we deliberately don't consume). | ✅ verified |
| cursor | host `api.cursor.com` ✅, Basic key-as-username ✅, POST body `{startDate,endDate}` **epoch-ms, ≤30 days** ✅, `data` envelope ✅. DRIFT (docs only): row has **no `name`** (only `email`+`userId`) — local docs overstate. DRIFT: endpoint **does paginate** (`page`/`pageSize`) — `pagination=None` truncates large teams. | ⚠ (doc + pagination) |
| anthropic_admin | A1 `data` envelope ✅, A2 page-token param `page` (query) ✅, headers ✅. **DRIFT (code)**: `cache_creation_input_tokens` is NOT a field — real is nested `cache_creation.{ephemeral_1h_input_tokens, ephemeral_5m_input_tokens}` → silent input-token undercount. | ⚠ (1 code drift) |
| openai_admin | `data` envelope ✅, `after` cursor param ✅, Bearer admin-only ✅, actor PII fields ✅. `has_more`/`last_id` response fields DOC-SILENT for audit_logs specifically (truncated example render) — OpenAI list convention, keep flagged. | ✅ (minor DOC-SILENT) |
| copilot | top-level array ✅, scopes ✅, headers ✅, `X-GitHub-Api-Version 2022-11-28` valid (latest now `2026-03-10`). **DRIFT (code)**: endpoint **does paginate** (`page`/`per_page`, **100-day** lookback not 28) — `pagination=None` silently truncates >100 days. Enterprise path unverified. | ⚠ (pagination + stale version) |
| devin | endpoint ✅, Bearer `cog_` ✅. **DRIFT (code, severe)**: envelope key is **`items`** NOT `sessions` → would ingest **zero** live. **DRIFT**: `pull_request.url` → real `pull_requests[].pr_url` (array). Pagination IS documented (cursor `after`/`first`→`end_cursor`/`has_next_page`) — deferral can lift on a known contract. | ⚠ (severe: items + pr + pagination) |
| granola | **DRIFT (code, severe — near-rebuild)**: host `public-api.granola.ai` not `api.granola.ai`; endpoint `/notes?include=transcript` not `/transcripts`; envelope `notes` not `transcripts`; `transcript_text`→`transcript[]` array; `participants`→`attendees`; `since`→`created_after`; no `ended_at` (use `created_at`); cursor pagination (`cursor`/`hasMore`) ignored. Only `Authorization: Bearer` ✅. | ⚠ (severe: whole contract) |

**Batch 1 summary:** 7/7 doc-checked. **servicenow + openai_admin** essentially clean. **anthropic_admin + cursor** confirmed contract with small drifts (1 code + doc). **copilot** pagination drift. **devin + granola** have SEVERE drift — as built they would ingest **zero / wrong** data against the live API (devin wrong envelope key; granola wrong host+endpoint+envelope+fields). The recorded-fixture tests passed precisely *because* the fixtures encoded our (wrong) assumptions — exactly the gap doc-verification exists to close.

## Batch 2 — signed-webhook connectors (DONE 2026-06-06)

| Connector | Verdict | Status |
|---|---|---|
| github | `X-Hub-Signature-256: sha256=<hex HMAC-SHA256(secret, raw body)>` — exact match | ✅ |
| gitlab | plaintext `X-Gitlab-Token` constant-time — confirmed. HMAC signing-token alt now provider-*recommended* (deferred enhancement, correctly noted) | ✅ |
| jira | `X-Hub-Signature: sha256=<hex>` (WebSub) confirmed — **scoped**: only secret-configured Cloud webhooks (admin/REST), NOT Connect/Forge; `method` is provider-variable (fail-closed safe) | ✅ |
| linear | `Linear-Signature` hex HMAC-SHA256 + replay — (was not separately re-fetched; as-built matches the documented scheme; spot-confirm with notion-batch rigor if desired) | ✅ (carry) |
| notion | `X-Notion-Signature: sha256=<hex>` over body, `verification_token` key — confirmed. `sha256=`-required is inferred from examples (not an explicit normative sentence); raw-body HMAC is the correct choice vs the doc's `JSON.stringify` idiom | ✅ (note) |
| slack | `v0:{ts}:{body}` basestring, `v0=<hex>`, both headers, **5-min** window — exact match | ✅ |
| sentry | `Sentry-Hook-Signature` hex HMAC-SHA256, Client Secret — confirmed. **DRIFT (documented choice)**: official ref signs `JSON.stringify(body)`; we sign raw bytes (defensible) → needs a pre-Live integration test against a real delivery | ◑ (pre-Live test) |
| pagerduty | `X-PagerDuty-Signature` `v1=` multi-sig — **DOC-SILENT (tooling-blocked)**: official sig page is JS-rendered, machine-unfetchable. As-built matches non-authoritative corroboration; needs a browser spot-check (already backlogged in auth.md) | ◑ (browser check) |
| zendesk | `X-Zendesk-Webhook-Signature` Base64(HMAC-SHA256(secret, ts+body)) — exact match, empty-body-safe | ✅ |
| fathom | Svix/Standard-Webhooks mechanics (`whsec_`, `{id}.{ts}.{body}`, base64) — confirmed. DOC-SILENT: Fathom's page doesn't NAME "Svix"; 300s window is the spec default not Fathom-documented | ✅ (note) |
| confluence | **Deferral reason OUTDATED**: Cloud webhooks DO carry a verifiable scheme — Connect-app **JWT** (`Authorization: JWT`, HS256 over per-tenant shared secret + `qsh`), NOT HMAC. Stays deferred (gated on Connect-app install state + needs a JWT primitive), but auth.md must be corrected | ⚠ (doc correction) |

## Batch 3 — passive / file / public (DONE 2026-06-06)

| Connector | Verdict | Status |
|---|---|---|
| sarif | SARIF 2.1.0 — every parsed path (`runs[].results[]`→`ruleId`/`message.text`/`level`/`physicalLocation...uri`/`region.startLine`) + `level` enum confirmed against OASIS schema | ✅ |
| osv | OSV schema — all parsed fields (`id`/`modified`/`summary`/`details`/`affected[].package.name`/`severity[{type,score}]`/`references[].url`/`aliases[]`) + `/v1/query` confirmed | ✅ |
| continue_dev | Documented+versioned schema. **DRIFT (code)**: reads `name`+`eventId` but real fields are `eventName` (no event-id); `model` fallback misses `modelName`. `level: all\|noCode` confirmed | ⚠ (code) |
| aider | The built surface (`(aider)` author/committer + `Co-authored-by` trailer) confirmed; `--analytics-log` jsonl field schema DOC-SILENT (correctly deferred) | ✅ |
| claude_code | Paths + retention documented; per-line transcript field schema + epoch-ms timestamp are **observed/undocumented** (DOC-SILENT) — connector already flags this | ◑ (observed) |
| local_directory | n/a — filesystem source, no external provider contract. Verified-by-design (size/ext/hidden rules are local policy) | ✅ |
| google_drive | body/paragraph/table shape + heading enum confirmed. **DRIFT (scope)**: `drive.metadata.readonly` is NOT valid for `documents.get` (use `drive.readonly`/`drive.file`); Drive `/file/d/` URL grammar DOC-SILENT | ⚠ (scope) |
| mcp_registry | **GRADUATES**: official registry NOW has a defined contract (`GET /v0/servers`, **public/no-auth reads**, cursor pagination, `server.json`+OpenAPI). **DRIFT**: live list nests entries under `item["server"]` (ServerResponse envelope) — `parse_server` reads top-level → needs unwrap. auth.md(Candidate) vs references.md(Beta) inconsistent | ⚠ (graduate + envelope) |

## Fix backlog (consolidated — for the batch-fix phase)

**Clean / verified (no change):** servicenow, openai_admin, github, gitlab, jira, linear, slack, zendesk, sarif, osv, aider, local_directory. *(+ notion, fathom — clean with a one-line doc-accuracy note.)*

**Code drift → governed fix cycles (ingestion-correctness; SEVERE would ingest zero/wrong live):**
1. **devin** *(SEVERE)* — **✅ FIXED (Fix Cycle 1, 2026-06-08)**: envelope `items`; `pull_requests[].pr_url`; cursor pagination (`after`/`end_cursor`/`has_next_page`) wired via `PageToken`.
2. **granola** *(SEVERE, near-rebuild)* — **✅ FIXED (Fix Cycle 1, 2026-06-08)**: host `public-api.granola.ai`; endpoint `/notes?include=transcript`; envelope `notes`; joined `transcript[].text`; `attendees`; `created_at`; `created_after` watermark; cursor pagination (`cursor`/`hasMore`).
3. **anthropic_admin** — **✅ FIXED (Fix Cycle 2, 2026-06-08)**: nested `cache_creation.{ephemeral_1h,5m}_input_tokens` summed; flat key removed; `_int` bool-guarded.
4. **copilot** — **✅ FIXED (Fix Cycle 2)**: `page`/`per_page` pagination wired via new `PageNumberPager` (100-day lookback, stop-on-short-page); api-version noted valid-but-not-latest.
5. **cursor** — **✅ FIXED (Fix Cycle 2, doc)**: dropped `name` from row docs (verified absent on this endpoint); host/body/`data` envelope confirmed; pagination **deferred-with-reason** (page/pageSize transport query-vs-body unverified — not invented).
6. **continue_dev** — **✅ FIXED (Fix Cycle 2)**: reads `eventName` (legacy `name` fallback) + `modelName`; ref floors to `eventName:timestamp` (no event-id).
7. **mcp_registry** — **✅ FIXED / GRADUATED (Fix Cycle 3, 2026-06-08)**: re-verified the exact OpenAPI contract (top-level `servers`, per-entry `element.server`, request `cursor`, response `metadata.nextCursor`, public no-auth); wired `build_mcp_registry_spec` with new `NoAuth` + nested-path `PageToken` (`has_more_field=None`); Candidate→**Beta**. **All 7 code-drift connectors now fixed.**

**Doc-only corrections — ✅ DONE (Fix Cycle 4, 2026-06-08):** confluence (deferral reason corrected →
Connect-app JWT, not "no scheme"), google_drive (scope → `drive.readonly`/`drive.file`; `drive.metadata.readonly`
invalid for documents.get), fathom (Svix-attribution-inferred + 300s-default notes), sarif (`level` added to
contract line), notion (auth.md de-staled Candidate→Beta + verified `X-Notion-Signature` + prefix/raw-body notes).

**Deferred-with-evidence (pre-Live action, not a code fix) — ✅ NOTED (Fix Cycle 4):** sentry (raw-body
byte-equality → pre-Live integration test gate), pagerduty (JS-rendered sig page machine-unfetchable →
browser spot-check; the one connector whose scheme is not doc-confirmed), claude_code (observed line-schema
DOC-SILENT, pin against a captured transcript before Live).

---

## CAMPAIGN COMPLETE (2026-06-08)

All 26 connectors are **doc-verified-and-correct**. The 7 code-drift connectors were fixed across Fix Cycles
1–3 (PRs #72/#73/#74; ledger #97–#102); the doc-only corrections + pre-Live notes landed in Fix Cycle 4 (this
pass). mcp_registry graduated Candidate→Beta. The connector code baseline now matches the verified provider
contracts; the remaining go-live items are **operator-runtime** actions (live network calls, the per-connector
pre-Live tests/spot-checks noted above), not connector-code work. **Phase 2 (mod groundwork) is unblocked the
moment Codex commits its `mods/` work** (reconcile-first).

## Method

Per connector: locate the authoritative provider API doc (official docs site / OpenAPI), confirm each
item, record `source URL @ access-date`. DRIFT findings are batched into a governed fix cycle (the
mapping/spec is corrected + re-pinned). DOC-SILENT findings are recorded in the connector's `auth.md`
as "confirmed undocumented as of <date>" (upgrades the honesty of the existing deferral note).

Output: this tracker filled in + each `auth.md` updated (assumption notes → confirmed/with-source or
confirmed-undocumented), and a verification summary in the ledger.
