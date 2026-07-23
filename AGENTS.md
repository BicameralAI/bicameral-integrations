# Contributor & agent development guide

This is a **contributor-only** development reference. It is not shipped in released
artifacts (`.gitattributes` `export-ignore` + `scripts/check_release_inventory.py`) and is
**not** a customer/product dependency or a required concept for *using* these integrations.
It documents how development is governed in this repository — for human contributors and for
AI/agent sessions working here.

Public product statements live in [`README.md`](README.md) and [`GOVERNANCE.md`](GOVERNANCE.md).
Contribution basics live in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Development-governance boundary

Repository **process** governance is layered; the full contract is
[`docs/governance/BOUNDARY.md`](docs/governance/BOUNDARY.md):

- **Shared Factory process contract** — the factory-owned development doctrine, owned
  upstream in `bicameral-factory` and consumed here by pin/hash. This is the one mandatory
  layer every PR must satisfy. The consumed pin is recorded in
  [`docs/governance/PIN.json`](docs/governance/PIN.json).
- **Sibling tools (registry)** — any local process, governance, or AI tooling a contributor
  uses is a registered, leak-guarded sibling: never tracked, never referenced. See
  [`docs/governance/SIBLINGS.md`](docs/governance/SIBLINGS.md).

This is repo/process governance only. It never produces product Decisions, gates, or
compliance outcomes: adapters and EM-safe mods emit candidates, evidence, hints, signals,
and advisories and never write canonical state ([ADR-0008](docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md)).

## Customer-distribution boundary

The customer artifact (released source archive) must never carry Factory-internal or
contributor-only development material. The machine-readable declaration is in
[`.bicameral/repo-governance.yaml`](.bicameral/repo-governance.yaml) under
`development_governance` / `customer_distribution`, and it is enforced by:

- `.gitattributes` `export-ignore` (what `git archive` omits), and
- `scripts/check_release_inventory.py` (fail-closed inventory + reference scan).

Run it before opening a PR:

```bash
python scripts/check_release_inventory.py            # fail-closed boundary check
python scripts/check_release_inventory.py --manifest # exact-head release inventory + sha256
```

## Factory attestation & evidence

Factory-run PRs follow the `Bicameral Factory Run` playbook. A factory attestation records
which `bicameral-factory` commit and context were relied on.

> **Attestation storage (governance-owner decision, integrations#249):** factory attestations
> **are tracked in-repo** under `.bicameral/factory-attestations/*.json`. The boundary guard
> (`scripts/validate_governance_boundary.py`) permits exactly two `.bicameral/` paths — the
> `repo-governance.yaml` declaration and `factory-attestations/*.json` — and forbids all other
> `.bicameral/` content. Each tracked attestation is validated **fail-closed** by
> `scripts/validate_factory_attestation.py` on: **filename** (`<factory_commit>.<run-id>.json`),
> **schema** (against the pinned mirror `docs/governance/factory-attestation.schema.json`),
> **factory commit** (a 40-char SHA reconciled with `docs/governance/PIN.json`
> `factory_governance.commit`), **roadmap reconciliation**, and **state refinement**.
> Attestations stay **excluded from customer release artifacts** (`.gitattributes`
> `export-ignore` + `scripts/check_release_inventory.py`), so `.bicameral/**` never ships.
>
> Add one for a factory-run PR:
>
> ```bash
> # <factory_commit> must equal PIN.json factory_governance.commit
> $EDITOR .bicameral/factory-attestations/<factory_commit>.<run-id>.json
> git add -f .bicameral/factory-attestations/<factory_commit>.<run-id>.json  # .bicameral/ is gitignored
> python scripts/validate_factory_attestation.py
> ```

## Local checks

```bash
ruff check adapter connectors runtime mods
mypy adapter connectors runtime mods
pytest adapter/core/tests connectors runtime mods scripts/tests tests/redteam -q
python scripts/validate_connector_config.py
python scripts/validate_mod_config.py
python scripts/validate_ingest_schema_pin.py
python scripts/validate_governance_pin.py
python scripts/validate_factory_attestation.py
python scripts/governance_gate.py
python scripts/validate_governance_boundary.py
python scripts/check_release_inventory.py
pre-commit run --all-files
```
