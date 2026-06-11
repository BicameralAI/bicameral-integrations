# Scope — Go-Live Batch (verified-4 poll connectors) + noisy_source_gate enablement

**Date**: 2026-06-11
**For**: the next `/qor-auto-dev-1` cycle (this is the scoping artifact it consumes; not yet implemented).

> **SUPERSEDED IN PART by the #135 research brief** (`research-brief-cursor-granola-doc-standard-2026-06-11.md`, verified live 2026-06-11): **cursor is now L1 / descriptor-ready** (host/body/envelope verified; pagination resolved = POST-body), and **granola is now L2** — it has a contract drift (identity is `owner`, not `attendees`) **and** a transcript-PII gap, so it needs a connector correction (re-point to `owner`, redact-and-pass the transcript, drop raw attendee identity) **before** its descriptor. Recommended batch: **cursor + copilot + servicenow as L1 descriptors; granola split to its own L2 sub-cycle.** The risk-tier cells below are pre-research; trust the brief.
**Risk posture**: feature; L1 for copilot/granola/servicenow + the mod enablement, **L2 for cursor** (live-contract verification debt + new asserted wire facts).
**Review boundary**: stage only unless the operator authorizes commit/push/PR at cycle end.

## Goal

Promote four active-poll connectors — **copilot, granola, servicenow, cursor** — to **flip-ready (NOT yet Live)** parity with Linear/Google Drive/Devin, and **enable the `noisy_source_gate` mod** on the live emission stream. Actual Live flip stays operator-gated (ADR-0012) — this cycle stops at flip-ready + runbooks-eligible.

## Why these four / why now

- All four already have a **live fetch-half built + runner-wired** (`runtime/poll_specs.py` builders + `runtime/runner_registry.py RUNNERS`), so the cycle adds **no new runtime fetch code** — only the FX-CFG-001 descriptor + a light per-connector go-live eval.
- The PR #103 purple-team hardening is in the **shared** path (`poll_client`/`graphql_poll`/`GatewaySink`/`pipeline`), so all four **already inherit** the SSRF no-follow, per-leaf screen, RecursionError, host-pin, and aggregate-cap fixes; the 30 Red Team gates already cover that shared surface. Per-connector residual security work is therefore small.
- `anthropic_admin` / `openai_admin` are **deliberately excluded** — their envelope + page-token wire details are UNVERIFIED in `poll_specs.py` (lines 67, 106-107); they carry more pre-Live verification debt and belong in a later cycle.

## In scope

1. Author `connectors/<id>/config.json` (FX-CFG-001) for copilot, granola, servicenow, cursor.
2. Regenerate `connectors/index.json` + each `SETUP.md` (generators; never hand-edit).
3. Per-connector light go-live eval (see checklist) + lift each `references.md` readiness line to flip-ready.
4. **Enable `noisy_source_gate`** in the operator live-config example + document the operator knob + a regression test that it gates as designed.
5. Ledger seal + governance-gate green + full suite green, to the Review Boundary.

## Out of scope

- The actual Live flip (operator: real secrets + live network + review).
- The other connectors; building any of the 10 manifest-only mods (Codex track).
- `anthropic_admin` / `openai_admin` (verification debt).
- Per-user PII surfaces explicitly deferred upstream (copilot per-user NDJSON; granola beyond notes/transcript).

## Per-connector spec

