# Granola Auth

Credentials are declared here but resolved by the operator runtime, not by
repository-local config.

- API key is read from an environment variable named in the source config
  (`api_key_env`, e.g. `GRANOLA_API_KEY`) at poll time — the key is **never**
  stored in the config file.
- Transport (verified 2026-06-08, docs.granola.ai): `GET https://public-api.granola.ai/v1/notes?include=transcript`
  with `Authorization: Bearer <key>`; `created_after` (ISO 8601) forwards the watermark.

## Privacy / PII (binding design contract — RE-VERIFIED 2026-06-11)

Granola is a **meeting-content** connector and is **PII-dense**, and the provider docs give **no
redaction/PII guidance** — so PII control is entirely ours:

- The **transcript** is verbatim meeting speech → it can carry names, emails, and phone numbers.
  FX-SEC-001 (`adapter.core.sensitive`) screens **secret/PHI/PAN only** and does **NOT** detect a
  generic email/phone/name — so there is **no downstream backstop** for spoken PII. **Required (build
  cycle): pass the transcript excerpt through `adapter.core.redaction.redact` (redact-and-pass)** so
  emails/phones are scrubbed before emit, matching the devin/servicenow/cursor model.
- **Identity:** the live note carries **`owner` {name, email}** (verified 2026-06-11). The connector
  currently emits `author = attendees[0].name` from a non-existent **`attendees`** field — **DRIFT**
  (author is empty/wrong against the live API). Re-point identity to `owner`, and do **not** emit the
  raw owner name/email as `author` (drop it PII-safe like the Linear active path, or `redact()` it).
- `speaker` is an **object** `{source, diarization_label}` — anonymized (Speaker A/B), no identity; the
  connector reads only `text`, which is correct.

## Live path — reference poll client (contract verified 2026-06-08, RE-VERIFIED LIVE 2026-06-11 against public-api.granola.ai docs)

The request-construction is **built** in `runtime/poll_specs.py` (`build_granola_spec`) and proven
against a recorded fixture. The harness supplies **fetch only** — the `created_after` watermark +
two-phase commit remain operator-run (this is a poll, not a webhook; PASSIVE here means
operator-cadence pull, not active streaming). The real network call + key resolution remain
operator-run.

- **Secret resolver key**: the `SecretResolver` resolves by the connector **`source_id`** (`granola`);
  the `GRANOLA_API_KEY` env var above is the credential's *source*, not the resolver lookup key.
- **Verified contract** (RE-VERIFIED 2026-06-11, public-api.granola.ai docs): host
  **`public-api.granola.ai/v1`**, resource **`GET /notes?include=transcript`** (+ `GET /notes/{id}`;
  there is no `/transcripts` collection); Bearer key is **`grn_`-prefixed**; list wraps under **`notes`**;
  each note carries `id` (`not_` prefix), `title`, `summary`, **`owner` {name, email}**, and an embedded
  **`transcript`** array of **`{speaker:{source,diarization_label}, text}`** (text joined); cursor
  pagination (`cursor` + `hasMore`, wired via `PageToken`); watermark **`created_after`** (ISO 8601,
  operator-side). **CORRECTION (2026-06-11): the identity field is `owner`, NOT `attendees`** — the
  connector's `attendees`/`attendees[].name` read is DRIFT (see Privacy/PII above; fix in the build
  cycle). The older `api.granola.ai/v1/transcripts` host, `transcripts` envelope, and
  `transcript_text`/`participants`/`ended_at`/`since` names were earlier DRIFT and remain corrected.
