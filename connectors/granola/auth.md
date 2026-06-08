# Granola Auth

Credentials are declared here but resolved by the operator runtime, not by
repository-local config.

- API key is read from an environment variable named in the source config
  (`api_key_env`, e.g. `GRANOLA_API_KEY`) at poll time — the key is **never**
  stored in the config file.
- Transport (verified 2026-06-08, docs.granola.ai): `GET https://public-api.granola.ai/v1/notes?include=transcript`
  with `Authorization: Bearer <key>`; `created_after` (ISO 8601) forwards the watermark.

## Live path — reference poll client (contract verified 2026-06-08 against docs.granola.ai)

The request-construction is **built** in `runtime/poll_specs.py` (`build_granola_spec`) and proven
against a recorded fixture. The harness supplies **fetch only** — the `created_after` watermark +
two-phase commit remain operator-run (this is a poll, not a webhook; PASSIVE here means
operator-cadence pull, not active streaming). The real network call + key resolution remain
operator-run.

- **Secret resolver key**: the `SecretResolver` resolves by the connector **`source_id`** (`granola`);
  the `GRANOLA_API_KEY` env var above is the credential's *source*, not the resolver lookup key.
- **Verified contract** (docs.granola.ai): host **`public-api.granola.ai/v1`**, resource
  **`GET /notes?include=transcript`** (there is no `/transcripts` collection); list wraps under
  **`notes`**; each note carries `id` (`not_` prefix), an embedded **`transcript`** array of
  `{speaker, text}` (joined), **`attendees`** (`[{name, email}]`), and **`created_at`**; cursor
  pagination (`cursor` + `hasMore`, wired via `PageToken`); the incremental watermark is
  **`created_after`** (operator-side). The earlier `api.granola.ai/v1/transcripts` host/endpoint,
  `transcripts` envelope, `transcript_text`/`participants`/`ended_at`/`since` field names were all
  DRIFT (would have hit a non-existent endpoint) and are corrected.
