# Research Brief — osv + sarif flip-ready (security batch)

**Date**: 2026-06-13
**Analyst**: The Qor-logic Analyst
**Target**: the security batch — `osv` (OSV.dev vulnerability records) + `sarif` (SARIF 2.1.0 static-analysis
findings) — assessed against the FX-CFG-001 descriptor contract + the flip-ready PII/security standard.
**Method**: verify-before-cite (SG-2026-06-12-A) — each provider contract re-verified against its live/frozen
source; flip-ready gap analysis; PII/secret review of each `connector.py` parse surface; explicit doc-standard
assessment per the standing attestation requirement.

---

## Executive Summary

Both are **Beta, harness-proven, read-only, no-credential** connectors (OSV = free unauthenticated query API;
SARIF = file import), **missing only the FX-CFG-001 descriptor** and **redact-and-pass parity**. **Zero contract
drift**: the OSV schema re-verified live (every field the connector reads matches) and SARIF 2.1.0 is a frozen
OASIS standard (pinned 2026-06-08). The headline is SARIF's: a **security-scanner finding message can embed the
very secret it flags**, and the current raw emission means FX-SEC-001 **hard-rejects** such a finding — *losing
the security signal*. Redact-and-pass is the correct fix and **improves** security coverage (scrub the secret
value, keep the finding). New lesson SG-2026-06-13-E.

| Connector | Contract drift | Code hardening | Descriptor | Effort |
|---|---|---|---|---|
| **osv** | none (schema re-verified live) | redact-and-pass summary+details (F1, low — public data, parity) | new | low |
| **sarif** | none (frozen OASIS 2.1.0) | redact-and-pass message.text (F1, medium — the security crux); doc-accuracy (F2) | new | medium |

## Contract Verification (verify-before-cite, SG-2026-06-12-A)

