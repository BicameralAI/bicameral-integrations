# Redaction backend recommendation (ADR-0020 evaluation evidence)

**Owner:** Kevin Knapp
**Date:** 2026-07-23
**Corpus digest:** `sha256:121b8cf9c1b641cd9d26870e93012b92075cb4f2c63bb8097f3cc81ed309b47c`
**Status:** advisory evidence for the #280 owner decision. Nothing here selects a backend.

## Hard-gate outcome

All four implemented candidates passed every executed hard gate: no raw
leakage, mandatory secret/credential protection, identity preservation,
fail-closed behavior on all 15 failure fixtures, deterministic output across
5 repeats, bounded cleanup with zero orphans, offline execution with zero
socket attempts, pinned provenance, and receipt-contract compatibility.
One gate is pending rather than passed for the two Presidio lanes:
`license-compatible` carries a `review_required` flag because MPL-2.0
(`certifi`) sits in their dependency closure and the pinned license policy
refuses to auto-classify it. MPL-2.0 is file-level copyleft and is
conventionally compatible with distribution, but the call is deliberately
left to the owner rather than passed silently.

## Weighted comparative score (advisory)

Sub-scores are computed from the artifacts in this directory with the
formulas below; anyone can reproduce the arithmetic from `metrics.json`,
`hard-gates.json`, `benchmark-results.json`, and `memory-isolated.json`.

- D1 detection (30): `30 x F2`
- D2 precision and preservation (20): `10 x precision + 10 x mean(decision-pass ratio, 1 - min(1,(destructive FP + clean-modified)/10))`
- D3 security and failure behavior (20): `20 x failure-expectation match ratio`, zeroed when any post-screen escape, determinism mismatch, or protected-field mutation occurred
- D4 performance and resource (10): mean of best-candidate/candidate ratios over warm p95 medium latency, isolated peak memory, installed package+model bytes, cold-start median (relative-to-best normalization: heavy engines score near zero by construction)
- D5 packaging and operational fitness (10): 10 minus itemized deductions listed below
- D6 maintainability and replacement seam (10): judged, reasons stated

