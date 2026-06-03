# Shadow Genome — Narrative Archaeology

Persistent memory of verified facts and corrected assumptions discovered during
research. Each entry prevents a future drift. Newest first.

---

## SG-2026-06-03-H — Security/governance standards: mcp is the baseline; bot under-enforces

**Discovered**: 2026-06-03 (`/qor-research`, cross-repo security+governance alignment)
**Prevents**: assuming the bot enforces the authority boundary our producers rely on, and shipping integrations out of step with the mcp standard.

- **mcp is the inheritance baseline.** Four ingest guards — `_check_payload_size`/`_check_rate_limit`/`_check_canary`/`_check_sensitive` (`bicameral-mcp/handlers/ingest.py:138/202/231/265`), hard-vs-soft gating + DLQ (`:83-91`, `dlq/store.py`), webhook HMAC+dedup (`webhooks/github.py:48-72`, `dedup.py:51-145`), keyring secrets (`secrets_store/store.py`). Sibling repos adopt, not re-derive.
- **CRIT — the bot's authority boundary is doctrine-only.** `bicameral-bot/crates/bicameral-gateway/src/routes.rs:265,616` accept review/dashboard state mutations (promote candidate, approve signoff) with **no actor identity** (actor is the spoofable string "dashboard", `:709`) and **no auth** (`lib.rs:45-52` only warns). The "edges can't write canonical" invariant our integrations work depends on is NOT enforced in code. Verify before trusting it.
- **CRIT — secret-scan fragmentation.** mcp=TruffleHog, bot=custom python, integrations=`gitleaks-action@v2` — the tool mcp's own `secret-scan.yml` flags as paid-license-for-orgs. Ours is likely broken under the BicameralAI org. Standardize on TruffleHog.
- **Integrations gaps:** no test/lint CI (only secret-scan); `validate_emissions` doesn't screen secrets/PII; missing `SYSTEM_STATE.md`/`GOVERNANCE_INDEX.md` scaffold.

## SG-2026-06-02-G — Norm cross-check: contract authority belongs to the bot

**Discovered**: 2026-06-02 (`/qor-research`, doctrine cross-check of D1/D2/D3)
**Prevents**: integrations claiming contract authority it does not own.

Verified doctrine, both repos:

- **Schema ownership is the bot's, explicitly including integrations.** bicameral-bot
  `docs/adr/0002-agent-surfaces-and-bot-runtime-interface.md:63`: "`bicameral-bot/protocol/`
  owns the public-local contract vocabulary for bot, MCP, integrations, and cloud clients:
  schemas, conformance fixtures, object vocabulary…". The `protocol/schemas/` dir is staged
  (README only). MCP separately treats `contracts.py` Pydantic as canonical (`CLAUDE.md`).
  → **D2 amended**: schema-first discipline kept, but the wire schema's HOME is
  `bot/protocol/schemas/`; integrations owns only its `AdapterEmission` impl + a conformance
  test. Our ADR-0005 "repository-owned neutral contract" is scoped to the INTERNAL emission,
  not the cross-boundary wire contract.

- **MCP already infers `level` and carries no char spans** — `contracts.py:528`
  (`decision_level ... #340 auto-classified when omitted`), `ledger/adapter.py:91-106`
  `_classify_decision_level`, evidence is excerpt-only (`contracts.py:465-474`).
  → D3 (clean projection) MATCHES the mature MCP norm; only the bot gateway is out of step
  (F7). The fix is not novel — port MCP's `#340` pattern to the bot.

