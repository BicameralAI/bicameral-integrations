<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Slack — backend setup

Slack message events as redact-and-pass governed evidence (read/ingest).

- **id** `slack` · **category** communication · **trust tier** T2
- **status** live-ready · **available** True · **modes** webhook

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `slack_webhook` — Slack signing secret (webhook_secret, required)
- Wire format: `X-Slack-Signature (v0= hex HMAC-SHA256 over 'v0:{timestamp}:{raw_body}') + X-Slack-Request-Timestamp`
- Serves run mode(s): `webhook`
- **Note:** webhook-*receive* path only — **NOT** consumed by `runtime.cli run` (the active fetch uses the API credential).
- Supply via config key `slack_webhook` **or** env `BICAMERAL_SLACK_WEBHOOK` (env wins when set).
- Where to get it: https://api.slack.com/authentication/verifying-requests-from-slack
  - In your Slack app's Basic Information, copy the Signing Secret.
  - Bicameral verifies X-Slack-Signature (v0= HMAC-SHA256 over 'v0:{ts}:{body}') with a 5-minute replay window, constant-time, fail-closed.

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "slack": {
      "enabled": true,
      "secrets": {
        "slack_webhook": "<Slack signing secret>"
      }
    }
  }
}
```
## Webhook setup

- Signature scheme: v0= hex HMAC-SHA256 over 'v0:{X-Slack-Request-Timestamp}:{raw_body}', 5-minute replay window (header `X-Slack-Signature`).
- Events: `message`
- Bicameral webhook receiver URL (operator-provisioned) — **you provision this inbound URL** (provisioned_by: operator) and register it at the provider.
  - Create a Slack app, enable Event Subscriptions, subscribe to message events.
  - Set the Request URL to your Bicameral webhook receiver (see receiver below); the url_verification handshake is handled.

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run slack                 # fetch -> print screened emissions
python -m runtime.cli run-mods slack --mods dependency_risk
python -m runtime.cli run slack --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: message
- PII posture: Message text is PII-dense human communication -> passed through adapter.core.redaction.redact (redact-and-pass: scrubs secret/PHI/PAN + email/phone). author is the OPAQUE Slack user id (e.g. U0123ABC) -- pseudonymous (the operator holds the id->identity mapping; SG-2026-06-05-D), not a name/email. FX-SEC-001 is the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + X-Slack-Signature verify (v0, 5-min replay) + handshake/dedup are built and harness-proven; message text redact-and-passed, opaque user id surfaced. Gated on operator review + a live signed event with a real signing secret + a provisioned receiver. To flip: create the app + signing secret + Request URL receiver; wire GatewaySink; send a signed test event; review before promoting.

- Gate: Webhook path built + verified: X-Slack-Signature v0= HMAC-SHA256 over 'v0:{ts}:{body}' + 5-minute replay window (constant-time, fail-closed); url_verification handshake + unverified deliveries normalize to []. Message text redact-and-passed; opaque user id (pseudonymous) surfaced.
- Gate: Trust tier T2 (read/ingest). Notify/write (T3+) is deferred (ADR-0008, evidence-before-action).
- Gate: Webhook RECEIPT is operator-runtime (receiver URL + slack_webhook injection). Live flip gated on operator review + a signed live event (ADR-0012).

## References

- events-api: https://api.slack.com/apis/connections/events-api
- verify: https://api.slack.com/authentication/verifying-requests-from-slack
