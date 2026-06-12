# Research Brief — gitlab + sentry + pagerduty flip-ready

**Date**: 2026-06-13
**Analyst**: The Qor-logic Analyst
**Target**: the webhook-trio batch queued for the live/flip-ready lane — `gitlab`, `sentry`, `pagerduty` —
assessed against the FX-CFG-001 descriptor contract + the flip-ready PII/security standard set by the
github/jira/slack/zendesk webhook exemplars.
**Method**: verify-before-cite (SG-2026-06-12-A) — each webhook signature scheme re-verified against its live
provider docs before assessment; flip-ready gap analysis; PII/identity review of each `connector.py` parse surface.

---

## Executive Summary

All three are **Beta, end-to-end harness-proven webhook connectors, missing only the FX-CFG-001 descriptor**
(`config.json` + generated `SETUP.md`) and the **redact-and-pass parity** the github exemplar already has. The
signature schemes are **clean — zero drift on the supported path**: GitLab's plaintext `X-Gitlab-Token`, Sentry's
hex-HMAC `Sentry-Hook-Signature`, and PagerDuty's `v1=` multi-signature `X-PagerDuty-Signature` all re-verified
and match the built verify functions. The flip work is descriptor authoring + the **one shared PII fix**: the
free-text title/body/error-detail/incident-title is emitted with NO `redact()`, exactly the gap github closed.

| Connector | Sig drift | Code hardening | Descriptor | Effort |
|---|---|---|---|---|
| **gitlab** | none (legacy + future-signing both documented) | redact-and-pass body+title (F1); keep public username (F2) | new | medium |
| **sentry** | none (hex-HMAC over raw body verified) | redact-and-pass title+culprit (F1) | new | medium |
| **pagerduty** | none (v1= multi-sig verified; header live-confirmed) | redact-and-pass title/summary (F1) | new | medium |

## Contract Verification (verify-before-cite, SG-2026-06-12-A)

