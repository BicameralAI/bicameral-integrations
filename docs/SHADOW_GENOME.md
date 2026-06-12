# Shadow Genome — Narrative Archaeology

Persistent memory of verified facts and corrected assumptions discovered during
research. Each entry prevents a future drift. Newest first.

---

## SG-2026-06-12-A — verify-before-cite is per-connector AND per-cycle; a stale "verified" date does not transfer

**Discovered**: 2026-06-12 (operator caught it: "I'm not seeing where you've performed any of the prerequisite /qor-research").
**Prevents**: shipping go-live descriptors on a connector's recorded "verified <date>" claim instead of a live re-fetch.

After running verify-before-cite `/qor-research` for cursor + granola (#135 — which caught real drift), the next four go-live cycles (mcp_registry/github/jira/slack) **skipped it** and authored descriptors off each connector's existing `references.md`/`auth.md` "verified 2026-06-08" lines. A recovery re-fetch (#143) confirmed all four MATCH the live docs — **lucky, not safe**: the same re-fetch surfaced a real notion gap (the connector requires a `sha256=` prefix on `X-Notion-Signature` that the live docs don't confirm Notion sends → would reject every delivery). **Rule: every go-live cycle's FIRST step is a live re-fetch of that connector's contract — the verification does not transfer from a sibling cycle or a recorded date.** This is SG-2026-06-11-D applied as a process gate, not just a one-off observation. The four shipped descriptors were retroactively validated by #143; the process, not the output, was the failure.

## SG-2026-06-11-D — A "verified" claim in a connector's own docs is not verification; re-fetch the live source

**Discovered**: 2026-06-11 (`/qor-research`, cursor + granola pre-go-live contract verification).
**Prevents**: shipping a descriptor that cites a connector's recorded-but-unverified contract, and under-screening a PII-dense source.

Two connectors carried a "verified 2026-06-08" line in their own `auth.md`; re-fetching the live provider docs found one fully correct and one drifted — the recorded claim alone is worthless without the re-fetch:
- **cursor**: live docs CONFIRMED every recorded fact (host `api.cursor.com`, `POST /teams/daily-usage-data`, Basic key-as-username, `{startDate,endDate}` epoch-ms ≤30d, `data` envelope, no `name`) **and resolved** the deferred pagination as **POST-body** `page`/`pageSize` + response `pagination.hasNextPage`. Meanwhile `runtime/poll_specs.py` still carried STALE "host inferred / envelope unverified" comments — the *code comment* drifted from the *verified doc*. Lesson: reconcile EVERY site (auth.md, references.md, poll_specs comments) to one verified truth.
- **granola**: live docs showed the note identity is **`owner` {name, email}**, but the connector reads a non-existent **`attendees`** field → author empty/wrong live. And the **transcript is emitted verbatim with no `redact()`** while a person's name rides as `author`; FX-SEC-001 (secret/PHI/PAN only) does NOT catch generic spoken email/phone/name — so a PII-dense meeting-content source had **no effective PII control on the wire**. **Rule: a meeting/content connector must redact-and-pass its free text and must not emit raw attendee identity; FX-SEC-001 is not a sufficient backstop for generic PII.** Reinforces SG-2026-06-05-D (cursor allowlist) + SG-2026-06-11-A (pin + re-verify the live source, not the recorded claim).

## SG-2026-06-11-C — Two ledger verifiers with INCOMPATIBLE Previous-Hash markup; the repo CI gate is authoritative

**Discovered**: 2026-06-11 (purple-team fix cycle; the #131 seal's own "fix" suggestion was wrong).
**Prevents**: "fixing" the qor-logic canonical-markup finding by backticking Previous Hash, which silently breaks the repo's blocking CI gate.

`scripts/governance_gate.py` (the repo's blocking `governance-gate.yml` CI gate) parses `**Previous Hash**:` with `_HEX64.match` anchored at string start, so it requires a **BARE hex** value and computes the chain as `sha256(content+previous)`. `qor-logic verify-ledger` (a separate, non-CI tool) requires the hash be **backtick-wrapped or `=`-prefixed** and flags entries #123+ as "missing canonical hash markup". **These two expectations are mutually exclusive on the same line.** Entry #131 recorded a "non-destructive fix = backtick the value" — that was itself drift: backticking #129-131 made `governance_gate.py` FAIL (the backtick was parsed into the hash, breaking the link + recompute). **Rule: the authoritative ledger verifier for this repo is `scripts/governance_gate.py` (bare-hex Previous Hash, `sha256(content+previous)`); author every new entry to satisfy IT.** The qor-logic "canonical markup" finding is a foreign-tool expectation incompatible with the repo format — it is NOT a drift to remediate, and #123-128 are correct as bare hex.

## SG-2026-06-11-B — The provider response is untrusted at the TRANSPORT layer too (no-follow redirects); screen every wire field PER-LEAF

**Discovered**: 2026-06-11 (purple-team go-live assessment, 17 confirmed gaps; issues #94-#102).
**Prevents**: a credentialed request following an attacker-controlled 3xx (token exfil + SSRF), and a cross-field ID-label suppressing a PAN on the wire.

Cores were sound; the gaps were edges, the SG-2026-06-05 family one layer deeper:
- **Transport SSRF (the sole go-live blocker):** stdlib `urllib`'s default opener auto-follows 3xx. An untrusted provider response can redirect a credential-bearing request to an arbitrary host — re-sending the secret (Authorization / `x-api-key`) and driving a server-side fetch — BEFORE any 200-only/screen defense (which inspect only the final body). **Rule: disable redirect-following at the transport** (a no-follow `HTTPRedirectHandler` returning None); a 3xx must surface as a non-200 and fail closed. Applies to BOTH `UrllibTransport` and `GatewaySink`.
- **Per-leaf screen:** joining wire fields into one blob before `detect_sensitive` lets a trailing ID-label in field A fabricate `_is_id_preceded` suppression for a Luhn-valid PAN at the start of field B — a false negative. **Rule: scan EACH wire-bound field (incl. author/timestamp) as its own unit** (the discipline metadata already used). Extends SG-2026-06-05-E.
- **Don't reflect untrusted response bodies into errors:** the FX-SEC-001 catalog matches specific key shapes, not an opaque bearer — a gateway echoing the Authorization header would leak it. Return a fixed discriminator (SECRET-LEAK-1).
- **Fail-closed parse covers `RecursionError`** (deeply-nested JSON) and **type-confusion** (`.strip()`/`.join()` on non-string provider scalars) — reinforces SG-2026-06-04-I skip-don't-crash. Every fix shipped with a regression gate in `tests/redteam/` + `red-team.yml`.

## SG-2026-06-11-A — A provider with two API versions is a re-drift trap; pin the doc HOST + version per connector

**Discovered**: 2026-06-11 (`/qor-research`, Devin v3 contract re-verification for the flip-ready cycle).
**Prevents**: re-introducing the 2026-06-08-corrected Devin drift by reading the wrong API version's docs.

Devin ships TWO parallel APIs with DIFFERENT response shapes:
- **v1** (`docs.devin.ai/api-reference/sessions/list-sessions`): `GET /v1/sessions`, list under `sessions`, singular `pull_request` object, `limit`/`offset` pagination, `apk_` keys.
- **v3 enterprise** (`docs.devinenterprise.com/api-reference/v3/sessions/organizations-sessions`): `GET /v3/organizations/{org}/sessions`, list under `items`, `pull_requests[]` array of `{pr_url, pr_state}`, cursor (`end_cursor`/`has_next_page` re-sent as `after`), `cog_` Service-User keys.

The connector targets **v3 by design** (`runtime/poll_specs.py:build_devin_spec`; `connectors/devin/auth.md`). The drift corrected on 2026-06-08 (`sessions`/singular-`pull_request.url`/deferred-pagination) was nothing other than the **v1 shape recorded against the v3 connector** — someone read the wrong version's docs. Re-verification on 2026-06-11 confirmed v3 is a full MATCH; the trap is still live because the v1 page is the more discoverable one. **Rule: when a provider versions its API, pin the exact doc HOST + version path in `references.md` and re-verify against THAT host only — a verify-before-cite against the wrong version silently re-introduces the corrected drift.** Reinforces the API_ASSUMPTION_DRIFT lineage (Shadow Genome Entry #2) and SG-2026-06-04-N (verify cross-source citations at write time).

## SG-2026-06-04-O — A reusable workflow's `permissions:` must stay within the caller's grant; verify CI fixes by RUNNING, not by reasoning

**Discovered**: 2026-06-04 (Scorecard gate `startup_failure`, two-iteration fix).

The `OpenSSF Scorecard` gate `startup_failure`'d on every push. **First fix** (drop `id-token: write` + `publish_results: false`) was reasoned-PASS by an independent audit on strong circumstantial evidence (0–2 s runs; CodeQL passes with `security-events: write`) — but the post-merge run **still failed**, proving the reasoning wrong. **Real root cause:** `_reusable-scorecard.yml` declared top-level `permissions: read-all`, which **exceeds** the caller's grant (`scorecard.yml`: `contents: read` + `security-events: write`). GitHub rejects a reusable workflow that requests broader permissions than its caller provides → `startup_failure` ("workflow file issue"). The working `_reusable-codeql.yml` declares the minimal `permissions: contents: read` (a subset) and passes. **Fix:** mirror the proven CodeQL pattern — reusable top `permissions: contents: read`, job `contents/security-events: write/actions: read`, caller grants the same. **Rules:** (1) a called (reusable) workflow's `permissions:` can only REDUCE, never widen, the caller's grant — never `read-all` in a reusable unless the caller also grants it; (2) a CI gate is only "green" when an actual run is OBSERVED green — a workflow fix whose verification is structurally post-merge (push/schedule-only triggers) must NOT be sealed as "all gates green" before the run is seen (Entry #59 over-claimed; corrected by #60). Empirical verification outranks audit reasoning for CI/infra. Extends SG-2026-06-04-B (fail-closed) with a process rule: prove-by-running.

## SG-2026-06-04-N — Never cite a cross-repo issue/PR number in a governance artifact without verifying it

**Discovered**: 2026-06-04 (operator challenge — "I don't see anything open that fits #99").
**Prevents**: a phantom cross-repo blocker propagating through SYSTEM_STATE / ledger / BACKLOG / memory as fact.

A hand-off summary referenced "bot #99 / #108 / #109"; `#99` was over-specified into a concrete claim never verified ("blocked until bot #99 lands the v1 protocol schema"). Live check: **bicameral-bot #99 is a CLOSED PR** ("Integration: dev → main … ingest gateway …"), unrelated to a pending schema — wrong on every count, and it had spread into `docs/SYSTEM_STATE.md` + memory. **Ground truth (verified 2026-06-04):** v1 ingest wire schema is **published** (bot PR #95, `protocol/schemas/v1/`); real OPEN emission-safety gate is bot **#109** (gateway `/api/v1/ingest` lacks size/rate/prompt-injection/sensitive-data guards); internal ingest authority mid-refactor (MCP→ToolRequest: bot #114/#115/#116/#117/#120 + #123 conformance); #73 (release signing) open; #108 CLOSED. **Rule:** any external issue/PR/commit citation in a Tier-1 governance artifact must be verified against the source repo at write time (`gh api repos/<r>/issues/<n>`) + tagged with the verification date; a half-remembered number is an Open Question, not a blocker. Cross-repo analogue of the SG-2026-06-04-F grounding discipline.

---

## SG-2026-06-04-M — Jira Cloud classic webhooks DO sign (sha256=-prefixed); ADF description is not text

**Discovered**: 2026-06-04 (`/qor-research`, jira connector).
**Prevents**: assuming Jira webhooks are unsigned (skipping verify), and routing the ADF description object into the excerpt.

Contrary to the initial assumption that Jira classic webhooks are unsigned, a webhook with a configured `secret` signs delivery `X-Hub-Signature: sha256=<hex-HMAC-SHA256(secret, raw_body)>` (WebSub) — so Jira ships `verify()` at parity, but the **`sha256=` prefix must be stripped** before a bare-hex verifier (`verify_hmac_hex`). And `issue.fields.description` (and comment `body`) is an **Atlassian Document Format object** (`{type:"doc", content:[…]}`), NOT a string — the excerpt must use `fields.summary` (str), never description; routing the ADF dict in is both meaningless and a PII-smuggle risk. Connect-JWT (HS256/RS256 `qsh`) / Forge / Automation use different auth — deferred. Reinforces SG-2026-06-04-A (per-provider signature divergence) + SG-2026-06-04-I (a dict is not text).

---

## SG-2026-06-04-L — A connector over an undocumented heterogeneous event log must FILTER, not assume

**Discovered**: 2026-06-04 (`/qor-research` + devil's-advocate, claude-code connector).
**Prevents**: a parser that crashes (or emits junk) on the meta/unknown line types in Claude Code's transcript JSONL.

Claude Code transcripts (`~/.claude/projects/<slug>/<session>.jsonl`) are an undocumented, **unversioned, heterogeneous** event log — `type` ∈ user/assistant/summary/system/mode/permission-mode/file-history-snapshot/attachment/last-prompt/… and one assistant turn **splits across multiple lines** (one per content block). Rule: parse it with a **filtering** surface — `parse_session_line(line) -> Observation | None`, keep only the evidence types, **skip unknown/meta types (return None), never error**; one line ≠ one message; and a sibling time format (`history.jsonl` is epoch-ms int, transcripts are ISO str) must never leak into the str timestamp. Devil's advocate also found unbounded recursion on deeply-nested `tool_result.content` lists → **depth-cap recursion** on hostile nested input. Extends SG-2026-06-04-I (skip-don't-crash on unknown record kinds + depth-cap).

---

## SG-2026-06-04-K — MCP is for interactive agent action (T3/T5); API/webhook is for read-only evidence (T0/T1) — pick by the interactivity test

**Discovered**: 2026-06-04 (operator design review, connector value-add)
**Prevents**: routing read-only evidence ingestion through a high-authority MCP/agent surface, or assuming MCP is the default/only connectivity for a candidate.

A candidate system can be reached as a read-only **evidence adapter** (this repo, `parse_* -> Observation -> normalize()`, T0/T1) or as an **MCP server** (`bicameral-mcp`, agent tool-calling, T3/T5 action authority). **Default to the evidence adapter; MCP is the EDGE case** reserved for when an agent must act interactively at inference time. Concrete reasons direct API/webhook wins for *evidence*: (1) webhooks are **push** — MCP is pull-only, so real-time event/decision capture can ONLY come direct; (2) a pure `payload -> Observation` parse is **deterministic + hash-chainable** for the ledger, an agent/tool layer is not; (3) **least authority** — read-only T0/T1 vs T3/T5; (4) no server/protocol/LLM runtime dependency; (5) batch scale (one `querybatch` vs per-item tool calls). A system may warrant **both** surfaces for different purposes (GitHub: MCP for governed action, API/webhook for evidence) — keep them separate so evidence never rides the authority channel. The `mcp_registry` connector already models the correct relationship: ingest evidence *about* MCP, don't transport *through* it. Encoded as the catalog §4 "Surface selection (interactivity test)" triage criterion; companion to ADR-0008 + SG-2026-06-04-J.

---

## SG-2026-06-04-J — For advisory data build the aggregator; developer-AI evidence is two surfaces, not one

**Discovered**: 2026-06-04 (`/qor-research`, connector value-add pass)
**Prevents**: building N redundant per-ecosystem advisory connectors, and conflating two different AI-tool evidence surfaces.

**Advisory data:** **OSV.dev** is a free, no-auth, versioned, read-only API that already aggregates GHSA-global, PyPA (PYSEC), and RustSec — so standalone npm / RustSec / PyPA advisory connectors are redundant (P3). Build the aggregator (P0); add GitHub's GHSA only for the *unique* per-repo **Dependabot alerts** signal. **Developer-AI evidence splits in two:** (1) local **transcripts/commits** — T0 passive file import, the richest first-party decision/implementation evidence (Claude Code `~/.claude/**/*.jsonl`, Continue dev-data, Aider git attribution), but secret-laden and schema-unversioned (mandatory `FX-SEC-001` redaction + SG-2026-06-04-I tolerant parser); and (2) vendor **admin/usage-metrics APIs** — T1 read-only governance/leverage evidence (GitHub Copilot, Cursor, OpenAI/Anthropic Admin), no source code but org-admin-key gated and per-user (PII). Choose the surface to the evidence class you want; don't assume a vendor has an API (Windsurf does not — deferred). Extends SG-2026-06-04-H (ingest the stable surface).

---

## SG-2026-06-04-I — A parse surface for a version-fragile schema must defend on TYPE and whitespace, not just presence

**Discovered**: 2026-06-04 (independent devil's-advocate review, connectors-dev-tools implement)
**Prevents**: a connector that claims "defensive parsing" crashing (or silently emitting blank) on a malformed/version-skewed record.

The `x.get(k) or ""` idiom guards absent/`None` but NOT wrong-type: a non-string field reaches `.strip()`/`.split()`/`[:7]`/`in` and raises a raw `AttributeError`/`TypeError` that aborts the whole `normalize()` batch with a stack trace instead of being floored. And the terminal-literal floor (SG-2026-06-04-G) uses `or`, which only catches the empty string — a **whitespace-only** value (e.g. an Aider commit `hash` of `"   "`) is truthy, skips the literal, and produces a whitespace excerpt that violates the parse surface's own "never blank" invariant (caught only by the downstream `.strip()` gate). Rule for any parse surface over a churning/external schema: coerce to `str` where the contract needs a string (`str(x.get(k) or "")`), skip non-string text fields in the excerpt scan (`isinstance(v, str)`), and `.strip()` a value BEFORE it participates in an `or`-floor. Test the wrong-type and whitespace-only payloads explicitly, not just the happy fixture. Extends SG-2026-06-04-G (terminal literal) and SG-2026-06-04-H (ingest the stable surface).

---

## SG-2026-06-04-H — AI-coding tools expose evidence as local artifacts, not APIs; ingest the stable surface, defer the fragile one

**Discovered**: 2026-06-04 (`/qor-research`, connectors-dev-tools)
**Prevents**: building a Continue/Aider connector against an API that does not exist, or against an unversioned file format that breaks on the next release.

Continue and Aider are both read-only, **file/git-import (T0)** evidence sources — neither has a public read API or webhook. **Continue** writes purpose-built "development data" as schema-*versioned* JSONL (`schema` 0.1.0/0.2.0) to `.continue/dev_data/` (events: `chatInteraction`/`editOutcome`/`autocomplete`/... ), with a native `level: noCode` redaction lever that strips file contents/prompts/completions. **Aider's** only stable, documented, code-free provenance surface is its deterministic **`(aider)` git-commit attribution** (author/committer name suffix, or a `Co-authored-by:` trailer); its rich transcript `.aider.chat.history.md` has **no versioned schema** (markdown prose) and is scraping-prone, so it is DEFERRED along with the opt-in `--analytics-log` JSONL. Rule: ingest the versioned/deterministic surface (Continue dev-data JSONL, Aider git attribution); defer the unversioned one. Both reduce to the same `parse_*(record) -> Observation -> normalize()` surface; both need the SG-2026-06-04-G terminal-literal excerpt floor (`"continue-event"` / `"aider-commit"`).

---

## SG-2026-06-04-G — An Observation excerpt needs a TERMINAL non-empty literal, not just a "better field" fallback

**Discovered**: 2026-06-04 (independent devil's-advocate review, connectors-phase1 implement)
**Prevents**: re-shipping the iter-1 Slack blank-excerpt VETO under a different connector.

`pipeline.normalize` rejects a blank/whitespace excerpt (`evidence_excerpt_blank`). A fallback chain is only safe if its LAST link is a guaranteed-non-empty literal. SARIF (`message or rule_id or ref`, `ref` floors to `"sarif-result"`) and MCP-Registry (`... or "mcp-server"`) had this; Notion's `title or page_id` did NOT — an untitled page arriving without a usable `id` (partial object / webhook envelope) produced `excerpt=""` and crashed the shared seam. The matching test gave false confidence by leaving the fixture `id` populated, so it never exercised the both-empty path. Fix: terminal literal `... or "notion-page"` + a test that feeds `{}` and asserts `normalize` does not raise. Same review found two Slack defects on documented cases: a present-but-empty `event` object was parsed as the envelope (leaking `type="event_callback"`), and `message_changed` edit subtypes dropped their real text (it lives in the nested `message` object). Both fixed by explicit `event`-dict unwrap + nested-`message` text/user extraction. Rule: every `parse_*` excerpt path must end in a literal; every "(no text)"/placeholder branch must be tested on the degenerate payload, not the happy fixture.

---

## SG-2026-06-04-F — The four Phase-1 candidate shapes all reduce to one Observation parse surface

**Discovered**: 2026-06-04 (`/qor-research`, connectors-phase1)
**Prevents**: over-building per-provider machinery for what are uniform read-only evidence adapters.

SARIF result, Slack message (or `event_callback` envelope), Notion page (title via the `type=="title"` property's `title[].plain_text`), and MCP-Registry `server.json` (`name`/`description`/`repository.url`) all map onto the same `parse_*(payload) -> Observation` -> `normalize()` surface as `connectors/github` — no contract change. SARIF emits one Observation per result. Slack's catalog "notify-first" mode is a deferred T3 write concern, not the read/ingest evidence surface built here (ADR-0008). Trust tiers: sarif T0, notion/mcp_registry T1, slack T2 (read). Live network/auth/webhook-signing deferred; the producer sensitive screen (`FX-SEC-001`) is the PII/secret guard.

---

## SG-2026-06-04-E — A cross-repo reusable verifier must take its repo-root as a parameter, not from __file__

**Discovered**: 2026-06-04 (`/qor-research`, reusable-gates cycle)
**Prevents**: a reusable governance-gate workflow that silently verifies the wrong repository.

A reusable workflow (`workflow_call`) that lives in repo A but is consumed by repo B runs in **B's** context. To run A's `governance_gate.py` it must `actions/checkout` A's script to a side path (e.g. `.governance-tooling`, SHA-pinned). But the script derives its repo root from `Path(__file__).resolve().parents[1]` — which, when run from `.governance-tooling/`, points at **A's** checkout, not B's. It would verify the tooling repo's own ledger and pass trivially, never checking the consumer. **Rule:** any verifier intended for cross-repo reuse must accept `--repo-root` (default `__file__`-derived for local use) and the reusable workflow passes the caller's `GITHUB_WORKSPACE`. Consumers SHA-pin both the reusable-workflow ref and the tooling checkout ref. Companion to [[SG-2026-06-04-D]].

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

## SG-2026-06-05-A — FX-SEC-001 screens secret/PHI/PAN, NOT generic PII/email

The emission-time sensitive screen (`adapter/core/sensitive.py`, surfaced via
`pipeline._screen_sensitive`) detects three classes only: **secret** (AWS/GitHub-PAT/
Azure/PEM/JWT regexes), **phi** (MRN / `patient_*:` / `dob:` / `ssn:` — all
*label-adjacent*), and **pan** (Luhn-validated card numbers). The lone `email`
token is `patient_email:` (PHI, requires the literal label). **A bare email such as
`jane.doe@example.com` is NOT matched by any pattern**, and `_screen_sensitive` scans
only `title + body + evidence.excerpt` — it never scans `Observation.metadata`, and
`_emission_from` does not copy metadata onto the emission.

**Consequence:** FX-SEC-001 is NOT a generic-PII backstop. Any connector ingesting a
PII-dense source (Cursor `daily-usage-data` rows carry `email` in every record; live
Zendesk ticket bodies; the Copilot per-user NDJSON report) MUST drop or redact PII at
**parse time** — that exclusion is the sole control. Prove it with a non-vacuous test:
the fixture must CONTAIN the PII, and the assertion must show it absent from the whole
Observation and the post-`normalize` emission. Surfaced by the independent audit of the
copilot/cursor cycle (META_LEDGER Entry #74/#75). The live redact-and-pass model (which
WOULD let PII-bearing bodies through after redaction) remains deferred.

## SG-2026-06-05-B — Redact-and-pass: the complement to FX-SEC-001's reject

`adapter/core/redaction.py::redact(text)` is the **redact-and-pass** model (the long-deferred
gate for live Zendesk bodies, Cursor per-developer, Devin/ServiceNow free-text). It **composes
with — never replaces** — FX-SEC-001 (`_screen_sensitive`), which stays the un-bypassable HARD
reject. `redact` scrubs the catalog classes (secret/PHI/PAN) via `sensitive.py::redact_catalog`
**plus** the generic PII the catalog misses (email, phone — see SG-2026-06-05-A), to irreversible
placeholders.

**Two non-obvious correctness facts (both surfaced by the independent audit, iter-1 VETO):**
1. **Ordering is the invariant guarantee.** `redact` runs email → phone → `redact_catalog`
   (**catalog LAST**). Because the catalog pass — which reuses the EXACT `_PAN_CANDIDATE_RE` +
   `_luhn_valid` + `_is_id_preceded` predicate `detect_sensitive` uses — operates on the FINAL
   string, `detect_sensitive(redact(x)) == []` holds by construction. An earlier ordering
   (catalog before phone) let phone redaction mutate a digit run and surface a PAN AFTER the
   catalog had passed → the emission then got REJECTED by the backstop (a redact-and-PASS failure,
   not a leak). Lesson: a "redact-and-pass" primitive must guarantee its OWN output passes
   detection; don't delegate that to the external gate.
2. **Redaction must be a strict SUPERSET of detection, per class.** `detect_sensitive` PHI patterns
   key on the LABEL only (`ssn:`); reusing them verbatim for redaction leaves the VALUE in cleartext,
   so `redact_catalog` uses value-consuming PHI patterns. **But the value quantifier must be `*`, not
   `+`** — the independent observer caught that `[\w@.\-]+` (requires a value char) leaves a bare or
   punctuation-led label (`dob:`, `ssn= (pending)`, `dob: <withheld>`, `ssn:\n`) DETECTED-but-not-
   REDACTED → `detect_sensitive(redact(x)) != []` → the emission is REJECTED (redact-and-FAIL).
   Generalized rule: for EVERY detection pattern, redaction must match wherever detection matches.
   Secret/MRN/PAN reuse the exact detection predicate (superset by equality); PHI field-label uses
   `…\s*[:=]\s*[\w@.\-]*`. The "catalog-runs-last by construction" argument only covered PAN/digit-
   mutation; it did NOT cover this detection⊋redaction asymmetry. Regression:
   `test_redact_bare_phi_labels_pass_detect`.

Proven by `test_redact_output_passes_detect` (adversarial corpus: phone-abutting-PAN, id-shielded
PAN with an intervening PHI label, concatenated phone+PAN) + the end-to-end ServiceNow harness proof
(a valid-shape `AKIA` secret in an incident description WOULD be rejected raw — companion assertion —
but is redacted so the emission passes). META_LEDGER Entry #77/#78/#79.

## SG-2026-06-05-C — AI-vendor admin APIs split by evidence type (audit vs usage)

Researching OpenAI + Anthropic admin APIs (Entry #80) surfaced a reusable distinction for vendor
admin connectors: the org-admin surface splits into two evidence types with opposite PII shapes.
- **Audit-log APIs = governance/security evidence** (who did what: key lifecycle, project/role
  changes, logins). The EVENT (type + project + timestamp) is the evidence; the **`actor` is
  structured identity (user email, IP, user id) → drop at parse** (the ServiceNow `caller_id`
  precedent — structured identity is dropped, not redacted). OpenAI `GET /v1/organization/audit_logs`.
- **Usage/cost APIs = leverage evidence** (tokens/cost by workspace/model/tier). Grouping dimensions
  are **opaque ids (`wrkspc_…`, `apikey_…`) → aggregate, PII-free** (the Copilot precedent — parse
  directly). Anthropic `/v1/organizations/usage_report/messages` + `/cost_report`.
- **Per-user** cost/analytics is always a SEPARATE, PII-bearing API (Anthropic's Claude Code Analytics;
  OpenAI's per-actor filters) → deferred behind the redact-and-pass model. Both are poll-only REST with
  org-admin keys (Bearer / `x-api-key`), no webhooks, no evidence MCP (SG-K).

## SG-2026-06-05-D — Opaque vendor user-id MAY be surfaced for per-developer attribution (supersedes -A for userId only)

**Supersedes**: SG-2026-06-05-A's "drop `userId`" clause, for `userId` ONLY. The email/name drop is unchanged.

SG-2026-06-05-A made dropping Cursor's `email`/`name`/`userId` the sole PII control. The redaction-retrofit
cycle (Entry #84) revisited the `userId` clause to enable **per-developer attribution** (an explicit
operator ask). Decision: the **opaque vendor integer `userId` MAY be surfaced** as a grouping/attribution
token (in `ref` + excerpt), while **`email`/`name` remain NEVER read**. Rationale: a bare vendor id is
**pseudonymous on its own** — re-identification requires the org's id→identity mapping, which the operator
already holds (operator already has full Cursor-admin access); the connector never emits the identity.
**Residual risk (accepted, documented here + SYSTEM_STATE):** an operator with the mapping can re-identify;
this is acceptable for an operator-run evidence adapter. **Scope:** applies to `userId` only; `redact()`
would scrub an email (defeating attribution), so attribution uses the opaque id, not redact-and-pass.
**Correction:** an earlier plan draft cited Anthropic `workspace_id`/`api_key_id` as precedent for surfacing
opaque ids — that was FALSE (the anthropic_admin connector deliberately does NOT surface them); the honest
analogue is Zendesk's emitted `requester_id` (a support-requester id), and even that is partial. This is a
deliberate narrow exception, not a general "surface all opaque ids" pattern. Reaffirms SG-2026-06-05-A for
generic email/PII (FX-SEC-001 is not a backstop) and the redact-and-pass model for free-text bodies.

## SG-2026-06-05-E — The sensitive screen must cover EVERY wire-bound field, and error channels must not echo raw values

**Discovered**: 2026-06-05 (adversarial red-team of the existing code; GH issues #50-#61).

A four-front red-team found the crypto + redaction CORES are sound (no HMAC forgery; `detect_sensitive(redact(x))==[]` held under 500k fuzz; GatewaySink 201-only + F-1 re-screen hold) — the real defects were at the EDGES:
- **FX-SEC-001 only scanned `title + body + excerpt`** but the gateway wire also carries `source` (from `source_ref.url`/`ref`) and `source_type` (from `source_id`). A secret in a `pull_request.url` / `detail.url` / `source_id` bypassed the HARD gate and was POSTed in cleartext. **Rule: the screen's scanned content must be a SUPERSET of every field `emission_to_ingest_request` forwards to the wire** — re-derive it whenever the mapping changes. (Fixed Cycle A: screen now covers source_id + source_ref.url/ref/source_id.)
- **The reject path itself leaked**: `_redact_excerpt` masked only the `secret` class, so a rejected emission's `EmissionContractError` carried the raw PAN/MRN into logs. **Rule: an error/log excerpt must never carry a raw value for ANY class** (pan/phi → `[cls:redacted]`; short secret → full mask). The reject channel is a leak channel.
- **The operator token leaked via an uncaught `ValueError`**: a CR/LF in the token makes `http.client` raise a value-embedding error before network I/O, outside `_post`'s HTTPError/URLError catch. **Rule: validate operator-injected header material up front (value-free error), and give error paths a token-free catch-all.**
- DoS/ReDoS surfaces (`_TAG_RE`/`_EMAIL_RE` quadratic; huge-int `json.loads` ValueError; type-confusion + non-dict crashes escaping `normalize_event`/`observations`) are latent-until-Live and tracked as #50/#51/#55/#56/#57/#59 (Cycle B). **Meta-rule: parse surfaces are an untrusted boundary — guard `isinstance(dict)` at `observations()`, catch `ValueError` around `json.loads`, and use possessive/length-capped regexes — before any connector goes Live.**

## SG-2026-06-05-F — Possessive quantifiers do NOT fix a "re-scan" quadratic; bound or exclude the anchor

**Discovered**: 2026-06-05 (red-team Cycle B; the audit's proposed fix was empirically wrong).

The confluence `<[^>]+>` and email `[A-Za-z0-9.-]+` ReDoS were O(n²) — but the quadratic came from
the OUTER re-scan (`re.sub`/search retries from each anchor position, and at each the greedy class
consumes a long run before failing), NOT from intra-match backtracking. So the intuitive fix —
**possessive quantifiers (`++`/`*+`) — DID NOT HELP** (measured: still 15-20 s). The correct fixes:
- exclude the anchor char from the inner class so each position fails in O(1): `<[^>]+>` → `<[^<>]*>`
  (a `<` can no longer be consumed mid-tag, so an unclosed-`<` run can't re-scan to EOF).
- **bound the quantifiers** so each anchor's work is a constant: email local `{1,64}`, label `{1,63}`,
  TLD `{2,63}` (RFC 5321 limits) → O(64·n) = linear, and no real email is missed (over-bound = leak).
**Meta-rule (reinforces SG-2026-06-05-O's "prove by running"): MEASURE a ReDoS fix on the adversarial
input; never trust the regex-shape reasoning.** Independent verification empirically confirmed the
bounded fix (200 KB: ~20 ms) — the audit's possessive reasoning would have shipped a still-broken fix.

---

## SG-2026-06-12-G — pin a file-import source's line schema against a REAL captured artifact, not the vendor doc

`/qor-research` for the **claude_code** flip verified the per-line transcript schema against a real
6,008-line session transcript (keys-only). The vendor docs (`code.claude.com/docs`) document file paths +
30-day retention but are **DOC-SILENT on the per-line field schema**. The real file showed the connector's
documented `summary` evidence type is **absent** from the current format, and new types exist (`ai-title`
carries the session summary now; `pr-link`, `system`, `queue-operation`). The connector's skip-unknown
discipline (SG-2026-06-04-I) means no crash, but it parses a now-dead type and misses new evidence.
**Rule:** for a local/desktop file-import connector, re-pin the line schema against a CURRENT real artifact
every flip cycle — a vendor doc that covers paths/retention does not pin the record shape.

## SG-2026-06-12-H — injecting a structured real-name field violates "real names dropped" even with `author` dropped

The **fathom** connector drops `recorded_by.name` from `author` (#150) but `_flatten_transcript` still
**prefixes every transcript line with `speaker.display_name`** (a structured real name). Redact-and-pass
scrubs email/phone/secret/PHI/PAN but NOT a deliberately-injected display name, so the platform's
now-public "human real names are dropped" guarantee (README / capability matrix) is contradicted on the
transcript path. **Rule:** identity minimization must cover every structured name a connector INJECTS into
emitted text, not just the `author` slot — drop or pseudonymize injected speaker/owner/actor names too.

## SG-2026-06-13-A — a local/passive connector that emits raw operator content still needs redact-and-pass parity

`/qor-research` for the local_directory + aider flip found both emit raw free text with NO redaction —
local_directory the **full file content + filename stem** (`connectors/local_directory/connector.py:39,46`),
aider the **commit subject** (`connectors/aider/connector.py:57,59`) — on the theory that "it's a local/passive
source, FX-SEC-001 is the guard." But the absence of a network/provider boundary is **not** the absence of a
PII boundary: FX-SEC-001 hard-rejects only secret/PHI/PAN, so an email/phone/name in an operator-dropped file
(or a filename like `jane.doe-severance.md`, or a token pasted into a commit message) reaches the evidence
stream unredacted. The network connectors (fathom/zendesk) already redact-and-pass free text; redaction is
non-destructive (scrubs only the sensitive classes), so it is pure upside. **Rule:** apply redact-and-pass to
ANY free-text excerpt regardless of transport — local, passive, and file-import surfaces included; keep an
opaque hash/id floor un-redacted so the phone regex cannot mangle it (the claude_code floor discipline).

## SG-2026-06-13-B — for a provenance connector the human name is signal, not noise; decide retain/drop per-connector

The fathom/claude_code flips established "drop real human names" (SG-2026-06-11-D / -H). Applying that
reflexively to **aider** would be wrong: aider's entire purpose is git provenance — *which human ran the AI
pair-programmer* — so `author_name` (`connectors/aider/connector.py:65`) is the evidence, at trust tier T0, and
stripping it would gut the connector. (The connector reads only `author_name`, not `author_email`, so no contact
handle leaks.) The discipline is per-connector: identity-minimization drops a name when it is **incidental**
(a meeting speaker, a session OS-username) and retains-and-documents it when it is the **signal** the connector
exists to carry. **Rule:** never blanket-apply the name-drop; for each connector decide whether the human
identity is signal or noise, and state the retention explicitly in `data.pii_posture` when you keep it.

## SG-2026-06-13-C — verify a finding's IMPACT against the real serializer, not the struct field's existence

The purple-team over local_directory/aider/zendesk (#170) confirmed a true code gap — `source_ref.kind` and
the `author` field bypass `redact()` and/or `_screen_sensitive` — but the red agents assigned MEDIUM on the
premise that these fields "reach the wire." They do not: `runtime/gateway_mapping.py:emission_to_ingest_request`
maps the v1 `IngestRequest` from only `title`/`description`/`source`/`source_type`/`evidence[].excerpt` and
**drops `kind`, `author`, `timestamp`, and metadata entirely**. The gap is real at the *mod-input* boundary
(mods consume the full in-process `AdapterEmission`, which is why `author`/`timestamp`/`metadata` are already
screened) and as descriptor-honesty/defense-in-depth — not as a gateway-wire leak. **Rule:** before assigning
severity to a "reaches the wire / forwarded to X" claim, trace it to the actual emit/serialize function and
confirm the field is in that function's output; a field's presence in the in-memory struct is not proof it
crosses the boundary. (Pairs with SG-2026-06-12-C: re-verify against the REAL envelope, not a fixture.) The fix
still stands — screen + descriptor honesty are warranted — but the severity is measured down med->low.

## SG-2026-06-13-D — when a provider's signature doc is a JS-SPA that fetches empty, record it + fall back honestly

`/qor-research` for the pagerduty flip needed to re-verify the `X-PagerDuty-Signature` `v1=` HMAC scheme
(verify-before-cite, SG-2026-06-12-A), but `developer.pagerduty.com/docs/webhooks/webhook-signatures` is a
client-rendered SPA that returns an empty body to a server-side fetch. The honest move is NOT to silently claim
a live re-verify: instead (a) confirm what IS statically retrievable — the `x-pagerduty-signature` header name
was confirmed via `support.pagerduty.com/main/docs/webhooks` — and (b) fall back to the connector's own
harness-proven verified-contract record (`references.md`, dated) + the `verify_hmac_hex_multi` implementation for
the scheme detail, and (c) state the provenance of each claim (live doc vs. support mirror vs. prior verified
contract) in the brief. **Rule:** a fetch that renders empty is a recorded limitation, not a pass; never upgrade
"couldn't retrieve" into "re-verified." Capture which channel substantiated each cited contract fact.

## SG-2026-06-13-E — for a security-scanner import, redact-and-pass BEATS relying on the FX-SEC-001 hard-screen

> **SCOPED by SG-2026-06-13-F (purple-team #185):** "redact-and-pass scrubs the secret value" holds only for the
> shared `_SECRET_PATTERNS` catalog. A non-catalog token (Slack/Google/Stripe/GitLab/npm/GitHub-fine-grained, now
> added) or a prefix-less high-entropy token is a residual — broaden the SHARED catalog and disclose the residual.

`/qor-research` for the sarif flip surfaced a counter-intuitive failure mode: a SARIF / secret-scanner result's
`message.text` can quote the very secret it flags (e.g. "Detected AWS key AKIAIOSFODNN7EXAMPLE in config.py").
The sarif connector emitted `message.text` RAW (`connectors/sarif/connector.py:30,35`), trusting FX-SEC-001 as
the guard — but FX-SEC-001 HARD-REJECTS any emission carrying a secret/PHI/PAN, so the entire finding is DROPPED
and the security signal ("a secret was found in config.py") is LOST. For a *security* connector that is the worst
outcome. **Rule:** apply `redact()` (redact-and-pass) to scanner-finding messages so the secret value becomes
`[redacted:secret]` while the finding SURVIVES as evidence; keep FX-SEC-001 as the backstop for anything redact
misses. Leaning only on the hard-screen REDUCES security coverage for the one connector class that most needs it.
Also keep the data minimization of reading the finding **message** but never the raw code **snippet**
(`region.snippet.text` — the rawest secret surface). Reinforces SG-2026-06-13-A (redact-and-pass any free-text
excerpt regardless of transport).

## SG-2026-06-13-F — "redact-and-pass scrubs the secret" is only as strong as the CATALOG; point the red team at your strongest claim

The osv+sarif purple-team (#185) aimed the red agent squarely at this session's strongest claim — SG-2026-06-13-E
("redact-and-pass scrubs the secret value while keeping the security finding") — and it over-generalized.
`redact()` and the FX-SEC-001 screen both reuse ONE catalog (`adapter/core/sensitive.py:_SECRET_PATTERNS`: AWS
`AKIA`, classic GitHub `ghp_`, Azure-storage, PEM, JWT). A scanner finding quoting a NON-catalog token — Slack
`xoxb-`, Google `AIza…`, GitHub fine-grained `github_pat_…`, Stripe `sk_live_…`, GitLab `glpat-…`, npm `npm_…` —
is scrubbed by NEITHER and reaches the gateway wire verbatim. The `AKIA` example used to justify SG-2026-06-13-E
happened to be covered, which masked the gap. **Rule:** (1) a redaction/screen claim must NAME the catalog it
depends on and STATE the residual — never imply universal coverage from one worked example; (2) broaden the
*shared* catalog (it fixes scrub + screen + every connector in one change) rather than patching one connector; (3)
an unbounded high-entropy secret with no recognizable prefix (e.g. a bare 40-char AWS *secret* key) is a permanent
regex residual to DISCLOSE, not to over-claim away (mirrors the bare-national-phone residual); (4) when you make a
strong security claim, point the next adversarial pass AT it. Corrects SG-2026-06-13-E; reinforces SG-2026-06-12-B
(sweep the shared surface) + SG-2026-06-05-F (measure the fix — a too-broad secret pattern false-positives).

## SG-2026-06-14-A — assemble secret-shaped TEST fixtures by concatenation or GitHub push-protection blocks the push

PT-sarif (#186) broadened `_SECRET_PATTERNS` to scanner token families (Slack/Stripe/Google/…) and the tests
used literal fake tokens (`xoxb-…`, `sk_live_…`) to prove detection. The push was REJECTED by **GitHub
push-protection** (GH013) — its own secret scanner flagged the test fixtures as real Slack/Stripe secrets, even
though they were obviously-fake example values. **Rule:** any test/fixture that must contain a secret SHAPE
(to exercise a detector/redactor) must ASSEMBLE the string by concatenation/repetition at runtime
(`"xox" + "b-" + …`, `"sk" + "_live_" + "0"*24`) so no contiguous token literal appears in the committed bytes —
the runtime value still matches your regex, but the scanner has nothing to flag. (The AWS-docs example `AKIA…`
and `ghp_0123…`-style sequential fakes are commonly allowlisted; the prefix families added in #186 are not.)
Pairs with the stealth-mode discipline: keep secret-shaped strings out of tracked literal source.

## SG-2026-06-14-B — a connector with an UNVERIFIABLE capability mode must declare only the verifiable subset in its FX-CFG-001 descriptor

`/qor-research` for the confluence flip found the connector's `capabilities` include WEBHOOK (the Data-Center
`X-Hub-Signature` HMAC scheme), but **Confluence Cloud publishes no payload signature** (the HMAC scheme is
Data-Center/Server only, confirmed across DC 7.18-10.2) and the connector ships no `verify()`. Declaring webhook
in the flip-ready descriptor would invite an operator to wire an UNAUTHENTICATED inbound path. **Rule:** the
FX-CFG-001 descriptor declares only the modes the connector can actually secure for the target deployment — here
`["active","passive"]` (the authenticated REST poll) — and records the unverifiable mode as a disclosed
`wire_gate`, NOT a webhook block. `capabilities ⊇ descriptor-modes` by design: a capability is what the parse
surface CAN handle; a descriptor mode is what an operator may safely flip Live. Pairs with SG-2026-06-13-D
(record what you could not verify) + ADR-0012 (flip-ready is an operator-safety claim, not a feature list).

## SG-2026-06-14-C — isinstance(x, int) is NOT enough before time.gmtime/strftime; an out-of-range int crashes

The final-four purple-team (#193) found that openai_admin's `_event_time` type-guarded `effective_at`
(`if not isinstance(effective_at, int): return ""`) but a provider-supplied OUT-OF-RANGE int (e.g. `10**20`)
passes the isinstance check and `time.gmtime(10**20)` raises OverflowError/OSError, uncaught — aborting the whole
poll batch (one bad row drops all). **Rule:** any `gmtime`/`localtime`/`strftime`/`datetime.fromtimestamp` on a
provider-supplied epoch int must be wrapped in `try/except (OverflowError, OSError, ValueError)` returning a safe
empty value, AND those exception types belong in the runtime per-row `_PARSE_SKIP` backstop so one bad row never
drops the batch. This is the time-conversion sibling of the `(x or "").strip()` truthy-non-str crash class
(fathom #164 / gitlab GITLAB-001 / anthropic_admin ANTHROPIC-ADMIN-PARSE-1) — both are "the lone field the
per-leaf type guards missed." Sweep every sibling that converts an epoch int (SG-2026-06-12-B).
