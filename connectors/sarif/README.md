# SARIF 2.1.0 Connector

Read-only SARIF 2.1.0 evidence adapter: flattens a static-analysis report into
neutral `Observation`s. **Status: Beta** (ADR-0012; catalog
security/compliance-evidence, priority P0, default trust tier T0). A Phase-1
foundation candidate from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Passive** — a SARIF 2.1.0 report (the output of a static-analysis tool) is
  imported as a file and flattened into one neutral `Observation` per result
  across every run (`parse_sarif`). No canonical-state writes — this is an
  evidence adapter, not a state authority (ADR-0008).

The live CI/file-watch collection path remains **deferred** to the operator
runtime (see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its `runtime.deliver_poll` → reference sink path is proven
end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo
dependency**. Live (gateway emission) remains gated on bicameral-bot #109.

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
