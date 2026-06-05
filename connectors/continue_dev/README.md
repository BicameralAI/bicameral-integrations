# Continue Connector

Provider-facing Continue (continue.dev) adapter. **Status: Beta** (ADR-0012; harness-proven via the `runtime/` deliver path) (catalog
source-control/developer-AI tooling, priority P1, default trust tier T0). A
candidate from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

> The package is `continue_dev` because `continue` is a Python keyword; the
> provider `source_id` is the string `"continue"`.

## Modes

- **Passive** — Continue writes "development data" as local JSONL (one event per
  developer-AI interaction: `chatInteraction`, `editOutcome`, `autocomplete`,
  …). Each event maps to one neutral `Observation` (`parse_event`). No
  canonical-state writes — evidence adapter, not state authority (ADR-0008).

The live JSONL file-watch / HTTP-sink collection, the `level: noCode` redaction
lever, and any Continue Hub API are deferred this cycle (see
[`auth.md`](auth.md)); this connector is the parse surface only.

## Surface

- `parse_event(event)` — Continue dev-data event → `Observation`. Excerpt is the
  first non-empty of `prompt`/`completion`/`content`/`message`, with a
  `continue {name}` terminal fallback (the event schema is versioned and churns,
  and `noCode` strips text — the excerpt must never be blank); `name` → kind /
  title; `eventId`/`id`/`name:timestamp` → ref; `userId` → author;
  `name`/`schema`/`modelTitle` → metadata.
- `ContinueConnector` — connector identity and capabilities (`PASSIVE`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
