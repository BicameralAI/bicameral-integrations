# Continue Auth

Auth model recorded for the live cycle; this connector ships the **parse
surface** only (the live collection path is deferred).

- Default trust tier: T0
- Auth: Not applicable for local file ingest. A Continue `config.yaml` `data`
  block may also POST events to an HTTP sink with a Bearer `apiKey` (T1 path,
  deferred).

## Deferred live paths

- Passive file-watch of `.continue/dev_data/*.jsonl` (the documented default).
- Optional HTTP-sink registration via the `config.yaml` `data` block.
- Continue Hub cloud read-API for development data — unverified (open question).

## Redaction lever

Continue's `data` block carries `level: all | noCode`; `noCode` strips file
contents, prompts, and completions at the source. The operator sets this; the
producer sensitive screen (`FX-SEC-001`) is the in-pipeline guard regardless.

Credentials (HTTP-sink `apiKey`, if used) are resolved by the operator runtime,
never stored in this package. See [references.md](references.md) and
[TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
