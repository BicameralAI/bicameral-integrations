<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Fathom — backend setup

Fathom meeting transcripts + summaries as redact-and-pass governed evidence (speaker + recorder real names dropped).

- **id** `fathom` · **version** 0.1.0 · **channel** beta · **category** meetings · **trust tier** T1
- **status** live-ready · **available** True · **modes** passive, webhook

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `fathom` — Fathom API key (api_key, required)
- Wire format: `X-Api-Key: <key>`
- Serves run mode(s): `passive`
- Supply via config key `fathom` **or** env `BICAMERAL_FATHOM` (env wins when set).
- Where to get it: https://developers.fathom.ai/
  - Generate an API key in your Fathom settings area.
  - Bicameral sends it as the X-Api-Key header on each GET /external/v1/meetings request (verified 2026-06-12).

### `fathom_webhook` — Webhook signing secret (whsec_) (webhook_secret, required)
- Wire format: `webhook-signature (Svix-style HMAC-SHA256 over {webhook-id}.{webhook-timestamp}.{body}, signed with the base64-decoded whsec_ secret)`
- Serves run mode(s): `webhook`
- **Note:** webhook-*receive* path only — **NOT** consumed by `runtime.cli run` (the active fetch uses the API credential).
- Supply via config key `fathom_webhook` **or** env `BICAMERAL_FATHOM_WEBHOOK` (env wins when set).
- Where to get it: https://developers.fathom.ai/webhooks
  - Create a webhook subscription in Fathom; capture the whsec_-prefixed signing secret.
  - Bicameral verifies webhook-signature (HMAC-SHA256, base64, constant-time) over {id}.{timestamp}.{body} with a 5-minute replay window.

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "fathom": {
      "enabled": true,
      "secrets": {
        "fathom": "<Fathom API key>",
        "fathom_webhook": "<Webhook signing secret (whsec_)>"
      }
    }
  }
}
```
## Webhook setup

- Signature scheme: HMAC-SHA256(base64decode(whsec_ secret), '{webhook-id}.{webhook-timestamp}.{body}'), base64, constant-time; Fathom-documented 5-minute replay window (header `webhook-signature`).
- Events: `new-meeting-content-ready`
- Bicameral webhook receiver URL (operator-provisioned) — **you provision this inbound URL** (provisioned_by: operator) and register it at the provider.
  - Add a Fathom webhook subscription for new-meeting-content-ready and capture the whsec_ signing secret.
  - Set the subscription URL to your Bicameral webhook receiver (see receiver below).

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run fathom                 # fetch -> print screened emissions
python -m runtime.cli run-mods fathom --mods dependency_risk
python -m runtime.cli run fathom --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: meeting
- PII posture: Transcript + summary + title are PII-dense free text -> redact-and-passed (secret/PHI/PAN + email/phone scrubbed). The speaker (transcript[].speaker.display_name) and recorder (recorded_by.name) REAL NAMES are DROPPED, not surfaced (identity minimization; SG-2026-06-12-H) -- honoring the 'human real names are dropped' guarantee. FX-SEC-001 hard-screens secret/PHI/PAN as the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + Svix-style verify + dedup are built and harness-proven; transcript/summary/title redact-and-passed, speaker + recorder real names dropped. Gated on operator review + a live signed delivery (webhook) and/or a live poll with a real X-Api-Key. To flip: add the webhook subscription + whsec_ secret + receiver (and/or the API key); wire GatewaySink; send a signed test delivery; review before promoting.

- Gate: Contract re-verified live 2026-06-12 (developers.fathom.ai): meeting fields recording_id/meeting_title/title/transcript[].text/transcript[].speaker.display_name/default_summary.markdown_formatted/share_url/recorded_by.name/recording_end_time all match; webhook headers webhook-id/webhook-timestamp/webhook-signature + whsec_ + {id}.{timestamp}.{body} HMAC-SHA256 match; REST header X-Api-Key; 5-minute replay window now Fathom-documented.
- Gate: PII: transcript/summary/title redact-and-passed; speaker (transcript[].speaker.display_name) + recorder (recorded_by.name) real names DROPPED (SG-2026-06-12-H).
- Gate: Webhook RECEIPT + REST poll are operator-runtime; live network deferred. Live flip gated on operator review + a signed live delivery / live poll with a real API key (ADR-0012).

## References

- api: https://developers.fathom.ai/
- webhooks: https://developers.fathom.ai/webhooks
