# Research Brief

**Date**: 2026-07-08
**Analyst**: The Qor-logic Analyst
**Target**: GH #226 — emit `ExternalIngestEnvelope` to bot `POST /api/v1/external-ingest` (integrations leg of RFQ 4 / bot#218; unblocks mcp#623) + backlog B15 (vendored v1 schema drift re-check)
**Scope**: bot-side contract (v2 schema, gateway handler, migration spec, emitter-facing ADR rules) vs the current integrations emission seam (`gateway_mapping.py` + `GatewaySink`)

---

## Executive Summary

The bot side is complete and waiting: `POST /api/v1/external-ingest` (routes.rs:469-471, handler
:632-636) accepts a strict `ExternalIngestEnvelope` (v2 schema, `additionalProperties:false`), rejects 18
top-level authority fields with 403, and returns **201** on success. Integrations still emits the legacy v1
`IngestRequest` to `/api/v1/ingest` — per the migration spec that path is **local/MCP-actor only**, so the
whole v1 emitter (mapping + vendored schema) is superseded, which **closes B15 by removal** rather than
re-pin. Two contract deltas need explicit handling: the gateway **422s on empty `evidence[]`** (v1 tolerated
empty), and v1's `title`/`description` have no direct envelope slot (they map naturally onto ONE advisory
`candidate_hints[]` entry). The `GatewaySink` transport discipline (201-only, no-follow, token-free errors,
boundary re-screen) carries over unchanged — only the payload mapping, endpoint documentation, and vendored
schema change.

## Findings

### F1 — Target contract (verified against local bot checkout, HEAD `22806ac2`, schema commit `5c24c60f`)

- Schema `bicameral-bot:protocol/schemas/v2/external-ingest-request.schema.json` (draft-07,
  `additionalProperties: false`): required `content` (string) + `source_system` (string) + `source_uri`
  (string); optional `content_hash` (string|null — daemon computes when omitted), `evidence[]`
  (`ExternalEvidenceItem`: required `excerpt`; optional `span_start`/`span_end` uint, `confidence` double),
  `candidate_hints[]` (`ExternalCandidateHint`: required `title`+`body`; optional `level` string|null,
  `labels` string[]).
- Route: `external_ingest_routes()` → `POST /api/v1/external-ingest` (routes.rs:469-471). Handler takes raw
  bytes; **no auth check in the handler** (perimeter-level concern; a Bearer header is ignored, not
  rejected).
- Status codes: **201 success** (routes.rs:986 — matches `GatewaySink._SUCCESS_STATUS`); 400 bad JSON; **403
  forbidden field** (typed `ExternalIngestRejection`); **422 empty evidence** (routes.rs:718) / injection
  canary / sensitive data; 429 rate limit.
- Forbidden fields: 18-name constant (routes.rs:500-521): authority, auth_method, actor_id, session_id,
  policy_scope, review_command, tool_command, approve_signoff, reject_signoff, resolve_compliance,
  compliance_verdict, policy_grant, governance_override, canonical_decision, signoff_state, decision_id,
  compliance_state, tracking_state. Checked on **raw JSON, top-level keys only** (routes.rs:591-616).
- Materialization: source `uri`←`source_uri`, `source_type`←`source_system`; snapshot content-addressed
  (`sha256:` of `content`); each evidence item → `SourceEvidence` with defaults `span_start=0`,
  `span_end=len(excerpt)`, `confidence=0.5`; `DecisionCandidate` only via daemon projection —
  `candidate_hints` are advisory input, never authority (bot ADR-0024: confidence/authority are *signal*,
  not gates; bot ADR-0002: external integrations never use `ToolRequest`).

### F2 — Current integrations seam (this repo)

- `runtime/gateway_mapping.py:47-62` `emission_to_ingest_request` → v1 `{title, description, source,
  source_type, evidence:[{excerpt}]}`; floors title/description/source non-empty; `_source`
  (gateway_mapping.py:27-44) picks first evidence URL, else `source_id:ref`, else `source_id`, **through
  `redact()`** (purple-team PII-4/GATEWAY-1) — this exact function is reusable as the envelope `source_uri`.
- `runtime/sinks.py:99-167` `GatewaySink`: endpoint is the **full operator-configured URL** (no path logic in
  the sink); 201-only; no-follow redirects; CR/LF token guard; boundary re-screen via `validate_emissions`;
  token-free `GatewayEmissionError(status, reason)` — 403 already surfaces as
  `GatewayEmissionError(403, "gateway_rejected")`. Transport discipline needs **no change**.
- Vendored v1 schema `runtime/schemas/ingest_request_v1.schema.json` + `schema_version="v1"` constructor
  default; conformance tests in `runtime/tests/test_gateway_mapping.py`.
