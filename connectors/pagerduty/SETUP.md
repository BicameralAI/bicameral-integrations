<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# PagerDuty — backend setup

PagerDuty v3 incident webhook events as redact-and-pass governed evidence (incident title/summary scrubbed; no actor/assignee identity surfaced).

- **id** `pagerduty` · **version** 0.1.0 · **channel** beta · **category** observability/incident-evidence · **trust tier** T1
- **status** live-ready · **available** True · **modes** webhook

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `pagerduty_webhook` — Webhook signing secret (webhook_secret, required)
- Wire format: `X-PagerDuty-Signature (comma-separated v1=<hex> HMAC-SHA256 set over the raw body; accept if ANY matches, for zero-downtime rotation)`
- Serves run mode(s): `webhook`
- **Note:** webhook-*receive* path only — **NOT** consumed by `runtime.cli run` (the active fetch uses the API credential).
- Supply via config key `pagerduty_webhook` **or** env `BICAMERAL_PAGERDUTY_WEBHOOK` (env wins when set).
- Where to get it: https://support.pagerduty.com/main/docs/webhooks
  - Create a V3 webhook subscription in PagerDuty; capture the signing secret it generates.
  - Bicameral verifies X-PagerDuty-Signature = a v1=<hex>,v1=<hex> HMAC-SHA256 set over the raw body (accept if ANY candidate matches), constant-time, fail-closed (header confirmed live 2026-06-13; SG-2026-06-13-D).

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "pagerduty": {
      "enabled": true,
      "secrets": {
        "pagerduty_webhook": "<Webhook signing secret>"
      }
    }
  }
}
```
## Webhook setup

- Signature scheme: X-PagerDuty-Signature = a comma-separated v1=<hex>,v1=<hex> set of HMAC-SHA256 digests over the raw request body (one per active signing secret during rotation); accept if ANY v1= candidate matches (constant-time, fail-closed). PagerDuty documents no replay-timestamp window -> best-effort dedup (envelope event.id -> body-hash) is the replay guard. (header `X-PagerDuty-Signature`).
- Events: `incident`
- Bicameral webhook receiver URL (operator-provisioned) — **you provision this inbound URL** (provisioned_by: operator) and register it at the provider.
  - In PagerDuty, create a V3 webhook subscription scoped to incident events.
  - Set its delivery URL to your Bicameral webhook receiver (see receiver below).

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run pagerduty                 # fetch -> print screened emissions
python -m runtime.cli run-mods pagerduty --mods dependency_risk
python -m runtime.cli run pagerduty --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: incident
- PII posture: The incident TITLE/SUMMARY is emitted via redact-and-pass -- secret/PHI/PAN + email/phone scrubbed to placeholders, because an incident title can carry customer PII (e.g. 'High latency for jane@acme.com'; FX-SEC-001 backstops only secret/PHI/PAN). The opaque incident id floor is NOT redacted. NO actor/assignee identity is surfaced -- only status/urgency/event_type ride in metadata. FX-SEC-001 hard-screens secret/PHI/PAN as the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + multi-signature v1= membership verify + dedup are built and harness-proven; incident title/summary redact-and-passed, no actor identity surfaced. Gated on operator review + a signed live delivery. To flip: create the V3 webhook subscription + signing secret + a Bicameral receiver URL; wire GatewaySink; send a signed test delivery; review before promoting.

- Gate: Webhook signature: the V3 x-pagerduty-signature header was confirmed live 2026-06-13 (support.pagerduty.com); the dedicated v1= format page (developer.pagerduty.com/docs/webhooks/webhook-signatures) is a JS-SPA that rendered empty to a server-side fetch, so the v1=<hex> HMAC-SHA256 membership scheme was substantiated from the harness-proven verified contract + verify_hmac_hex_multi (SG-2026-06-13-D). No drift on the supported path. Built verify_hmac_hex_multi accepts if ANY v1= candidate matches the raw body (constant-time, fail-closed).
- Gate: PII: incident title/summary redact-and-passed (secret/PHI/PAN + email/phone); opaque id floor un-redacted; no actor/assignee surfaced. FX-SEC-001 backstops secret/PHI/PAN.
- Gate: Webhook RECEIPT + the REST incident fetch (active fallback) are operator-runtime; the REST fetch is DEFERRED this cycle (webhook is the built + verified path). Live flip gated on operator review + a signed live delivery (ADR-0012).

## References

- api: https://developer.pagerduty.com/api-reference/
- webhooks: https://support.pagerduty.com/main/docs/webhooks
- webhook-verify: https://developer.pagerduty.com/docs/webhooks/webhook-signatures/
