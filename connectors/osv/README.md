# OSV Connector

Provider-facing OSV.dev adapter. **Status: Beta** (ADR-0012; harness-proven via the `runtime/` deliver path) (catalog
security/compliance-evidence, priority P0, default trust tier T1). The
supply-chain vulnerability **aggregator** — the OSV schema covers GHSA-global,
PyPA, and RustSec — from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Active** — an OSV vulnerability record (from the free, no-auth OSV.dev query
  API) maps to one neutral `Observation` (`parse_vuln`). Read-only evidence; no
  canonical writes (ADR-0008).

The live OSV.dev query client (`/v1/query`, `/v1/querybatch`) is deferred this
cycle (see [`auth.md`](auth.md)); this connector is the parse surface only.

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
