<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Jira — backend setup

Jira Cloud issue webhook events as redact-and-pass governed evidence.

- **id** `jira` · **category** project-management · **trust tier** T1
- **status** live-ready · **available** True · **modes** webhook

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `jira_webhook` — Webhook signing secret (webhook_secret, required)
- Wire format: `X-Hub-Signature (sha256= hex HMAC-SHA256 over the raw body, WebSub)`
- Serves run mode(s): `webhook`
- **Note:** webhook-*receive* path only — **NOT** consumed by `runtime.cli run` (the active fetch uses the API credential).
- Supply via config key `jira_webhook` **or** env `BICAMERAL_JIRA_WEBHOOK` (env wins when set).
- Where to get it: https://developer.atlassian.com/server/jira/platform/webhooks/
  - When you create the Jira webhook, set a Secret (classic webhooks sign with it).
  - Copy it — Bicameral verifies X-Hub-Signature (hex HMAC-SHA256, sha256= prefix) over the raw body, constant-time, fail-closed.

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "jira": {
      "enabled": true,
      "secrets": {
        "jira_webhook": "<Webhook signing secret>"
      }
    }
  }
}
```
## Webhook setup

- Signature scheme: hex HMAC-SHA256 over the raw request body (X-Hub-Signature, sha256= prefix, WebSub) (header `X-Hub-Signature`).
- Events: `jira:issue_created`, `jira:issue_updated`, `jira:issue_deleted`
- Bicameral webhook receiver URL (operator-provisioned) — **you provision this inbound URL** (provisioned_by: operator) and register it at the provider.
  - In Jira (system or app webhooks), create a webhook on Issue created/updated/deleted with a Secret.
  - Set its URL to your Bicameral webhook receiver (see receiver below).

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run jira                 # fetch -> print screened emissions
python -m runtime.cli run-mods jira --mods dependency_risk
python -m runtime.cli run jira --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: issue
- PII posture: Title/excerpt come from issue.fields.summary (a string), passed through adapter.core.redaction.redact (redact-and-pass: scrubs secret/PHI/PAN + email/phone). fields.description is an Atlassian Document Format OBJECT and is NEVER read. The issue actor's displayName (a real name) is NOT surfaced (author dropped, PII-safe). FX-SEC-001 is the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + X-Hub-Signature verify + best-effort dedup are built and harness-proven; summary redact-and-passed, ADF description never read, actor identity dropped. Gated on operator review + a live signed delivery with a real webhook secret + a provisioned receiver. To flip: create the webhook + secret + receiver; wire GatewaySink; send a signed test delivery; review before promoting.

- Gate: Webhook path built + verified: X-Hub-Signature (sha256= hex HMAC-SHA256, constant-time, fail-closed). Jira documents NO anti-replay window, so best-effort dedup (X-Atlassian-Webhook-Identifier -> issue.id -> body-hash) is the only replay guard. summary redact-and-passed; ADF description never read.
- Gate: The ACTIVE REST fetch is in capabilities but NOT wired this cycle; Connect-JWT / Forge / Automation auth are deferred -- the classic signed webhook is the ingest path.
- Gate: Webhook RECEIPT is operator-runtime (receiver URL + jira_webhook injection). Live flip gated on operator review + a signed live delivery (ADR-0012).

## References

- webhook: https://developer.atlassian.com/cloud/jira/platform/webhooks/
- api: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
