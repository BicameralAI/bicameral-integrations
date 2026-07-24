# Redaction backend decision validation (ADR-0020 evaluation evidence)

**Owner:** Kevin Knapp
**Evidence dates:** corpus run 2026-07-23, governed-boundary revalidation 2026-07-24
**Status:** decision-validation evidence. The alpha architecture decision is recorded by the owner: retain the current Bicameral engine for alpha, with `presidio-spacy-lg-v1` qualified as the governed replacement candidate. Generalized contextual PII detection is outside the universal alpha requirement. This document validates those decision assumptions against measured evidence and records the replacement qualification. It does not reopen selection; reopening would require measured evidence that directly falsifies an assumption below, and none does.

## Decision assumptions validated

1. **The current engine protects every mandatory secret and credential at the alpha boundary.** Confirmed: zero post-screen escapes, zero mandatory values in any emitted output, precision 1.000 with zero false positives across all negative controls, 8/8 decision preservation, deterministic across repeated runs, and every fail-closed fixture behaves with the expected typed reason through the governed worker boundary.
2. **The current engine meets the production 5-second deadline on every admitted payload class.** Confirmed by enforced-termination probes through the candidate worker: small through maximum-admitted all complete inside budget (max ~0.8 s), including the cold-worker probe with initialization inside the budget.
3. **Generalized contextual PII (person names, addresses, bare IPs, account handles) is not a universal alpha requirement.** This is an owner scope decision, not a measured property. The measured consequence of retention is quantified honestly: the baseline's recall on the synthetic corpus is 0.514 (F2 0.569), with all misses in contextual classes (30 person names, 7 addresses, 7 IPs, 4 account ids, 2 DOB, 2 government ids, 1 IBAN). Nothing in the evidence contradicts scoping these classes out of the universal alpha boundary; the classes and counts are recorded so the scope decision stays reviewable.
4. **A governed replacement exists if contextual coverage becomes a requirement.** Confirmed: `presidio-spacy-lg-v1` qualification below.

## Replacement qualification: presidio-spacy-lg-v1

Qualified as the governed replacement candidate on this evidence:

- passes every executed hard gate through the same governed worker boundary (fail-closed hang/crash/storm probes terminated its actual worker; zero orphans, candidate-bound cleanup evidence; complete production receipts validated against the external-ingest schema and the literal runtime sink gate);
- detection: F2 0.898, recall 0.908 vs baseline 0.514 (person names 27/30, all addresses, all IPs, all emails/phones), zero destructive false positives, 8/8 decision preservation, zero clean negative controls modified;
- mandatory secret protection preserved by construction (the Bicameral catalog runs inside the candidate configuration);
- offline: zero socket attempts under network denial; reproducibly pinned (spaCy model wheel by URL+version, all package pins in the configuration digest);
- measured costs, to be priced into any activation: 1.11 GB resident memory, worker prewarm ~13 s in the spawned-worker path (12.6 s direct cold init), ~44 ms p95 per medium field, and two enforced-termination findings from the production-deadline probes: the maximum-admitted (~1 MiB) payload exceeds the 5-second budget, and a cold (unprewarmed) worker cannot initialize inside the budget. Activation therefore requires a prewarmed-worker deployment posture and either a payload-class budget carve-out or acceptance of fail-closed loss at the admission ceiling.

Qualification is complete on the evidence side. One owner item gates activation, not qualification: the `license-compatible` hard gate is honestly `pending` on the MPL-2.0 (`certifi`) `review_required` flag, so `selection_eligible` remains false for both Presidio lanes until the owner records the license call. Under the tri-state eligibility rule (pending is never passed), this is the single item between the qualified replacement and formal eligibility.

## Non-qualified candidates

- `presidio-gliner-pii-v1`: not qualified as the replacement. Its detection edge over presidio-spacy is small (F2 0.920 vs 0.898) against 3.03 GB memory, 33 s cold start, enforced-termination failures on large (20 KB) fields at the production budget, 2 destructive false positives, 7/8 decision preservation, an unpinnable backbone-tokenizer revision, and a pre-1.0 engine.
- `datafog-regex-v1`: eliminated. Detects less than the baseline (F2 0.434), modified 2 clean records, and every catalog-secret record survived only by last-resort hard-screen rejection (fail-closed record loss).

## Weighted comparative score (advisory)

Reproduced mechanically by `weighted-scores.json` from `metrics.json`, `hard-gates.json`, `benchmark-results.json`, and `memory-isolated.json`; formulas and itemized deductions live in the scoring module and the artifact.

