# Connector Freshness Mod

Status: Scoped  ·  version 0.1.0

Advisory mod for surfacing provider-freshness signals — a deprecation or API-version change that may stale a connector's documented assumptions — so a reviewer can refresh references/auth before they break.

## How it works

Pure, read-only function over `list[AdapterEmission]` (no network, no provider fetch); signals come only from the emission text (title + body + evidence excerpts, lowercased), matched via `matched_terms`:

- **deprecation / breaking change** (strong → routes) — a `_BREAK_TERMS` hit: `deprecated` / `deprecation` / `deprecating`, `sunsetting` / `decommissioned` / `discontinued`, `eol` / `end of life`, `retire` / `retired` / `retiring` (word-boundary, so not `retirement`), `breaking change`, `no longer supported`, `will be removed`, `migrate to v1/v2/v3`, `upgrade to v1/v2/v3`.
- **soft version mention** (annotate only) — a `_VERSION_TERMS` hit (`api version`, `v1`, `v2`, `v3`) with NO break term. Too weak to route.

No freshness term → NO output.

## Outputs

On a strong (break) signal:

- `source_evidence_annotation` — `provider-freshness signal on <source>: <terms>`.
- `advisory_governance_result` — "provider change may stale a connector assumption … review references/auth", metadata `{terms, source}`.
- `routing_hint` — `role="connectors"`, `priority="normal"`.

On a soft signal only: a single `source_evidence_annotation` — "api-version mention … (soft freshness signal)", no routing.

## Boundary (EM-safe)

It flags a possibly-stale assumption and suggests a refresh; it never fetches a provider, expands a credential, or edits a doc — it cannot write canonical state, approve/sign off, resolve compliance, or block CI (ADR-0007/0008/0013). Every wire-bound field is re-screened by `run_mod` (FX-SEC-001).

## References

ADR-0008 (evidence adapters, not state authorities), ADR-0013 (mod execution contract). See the [mod safety contract](../README.md) and [references.md](references.md).
