# Research Brief

**Date**: 2026-06-04
**Analyst**: The Qor-logic Analyst
**Target**: Live webhook **signature verification + anti-replay + delivery dedup** for the `fathom` (Standard Webhooks / Svix) and `linear` (`Linear-Signature`) connectors, wired into the `adapter.core` `WebhookConnector` contract.
**Scope**: The security-critical, offline-testable slice of the live-connector work. Verifier crypto + dedup only; live HTTP server, secret/keyring resolution, and live REST/GraphQL polling remain in the operator runtime / a later credentialed cycle. Sources: the Standard Webhooks spec, Linear developer docs, `bicameral-mcp` webhook source (`file:line`), and the in-repo contract.

---

## Executive Summary

The verifier slice is fully buildable and testable offline — it is pure crypto over `(headers, body, secret)` plus a clock for anti-replay — and `bicameral-mcp` already ships the reference port targets: `webhooks/github.py::verify_signature` (constant-time HMAC, verify-before-parse, reject-empty-delivery-id, dedup-after-verify) and `webhooks/dedup.py::DeliveryDedupCache` (bounded partitioned LRU+TTL). The `adapter.core.contracts.WebhookConnector` protocol is `verify(*, headers, body: bytes) -> bool` + `normalize_event(*, headers, body: bytes) -> list[Observation]` — **no secret parameter**, so the secret must be **injected into the connector** (constructor), keeping keyring resolution out of scope. **This is an L3 (security-logic) cycle.** Two distinct signing schemes confirmed against primary sources: Fathom = Standard Webhooks/Svix (base64 over `id.timestamp.body`, `whsec_`-prefixed base64-decoded key, ±tolerance window), Linear = hex HMAC over the raw body with a 60s `webhookTimestamp` anti-replay window. No `adapter.core` contract change is required. No blocking gaps → research-complete; proceed to `/qor-plan` at L3.

## Findings

### F1 — The `WebhookConnector` contract (no secret param → inject the secret)
- `adapter/core/contracts.py`: `WebhookConnector(Connector, Protocol)` declares `verify(self, *, headers: dict[str, str], body: bytes) -> bool` and `normalize_event(self, *, headers: dict[str, str], body: bytes) -> list[Observation]`.
- The signature carries **no secret**; therefore the connector holds its signing secret (constructor injection) and `verify()` uses it. This keeps secret/keyring resolution deferred (operator runtime) while making `verify()` exercisable with a fixture secret.
- `normalize_event` is the verified-path bridge to the existing parse surface: verify → `json.loads(body)` → `parse_meeting` / `parse_event` → `[Observation]`. `FathomConnector`/`LinearConnector` already declare `WEBHOOK` in capabilities.

### F2 — Fathom = Standard Webhooks / Svix (primary source: standardwebhooks.com spec)
- Headers: `webhook-id` (unique id), `webhook-timestamp` (**unix seconds**), `webhook-signature` (a **space-delimited** list of `v1,<base64>` signatures — supports key rotation).
- Signed content: **`{webhook-id}.{webhook-timestamp}.{body}`** with full-stop delimiters; body is the exact raw payload.
- Secret: base64-encoded, prefixed `whsec_`; the portion **after** `whsec_` is **base64-decoded** to the raw HMAC key bytes.
- MAC: **HMAC-SHA256**, output **base64**-encoded; compare (constant-time) against each `v1,` signature in the header.
- Anti-replay: spec says verify `webhook-timestamp` is "within some allowable tolerance"; no fixed window prescribed — Svix's reference implementation uses **5 minutes (300 s)**. Adopt 300 s, configurable.

### F3 — Linear = `Linear-Signature` (primary source: linear.app/developers; prior brief F3 / SG-2026-06-03-J)
- Header `Linear-Signature` = **hex** HMAC-SHA256 of the **raw request body** with the webhook signing secret (no version prefix, no separate signed-content construction — the body alone is signed).
- Anti-replay: reject when `abs(now − webhookTimestamp) > 60000 ms` (`webhookTimestamp` is in the JSON body, **milliseconds**).
- Dedup key: `webhookId` (in the body).