### osv — OSV schema: VERIFIED live, no drift
- **Live source**: [ossf.github.io/osv-schema](https://ossf.github.io/osv-schema/) (2026-06-13). Confirmed every
  field `parse_vuln` reads: `id`+`modified` **required**, all others optional; `summary`/`details` free-text
  strings; `severity` = array of `{type, score}`; `affected` = array of `{package.{name, ecosystem}}`;
  `references` = array of `{type, url}`; `aliases` = array of id strings. **MATCH** — no drift. The OSV.dev query
  client (`POST /v1/query`, `/v1/querybatch`, `GET /v1/vulns/{id}`) stays operator-runtime (deferred).

### sarif — SARIF 2.1.0: re-affirmed (frozen OASIS standard), no drift
- **Source**: [OASIS SARIF 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html) — a **frozen
  published standard** (no version drift possible). The connector's result paths
  (`runs[].results[].{ruleId, level, message.text, locations[].physicalLocation.{artifactLocation.uri,
  region.startLine}}`, `runs[].tool.driver.name`) match the spec and were verified against the OASIS schema
  2026-06-08 (recorded in references.md). Re-affirmed; a frozen spec needs no live re-fetch (provenance recorded
  honestly per SG-2026-06-13-D).

## Flip-Ready Gap & Findings (file:line)

### osv
- **Gap**: no `connectors/osv/config.json` / `SETUP.md`.
- **F1 — pii_on_wire (low)** — `connector.py:62-63,68,70` `summary` + `details` emitted raw. OSV data is **public
  technical vuln text** (low PII risk), but a description can embed a contributor email or a URL with a token, and
  redact-and-pass is non-destructive — apply it for parity (`redact()` on summary + details; keep the `id` floor).
  metadata (severity/packages/aliases) is technical — keep. No author field (good).

### sarif
- **Gap**: no `connectors/sarif/config.json` / `SETUP.md`.
- **F1 — pii_on_wire / SECURITY (medium — the crux)** — `connector.py:30,35` `parse_result` emits the SARIF
  `message.text` raw. A **secret-scanner** (gitleaks/trufflehog/CodeQL secret rules) emits SARIF whose
  `message.text` quotes the **detected secret** ("Detected AWS key `AKIA…` in `config.py`"). Today FX-SEC-001
  **hard-rejects** that emission (secret class) — so the finding is **dropped and the security signal is lost**.
  **Fix:** redact-and-pass `message.text` (`redact()`), which scrubs the secret value to `[redacted:secret]` and
  **preserves the finding** ("Detected AWS key `[redacted:secret]` in `config.py`"). This is strictly better for a
  *security* connector. **Keep the existing data minimization** — the connector reads `message.text` only, NOT
  `region.snippet.text` (the rawest secret surface); do not add snippet reading. FX-SEC-001 stays the backstop for
  anything redact misses.
- **F2 — descriptor_accuracy / doc (low)** — `references.md:31` claims "no user PII in the SARIF schema by design."
  Incomplete: the risk is not *user PII* but **secrets/credentials embedded in scanner messages**. Correct the
  references.md PII line + state the redact-and-pass-converts-hard-reject posture in the descriptor.

## Recommended Descriptor Shapes (for /qor-auto-dev-1)

- **osv** — `modes:["active"]`, `credentials:[]` (free unauthenticated API), `runtime_config` for the query
  scope/ecosystem filter + host pin (operator-runtime), `data.emits:["vulnerability"]`, pii_posture:
  redact-and-pass summary+details + public technical metadata, `instructions`: `configure` (set the query/poll
  scope, ref → auth.md) + `verify`. status live-ready.
- **sarif** — `modes:["passive"]`, `credentials:[]` (file import), `runtime_config` for the SARIF file path /
  CI-artifact glob, `data.emits:["finding"]`, pii_posture: redact-and-pass message.text (converts an FX-SEC-001
  hard-reject of a secret-bearing finding into scrubbed-evidence; reads message.text only, never the snippet),
  `instructions`: `configure` (point at the SARIF file/CI artifact, ref → auth.md) + `verify`.

## Recommendations (one /qor-auto-dev-1 cycle per connector, then a /qor-deep-audit purple-team)

1. **osv** — redact-and-pass summary+details (F1), author config.json, regen, references.md PII line, explicit
   doc-standard attestation, regression tests (email/secret in a description scrubbed; id floor un-redacted).
2. **sarif** — redact-and-pass message.text (F1 — the security crux), author config.json, regen, **correct the
   references.md PII line (F2)**, explicit attestation, regression tests (a secret in `message.text` is scrubbed
   AND the finding survives, i.e. the emission is NOT hard-rejected; the snippet is still never read).
3. After both substantiate → **/qor-deep-audit purple-team** (red→blue→verdict) across parse_robustness,
   pii_on_wire (verify impact vs the real gateway serializer — SG-2026-06-13-C; SARIF secret-in-message is the
   crux), identity_minimization, descriptor_accuracy, em_safe_contract, plus **path-traversal/oversize** for the
   SARIF file import; remediate; tag @jinhongkuan.

## Updated Knowledge (Shadow Genome)

- **SG-2026-06-13-E** — *for a security-scanner import, redact-and-pass BEATS relying on the FX-SEC-001 hard-screen,
  because the finding message can embed the very secret it flags.* A SARIF/secret-scanner result's `message.text`
  may quote a detected `AKIA…`/PAT/PEM; if emitted raw, FX-SEC-001 hard-REJECTS the whole emission — and the
  security signal ("a secret was found in `config.py`") is **lost**. Apply `redact()` so the secret value becomes
  `[redacted:secret]` while the finding survives as evidence; keep FX-SEC-001 as the backstop. Counter-intuitive:
  for a *security* connector, leaning only on the hard-screen REDUCES coverage. Also keep the data minimization of
  reading the finding **message** but never the raw code **snippet** (`region.snippet.text`). Reinforces
  SG-2026-06-13-A (redact-and-pass any free-text excerpt regardless of transport).

---

_Research complete. Zero contract drift (OSV schema re-verified live; SARIF a frozen OASIS standard); flip work is
descriptor authoring + redact-and-pass parity, with SARIF's message redaction materially improving security
coverage. Findings are advisory — implementation decisions remain with the Governor. EM-safe + read-only +
ADR-0012 hold._
