# Ownership Routing Mod

Status: Scoped  ·  version 0.1.0

Advisory mod for mapping a change to a reviewer lens / domain owner, so a change reaches the right eyes without ever being auto-assigned.

## How it works

Pure, read-only function over `list[AdapterEmission]`, fires only on **change evidence** (`is_change_evidence` — a `pull_request` / `issue` / `merge_request`) and keys off the change text (title + body + evidence excerpts, lowercased). It maps domain hints to a reviewer lens (`any_match`; alphanumeric terms word-boundary, paths/phrases substring), in stable order:

- **security** — `security`, `auth`, `crypto`, `redact`, `sensitive`, `vulnerability`, `credential`, `signature`, `cve`, `xss`, `csrf`, `injection`, `rce`, `sqli`, `exploit`.
- **connectors** — `connector(s)`, `adapter`, `webhook`, `parse surface`, `poll spec`.
- **governance** — `governance`, `ledger`, `adr`, `compliance`, `policy`, `trust tier`.
- **ci** — `.github/workflows`, `ci pipeline`, `scorecard`, `sbom`, `workflow yaml`.
- **docs** — `readme`, `documentation`, `docs/`, `changelog`.

One `owner_lens_hint` + one `routing_hint` per matched domain, plus a single annotation. No domain matched, or non-change evidence → NO output.

## Outputs

- `source_evidence_annotation` — `change on <source> maps to owner lens(es): <domains>`.
- `owner_lens_hint` (per domain) — `review through the <domain> lens`, metadata `{lens, source}`.
- `routing_hint` (per domain) — `role=<domain>`, `priority="normal"`.

## Boundary (EM-safe)

It SUGGESTS a reviewer lens or owner; it never assigns a reviewer, requires approval, or overrides branch protection — it cannot write canonical state, approve/sign off, resolve compliance, or block CI (ADR-0007/0008/0013). Every wire-bound field is re-screened by `run_mod` (FX-SEC-001).

## References

ADR-0008 (evidence adapters, not state authorities), ADR-0013 (mod execution contract). See the [mod safety contract](../README.md) and [references.md](references.md).
