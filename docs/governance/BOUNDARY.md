# Governance Boundary

**Status**: Active · **Last reviewed**: 2026-06-09

This is the tracked, **contributor-only** development-governance contract for how process
governance touches this repository — it is a development reference, **not** a customer or
product contract, and is excluded from released artifacts (see `.gitattributes`
`export-ignore` and `scripts/check_release_inventory.py`). It declares which *classes* of
artifact are local versus shared, and it is
**enforced** by `scripts/validate_governance_boundary.py` (pre-commit + CI). It
never reproduces local contents.

## The three layers

| Layer | System | Lives where | Tracked? | Governs |
|---|---|---|---|---|
| **Local process** | Maintainer tooling (a registered sibling) | per `SIBLINGS.md` | **Never** | How *this* operator works locally |
| **Shared process** | shared Factory process contract | `bicameral-factory` upstream; pinned here | Pin + thin contract only | How a PR becomes acceptable — **the one mandatory layer** |
| **Sibling tools (registry)** | Any tool a contributor registers | per [`SIBLINGS.md`](SIBLINGS.md) | **Never** (registry row only) | Off-limits to commits; registered, leak-guarded, never referenced |

The third layer generalizes the first: the maintainer's own tooling is not required of
contributors — it is just another registered sibling. The only boundary a PR must clear
is the **shared Factory process contract layer**; everything below is free tool choice,
subject only to the leak guard.

## Invariants

1. **Sibling structural boundary** — registered sibling documents and runtimes stay where
   the sibling expects them; the shared layer is additive, never a refactor of sibling files.
2. **Shared-contract ownership** — the shared Factory process doctrine is owned upstream
   and consumed by pin/hash; no third divergent copy of the rules.
3. **Sibling boundary (leak-prevention)** — every registered sibling is leak-prevention only;
   no tracked file names a sibling's internals; the guard makes every registered root
   un-committable.
4. **No new product authority** — repo/process governance only; adapters and EM-safe mods
   emit candidates, evidence, hints, signals, and advisories through protocol-compatible
   paths — they never own canonical state.
5. **Sibling autonomy (tool freedom)** — the repo imposes no single local process on
   contributors; the only obligation is the shared Factory process contract plus a clean leak guard.

## Leak rules (enforced)

`scripts/validate_governance_boundary.py` fails a commit or PR when an introduced (staged or
PR-diff) path:

1. falls under a **registered sibling root** — from [`SIBLINGS.md`](SIBLINGS.md) unioned with a
   built-in default floor of common agent-scratch roots;
2. is a non-allowlisted file under `docs/governance/` — only `BOUNDARY.md`, `SIBLINGS.md`,
   `README.md`, `PIN.json`, and `factory-attestation.schema.json` are commit-permitted there;
3. is a non-allowlisted file under `.bicameral/` — only `repo-governance.yaml` (the
   machine-readable repo-local governance facts, an allowed tracked path per
   bicameral-factory#243) and `factory-attestations/*.json` (tracked factory attestations
   per the integrations#249 governance-owner decision, validated fail-closed by
   `scripts/validate_factory_attestation.py`) are commit-permitted; all other `.bicameral/`
   content — factory context, copied skills, run manifests, and receipts — stays
   local/gitignored, and `.bicameral/**` stays excluded from customer release artifacts;
4. or when a registered sibling root is **not** covered by `.gitignore` (registry ⇔
   `.gitignore` must agree).

Run `python scripts/validate_governance_boundary.py --audit` to scan the whole tracked tree
for pre-existing leaks (the default mode checks only what a change introduces).

## Related

- [`SIBLINGS.md`](SIBLINGS.md) — the sibling registry and how to register your own tool.
- `CONTRIBUTING.md` → *Bring your own tools*.
- [`PIN.json`](PIN.json) — pinned `bicameral-factory` governance-doctrine commit + sha256
  and the producer/consumer ownership of shared inter-repo contracts (drift-checked by
  `scripts/validate_governance_pin.py`).
