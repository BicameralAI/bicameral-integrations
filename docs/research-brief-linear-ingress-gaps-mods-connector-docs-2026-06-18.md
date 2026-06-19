# Research Brief

**Date**: 2026-06-18
**Analyst**: The Qor-logic Analyst
**Target**: (1) Linear **ingress** connector gaps ("dropped-ball" items on the webhook + GraphQL-poll paths); (2) documentation-completeness audit of **every connector and every mod**; (3) **mods-expansion** candidates
**Scope**: Inbound evidence only (egress moved to `bicameral-sidecar`/`bicameral-sdk`). Four parallel read-only audits: Linear ingress deep-dive; connector-docs group A (14); connector-docs group B (12); mods docs + expansion. Findings are advisory — implementation is a later governed phase.

---

## Executive Summary

The Linear **ingress** path has real, unaddressed gaps that were deferred while attention was on egress. **Two are HIGH severity and Live-blocking:** (1) the webhook receiver applies **no event-type filter** despite `config.json` subscribing only to `Issue` events — a `Comment`/`Project`/`Attachment` webhook is parsed unconditionally and emits a malformed, empty-`title`/`excerpt` Observation that **violates the ADR-0005 non-empty-excerpt contract** (`connector.py:117-120`, `:139-151`); and (2) the `remove`/delete `action` is **not distinguished** from create/update, so deleting an issue emits "evidence" of a now-deleted issue (`connector.py:33-63`). Ten further ingress gaps (fragile field fallbacks, missing-`data`-wrapper handling, circular-cursor non-detection, fixtures-only live gate, `updatedFrom` unused, doc drift) are catalogued below. **Documentation audit:** all 26 connectors carry the four-file doc set, and ~22 are operator-robust, but the audit surfaced **a consistent readiness-language drift** (READMEs say a mode is "deferred this cycle" while `config.json` says `live-ready` and `references.md` says `flip-ready, NOT yet Live` — three different claims for the same mode, Linear/notion/servicenow/slack), plus **three real implementation drifts beyond Linear** (granola broken `author`, cursor un-wired pagination, github mode mismatch). **Mods:** 10 of 13 READMEs are too thin (~700–900 B — a sentence or two) to be "robust and easy to understand"; only `dependency_risk`, `noisy_source_gate`, `security_mentions` meet the bar. `dependency_risk` is the exemplar; a 5-section README template is recommended. **Mods expansion:** 5 genuinely-new advisory mods are worth adding (de-duplicated against the existing 13). The remediation is naturally a documentation/hardening cycle that also subsumes the open issues **#93 (Linear stress test)** and **#101 (accepted-risk hardening)**.

## Findings

### A. Linear ingress gaps (ranked) — verified against `connectors/linear/connector.py` + `runtime/graphql_poll.py`

