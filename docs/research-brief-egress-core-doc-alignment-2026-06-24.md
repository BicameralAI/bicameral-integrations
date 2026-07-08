# Research Brief — existing-documentation alignment for egress-as-core

**Date**: 2026-06-24
**Analyst**: The Qor-logic Analyst
**Target**: the existing `bicameral-integrations` documentation corpus, for alignment with the operator decision — **`bicameral-sidecar` deprecated for alpha; governed egress is a `bicameral-bot` core function**
**Scope**: every active doc referencing `sidecar` / `egress`; classify alignment; confirm the in-flight 3-doc correction (`fix/egress-core-relocation`) is correct + sufficient; flag any other doc needing alignment. **No code; advisory.**

---

## Executive Summary

The in-flight 3-doc correction (ADR-0019 + `PROJECTION_CONTRACT.md` + `CONNECTOR_AUTHORITY_LIMITS.md`) is
**correct and sufficient for egress alignment** — and it does something stronger than first assumed: it
**realigns ADR-0019 back to ADR-0008**, which was *never wrong*. ADR-0008 already says "the bot governs and
executes it as `Egress`"; ADR-0019's "bot/sidecar" was the drift. The word **"sidecar" is overloaded** across
the corpus, and the central alignment risk is a **false-positive sweep**: most "sidecar" hits are the
**AGT-as-a-sidecar-for-`bicameral-bot`** concept (a governance-toolkit spike), which is **unrelated** to the
deprecated `bicameral-sidecar` repo and must **not** be touched. Only **one** active-doc reference to the
deprecated repo in a still-live role survives — `CONNECTOR_AUTHORITY_LIMITS.md:49` (customer **monitoring**,
not egress) — and that is a separate, narrow decision, not part of this egress cycle. One stale **memory**
note also needs updating. 1 drift confirmed-and-fixed (ADR-0019), 1 separate-item flagged, 0 wrongful sweeps.

## Findings

### F1 — ADR-0008 is the canonical anchor and was always aligned (the correction realigns to it)

`docs/adr/0008-…not-state-authorities.md:89`: *"integrations proposes, the bot governs and **executes it as
`Egress`**. Integrations holds no approval/execution/retry state for it."* The **bot executes egress** — this
is exactly the egress-as-core posture. ADR-0008 never named sidecar. **ADR-0019 had drifted** to "bot/sidecar
retains the governed execution"; the in-flight correction restores ADR-0019 to ADR-0008's wording. **The
correction is an alignment *toward* the canonical anchor, not a new claim.** (No change needed to ADR-0008.)

### F2 — "sidecar" is overloaded — separate three meanings (avoid a false-positive sweep)

| Meaning | Where (active docs) | Affected by "bicameral-sidecar deprecated"? |
|---|---|---|
| **`bicameral-sidecar` REPO — egress execution** | ADR-0019, `PROJECTION_CONTRACT.md`, `CONNECTOR_AUTHORITY_LIMITS.md:39` | **Yes** — corrected in-flight (→ `bicameral-bot` core). Aligned. |
| **`bicameral-sidecar` REPO — customer monitoring** | `CONNECTOR_AUTHORITY_LIMITS.md:49–50` ("sidecar #5 Alex monitoring") | **Yes — STALE.** The only live non-egress repo reference. Separate decision (F4). |
| **AGT *as a sidecar for `bicameral-bot`*** (microsoft/agent-governance-toolkit spike, BACKLOG B3) | `docs/ecosystem/agt-sidecar-evaluation.md`, `consuming-gates.md:67`, `BACKLOG.md:18`, `GOVERNANCE_INDEX.md:86`, `SYSTEM_STATE.md:193,208` | **No — DIFFERENT CONCEPT.** A governance-toolkit process attached to the *bot*, not the deprecated repo. **Do NOT sweep** (false positive). |

### F3 — Other "egress" references are a different egress (evidence→gateway) — already aligned

- `ADR-0016:5,49` + `CONNECTOR_BACKEND_SETUP.md:60`: `--sink gateway` "real egress" / "egresses" — this is
  the **operator-runner delivering evidence to the bot gateway** (ingress-evidence egress), **not** projection
  egress to an external tool. Different concept; already correct; **no change**.