| Candidate | D1 | D2 | D3 | D4 | D5 | D6 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bicameral-stdlib-v1` | 17.07 | 20.00 | 20.00 | 9.72 | 10.00 | 7.00 | **83.80** |
| `presidio-spacy-lg-v1` | 26.95 | 18.61 | 20.00 | 0.17 | 8.00 | 8.00 | **81.73** |
| `presidio-gliner-pii-v1` | 27.60 | 17.31 | 20.00 | 0.06 | 5.00 | 6.00 | **75.97** |
| `datafog-regex-v1` | 13.02 | 15.50 | 0.00 | 8.21 | 6.00 | 5.00 | **47.73** |

D5 deductions. presidio-spacy: 382 MB model provisioning via pinned wheel URL
(1), MPL-2.0 review flag (1). presidio-gliner: 1.16 GB unsigned `.bin`
checkpoint with an unpinnable backbone-tokenizer revision (2), HF cache and
offline-env requirements (1), MPL-2.0 review flag (1), torch>=2.6 CVE floor
to enforce (1). datafog: license metadata inconsistency (1), measured
fail-closed record loss on every catalog-secret record (3).

D6 reasons. baseline 7: zero dependencies but every new entity class is
hand-written regex work. presidio-spacy 8: active community project with a
first-class recognizer API behind the seam; governance moved from Microsoft
to the Data Privacy Stack org in 2026-06. presidio-gliner 6: gliner is
pre-1.0 with no semver promise and zero-shot labels are wording-sensitive.
datafog 5: single-vendor project, allowlist-only extension surface.

datafog's D3 zero reflects that 19 mandatory entities reached the last-resort
hard screen (which caught all of them); a detector that leans on the backstop
for every secret has no defense in depth of its own.

## Key measured facts

| | baseline | presidio-spacy | presidio-gliner | datafog |
|---|---:|---:|---:|---:|
| F2 | 0.569 | 0.898 | 0.920 | 0.434 |
| Recall | 0.514 | 0.908 | 0.927 | 0.385 |
| Precision | 1.000 | 0.861 | 0.894 | 0.875 |
| Decision preservation | 8/8 | 8/8 | 7/8 | 6/8 |
| Cold start (median) | 0.34 s | 15.6 s | 33.4 s | 0.73 s |
| Warm p95, medium field (2 KB) | 1.5 ms | 95 ms | 1.95 s | 1.3 ms |
| Warm p50, large field (20 KB) | 10 ms | 514 ms | 17.2 s | 7 ms |
| Max-admitted payload (~1 MiB), per call | 0.80 s | 36.5 s | 767 s | 0.69 s |
| Peak memory (isolated) | 35 MB | 1.11 GB | 3.03 GB | 42 MB |
| Installed package+model bytes | ~0 | 536 MB | 1.87 GB | 0.7 MB |

The production wrapper enforces a 5-second deadline per record. Against that
budget: the baseline and datafog clear every payload class; presidio-spacy
clears small through large and would time out only near the 1 MiB admission
ceiling; presidio-gliner would time out on large (20 KB) fields and is more
than two orders of magnitude outside budget at the ceiling. A timeout is
fail-closed record loss, so under the current budget GLiNER trades leakage
risk for availability loss on any non-trivial field.

## Recommendation

**Retain `bicameral-stdlib-v1` for the alpha ingress boundary (owner-decision
option 4: retention because no challenger earned replacement yet), and record
`presidio-spacy-lg-v1` as the qualified replacement candidate.**

Reasoning:

1. `datafog-regex-v1` is eliminated by evidence: it detects less than the
   baseline (F2 0.434 vs 0.569), modified 2 clean records, and every
   catalog-secret record survived only by last-resort rejection.
2. `presidio-gliner-pii-v1` does not justify replacement: its detection edge
   over presidio-spacy is small (F2 0.920 vs 0.898) while it costs 3 GB
   resident memory, a 33-second cold start, seconds per medium field,
   deadline-breaking latency on large fields, weaker information
   preservation (2 destructive false positives, 7/8 decision preservation,
   worst IP recall of the model lanes), an unpinnable tokenizer revision,
   and a pre-1.0 engine.
3. `presidio-spacy-lg-v1` is a genuine qualified challenger: it passes every
   hard gate, cuts the miss rate from 48.6% to 9.2% (person names 0/30 to
   27/30), preserves all decisions and all secrets, runs offline, and pins
   reproducibly. Its costs are real but bounded: 1.1 GB memory, 15.6 s cold
   start (which also prices each worker recycle after a timeout), ~95 ms
   p95 per medium field, one license review item, and a fresh
   community-governance transition upstream.
4. What the evidence cannot decide is whether contextual PII coverage is a
   REQUIREMENT for alpha. The baseline never leaks a mandatory secret (the
   hard screen guarantees that for every candidate), but it will pass person
   names, physical addresses, bare IPs, and account handles into Bot-bound
   evidence. If that class of data must be redacted at the alpha boundary,
   the baseline cannot deliver it and `presidio-spacy-lg-v1` is the
   evidence-backed selection (owner-decision option 2) despite the advisory
   score placing it 2.1 points behind the baseline; the gap is entirely the
   resource dimension's relative-to-best normalization, not a safety or
   quality deficit.

## Uncertainty

- The corpus is synthetic; absolute recall/precision will differ on real
  provider traffic. The comparative ordering is the reliable product.
- All numbers come from one pinned Windows host; model-lane determinism
  across platforms is explicitly not claimed (verified per environment).
- GLiNER was measured at one threshold (0.45) and one pinned label set; a
  tuned configuration could shift its precision/recall balance, not its
  resource profile.
- The MPL-2.0 (`certifi`) review flag and the datafog license metadata
  inconsistency are unresolved legal items, deliberately not auto-passed.
- spaCy NER on adversarially formatted text (markdown-heavy issue bodies)
  may under-detect relative to this corpus; the three missed person names
  in this run were all inside nested provider metadata.

## Required owner decisions (issue #280)

1. Choose an option: retain (1/4), select presidio-spacy (2), select another
   candidate (3), or require one bounded follow-up experiment (5).
2. State whether contextual PII (person names, addresses, IPs, account
   handles) must be redacted at the alpha ingress boundary; this single
   requirement decides between retention and the presidio-spacy path.
3. Resolve the MPL-2.0 `certifi` license review flag if a Presidio lane is
   ever selected.
4. If replacement is chosen: a separate governed implementation issue and PR
   (per ADR-0020), including budget tuning for the 1 MiB payload class and
   worker-recycle cost, regenerated tests/receipts/evidence, and a rollback
   pin.
