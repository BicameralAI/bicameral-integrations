# Dependency Risk Mod

Status: Built (the reference mod — ADR-0013 / FX-MOD-002)

Advisory mod for surfacing dependency-risk signals from connector evidence — known
vulnerabilities and dependency-manifest changes — so a reviewer can weigh them before a
change lands. Advisory only: it annotates and routes; it never blocks or approves (see the
[mod safety contract](../README.md)). Implemented in [`connector.py`](connector.py) as
`DependencyRiskMod`, run through `mods.contract.run_mod`.

## How it works

Pure, read-only function over `list[AdapterEmission]`, two deterministic paths:

- **Vulnerability path** — for each evidence with `source_ref.kind == "vulnerability"`
  (OSV-style), reads the connector `metadata` preserved through `normalize` (`packages` /
  `severity` / `aliases` — ADR-0014) and emits a `dependency_signal` naming the affected
  packages, a `routing_hint` to `security` (`priority="high"` when a `CVE-`/`GHSA-` alias is
  present — no CVSS-band fabrication), and a `source_evidence_annotation`.
- **Manifest-mention path** — for any emission with no vulnerability evidence whose text
  references a dependency-manifest filename (`requirements.txt`, `pyproject.toml`,
  `package.json`, `go.mod`, `Cargo.toml`, …, matched as contiguous substrings), emits a
  low-confidence `dependency_signal` + `source_evidence_annotation` (no routing).

## Outputs (mirror [`manifest.yaml`](manifest.yaml))

- `dependency_signal`
- `routing_hint`
- `source_evidence_annotation`

## References

See [references.md](references.md).
