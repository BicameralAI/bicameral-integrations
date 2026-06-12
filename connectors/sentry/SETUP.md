<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Sentry — backend setup

Sentry issue webhook events as redact-and-pass governed evidence (exception message + culprit scrubbed; full stack trace never read; no person attribution).

- **id** `sentry` · **version** 0.1.0 · **channel** beta · **category** observability/incident-evidence · **trust tier** T1
- **status** live-ready · **available** True · **modes** webhook

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `sentry_webhook` — Integration Client Secret (webhook_secret, required)
- Wire format: `Sentry-Hook-Signature (hex HMAC-SHA256 over the raw body, signed with the integration Client Secret)`
- Serves run mode(s): `webhook`
- **Note:** webhook-*receive* path only — **NOT** consumed by `runtime.cli run` (the active fetch uses the API credential).
- Supply via config key `sentry_webhook` **or** env `BICAMERAL_SENTRY_WEBHOOK` (env wins when set).
- Where to get it: https://docs.sentry.io/organization/integrations/integration-platform/webhooks/
  - Create an Internal/Public Integration in Sentry (Settings -> Developer Settings) and enable the Issue webhook; capture its Client Secret.
  - Bicameral verifies Sentry-Hook-Signature = hex HMAC-SHA256 over the raw body with that Client Secret, constant-time, fail-closed (verified 2026-06-13).

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "sentry": {
      "enabled": true,
      "secrets": {
        "sentry_webhook": "<Integration Client Secret>"
      }
    }
  }
}
```
## Webhook setup

- Signature scheme: Sentry-Hook-Signature = hex HMAC-SHA256 over the RAW request body, signed with the integration Client Secret; constant-time, fail-closed. Sentry documents no replay-timestamp window -> best-effort dedup (Request-ID header -> issue.id -> body-hash) is the replay guard. The connector verifies the raw received bytes (more robust than re-serializing the JSON, which risks key-order drift). (header `Sentry-Hook-Signature`).
- Events: `issue`
- Bicameral webhook receiver URL (operator-provisioned) — **you provision this inbound URL** (provisioned_by: operator) and register it at the provider.
  - In your Sentry Integration, subscribe to the Issue resource webhook.
  - Set the webhook URL to your Bicameral webhook receiver (see receiver below).

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run sentry                 # fetch -> print screened emissions
python -m runtime.cli run-mods sentry --mods dependency_risk
python -m runtime.cli run sentry --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: issue
- PII posture: The issue TITLE (the exception message) + CULPRIT (a code frame) are emitted via redact-and-pass -- secret/PHI/PAN + email/phone scrubbed to placeholders, because error messages routinely embed connection strings, emails, and tokens (FX-SEC-001 backstops only secret/PHI/PAN). The opaque shortId/id floor is NOT redacted. The FULL STACK TRACE / event body is never read (data minimization) and there is NO person attribution (no author field). FX-SEC-001 hard-screens secret/PHI/PAN as the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + hex-HMAC verify + dedup are built and harness-proven; issue title + culprit redact-and-passed, full stack trace never read, no person attribution. Gated on operator review + a live signed delivery. To flip: create the Sentry Integration + Issue webhook + Client Secret + a Bicameral receiver URL; wire GatewaySink; send a signed test delivery; review before promoting.

- Gate: Webhook signature re-verified live 2026-06-13 (docs.sentry.io integration-platform webhooks): Sentry-Hook-Signature = hex HMAC-SHA256 over the body with the integration Client Secret. Built verify_hmac_hex over the RAW received bytes MATCHES (more robust than the doc's JSON.stringify example -- avoids re-serialization key-order drift). No replay window -> dedup (Request-ID -> issue.id -> body-hash).
- Gate: PII: issue title (exception message) + culprit redact-and-passed (secret/PHI/PAN + email/phone); opaque shortId/id floor un-redacted; full stack trace / event body never read; no author. FX-SEC-001 backstops secret/PHI/PAN.
- Gate: Webhook RECEIPT + the REST issue fetch (active fallback) are operator-runtime; the REST fetch is DEFERRED this cycle (webhook is the built + verified path). Live flip gated on operator review + a signed live delivery (ADR-0012).

## References

- api: https://docs.sentry.io/api/
- webhooks: https://docs.sentry.io/organization/integrations/integration-platform/webhooks/
- webhook-issues: https://docs.sentry.io/organization/integrations/integration-platform/webhooks/issues/
