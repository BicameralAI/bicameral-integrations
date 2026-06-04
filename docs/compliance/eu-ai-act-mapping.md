# EU AI Act Mapping

Control alignment, not certification. This package is a producer-side component;
high-risk-system classification and deployer obligations belong to the operator
of the downstream AI system.

| Article | Obligation | How this repo aligns | Evidence |
|---------|-----------|----------------------|----------|
| Art. 9 — Risk management | Identify/mitigate risks across the lifecycle | L3 plans carry an `impact_assessment` (purpose, stakeholders, identified risks, mitigations, residual risks); VETO loop manages them before build. | `plan-*` impact_assessment; audit gates |
| Art. 12 — Record-keeping / logging | Automatic, tamper-evident event logging | Hash-chained `META_LEDGER` (re-verified in CI) + per-phase gate artifacts. | `governance-gate.yml`, `META_LEDGER` |
| Art. 13 — Transparency | Traceable provenance of automated steps | `ai_provenance` manifests record system/version/model-family/timestamp per gate. | `.qor/gates/*` provenance |
| Art. 14 — Human oversight | Oversight is recorded and meaningful | `ai_provenance.human_oversight` ∈ {PASS, VETO, ABSENT}; independent Judge issues PASS/VETO. | gate provenance, Entries #11/#15/#19 |
| Art. 50 — Transparency to users | Disclose AI involvement | Provenance + AI-attribution policy in outward artifacts is operator-configurable. | provenance manifests |

**Operator-owned:** Annex III high-risk classification, conformity assessment,
registration, and deployer transparency-to-end-users are decided by the system
operator, not this library.