| Candidate | D1 | D2 | D3 | D4 | D5 | D6 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bicameral-stdlib-v1` | 17.07 | 20.00 | 20.00 | 9.24 | 10.00 | 7.00 | **83.31** |
| `presidio-spacy-lg-v1` | 26.95 | 18.61 | 20.00 | 0.17 | 8.00 | 8.00 | **81.73** |
| `presidio-gliner-pii-v1` | 27.60 | 17.31 | 20.00 | 0.06 | 5.00 | 6.00 | **75.97** |
| `datafog-regex-v1` | 13.02 | 15.50 | 0.00 | 8.20 | 6.00 | 5.00 | **47.72** |

The score is advisory. The baseline-first ordering reflects the resource dimension's relative-to-best normalization; it does not contradict the replacement qualification, which is a coverage-capability judgment the owner has scoped.

## Key measured facts

| | baseline | presidio-spacy | presidio-gliner | datafog |
|---|---:|---:|---:|---:|
| F2 | 0.569 | 0.898 | 0.920 | 0.434 |
| Recall | 0.514 | 0.908 | 0.927 | 0.385 |
| Precision | 1.000 | 0.861 | 0.894 | 0.875 |
| Decision preservation | 8/8 | 8/8 | 7/8 | 6/8 |
| Cold start (direct, median) | 0.24 s | 12.6 s | 20.0 s | 0.53 s |
| Worker prewarm (spawned path) | 0.4 s | 13.4 s | 20.3 s | 0.6 s |
| Warm p95, medium field (2 KB) | 1.1 ms | 44 ms | 1.19 s | 0.8 ms |
| Peak memory (isolated) | 35 MB | 1.11 GB | 3.03 GB | 42 MB |
| Production 5 s budget: classes failing by enforced termination | none | max-admitted; cold worker | large; max-admitted; cold worker | none killed; medium through max fail closed at the hard screen (missed catalog secrets) |

## Uncertainty

- The corpus is synthetic; absolute recall/precision will differ on real provider traffic. The comparative ordering is the reliable product.
- All numbers come from one pinned Windows host; model-lane determinism across platforms is explicitly not claimed (verified per environment).
- GLiNER was measured at one threshold and label set.
- The MPL-2.0 (`certifi`) review flag and the datafog license metadata inconsistency are unresolved owner items, deliberately not auto-passed.
- spaCy NER on adversarially formatted text may under-detect relative to this corpus; the three missed person names were all inside nested provider metadata.

## Remaining owner items

1. Record the ADR-0020 owner decision packet (retain baseline; presidio-spacy qualified replacement; contextual PII outside the universal alpha requirement) once the exact-head adversarial review verdict permits.
2. Resolve the MPL-2.0 `certifi` review flag to make the qualified replacement formally selection-eligible.
3. If the replacement is ever activated: a separate governed implementation issue and PR with prewarmed-worker deployment posture, budget treatment for the maximum-admitted payload class, regenerated tests/receipts/evidence, and a rollback pin.

## Machine bindings

The fenced block below is written mechanically by
`python scripts/evaluate_redaction_backends.py bind-recommendation` and
verified byte-for-byte by `verify`; it binds this document to the exact
artifact digests it describes.

```json redaction-recommendation-bindings
{
  "artifact_sha256": {
    "hard-gates.json": "sha256:73d2aebf65187f6bd6a73321e59e3388d0ae6398f1e229910d5832f8d295a553",
    "metrics.json": "sha256:7f33b435c0dd8c825df65d9cb7788a4f0a06a03d0c032f0f9e21878cf1a054df",
    "weighted-scores.json": "sha256:ce49875a1703efe50b5747d46b5fa4694ae41f2a6e9d940463142d136ac10cc2"
  },
  "candidates": [
    {
      "aggregate_state": "passed",
      "candidate_id": "bicameral-stdlib-v1",
      "configuration_digest": "sha256:9b2e1d77b4f5995237a983c23e6df711d03ba8184b531b6fcb4645f8fc91faaf",
      "f2": 0.5691056910569106,
      "precision": 1.0,
      "recall": 0.5137614678899083,
      "selection_eligible": true,
      "weighted_total": 83.3105
    },
    {
      "aggregate_state": "passed",
      "candidate_id": "datafog-regex-v1",
      "configuration_digest": "sha256:571273ec8a5384b0d26c44e25389c7191bf2a03fe1aafac87e234a50cce70941",
      "f2": 0.4338842975206612,
      "precision": 0.875,
      "recall": 0.3853211009174312,
      "selection_eligible": true,
      "weighted_total": 47.7151
    },
    {
      "aggregate_state": "pending",
      "candidate_id": "presidio-gliner-pii-v1",
      "configuration_digest": "sha256:e422a21203a54fd8a2747668fd5d95ca8db56f457838941df327112b830a264d",
      "f2": 0.9198542805100183,
      "precision": 0.8938053097345132,
      "recall": 0.926605504587156,
      "selection_eligible": false,
      "weighted_total": 75.9703
    },
    {
      "aggregate_state": "pending",
      "candidate_id": "presidio-spacy-lg-v1",
      "configuration_digest": "sha256:5d43bf7c0de4b7ff083947dde3bbb12910635075a802ed02886d515e3cc8afb0",
      "f2": 0.898366606170599,
      "precision": 0.8608695652173913,
      "recall": 0.908256880733945,
      "selection_eligible": false,
      "weighted_total": 81.7341
    }
  ],
  "corpus_sha256": "sha256:121b8cf9c1b641cd9d26870e93012b92075cb4f2c63bb8097f3cc81ed309b47c",
  "evaluation_input_sha256": "sha256:b00e02728e6e6ed24e582ce0f6cbf181e5298f2af58b5b4a1c65b5e4cd5a6229"
}
```
