# Data Classification Mod

Status: Scoped  ·  version 0.1.0

Advisory mod for flagging confidentiality/PII-bearing evidence as RESTRICTED, so a reviewer can route it to restricted handling before it is reviewed or proposed for outbound notification.

## How it works

Pure, read-only function over `list[AdapterEmission]`. It classifies an emission's DATA sensitivity AFTER the FX-SEC-001 producer screen (and any connector redact-and-pass) have run — so it never sees a raw secret/PHI/PAN. Over the joined text (title + body + evidence excerpts) it flags two residual signals (deterministic, sorted, whole-word):

- **confidentiality markers** — a whole-word `_MARKERS` hit: `confidential`, `internal only` / `internal-only`, `proprietary`, `nda`, `do not share` / `do not distribute`, `restricted`, `classified`, `privileged`.
- **redaction placeholder** — a `[redacted:<type>]` token, proof the source carried PII/secret that was scrubbed, so the surrounding context is still sensitive → appends a `redacted-pii` signal.

No marker and no placeholder → general/unremarkable → NO output. (Source-TRUST tiering is a sibling concern — see `source_trust_calibration`.)

## Outputs

- `source_evidence_annotation` — `data classification: RESTRICTED (<signals>)`, `evidence_ids` = sorted distinct `source_ref.ref`s, metadata `{classification: "restricted", signals}`.
- `routing_hint` — `role="restricted-review"` (default priority).
- `advisory_governance_result` — "evidence classified RESTRICTED -> route to restricted review", metadata `{classification: "restricted"}`.

## Boundary (EM-safe)

It suggests a sensitivity classification and routes restricted review; it never deletes source evidence, resolves compliance, redacts canonical state, or sends a notification (ADR-0007/0008/0013). Every wire-bound field is re-screened by `run_mod` (FX-SEC-001).

## References

ADR-0008 (evidence adapters, not state authorities), ADR-0013 (mod execution contract). See the [mod safety contract](../README.md) and [references.md](references.md).
