# SARIF 2.1.0 Connector

Provider-facing SARIF 2.1.0 adapter. **Status: Beta** (ADR-0012; harness-proven via the `runtime/` deliver path) (catalog
security/compliance-evidence, priority P0, default trust tier T0). A Phase-1
foundation candidate from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Passive** — a SARIF 2.1.0 report (the output of a static-analysis tool) is
  imported as a file and flattened into one neutral `Observation` per result
  across every run (`parse_sarif`). No canonical-state writes — this is an
  evidence adapter, not a state authority (ADR-0008).

The live CI/file-watch collection path is deferred this cycle (see
[`auth.md`](auth.md)); this connector is the parse surface only.

## Surface

- `parse_result(result, tool_name)` — one SARIF result → `Observation`
  (`ruleId` → title; `message.text` → excerpt, with `ruleId` then a stable
  `ruleId@uri:line` ref as fallback; first `physicalLocation` → `uri`/`startLine`;
  `tool`/`level`/`uri`/`start_line` → `metadata`).
- `parse_sarif(report)` — fan a report out to one `Observation` per
  `runs[].results[]`.
- `SarifConnector` — connector identity and capabilities (`PASSIVE`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
