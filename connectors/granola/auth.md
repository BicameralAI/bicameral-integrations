# Granola Auth

Credentials are declared here but resolved by the operator runtime, not by
repository-local config.

- API key is read from an environment variable named in the source config
  (`api_key_env`, e.g. `GRANOLA_API_KEY`) at poll time — the key is **never**
  stored in the config file.
- Transport: `GET https://api.granola.ai/v1/transcripts` with
  `Authorization: Bearer <key>`; `since` (ISO 8601) forwards the watermark.

The live poll + watermark two-phase commit are deferred to the operator
runtime; this cycle ships the transcript parse surface only.