| Connector | Credential (key / type / wire) | runtime_config keys | PII posture | Contract status | Risk |
|---|---|---|---|---|---|
| **copilot** | `copilot` / api_key / `Authorization: Bearer` (+ `Accept`, `X-GitHub-Api-Version`); scope read:org | `base_url` (org-templated `…/orgs/<org>/copilot/metrics`, **required**), `api_version` (default 2022-11-28), `per_page` (default 100) | **PII-free** aggregate metrics (per-user NDJSON deferred) | **Verified** docs.github.com 2026-06-08 (page/per_page, max 100, 100-day lookback) | L1 |
| **granola** | `granola` / api_key / `Authorization: Bearer` | `base_url` (default `public-api.granola.ai/v1/notes?include=transcript`) | **Transcript PII-dense** — confirm redaction posture (FX-SEC-001 screen vs redact-and-pass) in-cycle | **Verified** docs.granola.ai 2026-06-08 (cursor `cursor`/`hasMore`) | L1 |
| **servicenow** | `servicenow` / basic / Basic (password=secret; **username is non-secret runtime**) | `instance` (**required**, host-validated), `username` (**required**), `limit` (default 100), `fields` (optional) | redact-and-pass (scrubs secret/PHI/PAN + email/phone) | Documented Table-API + offset pagination; **SSRF-4 host-pin already fixed (#103)** | L1 |
| **cursor** | `cursor` / basic / Basic (API key as username, empty password) + `Content-Type: application/json` | `base_url`, `body` (date-range POST) | PII-dense rows; **parse-time allowlist** (drops email/name, surfaces opaque `userId`) | **VERIFICATION DEBT** — host `api.cursor.com` *inferred*; POST body field names + envelope `data` **UNVERIFIED** (`poll_specs.py:179-199`). `auth.md` over-claims "verified". | **L2** |

## Verification debt → required `/qor-research` (verify-before-cite, SG-2026-06-04-N/SG-2026-06-11-A)

- **cursor (blocking for its descriptor):** confirm against live cursor.com/docs — (a) the host (`api.cursor.com`?), (b) the `POST /teams/daily-usage-data` request body field names/units, (c) the response envelope key. Until confirmed, cursor's `config.json` references/instructions must NOT assert these as fact (carry as `wire_gates`). If verification fails or is inaccessible, **split cursor into its own follow-on sub-cycle** and ship copilot/granola/servicenow first.
- **granola:** confirm the redaction posture (does the transcript path go through `redact()` redact-and-pass, or rely on the FX-SEC-001 screen?) and reflect it accurately in `data.pii_posture` + `data.redaction`.
- copilot, servicenow: contracts adequately verified; descriptor may cite them.

## noisy_source_gate enablement scope

- Already **built + runner-wired** (`mods/noisy_source_gate/connector.py`, `runner_registry._MODS`); no build needed.
- Add it (enabled) to the operator live-config example (`config/bicameral.example.json` mods block) so the first live stream is signal-gated; document the operator on/off knob in `docs/CONNECTOR_BACKEND_SETUP.md` (or the runbooks).
- Add a behavioral regression test (in `tests/redteam/` or `mods/noisy_source_gate/tests/`) asserting it gates a noisy/low-value emission and passes a high-value one (invoke `run_mod`, assert output) — lock the go-live behavior.

## Per-connector go-live eval checklist (light — shared path already hardened)

For each connector confirm (most are inherited from #103):
- [ ] `config.json` passes `validate_connector_config.py` (id==folder==source_id; modes ⊆ capabilities; credential modes; instructions[].ref; index + SETUP fresh).
- [ ] Credential never on the wire / never logged (inherited: `GatewaySink`/resolver discipline).
- [ ] PII posture in the descriptor matches the connector's actual parse (per-connector — the one real review item; e.g. granola transcript, cursor allowlist).
- [ ] No connector-specific parse crash on a hostile 200 (most covered by shared guards; confirm any connector-local walk).
- [ ] `wire_gates` record any UNVERIFIED wire fact (cursor especially) + the operator live-test step.

## Success criteria

- 4 `config.json` valid; `index.json` + 4 `SETUP.md` regenerated (byte-exact fresh); `validate_connector_config.py` exit 0.
- Each `references.md` readiness lifted to flip-ready, NOT yet Live; `wire_gates` capture residual verification (esp. cursor).
- `noisy_source_gate` enabled in the example config + documented + regression-tested.
- Full suite green (incl. `tests/redteam`); ruff/mypy/bandit/governance-gate/connector-config green.
- NO change under `runtime/`/`adapter/` fetch code (descriptors + docs + mod-config only); per-connector parse code only if a go-live eval finds a real connector-specific gap.

## Sequencing (proposed)

1. `/qor-research` — cursor live-contract verification (+ granola redaction posture confirm).
2. `/qor-plan` — the 4 descriptors + mod enablement (cursor descriptor gated on step 1; split out if unverified).
3. `/qor-audit` → PASS.
4. `/qor-implement` — author descriptors, regenerate, enable mod, tests.
5. `/qor-substantiate` — seal to Review Boundary.

## Open questions / decision log

- **Q (cursor):** if live Cursor docs are inaccessible to the cycle, ship copilot/granola/servicenow (L1) and defer cursor to a verification sub-cycle? **Default: yes** (don't block 3 verified connectors on 1 unverified). Confidence: high.
- **Q (servicenow `username`):** non-secret operator config in `runtime_config` (not a credential) — confirms the descriptor models it as runtime, password as the only `credentials` entry. Confidence: high (matches `build_servicenow_spec` signature).
- **Q (mod default-on):** enable `noisy_source_gate` by default in the example config, or document-as-opt-in? **Default: enabled in example + documented knob** (signal hygiene is the go-live value). Confidence: medium — confirm with operator at cycle handoff.