### F4 — The only genuinely stale active-doc item beyond egress: `CONNECTOR_AUTHORITY_LIMITS.md:49–50`

This describes customer **monitoring** opt-in via the `bicameral-sidecar` repo ("sidecar #5 Alex
monitoring"). If the repo is fully deprecated, this is stale — but it is a **monitoring** concern, not egress,
and its new home is an **operator decision** (likely also `bicameral-bot` core, but unconfirmed). **Out of
scope for the egress cycle** (the audited #226 plan correctly bounded it out). Recommend a **separate, narrow
follow-up** + operator confirmation on where customer monitoring lands.

### F5 — Sealed historical records are not retroactively edited

`META_LEDGER.md` entries, `research-brief-*.md`, `plan-*.md`, and `SHADOW_GENOME.md` carry "egress →
sidecar/sdk" mentions that were **true when written**. The ledger is append-only + hash-chained; briefs/plans
are point-in-time. **Do not edit** — they are accurate history. (The *current* posture lives in the active
contract docs, now corrected.)

### F6 — Stale memory note (out-of-repo, flag for update)

The session memory `bicameral-ecosystem-repo-split` records *"egress moved to sidecar/sdk."* This is now
**stale** — egress is a `bicameral-bot` core function; `bicameral-sidecar` is deprecated for alpha. Update the
memory (not a repo doc) so future sessions don't reintroduce the drift. (`bicameral-sdk`, the shared-contracts
repo, is **not** deprecated — only `bicameral-sidecar`; the memory should keep the SDK/evidence side intact.)

## Blueprint Alignment

| Claim under check | Finding | Status |
|---|---|---|
| Egress execution = `bicameral-bot` core (not sidecar/sdk) | ADR-0008:89 already says "bot executes Egress"; correction realigns ADR-0019 to it | MATCH (drift fixed) |
| The 3-doc correction is sufficient for **egress** alignment | no other active doc carries a stale *egress*-execution-in-sidecar claim (F2/F3) | MATCH |
| `bicameral-sdk` is also deprecated | NO — only `bicameral-sidecar`; SDK evidence contract (`CONNECTOR_AUTHORITY_LIMITS.md:3`) stays valid | DRIFT-AVOIDED (don't over-collapse "sidecar/sdk") |
| AGT-bot-sidecar references need updating | NO — different concept; false positive | MATCH (leave) |
| Customer-monitoring sidecar (`CONNECTOR_AUTHORITY_LIMITS.md:49`) | stale, but monitoring (not egress) — separate decision | DRIFT (separate follow-up) |

## Recommendations

1. **Land the 3-doc egress correction as-is** (`fix/egress-core-relocation`, audited #226/PASS) — it is
   correct, sufficient, and realigns ADR-0019 to ADR-0008. No additional egress edits required.
2. **Do NOT sweep the AGT-bot-sidecar references** (F2 row 3) — a different concept; sweeping them would be a
   wrongful edit. If the operator also kills the AGT-as-bot-sidecar idea, that is a *separate* BACKLOG-B3
   decision.
3. **File a narrow follow-up** for `CONNECTOR_AUTHORITY_LIMITS.md:49–50` (customer monitoring → new home),
   pending an operator decision on where monitoring lands now that `bicameral-sidecar` is deprecated. Not part
   of the egress cycle.
4. **Update the `bicameral-ecosystem-repo-split` memory** (F6): egress = bot-core; `bicameral-sidecar`
   deprecated; `bicameral-sdk` (contracts) unaffected.
5. **Leave sealed history untouched** (F5).

## Updated Knowledge

The repo's egress story has **one** canonical anchor (ADR-0008: the bot executes `Egress`); every other
egress doc must agree with it. "Sidecar" is a hazardous overloaded term — three meanings (the deprecated repo
for egress, the deprecated repo for monitoring, and AGT-as-a-bot-sidecar) — a deprecation sweep must classify
before editing, or it corrupts the AGT spike. Captured for the memory + as the alignment basis for landing
the correction.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
