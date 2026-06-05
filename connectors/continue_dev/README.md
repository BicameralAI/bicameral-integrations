# Continue Connector

Read-only evidence connector: it parses Continue (continue.dev) dev-data into
neutral `Observation`s. **Status: Beta** (ADR-0012; catalog source-control/
developer-AI tooling, priority P1, default trust tier T0). A candidate from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

> The package is `continue_dev` because `continue` is a Python keyword; the
> provider `source_id` is the string `"continue"`.

## Modes

- **Passive** — Continue writes "development data" as local JSONL (one event per
  developer-AI interaction: `chatInteraction`, `editOutcome`, `autocomplete`,
  …). Each event maps to one neutral `Observation` (`parse_event`). No
  canonical-state writes — evidence adapter, not state authority (ADR-0008).

The live boundary — JSONL file-watch / HTTP-sink collection, the `level: noCode`
redaction lever, any Continue Hub API, and secret resolution — stays in the
operator runtime (see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its `runtime.deliver_poll` → reference sink path is proven
end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo
dependency**. Live (gateway emission) remains gated on bicameral-bot #109.

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
