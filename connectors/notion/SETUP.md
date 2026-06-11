<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Notion — backend setup

Notion page-change webhook events as governed page-pointer evidence (keyed by the page entity.id).

- **id** `notion` · **category** docs · **trust tier** T1
- **status** live-ready · **available** True · **modes** webhook

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `notion_webhook` — Webhook verification token (webhook_secret, required)
- Wire format: `X-Notion-Signature (HMAC-SHA256 over the request body, signed with the verification_token)`
- Serves run mode(s): `webhook`
- **Note:** webhook-*receive* path only — **NOT** consumed by `runtime.cli run` (the active fetch uses the API credential).
- Supply via config key `notion_webhook` **or** env `BICAMERAL_NOTION_WEBHOOK` (env wins when set).
- Where to get it: https://developers.notion.com/reference/webhooks
  - Create a webhook subscription in your Notion integration; Notion issues a verification_token.
  - Bicameral verifies X-Notion-Signature (HMAC-SHA256 over the body) with the verification_token, constant-time, fail-closed.

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "notion": {
      "enabled": true,
      "secrets": {
        "notion_webhook": "<Webhook verification token>"
      }
    }
  }
}
```
## Webhook setup

- Signature scheme: HMAC-SHA256 over the (minified-JSON) request body, signed with the verification_token (X-Notion-Signature) (header `X-Notion-Signature`).
- Events: `page.content_updated`, `comment.created`, `database.schema_updated`, `page.locked`
- Bicameral webhook receiver URL (operator-provisioned) — **you provision this inbound URL** (provisioned_by: operator) and register it at the provider.
  - In your Notion integration, add a webhook subscription and capture the verification_token.
  - Set the subscription URL to your Bicameral webhook receiver (see receiver below).

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run notion                 # fetch -> print screened emissions
python -m runtime.cli run-mods notion --mods dependency_risk
python -m runtime.cli run notion --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: page
- PII posture: WEBHOOK path (live): the delivery is a thin event envelope carrying NO page content, so the Observation is a page-changed POINTER keyed by the opaque page entity.id (a Notion UUID -- pseudonymous, SG-2026-06-05-D) with title 'Notion <event_type>'. No free-text on this path -> nothing to redact. DEFERRED active-fetch path: the full page object's title (type=='title' property) is free-text -> redact-and-passed (scrubs secret/PHI/PAN + email/phone); author is the opaque created_by.id; block body is a further deferred fetch. FX-SEC-001 is the un-bypassable backstop on both.

## Go-live

Readiness: Flip-ready, NOT yet Live. Webhook verify + body-hash dedup + the page-changed pointer parse (keyed by entity.id) are built and harness-proven against a real delivery-envelope fixture. The webhook path emits a page-id pointer (no content); page-title redact-and-pass + active fetch are deferred. Gated on operator review + a live signed delivery with a real verification_token + a provisioned receiver, AND on confirming the X-Notion-Signature prefix format (open wire_gate). To flip: add the subscription + verification_token + receiver; wire GatewaySink; send a signed test delivery; confirm the signature format; review before promoting.

- Gate: Contract DOC-verified (developers.notion.com; auth.md 2026-06-08, re-confirmed research brief #143), NOT live-verified (no signed live delivery yet; ADR-0012): X-Notion-Signature = HMAC-SHA256 over the (minified-JSON) body signed with the verification_token; events page.content_updated/comment.created/database.schema_updated/page.locked.
- Gate: Webhook deliveries yield a page-changed POINTER Observation keyed by the page entity.id (NOT the ephemeral event id), title 'Notion <event_type>', with NO page content. Title/url/body require the deferred pages.retrieve active fetch (keyed by entity.id); the page-title redact-and-pass applies ONLY to that deferred path.
- Gate: UNVERIFIED (verify-before-cite, must confirm before Live): the connector's verify() REQUIRES a `sha256=` PREFIX on X-Notion-Signature and rejects a bare-hex value, but the live docs describe a bare HMAC-SHA256 hash and do NOT confirm a prefix. If Notion sends bare hex, verify() rejects EVERY real delivery (ingest zero) -- confirm the exact header format against a live delivery and relax the prefix requirement if needed (SG-2026-06-12-A). Also: verify() hashes the raw received bytes, which match only if the receiver forwards Notion's exact minified body without re-serializing.
- Gate: Webhook RECEIPT is operator-runtime; the active Notion API fetch + block-content retrieval + OAuth are deferred. Live flip gated on operator review + a signed live delivery (ADR-0012).

## References

- webhooks: https://developers.notion.com/reference/webhooks
- api: https://developers.notion.com/reference/intro