### gitlab — `X-Gitlab-Token`: VERIFIED, no drift
- **Live source**: [docs.gitlab.com/user/project/integrations/webhooks](https://docs.gitlab.com/user/project/integrations/webhooks/)
  — the **secret token** is sent verbatim in the `X-Gitlab-Token` header (a plaintext shared secret, GitLab's
  documented legacy method, "not recommended for new webhooks"); the newer **signing token** computes an
  HMAC-SHA256 over `{message_id}.{timestamp}.{body}` and is delivered as `webhook-signature: v1,{base64}` (the
  Svix Standard-Webhooks scheme `fathom` already uses).
- **As built**: `connectors/gitlab/connector.py:108-116` `verify()` → `verify_shared_token` (constant-time
  plaintext equality, fail-closed) on `X-Gitlab-Token`. **MATCHES** the documented legacy method; the docstring
  already names the HMAC signing-token as a future enhancement. No drift — the descriptor will state the
  plaintext path is built and the HMAC signing-token is the documented next step.

### sentry — `Sentry-Hook-Signature`: VERIFIED, no drift
- **Live source**: [docs.sentry.io/.../integration-platform/webhooks](https://docs.sentry.io/organization/integrations/integration-platform/webhooks/)
  — `Sentry-Hook-Signature` = **hex HMAC-SHA256** over the body, signed with the integration **Client Secret**.
- **As built**: `connectors/sentry/connector.py:96-106` `verify()` → `verify_hmac_hex` over the **RAW body**.
  **MATCHES.** Note: Sentry's doc example signs `JSON.stringify(body)`; the connector verifies the **raw received
  bytes** — the more robust choice (re-serialization risks key-order/whitespace drift). Correct, no drift.

### pagerduty — `X-PagerDuty-Signature`: VERIFIED (header live-confirmed; format from harness-proven contract)
- **Live source**: [support.pagerduty.com/main/docs/webhooks](https://support.pagerduty.com/main/docs/webhooks)
  confirms V3 introduces the `x-pagerduty-signature` header. The dedicated signature-format page
  ([developer.pagerduty.com/docs/webhooks/webhook-signatures](https://developer.pagerduty.com/docs/webhooks/webhook-signatures/))
  is a JS SPA that renders **empty to fetch** this cycle (limitation recorded — SG-2026-06-13-D).
- **As built**: `connectors/pagerduty/connector.py:93-103` `verify()` → `verify_hmac_hex_multi`: a comma-separated
  `v1=<hex>,v1=<hex>` set (zero-downtime key rotation), accept if **ANY** `v1=` candidate HMAC-SHA256 matches the
  raw body, constant-time, fail-closed (`adapter/core/webhook_security.py:105-125`). The header name is
  live-confirmed; the `v1=` hex-HMAC membership scheme matches the connector's harness-proven verified-contract
  record (references.md, 2026-06-05) and the well-documented PagerDuty v3 scheme. No drift on the supported path.

## Flip-Ready Gap & Findings (file:line)

**Shared root (all three): the free-text excerpt/title is emitted with NO `redact()`** — FX-SEC-001 backstops
only secret/PHI/PAN, so an email/phone in a PR description, a Sentry error message, or a PagerDuty incident title
reaches the evidence stream un-scrubbed. github/jira/slack/zendesk already redact-and-pass this exact surface;
the trio simply hasn't been brought to parity. Redaction is non-destructive — pure upside.

### gitlab
- **Gap**: no `connectors/gitlab/config.json` / `SETUP.md`.
- **F1 — pii_on_wire (medium)** — `connector.py:44-45,53` MR/issue `title` + `description` emitted raw. Fix:
  mirror github exactly — `title = redact(_text(...))`, `excerpt = redact(body) or title or floor`.
- **F2 — identity_minimization (KEEP + document)** — `connector.py:56` `author = user.username` is a **public
  GitLab handle** (the artifact author), the kept-public-login precedent github set (`author=user.login`,
  un-redacted) — a public handle is the attribution signal, not incidental PII (SG-2026-06-13-B). Retain; state
  it honestly in the descriptor. (Reads only `username`, not name/email.)

### sentry
- **Gap**: no `connectors/sentry/config.json` / `SETUP.md`.
- **F1 — pii_on_wire (medium)** — `connector.py:46-47,53,55` `title` + `culprit` emitted raw. A Sentry issue
  title is the **exception message** (and culprit = a code frame) — error messages routinely embed connection
  strings, emails, tokens. Fix: redact-and-pass `title` + `culprit` (keep the `shortId`/`iid` floor un-redacted —
  it is an opaque id). The connector reads only title/culprit/shortId, NOT the full stack trace or event body —
  good data minimization already; the fix closes the inline-PII-in-title residual. No author field (good).

### pagerduty
- **Gap**: no `connectors/pagerduty/config.json` / `SETUP.md`.
- **F1 — pii_on_wire (medium)** — `connector.py:46,51,53` incident `title`/`summary` emitted raw; an incident
  title can carry customer PII ("High latency for jane@acme.com"). Fix: redact-and-pass `title`/`summary` (keep
  the `iid` floor un-redacted). No actor/assignee surfaced (good — only event_type/status/urgency in metadata).

## Recommended Descriptor Shapes (for /qor-auto-dev-1)

- **gitlab** — `modes:["webhook","active"]`; credentials `gitlab_webhook` (`webhook_secret`, plaintext
  `X-Gitlab-Token`, `modes:["webhook"]`) + the deferred active REST token (`api_key`, `modes:["active"]`,
  `required:false`, `wiring_oversight:true`); `webhook` block (signature_scheme = plaintext `X-Gitlab-Token`
  shared secret, with the HMAC signing-token named as the documented next step; header `X-Gitlab-Token`; setup +
  operator receiver); `data.emits:["merge_request","issue"]`; pii_posture: redact-and-pass body+title, public
  username retained; `instructions`: `register_webhook` + `paste_secret` + `verify`.
- **sentry** — `modes:["webhook"]`; credential `sentry_webhook` (`webhook_secret` = integration Client Secret,
  `modes:["webhook"]`); `webhook` block (`Sentry-Hook-Signature` hex HMAC-SHA256 over the raw body; header; setup
  + receiver); `data.emits:["issue"]`; pii_posture: redact-and-pass title+culprit, full stack trace not read, no
  author; `instructions`: `register_webhook` + `paste_secret` + `verify`.
- **pagerduty** — `modes:["webhook"]`; credential `pagerduty_webhook` (`webhook_secret`, `modes:["webhook"]`);
  `webhook` block (`X-PagerDuty-Signature` `v1=` multi-signature HMAC-SHA256 membership over the raw body, no
  replay window → dedup; header; setup + receiver); `data.emits:["incident"]`; pii_posture: redact-and-pass
  title/summary, no actor surfaced; `instructions`: `register_webhook` + `paste_secret` + `verify`.

## Recommendations (one /qor-auto-dev-1 cycle per connector, then a /qor-deep-audit purple-team)

1. **gitlab** — redact-and-pass body+title (F1), author config.json (webhook+active), regen, references.md PII
   line, regression tests (email/secret in description scrubbed; public username retained; floor un-mangled).
2. **sentry** — redact-and-pass title+culprit (F1), author config.json (webhook), regen, regression tests
   (secret/email in error title scrubbed; opaque shortId floor un-redacted).
3. **pagerduty** — redact-and-pass title/summary (F1), author config.json (webhook), regen, regression tests
   (email in incident title scrubbed; iid floor un-redacted).
4. After all three substantiate → **/qor-deep-audit purple-team** (red→blue→verdict) across parse_robustness,
   pii_on_wire (verify impact against the real gateway serializer — SG-2026-06-13-C), identity_minimization,
   webhook_replay/signature (per-provider scheme), descriptor_accuracy, em_safe_contract; remediate; tag
   @jinhongkuan.

## Updated Knowledge (Shadow Genome)

- **SG-2026-06-13-D** — *when a provider's canonical signature doc is a JS-SPA that renders empty to fetch,
  record the fetch limitation and fall back to (a) the provider's static support mirror for the header name +
  (b) the connector's harness-proven verified-contract record + verify-fn consistency — do NOT silently claim a
  live re-verify you could not perform.* PagerDuty's `developer.pagerduty.com/docs/webhooks/webhook-signatures`
  fetched empty this cycle; the `x-pagerduty-signature` header was confirmed via `support.pagerduty.com`, and the
  `v1=` HMAC membership scheme via the connector's references.md (2026-06-05) + `verify_hmac_hex_multi`. State
  the provenance of each verified claim honestly. (Reinforces SG-2026-06-12-A.)
- (Reinforces **SG-2026-06-13-A**: the redact-and-pass parity gap is transport-agnostic — these are webhook
  free-text surfaces, the same omission the local/passive connectors had.)

---

_Research complete. Zero signature drift across all three; flip work is descriptor authoring + the one shared
redact-and-pass parity fix (the github standard). Findings are advisory — implementation decisions remain with
the Governor. EM-safe + read-only boundary + ADR-0012 hold._