| # | Sev | Gap | Location | Remediation |
|---|---|---|---|---|
| **A1** | **HIGH** | **No webhook event-type filter.** `config.json:57` subscribes `events:["Issue"]`, but `observations()`/`normalize_event()` parse *any* type. A `Comment` (has `body`, no `identifier`/`title`/`description`) emits `title=""`/`excerpt=""` → **ADR-0005 violation**. | `connector.py:117-120`, `:139-151` | Add `if payload.get("type") != "Issue": return []` before parse; test with a Comment fixture. |
| **A2** | **HIGH** | **`remove`/delete action not distinguished.** `action ∈ {create,update,remove}` (auth.md:16) is preserved only as metadata; a `remove` emits stale issue data as live "evidence." | `connector.py:33-63` | Decide policy (skip vs. retraction marker); implement in `normalize_event()`; add `remove` fixture + test. |
| **A3** | MED | **Fragile field chain, silent fallback.** `data.get("identifier")`/`description` assume the Issue shape; a non-Issue or `data`-less envelope falls through to empty fields rather than failing closed. | `connector.py:40-44`, `:66-78` | Reject when `identifier` empty (Issue invariant); pairs with A1. |
| **A4** | MED | **GraphQL missing-`data`-wrapper** produces a confusing `nodes_not_a_list` instead of a clear error. | `runtime/graphql_poll.py` (`_dig` on `data.issues.nodes`) | Assert `isinstance(page.get("data"), dict)` → `PollError("missing_data_wrapper")`; test. |
| **A5** | MED | **`webhookId` null vs empty** both silently drop a HMAC-verified delivery with no signal (replay-blindness on old API/malformed delivery). | `connector.py:146-150` | Document the policy; add a `webhookId:null` test (distinct from `""`). |
| **A6** | MED | **Live gate is fixtures-only.** `config.json:112-114` flags the field set + `200-with-errors` as UNVERIFIED against the real API; fixtures are hand-authored, not captured. | `config.json`, `fixtures/*` | On flip, capture one real webhook + one real GraphQL page as fixtures; cross-check optional fields. (= issue **#93**.) |
| **A7** | MED | **`updatedFrom` (before/after diff) unused/undocumented** — update webhooks carry prior values; no diff is surfaced. | `connector.py:33-63` | Document the omission in README limitations; surface in metadata only if a mod needs it. |
| **A8** | MED | **No circular-cursor detection.** A buggy/malicious `hasNextPage:true`+repeated `endCursor` re-fetches the same page up to `_MAX_PAGES=100`. | `runtime/graphql_poll.py:~149` | Track seen cursors → `PollError("circular_cursor")`; test. |
| **A9** | LOW | `parse_event` drops `actor.name` (`author=""`, SG-2026-06-11-D) but the **docstring doesn't say so** (unlike `parse_issue_node`). | `connector.py:34,55-56` | Mirror the `parse_issue_node` PII note in the `parse_event` docstring. |
| **A10** | LOW | **README drift:** README:10 says Active GraphQL is "deferred this cycle"; it is **built and harness-proven** (FX-LINEAR-003, `connector.py` docstring). | `connectors/linear/README.md:10` | Correct to "live-ready, proven by `runtime/` harness." |
| **A11** | LOW | No test for `data`-less / malformed-but-valid-JSON envelope. | `tests/test_linear_*` | Add the missing-`data` test (asserts fail-closed once A3 lands). |
| **A12** | LOW | Non-dict GraphQL nodes silently skipped (correct, but unsignalled). | `runtime/graphql_poll.py:~145` | Count + optional warning; test. |

**A1+A2+A3 are one coherent defect:** the webhook receiver trusts the envelope shape. The fix is a single fail-closed guard (type==Issue, action handling, identifier-required) + fixtures for Comment/remove/malformed. This is the "dropped ball."

### B. Connector documentation audit (26 connectors, four-file set each)

**~22 of 26 are operator-robust.** Best exemplar: **`gitlab`** (clear implemented-vs-deferred boundary, explicit operator residual-risk, dated drift corrections). Strong runners-up: `fathom`, `aider`, `zendesk`, `sentry`.

**B1 — Systemic readiness-language drift (the highest-value doc fix).** The same mode is described three different ways across a connector's own docs: README "**deferred this cycle**" ↔ `config.json` "**status: live-ready**" ↔ `references.md` "**flip-ready, NOT yet Live**." Confirmed on **linear** (README:10), **notion** (README active vs config webhook-only), **servicenow** (README omits poll-only), **slack** (README T2/T3 vs config T2). Operators reading only the README get a wrong picture. **Fix:** one canonical readiness vocabulary, propagated README→config→references (recommend "flip-ready (code-complete, harness-proven) / Live").

**B2 — Three real implementation drifts surfaced during the doc read (beyond docs; flagged for verification in the plan phase):**
- **granola** — `author` reads a non-existent `attendees[].name`; identity is actually `owner` (auth.md, LIVE 2026-06-11). Currently `author=""` placeholder — broken, `config.json` notes it but it is **not fixed**.
- **cursor** — `build_cursor_spec` (`runtime/poll_specs.py`) issues a **single request**, but the verified contract paginates via POST body (`page`/`pageSize`, `pagination.hasNextPage`); large teams **truncate silently**. Stale "host inferred/unverified" comments contradict the re-verified contract. README doesn't mention the limit.
- **github** — README claims **Active + Webhook**; `config.json` declares **webhook-only**; `auth.md` says Active "deferred." Mode mismatch, unflagged.

**B3 — auth.md depth vs. config.json complexity mismatch.** `sarif` (auth.md 390 B) and `sentry` carry rich redaction nuance (broadened secret catalog, prefix-less/high-entropy residual tokens) in `config.json` that never reaches `auth.md`/`references.md` where an operator looks. Surface the redaction posture where it's read.

**B4 — `references.md` is largely a README mirror.** Across most connectors it duplicates links rather than holding the verified field-shape/contract detail (the few exceptions: aider/github/gitlab). Opportunity: make `references.md` the home of the verified wire contract (Jira ADF avoidance, Devin cursor pagination, Cursor POST-body pagination, Linear field set).

### C. Mods documentation audit (13 mods)

**10 of 13 READMEs are too thin** (~700–900 B — scope-list only, no decision logic/outputs/boundary). **Robust (3):** `dependency_risk` (1590 B — exemplar), `noisy_source_gate`, `security_mentions`. **Thin (10):** adapter_contract, authority_boundary, code_review_risk, connector_freshness, data_classification, decision_drift, ownership_routing, source_trust_calibration, test_adequacy, webhook_risk.

**Shared framework (consistent, well-built):** `mods/contract.py` (`run_mod` enforcer: input re-screen FX-SEC-001 → manifest id/version/outputs parity → outputs allowlist → no opaque numeric confidence → output re-screen), `mods/_signals.py` (`matched_terms` word-boundary/phrase matcher, `safe_id`, `is_change_evidence`), `mods/README.md` (EM-safe boundary, ADR-0008/0013). The **code and config are consistent; only the human-facing README prose is thin.**

**C1 — Recommended README template** (from `dependency_risk`): `Status` line · one-line purpose · **How it works** (2–3 deterministic decision paths in plain English) · **Outputs** (each output type + message template + metadata keys + routing role/priority) · **Boundary** (can / cannot) · **References** (ADRs, trust tier). Lifts a thin README from ~700 → ~1200 B and makes each mod self-documenting.

### D. Mods-expansion candidates (de-duplicated against the existing 13)

Curated to genuinely-new, EM-safe advisory mods (read `AdapterEmission`, emit advisory/routing only — never block, never write). Dropped as redundant: `connector_health_drift`/`schema_evolution_risk` (⊂ `connector_freshness`/`webhook_risk`), `async_consistency_gap` (⊂ `webhook_risk`), `compliance_gate` partially overlaps `data_classification` (kept, re-scoped to *routing* not classification).

| Rank | Candidate | Why it fills a real blind spot | Primary emission |
|---|---|---|---|
| 1 | **cross_system_reference** | Evidence citing another system's id (GitHub PR# in a Jira ticket, Notion link in Slack) — no mod handles multi-system linkage today; high value given 26 connectors. | `suggested_review_question` + `routing_hint:integrations` |
| 2 | **ai_authorship_review** | AI-coding evidence (aider/cursor/copilot/claude_code/continue_dev/devin) carrying low-confidence/`TODO`/`FIXME`/hedging signals → route to human review. No mod is AI-coding-aware. | `advisory_governance_result` + `routing_hint:qa` |
| 3 | **policy_exemption_audit** | Evidence claiming `exempt`/`waived`/`bypass`/`exception` → surface for re-approval. Governance blind spot distinct from `authority_boundary`. | `suggested_review_question` + `routing_hint:policy` |
| 4 | **compliance_routing** | Routes (not classifies) changes touching regulated evidence to a compliance role; complements `data_classification` which classifies but doesn't route to compliance. | `routing_hint:compliance` |
| 5 | **notification_scope_risk** | Broadcast/alert/notify keywords without an explicit recipient/channel gate → over-broad-notification risk. | `advisory_governance_result` + `routing_hint:security` |

## Blueprint Alignment

| Expectation | Actual finding | Status |
|---|---|---|
| Webhook connector emits only subscribed event types | Linear parses any type; no filter (`connector.py:117-120`) | **DRIFT** — A1, Live-blocking |
| `remove`/delete distinguished from create/update | Not distinguished; emits deleted-issue evidence | **DRIFT** — A2 |
| Connector docs state modes/readiness consistently | README "deferred" ↔ config "live-ready" ↔ references "flip-ready" (linear/notion/servicenow/slack) | **DRIFT** — B1 |
| Docs match code | granola author, cursor pagination, github mode all drift README↔code | **DRIFT** — B2 |
| Every mod has robust, clear docs | 10/13 READMEs are scope-stubs (~700–900 B) | **DRIFT** — C |
| Mod framework consistent + EM-safe | `contract.py`/`_signals.py` consistent; code/config solid | **MATCH** |
| Linear Active GraphQL deferred | Built + harness-proven (FX-LINEAR-003); README stale | **DRIFT** — A10 |

## Recommendations

1. **(P1, Live-blocking)** Fix Linear ingress A1+A2+A3 as one fail-closed envelope guard (type==Issue, `remove` policy, identifier-required) + Comment/remove/malformed fixtures and tests. This is the named "dropped ball." Closes the ingress half of issue **#93**.
2. **(P1, docs)** Resolve the systemic readiness-language drift (B1): adopt one canonical readiness vocabulary and propagate it README→config→references across linear/notion/servicenow/slack (and audit the rest).
3. **(P1, verify-then-fix)** Confirm and remediate the three implementation drifts (B2): granola `author`→`owner`, cursor pagination wiring, github mode declaration. Each is a real correctness/coverage bug, not just docs.
4. **(P2, mods docs)** Apply the `dependency_risk` README template (C1) to the 10 thin mods — robust, easy-to-understand docs on every mod, as requested.
5. **(P2, Linear hardening)** Address A4–A8 (missing-`data` wrapper, webhookId null, circular cursor, fixtures-only gate, `updatedFrom`). A8/A4 overlap the **#101** accepted-risk hardening (aggregate response cap, screens) — fold them together.
6. **(P2, mods expansion)** Build the 5 curated new mods (D) following the proven mod pattern (`mods/_signals.py` word-boundary matcher, manifest parity, output re-screen). Sequence after the doc template so each ships robust docs from day one.
7. **(P3, docs hygiene)** Make `references.md` the home of the verified wire contract per connector (B4); surface redaction posture in `auth.md` where complexity warrants (B3, sarif/sentry).
8. **(governance)** This is a research answer. Next phase `/qor-plan` should split into: (a) Linear ingress fail-closed hardening (#93/#101 overlap), (b) connector-doc readiness-language pass, (c) the three implementation-drift fixes, (d) mod-README template rollout, (e) the 5 new mods. Items (a)/(c) are code (need tests + gates); (b)/(d) are docs.

## Updated Knowledge

For `docs/SHADOW_GENOME.md`:

- **SG-2026-06-18-A (a `config.json events:[...]` subscription is a UI hint, NOT an enforced filter):** Linear's webhook receiver parsed *any* event type despite subscribing only to `Issue`, emitting empty-field Observations that violate the ADR-0005 non-empty contract. A connector must **fail-closed on `type`/`action` at the receiver** (`type==Issue`, handle `remove`, require the entity invariant like `identifier`) — never assume the provider only sends what you subscribed to, and never assume the envelope matches the happy-path shape. Sweep every webhook connector for the same "subscribed ⇒ trusted shape" assumption.
- **SG-2026-06-18-B (readiness is described in three contradictory voices):** for several connectors the same mode reads "deferred this cycle" (README), "live-ready" (config.json), and "flip-ready, NOT yet Live" (references.md). Pick one canonical readiness vocabulary and propagate it; the README is what an operator reads first and was the most-stale. Doc drift hides real state.
- **SG-2026-06-18-C (mod code can be solid while mod docs are stubs):** the mod framework (`contract.py`/`_signals.py`) and per-mod `config.json` were consistent and correct, yet 10/13 READMEs were one-sentence scope stubs. "All mods built + tested" did not imply "all mods documented." Treat a robust README (purpose · decision paths · outputs · boundary) as part of done, using `dependency_risk` as the template.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor. Linear ingress A1/A2 are Live-blocking; the doc and mods-expansion work is sequenced behind a README template. Next: `/qor-plan`._

## Audit Method

Four parallel read-only audits (Explore agents): Linear ingress deep-dive (`connectors/linear/**`, `runtime/graphql_poll.py`, `runtime/poll_specs.py`, `adapter/core/pipeline.py`); connector-docs group A (14) + group B (12); mods docs + expansion (13 + `mods/contract.py`/`_signals.py`). HIGH-severity Linear findings (A1/A2/A3/A10) re-verified against source by the analyst; B2 implementation drifts are agent-surfaced and flagged for confirmation in the plan phase.