### F4 — mcp port targets (don't reinvent)
- `bicameral-mcp/webhooks/github.py:verify_signature` — `hmac.new(secret, body, sha256).hexdigest()` + `hmac.compare_digest`; raises `WebhookVerificationError` on missing header / malformed prefix / **empty secret** (fail-closed) / mismatch. Discipline: **verify before parse**; reject empty delivery-id; **dedup only after verify** (so an attacker can't poison the cache with unverified ids).
- `bicameral-mcp/webhooks/dedup.py:DeliveryDedupCache` — bounded **partitioned LRU + TTL** (`max_entries`, `max_partitions`, `ttl_seconds=86400`), `threading.Lock`, `is_duplicate`/`mark_seen`. Port near-verbatim; the partition arg is unused for fathom/linear (globally-unique ids) but kept for parity.

### F5 — Testability + time dependence
- Verification is pure over `(headers, body, secret)` — deterministic. Anti-replay needs "now"; inject a **clock** (`now: float` param / callable, default `time.time`) so stale/in-window cases are deterministic in tests. The dedup cache is time-dependent only via TTL — tests use short TTLs or the injected clock.
- Out of scope (deferred, operator runtime): the live HTTP boundary (`bicameral-mcp/webhooks/server.py`), secret/keyring resolution, live REST/GraphQL polling.

## Blueprint Alignment

| Blueprint claim | Actual finding | Status |
|---|---|---|
| Active/passive/webhook modes (ADR-0006); `WebhookConnector` exists | Contract present; fathom/linear declare `WEBHOOK` | MATCH |
| Webhook verify/dedup deferred until live; inherit mcp HMAC+dedup (security brief HIGH-2; SG-I/J) | This cycle ports exactly that discipline | MATCH |
| Adapters are read-only, emit to gateway only | verify→normalize_event→`parse_*`→Observation; no canonical write | MATCH |
| `adapter.core` contract is provider-agnostic | Two schemes fit `verify(headers,body)->bool` with injected secret; no schema change | MATCH |

No DRIFT.

## Recommendations

1. **[P1] Proceed to `/qor-plan` at risk_grade L3** (security logic). `high_risk_target: false` (this verifies webhooks; it is not itself an Annex-III high-risk AI system) but include an `impact_assessment` given the security surface.
2. **[P1] Shared primitives in `adapter/core`**: port `DeliveryDedupCache` and add a verifier module (`verify_standard_webhook(...)` for Svix, `verify_hmac_hex(...)` for Linear). Connectors hold an injected `secret` + optional `clock`/`dedup` and implement `verify`/`normalize_event`.
3. **[P1] Fail-closed**: missing/empty secret, missing/malformed signature header, stale timestamp, or replay → `verify()` returns False (or raises a verification error the connector maps to False). Constant-time compare via `hmac.compare_digest` only.
4. **[P2] Exhaustive crypto fixtures**: per provider — valid signature passes; tampered body fails; wrong secret fails; stale timestamp (outside window) fails; replayed id fails on second delivery; key-rotation (two `v1,` sigs, one valid) passes for Svix.
5. **[P2] Verify-before-parse** and **dedup-after-verify** ordering is a binding sequence (filter-stage ordering); the plan must state it explicitly.

## Updated Knowledge

SHADOW_GENOME **SG-2026-06-04-A**: Standard Webhooks/Svix verification precisely (content `id.timestamp.body`, `whsec_` base64-decoded key, base64 HMAC-SHA256, space-delimited `v1,` sigs, ~300 s tolerance) vs Linear's hex-over-raw-body + 60 s ms-window — the two schemes differ in encoding (base64 vs hex), keyed content (constructed vs raw body), and timestamp unit (s vs ms). Inherit mcp's verify-before-parse + dedup-after-verify ordering.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
