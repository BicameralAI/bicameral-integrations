<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# GitHub — backend setup

GitHub pull-request webhook events as redact-and-pass governed evidence.

- **id** `github` · **category** source-control · **trust tier** T1
- **status** live-ready · **available** True · **modes** webhook

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `github_webhook` — Webhook signing secret (webhook_secret, required)
- Wire format: `X-Hub-Signature-256 (sha256= hex HMAC-SHA256 over the raw body)`
- Serves run mode(s): `webhook`
- **Note:** webhook-*receive* path only — **NOT** consumed by `runtime.cli run` (the active fetch uses the API credential).
- Supply via config key `github_webhook` **or** env `BICAMERAL_GITHUB_WEBHOOK` (env wins when set).
- Where to get it: https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
  - When you create the repository (or org) webhook, set a Secret.
  - Copy it — Bicameral verifies X-Hub-Signature-256 (hex HMAC-SHA256, sha256= prefix) over the raw body, constant-time, fail-closed.

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "github": {
      "enabled": true,
      "secrets": {
        "github_webhook": "<Webhook signing secret>"
      }
    }
  }
}
```
## Webhook setup

- Signature scheme: hex HMAC-SHA256 over the raw request body (sha256= prefix) (header `X-Hub-Signature-256`).
- Events: `pull_request`
- Bicameral webhook receiver URL (operator-provisioned) — **you provision this inbound URL** (provisioned_by: operator) and register it at the provider.
  - In the GitHub repo/org settings, create a webhook subscribed to Pull request events (content type application/json).
  - Set its Payload URL to your Bicameral webhook receiver (see receiver below).

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run github                 # fetch -> print screened emissions
python -m runtime.cli run-mods github --mods dependency_risk
python -m runtime.cli run github --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: pull_request
- PII posture: PR title + body are free-text -> passed through adapter.core.redaction.redact (redact-and-pass: scrubs secret/PHI/PAN + email/phone). author is the PUBLIC PR-author login (the artifact author, like the kept pr_url precedent), not redacted. FX-SEC-001 is the un-bypassable backstop. X-GitHub-Delivery dedups replays.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + X-Hub-Signature-256 verify + dedup are built and harness-proven; PR body/title redact-and-passed. Gated on operator human review + a live signed delivery with a real webhook secret + a provisioned receiver. To flip: create the webhook + secret + receiver; wire GatewaySink; send a signed test delivery; review before promoting.

- Gate: Webhook path is built + verified: X-Hub-Signature-256 (sha256= hex HMAC-SHA256, constant-time, fail-closed) + X-GitHub-Delivery dedup + envelope unwrap (top-level number injected into the nested pull_request). PR body/title redact-and-passed.
- Gate: The ACTIVE REST fetch (GET pulls) is in the connector's capabilities but is NOT wired in the runtime this cycle -- webhook is the ingest path; an active poller is a future enhancement.
- Gate: Webhook RECEIPT is operator-runtime: provision the receiver URL + inject github_webhook into the receive path (the CLI runs active fetches, not webhook receipt). Live flip gated on operator review + a signed live delivery (ADR-0012).

## References

- webhook: https://docs.github.com/en/webhooks
- api: https://docs.github.com/en/rest/pulls/pulls