- **D1 (emit to bot gateway) intentionally breaks MCP's `pull → handle_ingest →
  confirm_watermark` two-phase orchestration** (`cli/sync_and_brief_cli.py`). Sanctioned by
  ADR-0004, but the `confirm()`-after-ack orchestration moves from MCP to integrations.

## SG-2026-06-02-F — Adapter contract decisions + the clean-projection blocker

**Discovered**: 2026-06-02 (`/qor-research` reconciliation, operator decisions)
**Prevents**: building a bridge that cannot produce a valid gateway request.

Operator decisions: **D1** bridge target = bicameral-bot `POST /api/v1/ingest`;
**D2** contract source of truth = repo-owned **JSON Schema** (schema-first), Python
dataclasses are one impl, repo stays Python; **D3** bridge is a **clean projection**
(never authors canonical fields).

**Blocker (F7):** A clean projection CANNOT emit a valid bot `IngestRequest` today.
`bicameral-bot/crates/bicameral-gateway/src/routes.rs:57-82` requires `level:
DecisionLevel` (no serde default, `:61`) and evidence `span_start/span_end: usize`
(no default, `:77-78`) — neither is adapter-owned (ADR-0005:48); emission
`SourceEvidence` has `excerpt` but no spans (`adapter/core/emissions.py:19-28`).
Resolution = cross-repo change on bicameral-bot: make `level` gateway-inferred and
evidence spans optional, BEFORE the first bridge lands. Note: evidence non-empty is
also gate-enforced (422 `EmptyEvidence`, `routes.rs:112-120`) — that one MATCHES
ADR-0005:45.

**Scaffold reconciliation:** ADR-0005's four emission objects + `adapter_version`
+ ADR-0006's three-mode interface ALREADY exist in `adapter/core/` (resolves earlier
"net-new"/"missing" drift claims). Still open for `/qor-plan`: F1 connector/normalizer
seam (`fetch_active` returns emissions directly) and a stale `pipeline.py:11` pointer
to "MCP bridges" (should be bot gateway).

## SG-2026-06-02-A — The adapter contract is NOT greenfield

**Discovered**: 2026-06-02 (`/qor-research`, target: adapter shape)
**Prevents**: API_ASSUMPTION_DRIFT — treating the universal adapter as a clean-slate design.

Both halves of the adapter contract already exist in source, split across two repos:

- **Connector reality** lives in `bicameral-mcp` (Python). The only existing
  abstraction is `sources/protocol.py:24-46` `SourceAdapter` — `source_id`,
  `can_handle_url(url)->bool`, `fetch_active(url)->dict`. It is **active-only
  (Phase 1)** and the connector **also normalizes** (returns an MCP ingest dict).
  ADR-0004/0005 require splitting connector (raw observations) from the universal
  adapter (normalizer) — that seam does not exist yet.
- **Neutral object-model reality** lives in `bicameral-bot` (Rust), canonical at
  `crates/bicameral-api/src/` (NOT the empty `protocol/schemas/`):
  `Source{uri,source_type,label?}` (`source.rs:13-19`),
  `SourceSnapshot` content-addressed (`source.rs:25-36`),
  `SourceEvidence{...,confidence:f64,...}` (`evidence.rs:13-25`),
  `DecisionCandidate` (`candidate.rs:18-36`),
  `IngestPayload{source,snapshot?,evidence[],candidate}` (`event_store.rs:113-120`)
  ≈ ADR-0005's `AdapterEmission`.

## SG-2026-06-02-B — Confidence is dimensional in the bot, absent in the MCP dict

`bicameral-bot` keeps confidence on separate axes by design — `ExtractionConfidence`
(`candidate.rs:142-148`, comment: "Collapsing these into one score creates cognitive
debt"), evidence `confidence:f64` (`evidence.rs:21`), `BindingConfidence`
(`evidence.rs:111-117`), plus `SignoffState`/`ComplianceState` (`dashboard.rs:85-105`).
The MCP ingest dict carries **no confidence field**. Therefore the integration
adapter is the layer that must introduce ADR-0005's `ConfidenceSurface`. Never
collapse to a scalar (ADR-0002/0007 forbid it).

## SG-2026-06-02-C — Two ingest boundaries exist; target the typed one

1. MCP `handle_ingest(ctx, payload:dict, source_scope, *, ingest_mode)`
   (`bicameral-mcp/handlers/ingest.py:502+`) — lossy `decisions[]`/`mappings[]` dict.
2. Bot `POST /api/v1/ingest` taking typed `IngestRequest`
   (`bicameral-bot/crates/bicameral-gateway/src/routes.rs:57-86`).

The neutral emission should be lossless toward the **richer** bot model; the MCP
dict is a legacy/lossy bridge. ARCHITECTURE_PLAN:47 names the bot gateway;
ADR-0005:18 names MCP ingest — reconcile via a bridge-agnostic emission. (Open Q1.)

## SG-2026-06-02-D — The connectors were built, then backed out FOR this extraction

`bicameral-mcp` git history: Jira reached active adapter + ADF flattener
(`ccb831d`) and webhook receiver (`087ba31`), then `fbdd9ec` "back
Jira/Notion/Slack/Linear integrations out of dev". That backout is the payload
this repository receives. **GitHub + Google Drive remain** as the reference
connectors; Jira (ADF rich-text) and Drive (no participants/date) are the shapes
most likely to expose a leaky contract — design fixtures against them.

## SG-2026-06-02-E — Existing enums to reuse, not reinvent

- `CaptureMethod { ApiPoll, Webhook, Manual, AgentExtract }` (`source.rs:41-46`)
  is the natural discriminator for ADR-0006's active/passive/webhook modes.
- `SourceFreshness { Fresh, Stale, Offline, Unknown }` (`source.rs:62-69`)
  serves ADR-0003 source-trust/gating.
- ADR-0005's `RoutingHint` and `AdvisoryResult` have **no existing type** —
  they are net-new; `producer_version` (ADR-0005:46) is also absent everywhere.
