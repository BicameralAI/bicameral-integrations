# Authority Boundary Mod

Status: Scoped  ·  version 0.1.0

Advisory mod for surfacing changes that name an authority-, trust-tier-, or canonical-state-crossing action, so a reviewer can confirm the path is gated by human approval before it lands.

## How it works

Pure, read-only function over `list[AdapterEmission]`, fires only on **change evidence** (`is_change_evidence` — a `pull_request` / `issue` / `merge_request`) and keys off the change text (title + body + evidence excerpts, lowercased):

- **authority-crossing term** — the text names an authority action drawn from `_AUTHORITY_TERMS`: `auto-approve` / `auto-merge` / `self-approve`, `signoff` / `sign-off`, `write canonical` / `canonical decision`, `bypass governance` / `bypass policy` / `skip review` / `without review`, `force merge` / `force push`, `deploy to production` / `delete production`, `expand scope` / `credential scope`, `shell execution` / `run shell` / `rm -rf` / `sudo` / `grant admin`. Matched via `matched_terms` (phrases substring-matched; `signoff` word-boundary). Routes GOVERNANCE review + asks a boundary question.

No authority term on a change, or non-change evidence → NO output.

## Outputs

- `source_evidence_annotation` — `change on <source> names an authority-crossing action: <terms>`.
- `advisory_governance_result` — "possible authority-boundary crossing … confirm human review + policy gate", metadata `{terms, source}`.
- `routing_hint` — `role="governance"`, `priority="high"`.
- `suggested_review_question` — "Is the '<terms>' path gated by explicit human approval, actor identity, and an audit record?"

## Boundary (EM-safe)

It can RAISE a boundary risk and route review. It must never block CI or enforce policy — it cannot write canonical state, approve/sign off, resolve compliance, or bypass governance (ADR-0007/0008/0013). Every wire-bound field is re-screened by `run_mod` (FX-SEC-001).

## References

ADR-0008 (integrations observe; they never own authority), ADR-0013 (mod execution contract). See the [mod safety contract](../README.md) and [references.md](references.md).
