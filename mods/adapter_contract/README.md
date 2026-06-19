# Adapter Contract Mod

Status: Scoped  ·  version 0.1.0

Advisory mod for surfacing evidence-shape / contract-preservation defects in connector output, so a reviewer can confirm the evidence is still independently locatable before a change lands.

## How it works

Pure, read-only function over `list[AdapterEmission]`, deriving every signal from the emission's OWN structure (no I/O, no repo access — the structure is the one contract surface a mod can see):

- **lost provider pointer** — an evidence entry with NEITHER a `source_ref.ref` NOR a `url` (both blank/non-str): the evidence cannot be tied back to its source artifact. The strongest breach — it marks the emission **routable**.
- **no evidence** — an emission carrying zero `SourceEvidence` (nothing reviewable). Also routable.
- **blank excerpt** — an evidence entry with an empty excerpt (no reviewable content). Annotated only, too weak to route on its own.

A well-formed emission (ref or url present, non-blank excerpt, ≥1 evidence) produces NO output — silence is the default. Totality-safe: a non-tuple `evidence` or `None` `source_ref` is treated as a lost pointer, never a crash.

## Outputs

- `source_evidence_annotation` — `evidence-contract risk on <source>: <issues>`.
- `advisory_governance_result` — `adapter contract not fully preserved: <issues>`, metadata `{issues, source}`.
- `routing_hint` — only when routable: `role="connectors"`, `priority="normal"`, "review the connector parse surface".

Source ids are passed through `safe_id` before echoing.

## Boundary (EM-safe)

It may annotate contract risk and route a parse-surface review. It must never accept, reject, mutate, or repair a canonical record — it cannot write canonical state, approve/sign off, resolve compliance, or block CI (ADR-0007/0008/0013). Every wire-bound field is re-screened by `run_mod` (FX-SEC-001).

## References

ADR-0008 (integrations are evidence adapters, not state authorities), ADR-0013 (mod execution contract). See the [mod safety contract](../README.md) and [references.md](references.md).
