# Shadow Genome — Narrative Archaeology

Persistent memory of verified facts and corrected assumptions discovered during
research. Each entry prevents a future drift. Newest first.

---

## SG-2026-06-04-G — An Observation excerpt needs a TERMINAL non-empty literal, not just a "better field" fallback

**Discovered**: 2026-06-04 (independent devil's-advocate review, connectors-phase1 implement)
**Prevents**: re-shipping the iter-1 Slack blank-excerpt VETO under a different connector.

`pipeline.normalize` rejects a blank/whitespace excerpt (`evidence_excerpt_blank`). A fallback chain is only safe if its LAST link is a guaranteed-non-empty literal. SARIF (`message or rule_id or ref`, `ref` floors to `"sarif-result"`) and MCP-Registry (`... or "mcp-server"`) had this; Notion's `title or page_id` did NOT — an untitled page arriving without a usable `id` (partial object / webhook envelope) produced `excerpt=""` and crashed the shared seam. The matching test gave false confidence by leaving the fixture `id` populated, so it never exercised the both-empty path. Fix: terminal literal `... or "notion-page"` + a test that feeds `{}` and asserts `normalize` does not raise. Same review found two Slack defects on documented cases: a present-but-empty `event` object was parsed as the envelope (leaking `type="event_callback"`), and `message_changed` edit subtypes dropped their real text (it lives in the nested `message` object). Both fixed by explicit `event`-dict unwrap + nested-`message` text/user extraction. Rule: every `parse_*` excerpt path must end in a literal; every "(no text)"/placeholder branch must be tested on the degenerate payload, not the happy fixture.

---

## SG-2026-06-04-F — The four Phase-1 candidate shapes all reduce to one Observation parse surface

**Discovered**: 2026-06-04 (`/qor-research`, connectors-phase1)
**Prevents**: over-building per-provider machinery for what are uniform read-only evidence adapters.

SARIF result, Slack message (or `event_callback` envelope), Notion page (title via the `type=="title"` property's `title[].plain_text`), and MCP-Registry `server.json` (`name`/`description`/`repository.url`) all map onto the same `parse_*(payload) -> Observation` -> `normalize()` surface as `connectors/github` — no contract change. SARIF emits one Observation per result. Slack's catalog "notify-first" mode is a deferred T3 write concern, not the read/ingest evidence surface built here (ADR-0008). Trust tiers: sarif T0, notion/mcp_registry T1, slack T2 (read). Live network/auth/webhook-signing deferred; the producer sensitive screen (`FX-SEC-001`) is the PII/secret guard. (SG-2026-06-04-E lives on the unmerged reusable-gates branch.)

## SG-2026-06-04-D — A ledger-chain verifier must encode the genesis anchor or it false-fails on entry #1

**Discovered**: 2026-06-04 (`/qor-audit` VETO, ci-gates iter 1)
**Prevents**: a governance-integrity CI gate that wedges the repo on its own committed history.

The `META_LEDGER` hash chain is NOT uniform from entry #1: **Entry #1 (GENESIS)** carries a `Content Hash` + `Previous Hash: GENESIS (no predecessor)` and **no `Chain Hash`**. **Entry #2's `previous_hash` equals Entry #1's CONTENT hash** (`274bc6…`), not a chain hash (genesis has none). From Entry #3 onward, `previous_N == chain_{N-1}` and `chain_N == sha256(content_N + previous_N)`.

A naive verifier ("every entry has all three hashes; every `previous` == prior `chain`") false-fails at #1 (missing chain) and #1→#2 (content-vs-chain link) — and if it's a *blocking* gate with a `test_repo_ledger_verifies` assertion, it wedges CI on the repo's own ledger. **Rule for any ledger verifier (incl. cross-repo reuse on bot/mcp/cloud):** treat the first entry as the genesis anchor (content hash, no chain hash); the first chained entry links to the genesis *content* hash; thereafter standard linkage + recomputation. Verify recomputation per-entry (tamper-evidence) and run the verifier against the real ledger during implementation before marking the gate blocking. Same Promise-vs-Reality family as [[SG-2026-06-03-K]].

## SG-2026-06-04-C — Compliance frameworks are control-mappings + evidence, not per-law CI checkers

**Discovered**: 2026-06-04 (`/qor-research`, CI gates vs microsoft/agent-governance-toolkit)
**Prevents**: shipping a `gdpr.yml`/`hipaa.yml`/`soc2.yml` that "passes" a build without verifying any real control (ghost compliance).

Even Microsoft's AGT — which advertises NIST AI RMF / EU AI Act / SOC 2 / OWASP coverage — has **no per-law CI checker**. It satisfies frameworks with three layers: (1) real automated scanners (CodeQL, OpenSSF Scorecard, dependency-review, SBOM+attestation, secret-scanning, supply-chain pinning); (2) a **blocking governance gate** (`scripts/governance_gate.py` → policy validation + Ed25519 provenance receipt + audit-log artifact); (3) **`docs/compliance/` mapping docs** (`owasp-agentic-top10-architecture.md`, `nist-ai-rmf-alignment.md`, `soc2-mapping.md`) over a tamper-evident Merkle audit trail. GDPR/HIPAA/ISO-27001/SSDF aren't even named there.

**Rule for us:** the CI-enforceable layer is SAST/secret/dep/supply-chain/SBOM/Scorecard + a stdlib **governance-integrity gate** that re-verifies the committed `META_LEDGER` hash chain + FEATURE_INDEX (the `.qor/` gate JSONs are gitignored, so CI checks the *committed* chain). Frameworks become `docs/compliance/*.md` that *cite* those gates + the QOR `ai_provenance` (EU AI Act Art. 13/14/50, AI RMF, SSDF) + the `FX-SEC-001` sensitive-data screen (GDPR/HIPAA PII/PHI control) as evidence — control alignment, never certification.

## SG-2026-06-04-B — Correct crypto can still fail OPEN: every attacker-input path in a verifier must raise the caught error type

**Discovered**: 2026-06-04 (`/qor-audit` VETO, webhook-verify iter 1)
**Prevents**: shipping a webhook verifier whose HMAC math is right but which crashes (instead of rejecting) on malformed attacker input.

A verifier's `verify()` is specified to map only `WebhookVerificationError → False`. So any OTHER exception on an attacker-controlled path escapes the contract boundary as an uncaught raise — and depending on the (out-of-scope) caller's handling, a crash can become a retry storm or a swallowed truthy path. The L3 audit found four such paths even though the HMAC construction was spec-perfect:
- `json.loads(body)` to read a timestamp **before** the HMAC check → `JSONDecodeError` escape **and** parse-before-verify.
- `headers.get("Linear-Signature")` → `None` into `compare_digest` → `TypeError`.
- `body.decode()` on a non-UTF-8 body → `UnicodeDecodeError` (also: HMAC the signed content over **bytes**, not a decoded str).
- `int(timestamp)` on a non-numeric header → `ValueError`.

**Rule:** in a security verifier, (1) do the HMAC/`compare_digest` FIRST over raw bytes; (2) parse/inspect the body only after it verifies; (3) wrap every attacker-input conversion so it raises the ONE error type the connector maps to `False` (fail closed); (4) self-guard the parse step (`normalize_event` re-checks `verify`) — a documentation-only "assumes prior verify" is not a code guarantee; (5) test the malformed/missing/replay/empty negatives, not just tamper+wrong-secret. Correct math is necessary, not sufficient.

## SG-2026-06-04-A — Fathom (Svix) and Linear webhook verification differ on three axes; don't share one verifier blindly

**Discovered**: 2026-06-04 (`/qor-research`, webhook verification core)
**Prevents**: writing one HMAC verifier and assuming both providers fit it — they differ in encoding, signed content, and timestamp unit.

| Axis | Fathom (Standard Webhooks / Svix) | Linear (`Linear-Signature`) |
|---|---|---|
| Header(s) | `webhook-id`, `webhook-timestamp` (unix **s**), `webhook-signature` (space-delim `v1,<b64>`) | `Linear-Signature` (single hex digest) |
| Signed content | `{id}.{timestamp}.{body}` (constructed) | the **raw body** alone |
| Secret → key | `whsec_<base64>` → **base64-decode** to key bytes | secret used as-is |
| MAC encoding | HMAC-SHA256 → **base64** | HMAC-SHA256 → **hex** |
| Anti-replay | `webhook-timestamp` within ~**300 s** (Svix ref) | `webhookTimestamp` (**ms**) within **60 s** |
| Dedup id | `webhook-id` header | `webhookId` (in body) |

Shared discipline (port from `bicameral-mcp/webhooks/github.py` + `dedup.py`): constant-time `hmac.compare_digest`; **verify before parse**; **dedup only after verify** (don't let unverified ids poison the cache); fail-closed on missing/empty secret; bounded LRU+TTL dedup. Inject a clock for deterministic anti-replay tests. The `WebhookConnector` contract carries no secret → inject it into the connector (keyring resolution deferred). (standardwebhooks.com spec; linear.app/developers.)

## SG-2026-06-03-K — A widened CI command in the plan is a lie if ci.yml path-allowlists the old dirs

**Discovered**: 2026-06-03 (`/qor-audit` VETO, fathom-linear cycle iteration 1)
**Prevents**: shipping new connector tests that never run in CI because the workflow's hardcoded path allowlist wasn't widened.

`.github/workflows/ci.yml` runs `mypy adapter/core connectors/github` and `pytest adapter/core/tests connectors/github/tests -q` — both **path-allowlisted to github**. A plan whose `## CI Commands` reads `pytest -q` / `mypy adapter connectors` describes intent, not reality: the new `connectors/{fathom,linear,granola,local_directory,google_drive}` suites + type-checks would be silently ungated, so a broken connector ships green. **Rule:** any cycle adding a connector dir MUST add `.github/workflows/ci.yml` to its Affected Files and widen the mypy/pytest steps to `adapter connectors` / `adapter/core/tests connectors`. The `ci_coverage_lint` WARN at audit Step 0.6 surfaces this; treat it as load-bearing, not noise. The plan's `## CI Commands` must match what ci.yml actually executes.

## SG-2026-06-03-J — Linear's richest ingest point is the webhook envelope, not a GraphQL poll

**Discovered**: 2026-06-03 (`/qor-research`, Fathom + Linear connector surface)
**Prevents**: building Linear as a GraphQL poller and losing change context that only the webhook carries.

- Linear's API is GraphQL (`https://api.linear.app/graphql`, personal API key via `Authorization`), but the **webhook** delivers a fully-serialized entity plus change context a poll cannot: `{action(create|update|remove), type, actor, createdAt, data, url, updatedFrom, webhookId, webhookTimestamp(ms), organizationId}`. `updatedFrom` (prior values of changed fields) exists **only** on the webhook — invaluable for decision-candidate diffing.
- Issue `data`: `id`(uuid), `identifier`(e.g. `PROJ-123`), `title`, `description`, `priority`, `state`, `team{id,name}`, `assignee{id,name}`, `url`.
- Signature: `Linear-Signature` = **hex** HMAC-SHA256 over the **raw** body with the signing secret; anti-replay rejects `abs(now − webhookTimestamp) > 60000 ms`. Treat WEBHOOK as primary, ACTIVE GraphQL as fallback fetch.
- No live Linear code survives in MCP to port (backed out per SG-2026-06-02-D) — clean-room build from the public contract. (linear.app/developers.) Live verification deferred this cycle.

## SG-2026-06-03-I — Fathom signs webhooks with the Standard Webhooks (Svix) scheme

**Discovered**: 2026-06-03 (`/qor-research`, Fathom + Linear connector surface)
**Prevents**: hand-rolling a Fathom signature verifier and confusing its epoch-seconds timestamp with Linear's milliseconds.

- Fathom's `new-meeting-content-ready` webhook uses the **Standard Webhooks / Svix** envelope: headers `webhook-id`, `webhook-timestamp` (epoch **seconds**), `webhook-signature` (base64, space-delimited *versioned* sigs e.g. `v1,<b64>`). Secret prefixed `whsec_`; verify = `HMAC-SHA256(base64decode(secret), "${id}.${timestamp}.${body}")` → base64 → constant-time compare.
- REST: base `https://api.fathom.ai/external/v1`, API-key auth, **60 req/60 s** (`RateLimit-*` headers). `GET /meetings` cursor-paginates via `next_cursor`/`cursor`; transcript/summary/action-items are opt-in expansions. Webhook payload **is a meeting object** (same shape as list items).
- Implication: reuse a Svix-style verifier when live; do **not** hand-roll. Seconds-vs-ms timestamp differs from Linear (SG-J). (developers.fathom.ai.) Live verification deferred this cycle.

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
