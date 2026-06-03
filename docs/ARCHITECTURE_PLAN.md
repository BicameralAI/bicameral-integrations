# Architecture Plan

## Risk Grade: L1

### Risk Assessment

- [ ] Contains security/auth logic -> L3
- [ ] Modifies existing APIs -> L2
- [x] Documentation and repository bootstrap only -> L1

## File Tree (The Contract)

```text
adapters/
|-- <source adapter packages land here as implementation cycles begin>
mods/
|-- <EM-safe manifest, prompt, and fixture packages land here>
docs/
|-- adr/
|-- ARCHITECTURE_PLAN.md
|-- BACKLOG.md
|-- CONCEPT.md
|-- FEATURE_INDEX.md
|-- META_LEDGER.md
.github/
|-- ISSUE_TEMPLATE/
|-- workflows/secret-scan.yml
```

## Interface Contracts

### Source Adapter

- **Input**: External source payloads from Jira, Linear, Slack, Notion, GitHub, email, meetings, or customer workflows.
- **Output**: Bicameral protocol-shaped candidates, source evidence, hints, signals, and advisories.
- **Side Effects**: Emits to the Bicameral gateway only; does not write canonical event store artifacts.

### EM-Safe Mod

- **Input**: Declarative manifest, prompt content, fixtures, and review role metadata.
- **Output**: Typed candidates, evidence, dependency signals, routing hints, or advisory governance results.
- **Side Effects**: No direct signoff approval, compliance resolution, single-score confidence collapse, or direct blocking authority.

### Bicameral Gateway Compatibility

- **Input**: Objects emitted by adapters and mods.
- **Output**: Review-routed commands and evidence handled by `bicameral-bot/protocol/` contracts.
- **Side Effects**: Governance and materialization remain outside this repository.

## Data Flow

```text
External source -> bicameral-integrations adapter/mod -> typed protocol object -> bicameral-bot gateway -> governance policy -> event store substrate
```

## Dependencies

| Package | Justification | Vanilla Alternative |
|---------|---------------|---------------------|
| gitleaks pre-commit hook | Secret scanning before local commits and in CI | Manual review is insufficient for public source-adapter payload risk |

## Section 4 Razor Pre-Check

- [x] All planned functions <= 40 lines
- [x] All planned files <= 250 lines
- [x] No planned nesting > 3 levels

## Governance Controls

- Secret scanning is configured through `.pre-commit-config.yaml` and `.github/workflows/secret-scan.yml`.
- Branch protection should restrict force pushes on `main` and require PR review plus status checks before merge.
- Future implementation cycles that touch source behavior must update `docs/FEATURE_INDEX.md` in the same commit.

---
*Blueprint sealed. Awaiting GATE tribunal.*
