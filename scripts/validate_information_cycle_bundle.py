#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate an ingress information-cycle evidence bundle (GH #269 round 3).

Fail-closed, two layers:

1. **Structural** — the repo's stdlib JSON-Schema-subset checker against the
   closed ``ingest/_schema/information-cycle-evidence-bundle.schema.json``.
2. **Cryptographic + honesty semantics** — the exact 20-stage ordered ledger;
   contiguous sequences; unique stage ids; every stage after the first linked
   to the previous stage's output digest (carried through output-less
   stages); artifact digests recomputed from disk (LF-normalized bytes);
   aggregate digests recomputed; bundle_id recomputed over the canonical
   content minus ``bundle_id``/``started_at``/``completed_at``; a stage can
   never claim ``passed`` after an upstream failed/unproven stage; unproven
   stages carry their dependency record and NO fabricated outputs; and
   ``passed`` with an evidence class beyond ``component`` requires a receipt
   artifact of the required type (none exists in this repo yet, so such a
   claim fails closed here).

Exits non-zero on any failure.
"""

from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO / "scripts"))

from validate_connector_config import _check  # noqa: E402

_SCHEMA = _REPO / "ingest" / "_schema" / "information-cycle-evidence-bundle.schema.json"

REQUIRED_STAGE_ORDER = (
    "raw_acquisition",
    "acquisition_verification",
    "sanitized_capture",
    "provider_fact_extraction",
    "provider_neutral_observation",
    "guarded_redaction",
    "sanitized_observation",
    "redaction_receipt",
    "integration_advisories",
    "universal_normalization",
    "universal_advisories",
    "adapter_emission",
    "external_ingest_envelope",
    "cursor_or_delivery_decision",
    "gateway_negotiation",
    "bot_acceptance",
    "durable_evidence",
    "candidate_or_decision_lifecycle",
    "recall_transformation",
    "agent_session_exposure",
)

_BUNDLE_ID_EXCLUDED = ("bundle_id", "started_at", "completed_at")


def file_digest(path: Path) -> str:
    return "sha256:" + sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def aggregate_digest(artifacts: list[dict]) -> str:
    canon = json.dumps(
        sorted(
            ({"path": a["path"], "digest": a["digest"]} for a in artifacts),
            key=lambda item: item["path"],
        ),
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + sha256(canon.encode("utf-8")).hexdigest()


def bundle_id(bundle: dict) -> str:
    clone = {k: v for k, v in bundle.items() if k not in _BUNDLE_ID_EXCLUDED}
    canon = json.dumps(clone, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(canon.encode("utf-8")).hexdigest()


def semantic_errors(bundle: dict, repo: Path = _REPO) -> list[str]:
    errs: list[str] = []
    stages = bundle.get("stages", [])

    ids = [stage.get("stage_id") for stage in stages]
    if len(ids) != len(set(ids)):
        errs.append("duplicate stage ids")
    if tuple(ids) != REQUIRED_STAGE_ORDER:
        missing = [s for s in REQUIRED_STAGE_ORDER if s not in ids]
        if missing:
            errs.append(f"missing required stage(s): {missing}")
        else:
            errs.append("stages are reordered; the ledger order is fixed")
        return errs

    chain_anchor = ""
    upstream_ok = True
    for index, stage in enumerate(stages):
        label = f"stages[{index}]({stage['stage_id']})"
        if stage["sequence"] != index + 1:
            errs.append(f"{label}: sequence must be {index + 1}")

        output = stage.get("output")
        if output is not None:
            for artifact in output["artifacts"]:
                target = repo / artifact["path"]
                if not target.is_file():
                    errs.append(f"{label}: output artifact missing from disk: {artifact['path']}")
                elif file_digest(target) != artifact["digest"]:
                    errs.append(f"{label}: output artifact digest mismatch: {artifact['path']}")
            if output["aggregate_digest"] != aggregate_digest(output["artifacts"]):
                errs.append(f"{label}: output aggregate_digest incorrect")
        inputs = stage.get("input")
        if inputs is not None:
            for artifact in inputs["artifacts"]:
                target = repo / artifact["path"]
                if not target.is_file():
                    errs.append(f"{label}: input artifact missing from disk: {artifact['path']}")
                elif file_digest(target) != artifact["digest"]:
                    errs.append(f"{label}: input artifact digest mismatch: {artifact['path']}")
            if inputs["aggregate_digest"] != aggregate_digest(inputs["artifacts"]):
                errs.append(f"{label}: input aggregate_digest incorrect")

        if index == 0:
            if stage.get("previous_stage") is not None:
                errs.append(f"{label}: the first stage may not carry previous_stage")
        else:
            link = stage.get("previous_stage")
            prev = stages[index - 1]
            if not isinstance(link, dict):
                errs.append(f"{label}: previous_stage link is required")
            else:
                if link["stage_id"] != prev["stage_id"]:
                    errs.append(f"{label}: previous_stage.stage_id must be {prev['stage_id']}")
                if link["output_digest"] != chain_anchor:
                    errs.append(f"{label}: broken previous-stage digest link")

        if output is not None:
            chain_anchor = output["aggregate_digest"]

        status = stage["status"]
        if status == "passed":
            if not upstream_ok:
                errs.append(f"{label}: cannot claim passed after an upstream failed/unproven stage")
            if output is None:
                errs.append(f"{label}: passed requires output artifacts")
            if stage.get("transformation") is None:
                errs.append(f"{label}: passed requires the transformation record")
            if stage["evidence_class"] != "component":
                errs.append(
                    f"{label}: {stage['evidence_class']} claims require the "
                    "corresponding receipt type, which this repository does not "
                    "hold; only component claims are currently provable here"
                )
        elif status == "failed":
            if stage.get("failure") is None:
                errs.append(f"{label}: failed requires the failure record")
            upstream_ok = False
        elif status == "unproven":
            if stage.get("unproven") is None:
                errs.append(f"{label}: unproven requires the dependency record")
            if output is not None:
                errs.append(f"{label}: an unproven stage must not carry fabricated output artifacts")
            if stage["stage_id"] not in bundle.get("unproven_downstream", []):
                errs.append(f"{label}: unproven stage must be listed in unproven_downstream")
            upstream_ok = False

    declared = bundle.get("bundle_id", "")
    if declared != bundle_id(bundle):
        errs.append("bundle_id does not match the canonical bundle content")
    for stage_id in bundle.get("unproven_downstream", []):
        matching = [s for s in stages if s["stage_id"] == stage_id]
        if not matching or matching[0]["status"] != "unproven":
            errs.append(f"unproven_downstream lists {stage_id} but its stage is not unproven")
    return errs


def validate_bundle(path: Path) -> list[str]:
    bundle = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    errs = _check(bundle, schema, "bundle")
    if errs:
        return errs
    return semantic_errors(bundle)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_information_cycle_bundle.py <bundle.json>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    errs = validate_bundle(path)
    if errs:
        print("information-cycle bundle validation FAILED:", file=sys.stderr)
        for err in errs:
            print(f"- {err}", file=sys.stderr)
        return 1
    bundle = json.loads(path.read_text(encoding="utf-8"))
    proven = sum(1 for s in bundle["stages"] if s["status"] == "passed")
    print(
        f"information-cycle bundle OK: {proven}/{len(bundle['stages'])} stages "
        f"component-proven, {len(bundle['unproven_downstream'])} honestly unproven, "
        "digest chain intact"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
