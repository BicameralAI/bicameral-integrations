# Granola Auth

Credentials are declared here but resolved by the operator runtime, not by
repository-local config.

- API key is read from an environment variable named in the source config
  (`api_key_env`, e.g. `GRANOLA_API_KEY`) at poll time — the key is **never**
  stored in the config file.
- Transport: `GET https://api.granola.ai/v1/transcripts` with
  `Authorization: Bearer <key>`; `since` (ISO 8601) forwards the watermark.

## Live path — reference poll client (recorded-fixture-proven)

The request-construction is **built** in `runtime/poll_specs.py` (`build_granola_spec`) and proven
against a recorded fixture (`Authorization: Bearer`; `transcripts` envelope → one emission per
transcript). The harness supplies **fetch only** — the `since` watermark + two-phase commit remain
operator-run (this is a poll, not a webhook; PASSIVE here means operator-cadence pull, not active
streaming). The real network call + key resolution remain operator-run.

- **Secret resolver key**: the `SecretResolver` resolves by the connector **`source_id`** (`granola`);
  the `GRANOLA_API_KEY` env var above is the credential's *source*, not the resolver lookup key.
- **Assumptions to confirm before live-network wiring** (verify-before-cite): the **envelope key**
  (`transcripts`? `data`?) is unverified → `items` is a config callable. Pagination is **deferred**
  (the `since` watermark is operator-side).
