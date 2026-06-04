# Data Protection Mapping — GDPR / HIPAA

**Applicability + control alignment, not certification or legal advice.**
Neither GDPR nor HIPAA is a thing a library "passes"; both are obligations on
the data controller / covered entity (the operator). This documents the
technical controls in the repo that *support* those obligations and marks the
rest operator-owned.

## What this repo does with data

Connectors are **read-only parse surfaces**: they transform an external payload
into a neutral `Observation` (an excerpt + provenance ref) and hand it to the
universal adapter, which emits evidence to the gateway. The repo **does not**
persist canonical records, build profiles, or store data at rest.

## GDPR (principles → controls)

| Principle (Art. 5) | Control in this repo | Evidence |
|--------------------|----------------------|----------|
| Data minimisation | Connectors emit only the excerpt + refs needed as evidence; no bulk copy, no canonical store. | `connectors/*/connector.py`, `Observation` |
| Integrity & confidentiality (security) | Sensitive-data screen rejects secrets/PHI/PAN before emission; secret scanning; fail-closed webhook verify. | `sensitive.py` (`FX-SEC-001`), `secret-scan.yml`, `webhook_security.py` |
| Purpose limitation | Read-only → gateway; producers are non-authoritative (cannot repurpose into canonical state). | authority boundary (ADR-0004) |
| Accountability | Tamper-evident decision/audit trail. | `META_LEDGER`, `governance-gate.yml` |

**Operator-owned:** lawful basis, data-subject requests (access/erasure/portability),
DPIA for the deployed system, controller/processor agreements, retention,
international-transfer mechanisms.

## HIPAA (Security Rule → controls)

| Safeguard | Control | Evidence |
|-----------|---------|----------|
| Technical — access control / integrity | No canonical writes; constant-time, fail-closed webhook auth; hash-chained integrity gate. | `webhook_security.py`, `governance-gate.yml` |
| Technical — PHI handling | PHI patterns are a HARD reject in the producer screen (PHI never forwarded). | `adapter/core/sensitive.py` |
| Technical — audit controls | `META_LEDGER` + provenance audit trail. | `governance_gate.py` |

**Operator-owned:** Business Associate Agreements, the administrative and
physical safeguards, risk analysis of the deployed environment, and any actual
storage/transmission of PHI (this library is designed so PHI is screened out,
not stored).
