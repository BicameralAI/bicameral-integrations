# Redaction backend owner decision packet

**Status:** Owner decision template under ADR-0020  
**Decision owner:** Kevin Knapp  
**Decision issue:** #280  
**Schema:** `tests/redaction_evaluation/schema/owner-decision-packet.schema.json`

## Purpose

This packet records the owner decision after the comparative spike and independent adversarial review are complete.

It deliberately separates:

1. measured evidence;
2. candidate eligibility;
3. comparative scoring;
4. operational and security tradeoffs;
5. unresolved uncertainty;
6. adversarial review findings;
7. owner judgment;
8. migration or retention disposition.

The evaluation may recommend. Only Kevin decides.

## Required prerequisites

Do not prepare an accepted packet until:

- [ ] ADR-0020 is accepted as the governing evaluation decision.
- [ ] The comparative spike is bound to an exact PR and head SHA.
- [ ] The spike remains unmerged.
- [ ] The corpus manifest and expected annotations pass the repository gate.
- [ ] Candidate identities, versions, models, recognizers, mappings, and configurations are digest-pinned.
- [ ] Hard-gate results are complete for every implemented candidate.
- [ ] Metrics and benchmarks reproduce from the documented top-level command.
- [ ] Dependency, license, and vulnerability reports are complete.
- [ ] The adversarial review verdict is `owner_decision_ready`.
- [ ] No blocker discrepancy remains.

## Allowed outcomes

### `retain_baseline`

Use when the current Bicameral engine remains the alpha choice because no challenger earns replacement or because its operational simplicity outweighs measured detection gains.

Required disposition:

- `selected_candidate_id`: `null`
- `migration_disposition`: `no_change`
- `migration_issue`: `null`
- `production_evidence_rebind_required`: `false`

The packet must state what future evidence would justify reopening the decision.

### `select_candidate`

Use when one eligible challenger passes every hard gate and provides enough measured benefit to justify migration cost.

Required disposition:

- `selected_candidate_id`: exact candidate ID
- `migration_disposition`: `implementation_issue_required`
- `production_evidence_rebind_required`: `true`

Create a separate governed implementation issue. Do not treat the evaluation spike as production code.

### `bounded_follow_up_required`

Use when the existing evidence is valid but one narrow unresolved experiment is necessary before selection.

Required disposition:

- `selected_candidate_id`: `null`
- `migration_disposition`: `bounded_follow_up_required`
- `production_evidence_rebind_required`: `false`

The packet must name the exact question, candidate scope, evidence required, and completion boundary. It must not reopen unlimited framework research.

## Evidence bindings

Bind the packet to exact digests for:

- evaluation PR and exact head;
- PR #269 exact parent head;
- corpus;
- candidate matrix;
- hard-gate results;
- metrics;
- benchmarks;
- dependency report;
- license report;
- vulnerability report;
- adversarial review.

Any changed binding invalidates the accepted packet and requires a new owner decision.

## Decision writing guidance

### Measured evidence

State only what the artifacts directly demonstrate, including:

- eligible and ineligible candidates;
- failed hard gates;
- detection and preservation metrics;
- performance and memory results;
- package and model cost;
- dependency, license, and vulnerability findings;
- offline behavior;
- reproducibility status.

### Inference

Clearly label inferences, such as expected maintenance burden, deployment friction, or future recognizer extensibility. Tie each inference to supporting measurements or primary-source evidence.

### Owner judgment

State the product and engineering judgment that measurements cannot mechanically decide, including acceptable operational cost, alpha timing, security margin, and replacement value.

Do not disguise owner judgment as a metric.

## JSON packet template

Create `artifacts/redaction-evaluation/owner-decision.json` conforming to the schema.

```json
{
  "schema_version": 1,
  "decision_id": "redaction-backend-alpha-v1",
  "decision_owner": "Kevin Knapp",
  "status": "proposed",
  "outcome": "bounded_follow_up_required",
  "selected_candidate_id": null,
  "evidence_bindings": {
    "evaluation_repository": "BicameralAI/bicameral-integrations",
    "evaluation_pr_number": 0,
    "evaluation_head_sha": "0000000000000000000000000000000000000000",
    "parent_pr_269_head_sha": "fd69ff2742363b5d619bc073b8e8490c0f50733d",
    "corpus_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "candidate_matrix_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "hard_gates_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "metrics_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "benchmarks_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "dependency_report_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "license_report_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "vulnerability_report_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "adversarial_review_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  },
  "eligible_candidates": [],
  "ineligible_candidates": [],
  "measured_summary": {
    "baseline_candidate_id": "bicameral-stdlib-redaction",
    "recommended_candidate_id": null,
    "recommendation_confidence": "low",
    "score_summary": [],
    "material_tradeoffs": []
  },
  "owner_judgment": "Pending owner review.",
  "rationale": "Pending exact evaluation and adversarial review evidence.",
  "unresolved_uncertainty": [],
  "migration_disposition": "bounded_follow_up_required",
  "migration_issue": null,
  "rollback_requirements": [],
  "architecture_update_required": false,
  "production_evidence_rebind_required": false,
  "release_authority_granted": false,
  "decided_at": null
}
```

Placeholder zero values are template-only and must not appear in an accepted decision packet.

## Post-decision actions

### When retaining the baseline

- update ADR-0020 with the accepted retention rationale;
- reconcile Factory architecture only if the accepted wording changed;
- document the evidence threshold for reopening;
- leave PR #269 unchanged unless other accepted work requires rebinding.

### When selecting a challenger

- create a separate implementation issue and PR;
- preserve the Bicameral wrapper and hard-screen postcondition;
- add production dependency and model pinning intentionally;
- prove packaging and offline installation;
- regenerate affected goldens, receipts, evidence digests, and exact-head review;
- provide rollback to the previously accepted backend;
- reconcile Factory architecture after implementation acceptance, not before.

### When requiring bounded follow-up

- create one narrow issue with explicit completion evidence;
- preserve the current production choice meanwhile;
- do not broaden candidate discovery unless the discrepancy specifically requires it.

## Authority boundary

An accepted owner packet records the architecture choice. It does not by itself:

- merge production implementation;
- rebind PR #269 evidence;
- supersede PR #262;
- assign a Release Unit;
- establish merge eligibility;
- grant topology, deployment, Product, or human acceptance;
- set `release_authority_granted` to true.
