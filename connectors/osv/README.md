# OSV Connector

Read-only evidence connector: it parses OSV.dev vulnerability records into
neutral `Observation`s. **Status: Beta** (ADR-0012; catalog security/
compliance-evidence, priority P0, default trust tier T1). The supply-chain
vulnerability **aggregator** — the OSV schema covers GHSA-global, PyPA, and
RustSec — from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Active** — an OSV vulnerability record (from the free, no-auth OSV.dev query
  API) maps to one neutral `Observation` (`parse_vuln`). Read-only evidence; no
  canonical writes (ADR-0008).

The live boundary — the OSV.dev query client (`/v1/query`, `/v1/querybatch`) and
its REST poll — stays in the operator runtime (see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its `runtime.deliver_poll` → reference sink path is proven
end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo
dependency**. Live (gateway emission) remains gated on bicameral-bot #109.

## Surface

- `parse_vuln(record)` — OSV record → `Observation`. `summary` → excerpt, with
  `details` then the required `id` as terminal fallback; `id` → ref; first
  `references[].url` → ref url; `kind="vulnerability"`; `modified` → timestamp;
  `severity`/affected packages/`aliases` → metadata. Defends on the OSV schema's
  all-optional, sometimes-wrong-typed fields throughout (SG-2026-06-04-I).
- `OsvConnector` — connector identity and capabilities (`ACTIVE`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
