# Research Brief — gitlab + sentry + pagerduty purple-team

**Date**: 2026-06-13
**Analyst**: The Qor-logic Analyst (purple-team workflow `wf_1b274b00`, 5 agents: red penetration-tester → blue security-auditor → per-target verdict)
**Target**: the webhook-trio flips (gitlab #174, sentry #176, pagerduty #177) — the deferred adversarial pass.
**Method**: per connector, a red agent attacked across its attack classes (parse_robustness, pii_on_wire, identity_minimization, webhook_replay/signature, descriptor_accuracy, em_safe_contract); each finding blue-verified against source, with every "reaches the wire" claim traced to the real serializer (`emission_to_ingest_request`, SG-2026-06-13-C).

---

## Executive Summary

**All three connectors = approved-with-fixes; ZERO blocked.** 2 findings confirmed — **both on gitlab**
(sentry: 0, pagerduty: 0). The redact-and-pass fixes from the flips hold; FX-SEC-001 (now incl. `source_ref.kind`)
is intact; all three are read-only; the three signature verifiers (`verify_shared_token`, `verify_hmac_hex`,
`verify_hmac_hex_multi`) are sound (constant-time, fail-closed, correct raw-body / multi-sig membership). **sentry
and pagerduty were built with the mature isinstance-unwrap + body-hash-dedup-fallback patterns and cleared with
no findings; gitlab predates both** and is the lone connector still missing them.

| Connector | Findings | Verdict |
|---|---|---|
| **gitlab** | 2 (both medium) | approved-with-fixes |
| **sentry** | 0 | approved-with-fixes (clean) |
| **pagerduty** | 0 | approved-with-fixes (clean) |

## Findings (blue-verified + boundary-checked, file:line)

### gitlab
1. **GITLAB-001 — parse_robustness (medium; boundary: mod-input)** — `connectors/gitlab/connector.py:46-47,61`
   `_event_observation` floors only *falsy* nested containers: `attrs = payload.get("object_attributes") or {}`,
   `(payload.get("project") or {}).get(...)`, `(payload.get("user") or {}).get(...)`. A **truthy non-dict**
   (`"object_attributes": "oops"` — provider drift / a validly-token'd hostile body) makes `attrs` a `str`, and
   line 48 `attrs.get("iid")` raises `AttributeError`. `observations()` dispatch (`:106`) and `normalize_event`
   (`:127`) do not catch it, so it propagates out of the webhook path (single-delivery failure). This is exactly
   the fathom `default_summary` class (#164) and the sibling **jira already isinstance-guards** this. Fix:
   `attrs = payload.get("object_attributes"); attrs = attrs if isinstance(attrs, dict) else {}` (and the same for
   `project` + `user`). Reachable only by a holder of the valid `X-Gitlab-Token` (signed) — provider drift, not
   external forgery; boundary is mod-input/availability, not a wire leak.
2. **GITLAB-002 — webhook_replay (medium; boundary: v1-gateway-wire)** — `connectors/gitlab/connector.py:132-137`
   `normalize_event` dedup is guarded `if delivery_id and self._dedup.is_duplicate(...)`, and `_delivery_id`
   returns `""` when `X-Gitlab-Event-UUID` is absent — so a **UUID-less replay bypasses dedup entirely** and
   emits a **duplicate evidence record to the gateway** (the duplicate emission's title/excerpt DO reach the v1
   wire). Every sibling (jira/sentry/pagerduty/zendesk) has the platform-documented **body-hash fallback**;
   gitlab is the lone omission. Fix: `delivery_id = self._delivery_id(headers) or hashlib.sha256(body).hexdigest()`
   then dedup unconditionally (drop the `if delivery_id and` guard); `import hashlib`; correct the
   config.json/auth.md disclosure to state the body-hash fallback. Re-verify with a UUID-less double-delivery
   collapsing to one emission (MEASURE the fix — SG-2026-06-05-F).

### sentry — clean
No confirmed findings. `parse_issue` isinstance-guards the `data.issue` unwrap + bare-issue fallback; title +
culprit redact-and-passed; opaque shortId/id floor; the full stack trace / event body is genuinely never read;
`verify_hmac_hex` over the raw body is sound; dedup has the `Request-ID → issue.id → body-hash` fallback.

### pagerduty — clean
No confirmed findings. `parse_event` isinstance-guards both the `event` and nested `data` unwraps; title/summary
redact-and-passed; opaque id floor; no actor surfaced; `verify_hmac_hex_multi` correctly accepts-if-any `v1=`
candidate matches, rejects bare/empty `v1=`, constant-time fail-closed; dedup has the `event.id → body-hash`
fallback; the config.json honestly records the SG-2026-06-13-D SPA-fetch limitation.

## Recommendations (one governed remediation cycle after this brief; modular-commit → PR → merge-if-green)

1. **PT-gitlab — parse-robustness + dedup parity (both findings, gitlab only):** isinstance-guard
   `object_attributes`/`project`/`user` in `_event_observation` (GITLAB-001, jira pattern); add the
   `hashlib.sha256(body).hexdigest()` dedup fallback + drop the id-guard in `normalize_event` (GITLAB-002, the
   sibling pattern) and correct the config.json/auth.md disclosure. Regression tests: a truthy non-dict
   `object_attributes`/`project`/`user` normalizes (no raise); two UUID-less identical deliveries collapse to one
   emission. Bring gitlab to the sibling-webhook standard.

## Updated Knowledge (Shadow Genome)

- (Reinforces **SG-2026-06-12-B**: sweep ALL siblings when hardening a shared surface — the *inverse* showed here:
  sentry/pagerduty inherited the mature isinstance-unwrap + body-hash-dedup patterns and cleared clean, while the
  older gitlab connector, written before those patterns were standard, carried both gaps. When a connector
  predates a now-standard defensive pattern, audit it against its *siblings*, not just its own contract.)

---

_Recon complete. Webhook trio cleared with two medium fixes on gitlab only (parse robustness + dedup parity);
sentry + pagerduty clean. EM-safe + read-only + ADR-0012 + the sound signature-verify cores all hold._
