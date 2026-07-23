# Governance (tracked, contributor-only)

This directory holds the **tracked, contributor-only development-governance** contract. It
is a development reference for how a PR becomes acceptable in this repo — **not** a customer
or product contract — and is excluded from released artifacts (`.gitattributes`
`export-ignore` + `scripts/check_release_inventory.py`). It declares *which classes* of
artifact are local versus shared, and never reproduces local contents.

| File | Purpose |
|---|---|
| [`BOUNDARY.md`](BOUNDARY.md) | The tracked governance boundary contract — three layers, five invariants, enforced leak rules. |
| [`SIBLINGS.md`](SIBLINGS.md) | The sibling registry — every leak-guarded local contributor tool and the rules that keep it out of commits. |
| [`PIN.json`](PIN.json) | Pinned shared inter-repo contracts (upstream commit + sha256) and their producer/consumer ownership; drift-checked in CI. |

**Doctrine is shared upstream.** The shared Factory process contract (the factory-owned
development doctrine) is owned in `bicameral-factory` and consumed here — not copied.
**Local artifacts are never here**:
any sibling's scratch stays local and gitignored. Architecture decisions live in
`docs/adr/`.