- Docs/examples that name the legacy path: `docs/adr/0012-...` (the seam ADR), `docs/runbooks/golive-linear.md:28`
  and `golive-google_drive.md` (gateway endpoint examples), `docs/CONNECTOR_BACKEND_SETUP.md`,
  `config/bicameral.example.json` (`gateway.endpoint` placeholder is `""` — only docs name the path).

### F3 — Contract deltas the plan must decide

1. **Empty evidence 422**: v1 emitted `evidence` as-is (possibly empty). The envelope needs a floor —
   guarantee ≥1 evidence item (fallback excerpt = the same title/description floor chain).
2. **title/description have no envelope slot**: `content` carries the body text; the natural preservation of
   the v1 title/description signal is ONE `candidate_hints` entry `{title, body}` (advisory-only per bot
   ADR-0024; `level` omitted — the daemon classifies, mirroring the v1 mapping's deliberate `level` omission).
3. **Migration spec** (`bicameral-bot:docs/specs/source-adapter-gateway-migration-218.md`): "integrations
   retarget lands first"; `/api/v1/ingest` = local/MCP-actor contract only → the v1 emitter path in this repo
   has **no remaining consumer**. Repo doctrine (no backwards compatibility) ⇒ remove
   `emission_to_ingest_request` + the v1 vendored schema. **B15 closes as superseded-by-removal.**
4. **Spans/confidence**: omit — SG-2026-06-02-B (dimensional confidence is never collapsed to a scalar) and
   bot-side defaults (span 0..len, confidence 0.5) are the daemon's own floors.
5. **`content_hash`**: omit — daemon computes; emitting it adds a drift surface for zero value.

## Blueprint Alignment

| #226 claim | Actual finding | Status |
|---|---|---|
| Bot gateway implemented at routes.rs:632-842 | Handler at :632-636, route at :469-471, success 201 at :986 | MATCH |
| 18 forbidden fields, 403 on injection | Constant :500-521 (18 names), raw-JSON top-level check :591-616, 403 :673-682 | MATCH |
| Envelope `{source_system, source_uri, content, evidence[], candidate_hints?[]}` | Schema adds optional `content_hash`; `additionalProperties:false`; evidence/hints item shapes as in F1 | MATCH (+detail) |
| "Vendor the v2 schema (pin the bot commit)" | Schema last touched `5c24c60f`; bot HEAD `22806ac2` | MATCH (pin both in header note) |
| "conformance test … forbidden-authority field rejected 403 by the gateway" | The 403 behavior is bot-side-tested (10+ conformance tests there); OUR side can assert (a) emitted envelope validates vs vendored schema, (b) emitted top-level keys ∩ forbidden set = ∅, (c) `GatewaySink` fail-closes on a mocked 403 | DRIFT (test intent restated — cross-process 403 can't run in this repo's suite) |
| "Update docs/adr/0012" | ADR-0012 documents the v1 seam; runbooks + CONNECTOR_BACKEND_SETUP also name `/api/v1/ingest` | MATCH (+2 doc surfaces) |

## Recommendations

1. **(P0)** New `emission_to_external_envelope(emission) -> dict` in `runtime/gateway_mapping.py`: reuse
   `_source` (redacted) for `source_uri`; `content` = the v1 description floor chain; evidence floored to ≥1
   excerpt; ONE candidate hint `{title, body}`; nothing else (strict schema).
2. **(P0)** `GatewaySink` posts the envelope; `schema_version` default → `"v2"`; endpoint stays the full
   operator URL (docs updated to `/api/v1/external-ingest`). Transport/hygiene unchanged.
3. **(P0)** Vendor `runtime/schemas/external_ingest_request_v2.schema.json` (header note pins bot commits);
   DELETE `ingest_request_v1.schema.json` + `emission_to_ingest_request` (B15 superseded).
4. **(P0)** Conformance tests per the DRIFT row above (schema-validate, forbidden-key disjointness, 403
   fail-closed, empty-evidence floor).
5. **(P1)** Docs: ADR-0012 amendment, runbook endpoint lines, CONNECTOR_BACKEND_SETUP.
6. **(P1)** Check how `test_gateway_mapping.py` validates against the vendored v1 schema today (stdlib-only
   subset validator vs jsonschema availability) and reuse the same mechanism for v2.

## Updated Knowledge

- The external-ingest handler enforces authority-stripping on **top-level keys only** — nested forbidden
  names pass through to deserialization (which drops them via the strict schema). Our emitter never nests
  authority fields, but the fact matters for future red-teaming.
- `/api/v1/ingest` is contractually local/MCP-actor only (migration spec §Contract Decision) — any future
  integrations emitter pointing there is drift, not compatibility.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
