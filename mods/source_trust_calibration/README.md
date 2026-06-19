# Source Trust Calibration Mod

Status: Scoped  ·  version 0.1.0

Advisory mod for surfacing weak-provenance signals, so a reviewer can keep a weakly-attributed source advisory / under manual review rather than promoting it to a decision.

## How it works

Pure, read-only function over `list[AdapterEmission]` (no I/O). It weighs the provenance an emission actually carries and collects trust-weakening signals (deterministic, totality-safe):

- **no actor identity** — an attributable-kind evidence with a blank `author`. Attributable kinds (`_ATTRIBUTABLE_KINDS`): `pull_request`, `merge_request`, `issue`, `message`, `page`, `comment`, `meeting`, `commit`, `ticket`, `document`, `transcript`, `session`, `incident`, `finding`. Machine-emitted kinds (`usage_metrics`, `audit_event`, `vulnerability`, `mcp_server`) are deliberately EXCLUDED — a blank author there is expected.
- **unknown schema** — an evidence entry with no declared `source_ref.kind`.
- **public / no-auth source** — `source_id` in `_PUBLIC_SOURCES` (e.g. `mcp_registry`): attacker-publishable content, keep advisory regardless.
- **already-advisory emission_type** — `emission_type` of `hint` / `advisory` is low-trust by construction.

A normally-attributable, well-identified emission produces NO output.

## Outputs

- `source_evidence_annotation` — `source-trust note on <source>: <signals>`.
- `advisory_governance_result` — "weak provenance … keep advisory / manual review", metadata `{signals, source}`.
- `routing_hint` — `role="review"`, `priority="normal"`.

## Boundary (EM-safe)

It SUGGESTS a calibration; it never changes a canonical trust tier or promotes evidence to an accepted decision — it cannot write canonical state, approve/sign off, resolve compliance, or block CI (ADR-0007/0008/0013). Every wire-bound field is re-screened by `run_mod` (FX-SEC-001).

## References

ADR-0008 (evidence adapters, not state authorities), ADR-0013 (mod execution contract). See the [mod safety contract](../README.md) and [references.md](references.md).
