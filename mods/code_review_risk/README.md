# Code Review Risk Mod

Status: Scoped  ·  version 0.1.0

Advisory mod for surfacing PR-level review risk — the first mod family behind the [Bicameral Review Bot](../../docs/adr/0011-bicameral-review-bot.md) — so a reviewer can weigh the blast radius before merge.

## How it works

Pure, read-only function over `list[AdapterEmission]`, fires only on **change evidence** (`is_change_evidence` — a `pull_request` / `issue` / `merge_request`) and keys off the change text (title + body + evidence excerpts, lowercased):

- **high blast radius** — the text names one or more risky areas from `_RISK_AREAS` (matched via `any_match`; alphanumeric terms word-boundary, phrases/paths substring):
  - `schema/migration` (`migration`, `alter table`, `drop table`, `ddl`), `auth` (`auth`, `oauth`, `token`, `credential`, `session`, `cve`, `xss`, `csrf`, `injection`, `rce`, `sqli`), `ci/workflow` (`.github/workflows`, `ci pipeline`, `release pipeline`), `container/infra` (`dockerfile`, `kubernetes`, `terraform`, `helm chart`), `secrets` (`secret`, `api key`, `private key`, `signing key`), `breaking` (`breaking change`, `remove endpoint`, `drop support`).
  - The review question names the category that tripped. Routes review.

No risky area named on a change, or non-change evidence → NO output.

## Outputs

- `source_evidence_annotation` — `change on <source> touches high-risk area(s): <areas>`.
- `advisory_governance_result` — "PR-level review risk … review blast radius before merge", metadata `{areas, source}`.
- `routing_hint` — `role="review"`, `priority="high"`.
- `suggested_review_question` — "Does this change to <areas> have a tested rollback and a clear blast-radius bound?"

## Boundary (EM-safe)

It advises a reviewer; it never approves, requests changes, posts a comment, or merges — it cannot write canonical state, approve/sign off, resolve compliance, or create a blocking CI result (ADR-0007/0008/0013). Every wire-bound field is re-screened by `run_mod` (FX-SEC-001).

## References

ADR-0011 (Bicameral Review Bot), ADR-0008 (evidence adapters, not state authorities), ADR-0013 (mod execution contract). See the [mod safety contract](../README.md) and [references.md](references.md).
