<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Zendesk — backend setup

Zendesk support-ticket webhook events as redact-and-pass governed evidence (subject + body scrubbed; requester surfaced as an opaque id, never a name/email).

- **id** `zendesk` · **category** support / customer-success · **trust tier** T1
- **status** live-ready · **available** True · **modes** webhook, active

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `zendesk_webhook` — Webhook signing secret (webhook_secret, required)
- Wire format: `X-Zendesk-Webhook-Signature (base64 HMAC-SHA256 over {timestamp}{body}, companion X-Zendesk-Webhook-Signature-Timestamp)`
- Serves run mode(s): `webhook`
- **Note:** webhook-*receive* path only — **NOT** consumed by `runtime.cli run` (the active fetch uses the API credential).
- Supply via config key `zendesk_webhook` **or** env `BICAMERAL_ZENDESK_WEBHOOK` (env wins when set).
- Where to get it: https://developer.zendesk.com/documentation/webhooks/verifying/
  - Create the webhook in Zendesk Admin Center; Zendesk generates a per-webhook signing secret (a static test secret applies before creation).
  - Copy it — Bicameral verifies X-Zendesk-Webhook-Signature = base64(HMAC-SHA256(secret, timestamp + body)), constant-time, fail-closed (verified 2026-06-13).

### `zendesk` — API token (active REST poll — deferred) (api_key, optional)
- Wire format: `Authorization: Basic base64('{email}/token:{api_token}')`
- Serves run mode(s): `active`
- Supply via config key `zendesk` **or** env `BICAMERAL_ZENDESK` (env wins when set).
- Where to get it: https://developer.zendesk.com/api-reference/introduction/security-and-auth/
  - In Zendesk Admin Center, enable token access and create an API token (Apps and integrations -> APIs -> Zendesk API).
  - The active REST poll (/api/v2) is operator-runtime and DEFERRED this cycle; the webhook is the built + verified path. Wiring the token/OAuth exchange needs operator oversight.

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "zendesk": {
      "enabled": true,
      "secrets": {
        "zendesk_webhook": "<Webhook signing secret>",
        "zendesk": "<API token (active REST poll \u2014 deferred)>"
      }
    }
  }
}
```
## Webhook setup

- Signature scheme: base64 HMAC-SHA256 over '{timestamp}{body}' (no separator) with companion X-Zendesk-Webhook-Signature-Timestamp; constant-time; Zendesk documents no replay window, so best-effort dedup (envelope id -> detail.id -> body-hash) is the replay guard (header `X-Zendesk-Webhook-Signature`).
- Events: `ticket`
- Bicameral webhook receiver URL (operator-provisioned) — **you provision this inbound URL** (provisioned_by: operator) and register it at the provider.
  - In Zendesk Admin Center, create a webhook (and a trigger/automation that fires it on ticket events).
  - Set its endpoint URL to your Bicameral webhook receiver (see receiver below).

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run zendesk                 # fetch -> print screened emissions
python -m runtime.cli run-mods zendesk --mods dependency_risk
python -m runtime.cli run zendesk --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: ticket
- PII posture: Ticket SUBJECT + BODY (detail.description) are PII-dense free text -> redact-and-passed (secret/PHI/PAN + email/phone scrubbed to placeholders). The requester is surfaced only as detail.requester_id, an OPAQUE numeric id -- never a requester name or email (a deliberate identity-minimization choice); requester_id is itself redact-and-passed so a numeric id passes unchanged while a stray email/phone is scrubbed -- the opacity guarantee is enforced, not merely trusted (purple-team #170). Comment threads and attachments are excluded (first description only). FX-SEC-001 hard-screens secret/PHI/PAN as the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + Base64-HMAC webhook verify + dedup are built and harness-proven; ticket subject + body redact-and-passed, requester an opaque id. The active REST poll is deferred (operator-runtime). Gated on operator review + a live signed delivery. To flip: create the webhook + trigger + signing secret + a Bicameral receiver URL; wire GatewaySink; send a signed test delivery; review before promoting.

- Gate: Webhook signature re-verified live 2026-06-13 (developer.zendesk.com/documentation/webhooks/verifying): X-Zendesk-Webhook-Signature = base64(HMAC-SHA256(secret, timestamp + body)) with companion X-Zendesk-Webhook-Signature-Timestamp, constant-time. Built verify_zendesk_signature MATCHES (no separator; Base64 not hex). No documented replay window -> best-effort dedup (envelope id -> detail.id -> body-hash fallback) is the only replay guard.
- Gate: PII: subject + body redact-and-passed (secret/PHI/PAN + email/phone); requester surfaced as opaque requester_id (no name/email); comments + attachments excluded. FX-SEC-001 backstops secret/PHI/PAN.
- Gate: Webhook RECEIPT + the active REST poll (/api/v2, API token or OAuth) are operator-runtime; the REST poll is DEFERRED this cycle (webhook is the built + verified path). Live flip gated on operator review + a signed live delivery (ADR-0012).

## References

- api: https://developer.zendesk.com/api-reference/ticketing/introduction/
- webhooks: https://developer.zendesk.com/documentation/webhooks/
- webhook-verify: https://developer.zendesk.com/documentation/webhooks/verifying/
- auth: https://developer.zendesk.com/api-reference/introduction/security-and-auth/
