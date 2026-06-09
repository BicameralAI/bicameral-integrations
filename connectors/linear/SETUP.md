<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Linear — backend setup

Linear issues — webhook events + active GraphQL fetch — as governed evidence.

- **id** `linear` · **category** project-management · **trust tier** T1
- **status** live-ready · **available** True · **modes** webhook, active

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `linear` — Personal API key (api_key, required)
- Wire format: `Authorization (raw key, NO Bearer prefix)`
- Serves run mode(s): `active`
- Supply via config key `linear` **or** env `BICAMERAL_LINEAR` (env wins when set).
- Where to get it: https://linear.app/developers/graphql
  - In your Linear workspace settings, create a personal API key.
  - Copy the key — it is sent as a raw Authorization header (no Bearer prefix).

### `linear_webhook` — Webhook signing secret (webhook_secret, required)
- Wire format: `Linear-Signature (hex HMAC-SHA256 over the raw body)`
- Serves run mode(s): `webhook`
- **Note:** webhook-*receive* path only — **NOT** consumed by `runtime.cli run` (the active fetch uses the API credential).
- Supply via config key `linear_webhook` **or** env `BICAMERAL_LINEAR_WEBHOOK` (env wins when set).
- Where to get it: https://linear.app/developers/webhooks
  - When you create the Linear webhook, Linear shows a signing secret.
  - Copy it — Bicameral verifies Linear-Signature (hex HMAC-SHA256) + a 60s anti-replay window.

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "linear": {
      "enabled": true,
      "secrets": {
        "linear": "<Personal API key>",
        "linear_webhook": "<Webhook signing secret>"
      },
      "runtime": {
        "page_size": 50
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `page_size` | False | 50 | Issues fetched per GraphQL page (Linear Relay cursor; default 50). |

## Webhook setup

- Signature scheme: hex HMAC-SHA256 over the raw request body (header `Linear-Signature`).
- Events: `Issue`
- Bicameral webhook receiver URL (operator-provisioned) — **you provision this inbound URL** (provisioned_by: operator) and register it at the provider.
  - In Linear, create a webhook subscribed to Issue events.
  - Set its URL to your Bicameral webhook receiver (see receiver below).

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run linear                 # fetch -> print screened emissions
python -m runtime.cli run-mods linear --mods dependency_risk
python -m runtime.cli run linear --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: issue
- PII posture: Webhook: issue identifier/title/description/url + actor.name. GraphQL active fetch: PII-safe (no assignee/creator identity surfaced). FX-SEC-001 producer screen is the backstop.

## Go-live

Readiness: Code-ready on both paths (FX-LINEAR-002 webhook, FX-LINEAR-003 GraphQL). Operator provides: the API key, the webhook signing secret, and a webhook receiver URL; then wires GatewaySink.

- Gate: Two-secret model (RESOLVED, FX-RUNTIME-005): Linear needs two namespaced credential keys — 'linear' (GraphQL API key, modes: active) + 'linear_webhook' (webhook signing secret, modes: webhook). The resolver resolves each by key (env BICAMERAL_LINEAR / BICAMERAL_LINEAR_WEBHOOK), and assert_runnable is mode-scoped so an active `runtime.cli run linear` requires only 'linear'. Residual: injecting 'linear_webhook' into deliver_webhook's receive path stays operator-runtime (the CLI runs active fetches, not webhook receipt).
- Gate: GraphQL issue field set (id/identifier/title/description/url/updatedAt/state.name) confirmed against a live response before the Live flip (verify-before-cite).

## References

- api: https://linear.app/docs/api-and-webhooks
- graphql: https://linear.app/developers/graphql
- webhook: https://linear.app/developers/webhooks
- pagination: https://linear.app/developers/pagination
- rate-limiting: https://linear.app/developers/rate-limiting
