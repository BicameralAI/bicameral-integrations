# Research Brief

**Date**: 2026-06-04
**Analyst**: The Qor-logic Analyst
**Target**: Connector hardening — wire **live webhook signature verification + replay dedup** into the Sentry and PagerDuty connectors, extending `adapter/core/webhook_security.py`.
**Scope**: Confirm the exact signature schemes (L3, fail-closed, constant-time) and map them onto the existing `verify_*`/`DeliveryDedupCache` primitives + the Linear/Fathom `verify()`/`normalize_event()` wiring pattern. Sources: official docs + cross-verified third parties (cited inline), per-fact verified/uncertain.

---

## Executive Summary

Both schemes are HMAC-SHA256-hex over the **raw request body**, fail-closed, constant-time-compared. **Sentry** is a single signature (`Sentry-Hook-Signature`) → reuses the existing `verify_hmac_hex` primitive **with body = raw received bytes** (operator decision; the JS reference's `JSON.stringify(request.body)` is the wire JSON, not a re-serialization we should perform). **PagerDuty** is a comma-separated `v1=<hex>,v1=<hex>` rotation set (`X-PagerDuty-Signature`) → needs a **new `verify_hmac_hex_multi` primitive** (membership: accept if ANY `v1=` candidate matches). **Neither provider documents a timestamp/anti-replay window**, and **neither guarantees a per-delivery id header** — so replay mitigation is the dedup cache (best-effort: dedup only when a delivery id is derivable; never drop a legitimate event for lacking one). This is weaker than Linear's 60s window and must be documented honestly, not papered over.

## Findings

### F1 — Sentry `Sentry-Hook-Signature` (single hex HMAC; SG-2026-06-04-A axis: scheme confirmed)
HMAC-SHA256, hex, over the request body, keyed by the integration **Client Secret**; single signature, **no rotation**, **no documented replay window** [verified: docs.sentry.io integration-platform webhooks]. **Sharp edge (fail-open trap):** the official JS reference signs `JSON.stringify(request.body)` — for L3 we HMAC the **raw received bytes** (operator decision) to avoid serializer-mismatch; flag in `auth.md` + cover with a fixture test. Maps to the existing `verify_hmac_hex(header_sig, body, secret)` unchanged. Dedup id: `Request-ID` header exists but is `[uncertain]` as a dedup key → best-effort.

### F2 — PagerDuty `X-PagerDuty-Signature` (multi-sig membership; needs new primitive)
HMAC-SHA256, hex, over the raw body, keyed by the subscription **signing secret**; header is a **comma-separated list of `v1=<hex>`** for zero-downtime rotation [verified: support.pagerduty.com + cross-verified]. **Accept if ANY candidate matches; reject otherwise** — constant-time. No documented replay window; no verified per-delivery id header (`X-Webhook-Subscription` identifies the subscription, not the delivery) → dedup on the envelope `event.id`, best-effort `[uncertain]`. First-party `developer.pagerduty.com/docs/verifying-signatures` is JS-rendered and was not directly fetched — cross-verified from support docs + ngrok + convoy; **recommend a human spot-check before relying in production**.

### F3 — Mapping onto existing primitives
- Sentry: reuse `verify_hmac_hex` (raw body). New `SentryConnector.verify()/normalize_event()` mirroring Linear, minus the timestamp window (none documented).
- PagerDuty: add `verify_hmac_hex_multi(*, header_sig, body, secret)` to `webhook_security` (split `,` → strip `v1=` → expected hex HMAC → `any(compare_digest)`; fail-closed on empty secret / missing header / no `v1=` candidate / no match). New `PagerDutyConnector.verify()/normalize_event()`.
- Dedup: reuse `DeliveryDedupCache`; **best-effort** (process when no delivery id — do NOT drop, unlike Linear which is guaranteed an id).
- Replay: documented limitation — no provider timestamp window for either; dedup TTL is the only replay guard.

### F4 — Fail-closed discipline (SG-2026-06-04-B)
Every attacker-input path raises `WebhookVerificationError`, caught by `verify()` → `False`: missing/empty secret, missing/empty/malformed header, no `v1=` entry (PagerDuty), no match, non-UTF8 body on JSON parse. `verify()` runs BEFORE parsing; `normalize_event()` self-guards (re-verifies) then dedups then parses. Constant-time compare throughout.

## Blueprint Alignment

| Claim | Finding | Status |
|---|---|---|
| Don't share one verifier blindly (SG-A) | Sentry single-sig vs PagerDuty multi-sig — distinct paths | MATCH |
| Fail-closed on every attacker path (SG-B) | all failure modes raise WebhookVerificationError | MATCH |
| Reuse the webhook_security primitives | Sentry reuses verify_hmac_hex; PagerDuty adds one primitive | MATCH |
| Honest about limitations | no replay window + best-effort dedup documented, not hidden | MATCH |

No DRIFT. Open item: PagerDuty first-party signature page human spot-check.

## Recommendations

1. **[P0] `/qor-plan` at L3** — add `verify_hmac_hex_multi`; wire Sentry (raw-body single-sig) + PagerDuty (multi-sig) `verify()`/`normalize_event()`; best-effort dedup; no fabricated replay window.
2. **[P1] Document limitations** in each `auth.md`: Sentry JSON.stringify sharp edge + no replay window; PagerDuty multi-sig + no replay window + no guaranteed delivery id + first-party spot-check pending.
3. **[P1] Mandatory devil's-advocate fail-open pass** before seal (SG-B history).

## Updated Knowledge

Reinforces SG-2026-06-04-A (per-provider scheme divergence — Sentry single vs PagerDuty multi-sig) and SG-2026-06-04-B (fail-closed every path). New nuance: when a provider guarantees no per-delivery id, dedup must be **best-effort** (process-on-missing), never fail-closed-drop — dropping legitimate events is its own defect.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
