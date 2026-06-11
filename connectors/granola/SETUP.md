<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Granola — backend setup

Granola meeting notes + transcript (redact-and-pass) as governed evidence.

- **id** `granola` · **category** meetings · **trust tier** T1
- **status** live-ready · **available** True · **modes** passive

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `granola` — Granola API key (grn_) (api_key, required)
- Wire format: `Authorization: Bearer grn_<key>`
- Supply via config key `granola` **or** env `BICAMERAL_GRANOLA` (env wins when set).
- Where to get it: https://docs.granola.ai
  - Create a Granola API key (grn_ prefix) in your Granola workspace settings.
  - Sent as Authorization: Bearer grn_<key>.

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "granola": {
      "enabled": true,
      "secrets": {
        "granola": "<Granola API key (grn_)>"
      },
      "runtime": {
        "base_url": "https://public-api.granola.ai/v1/notes?include=transcript"
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `base_url` | False | https://public-api.granola.ai/v1/notes?include=transcript | The notes-with-transcript endpoint (verified 2026-06-11). The incremental created_after watermark + two-phase commit are operator-runtime. |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run granola                 # fetch -> print screened emissions
python -m runtime.cli run-mods granola --mods dependency_risk
python -m runtime.cli run granola --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: transcript
- PII posture: Meeting content is PII-dense and the provider gives no redaction guidance. The transcript + title are passed through adapter.core.redaction.redact (redact-and-pass: scrubs secret/PHI/PAN + email/phone). The meeting OWNER's identity (owner.name/email) is NEVER surfaced (author dropped, PII-safe). speaker is an anonymized object (source/diarization label), never read. FX-SEC-001 is the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Redacted transcript parse surface + the live fetch-half (build_granola_spec) are built and harness-proven against a recorded fixture; contract re-verified live 2026-06-11; the owner-vs-attendees drift + transcript-PII gap are fixed (L2). Gated on operator review + a live poll with a real grn_ key. To flip: provide the key; wire GatewaySink; run the live poll; review before promoting.

- Gate: Contract re-verified live 2026-06-11 (public-api.granola.ai): GET /v1/notes?include=transcript, Bearer grn_; `notes` envelope; cursor `cursor`/`hasMore` pagination; note carries owner{name,email}, title, summary, transcript[{speaker:{source,diarization_label},text}], created_at.
- Gate: PII (SG-2026-06-11-D, fixed this cycle): identity is `owner` (NOT `attendees`); transcript + title are redact-and-passed; owner identity is dropped (FX-SEC-001 does not catch a generic name/email).
- Gate: Live flip gated on operator human review + a live poll with a real grn_ key (ADR-0012).

## References

- api: https://docs.granola.ai
