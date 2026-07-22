#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate an ingress information-cycle evidence bundle (GH #269 rounds 3-4).

Fail-closed, layered:

1. **Structural** — the repo's stdlib JSON-Schema-subset checker against the
   closed ``ingest/_schema/information-cycle-evidence-bundle.schema.json``.
2. **Implementation provenance** — ``implementation_provenance.reviewed_commit``
   must be an ancestor of the current head that already contains every listed
   component with the exact blob bytes; current file bytes must still match
   (behavior introduced after the reviewed commit fails); every passed stage's
   implementation path must be a registered component. An optional
   ``--emit-head-receipt`` writes the separate exact-current-head validation
   receipt (honest self-reference: the committed bundle never contains the SHA
   of the commit that contains itself).
3. **Two chains** — (a) the stage-RECORD chain: every stage carries
   ``stage_record_digest`` (canonical record minus ``stage_record_digest`` and
   ``previous_stage_record`` — the documented digest domain) and links to the
   immediately preceding record, covering unproven/failed stages too, so any
   tampering with reasons, authority, classes, or dependencies breaks the
   chain; (b) the transformation-OUTPUT dependency chain:
   ``depends_on_outputs`` cites only stages that actually produced outputs
   (with matching aggregate digests) or explicitly missing future prerequisites
   — an output-less stage can never be cited as having emitted a digest.
4. **Raw-sample policy** — the approved repository-owned raw value may appear
   ONLY in the stages its allowlist entry names (stored as digest+category,
   never the value); unknown emails anywhere fail; secret/PHI/PAN scans apply
   to every committed artifact; failures and warnings must be value-free.
5. **Evidence classes** — held evidence (``evidence_class``) is distinct from
   required future evidence (``required_evidence_class``): unproven stages hold
   ``none`` and declare their requirement; passed stages never hold ``none``;
   the bundle-level class equals the strongest ACTUALLY HELD class; live,
   terminal, or accepted claims require their receipt types (none exist here).

Exits non-zero on any failure.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
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
_RECORD_DIGEST_EXCLUDED = ("stage_record_digest", "previous_stage_record")

_CLASS_RANK = {"none": 0, "component": 1, "observed_live": 2, "terminal_product": 3, "human_accepted": 4}

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}\b")


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


def stage_record_digest(stage: dict) -> str:
    clone = {k: v for k, v in stage.items() if k not in _RECORD_DIGEST_EXCLUDED}
    canon = json.dumps(clone, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(canon.encode("utf-8")).hexdigest()


def value_digest(value: str) -> str:
    return "sha256:" + sha256(value.encode("utf-8")).hexdigest()


def _git(repo: Path, *args: str) -> tuple[int, bytes]:
    completed = subprocess.run(  # nosec B603 B607
        ["git", "-C", str(repo), *args], capture_output=True, check=False
    )
    return completed.returncode, completed.stdout


def git_blob_digest(repo: Path, commit: str, path: str) -> str | None:
    code, out = _git(repo, "show", f"{commit}:{path}")
    if code != 0:
        return None
    return "sha256:" + sha256(out.replace(b"\r\n", b"\n")).hexdigest()


def git_is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    code, _ = _git(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    return code == 0


def provenance_errors(bundle: dict, repo: Path, *, head: str | None = None) -> list[str]:
    errs: list[str] = []
    prov = bundle.get("implementation_provenance", {})
    reviewed = prov.get("reviewed_commit", "")
    if head is None:
        code, out = _git(repo, "rev-parse", "HEAD")
        head = out.decode().strip() if code == 0 else ""
    if not head:
        return ["cannot resolve the current head to validate provenance"]
    if not git_is_ancestor(repo, reviewed, head):
        errs.append(f"implementation_provenance.reviewed_commit {reviewed[:12]} is not an ancestor of the current head")
        return errs
    if bundle.get("integrations", {}).get("commit") != reviewed:
        errs.append("integrations.commit must equal implementation_provenance.reviewed_commit")
    component_paths = set()
    for component in prov.get("components", []):
        path = component["path"]
        component_paths.add(path)
        at_reviewed = git_blob_digest(repo, reviewed, path)
        if at_reviewed is None:
            errs.append(f"implementation path absent at reviewed_commit: {path}")
            continue
        if at_reviewed != component["blob_sha256"]:
            errs.append(f"implementation blob digest stale at reviewed_commit: {path}")
        current = repo / path
        if not current.is_file() or file_digest(current) != component["blob_sha256"]:
            errs.append(
                f"implementation changed after reviewed_commit (bundle describes stale behavior): {path}"
            )
    for stage in bundle.get("stages", []):
        transformation = stage.get("transformation")
        if stage.get("status") == "passed" and isinstance(transformation, dict):
            impl_path = transformation.get("implementation", {}).get("path", "")
            if impl_path and impl_path not in component_paths:
                errs.append(
                    f"stage {stage.get('stage_id')} cites implementation {impl_path} "
                    "not registered in implementation_provenance.components"
                )
    exact = prov.get("exact_head_validation")
    if isinstance(exact, dict) and exact.get("head_commit") != head:
        errs.append("exact_head_validation.head_commit does not match the current head")
    return errs


def _artifact_errors(label: str, block: dict, repo: Path, errs: list[str]) -> None:
    for artifact in block["artifacts"]:
        target = repo / artifact["path"]
        if not target.is_file():
            errs.append(f"{label}: artifact missing from disk: {artifact['path']}")
        elif file_digest(target) != artifact["digest"]:
            errs.append(f"{label}: artifact digest mismatch: {artifact['path']}")
    if block["aggregate_digest"] != aggregate_digest(block["artifacts"]):
        errs.append(f"{label}: aggregate_digest incorrect")


def semantic_errors(bundle: dict, repo: Path = _REPO, *, head: str | None = None) -> list[str]:
    errs: list[str] = []
    stages = bundle.get("stages", [])

    ids = [stage.get("stage_id") for stage in stages]
    if len(ids) != len(set(ids)):
        errs.append("duplicate stage ids")
    if tuple(ids) != REQUIRED_STAGE_ORDER:
        missing = [s for s in REQUIRED_STAGE_ORDER if s not in ids]
        errs.append(f"missing required stage(s): {missing}" if missing else "stages are reordered; the ledger order is fixed")
        return errs

    outputs_by_stage: dict[str, str] = {}
    upstream_ok = True
    held_ranks = [0]

    for index, stage in enumerate(stages):
        label = f"stages[{index}]({stage['stage_id']})"

        # Stage-RECORD chain (covers every stage, including unproven/failed).
        declared_record = stage.get("stage_record_digest", "")
        if declared_record != stage_record_digest(stage):
            errs.append(f"{label}: stage_record_digest does not match the record content")
        if index == 0:
            if stage.get("previous_stage_record") is not None:
                errs.append(f"{label}: the first stage may not carry previous_stage_record")
        else:
            link = stage.get("previous_stage_record")
            prev = stages[index - 1]
            if not isinstance(link, dict):
                errs.append(f"{label}: previous_stage_record link is required")
            else:
                if link["stage_id"] != prev["stage_id"]:
                    errs.append(f"{label}: previous_stage_record.stage_id must be {prev['stage_id']}")
                if link["stage_record_digest"] != prev.get("stage_record_digest"):
                    errs.append(f"{label}: broken stage-record chain link")

        output = stage.get("output")
        if output is not None:
            _artifact_errors(f"{label} output", output, repo, errs)
            outputs_by_stage[stage["stage_id"]] = output["aggregate_digest"]
        if stage.get("input") is not None:
            _artifact_errors(f"{label} input", stage["input"], repo, errs)

        # Transformation-OUTPUT dependency chain (separate from record order).
        for dep_index, dep in enumerate(stage.get("depends_on_outputs", [])):
            dep_label = f"{label}.depends_on_outputs[{dep_index}]"
            target = dep.get("stage_id", "")
            has_digest = "output_digest" in dep
            has_missing = "required_output" in dep or dep.get("status") == "missing"
            if has_digest == has_missing:
                errs.append(f"{dep_label}: exactly one of output_digest or required_output+status=missing")
                continue
            if has_digest:
                if target not in outputs_by_stage:
                    errs.append(
                        f"{dep_label}: cites {target} as having emitted an output, "
                        "but that stage produced no output artifacts"
                    )
                elif dep["output_digest"] != outputs_by_stage[target]:
                    errs.append(f"{dep_label}: output digest does not match {target}'s aggregate")
            else:
                if dep.get("status") != "missing" or not str(dep.get("required_output", "")).strip():
                    errs.append(f"{dep_label}: missing prerequisite must carry required_output and status=missing")
                target_stage = next((s for s in stages if s["stage_id"] == target), None)
                if target_stage is not None and target_stage.get("output") is not None:
                    errs.append(f"{dep_label}: {target} has real output; it cannot be cited as missing")

        status = stage["status"]
        held = stage.get("evidence_class", "")
        required_class = stage.get("required_evidence_class")

        if status == "passed":
            if not upstream_ok:
                errs.append(f"{label}: cannot claim passed after an upstream failed/unproven stage")
            if output is None:
                errs.append(f"{label}: passed requires output artifacts")
            if stage.get("transformation") is None:
                errs.append(f"{label}: passed requires the transformation record")
            if held == "none":
                errs.append(f"{label}: a passed stage cannot hold evidence_class none")
            elif held != "component":
                errs.append(
                    f"{label}: held class {held} requires the corresponding receipt "
                    "type, which this repository does not hold; only component "
                    "evidence is currently provable here"
                )
            held_ranks.append(_CLASS_RANK.get(held, 0) if held == "component" else 0)
        elif status == "failed":
            if stage.get("failure") is None:
                errs.append(f"{label}: failed requires the failure record")
            upstream_ok = False
        elif status == "unproven":
            if stage.get("unproven") is None:
                errs.append(f"{label}: unproven requires the dependency record")
            if output is not None:
                errs.append(f"{label}: an unproven stage must not carry fabricated output artifacts")
            if held != "none":
                errs.append(f"{label}: an unproven stage holds no evidence; evidence_class must be none")
            if required_class not in ("component", "observed_live", "terminal_product", "human_accepted"):
                errs.append(f"{label}: unproven requires required_evidence_class (the future class, not held)")
            if stage["stage_id"] not in bundle.get("unproven_downstream", []):
                errs.append(f"{label}: unproven stage must be listed in unproven_downstream")
            upstream_ok = False

        # Value-free failure/warning surfaces.
        for text in ([json.dumps(stage.get("failure"))] if stage.get("failure") else []) + list(stage.get("warnings", [])):
            if text and _EMAIL_RE.search(str(text)):
                errs.append(f"{label}: raw values must not appear in failures or warnings")

    strongest_held = max(held_ranks)
    declared_bundle_class = bundle.get("evidence_class", "")
    if _CLASS_RANK.get(declared_bundle_class, -1) != strongest_held:
        errs.append(
            "bundle evidence_class must equal the strongest ACTUALLY HELD stage "
            "class (future required classes never escalate it)"
        )

    declared = bundle.get("bundle_id", "")
    if declared != bundle_id(bundle):
        errs.append("bundle_id does not match the canonical bundle content")
    for stage_id in bundle.get("unproven_downstream", []):
        matching = [s for s in stages if s["stage_id"] == stage_id]
        if not matching or matching[0]["status"] != "unproven":
            errs.append(f"unproven_downstream lists {stage_id} but its stage is not unproven")

    errs.extend(raw_sample_errors(bundle, repo))
    errs.extend(provenance_errors(bundle, repo, head=head))
    return errs


def raw_sample_errors(bundle: dict, repo: Path) -> list[str]:
    """Stage-aware raw-sample safety: the approved raw value may appear only in
    its allowlisted stages; unknown emails and catalog hits fail everywhere."""
    errs: list[str] = []
    policy = bundle.get("raw_sample_policy", {})
    permitted: dict[str, set[str]] = {}
    for item in policy.get("permitted_raw_values", []):
        permitted[item["value_digest"]] = set(item.get("allowed_stage_ids", []))

    from adapter.core.sensitive import detect_sensitive

    for stage in bundle.get("stages", []):
        output = stage.get("output")
        if output is None:
            continue
        for artifact in output["artifacts"]:
            target = repo / artifact["path"]
            if not target.is_file():
                continue
            text = target.read_text(encoding="utf-8")
            if detect_sensitive(text):
                errs.append(f"{artifact['path']}: secret/PHI/PAN detected in committed artifact")
            for email in set(_EMAIL_RE.findall(text)):
                digest = value_digest(email)
                if digest not in permitted:
                    errs.append(f"{artifact['path']}: unknown email present (not in raw_sample_policy)")
                elif stage["stage_id"] not in permitted[digest]:
                    errs.append(
                        f"{artifact['path']}: permitted raw value appears outside its "
                        f"allowed stage(s) (stage {stage['stage_id']})"
                    )
    bundle_text = json.dumps(bundle, sort_keys=True)
    for email in set(_EMAIL_RE.findall(bundle_text)):
        errs.append("bundle metadata must not contain raw email values")
        break
    return errs


def emit_head_receipt(bundle: dict, repo: Path, out_path: Path) -> dict:
    """The separate exact-current-head validation receipt (honest
    self-reference: generated AFTER the bundle exists, at the actual head)."""
    code, out = _git(repo, "rev-parse", "HEAD")
    head = out.decode().strip()
    components = [
        {"path": c["path"], "blob_sha256": git_blob_digest(repo, head, c["path"]) or ""}
        for c in bundle.get("implementation_provenance", {}).get("components", [])
    ]
    receipt = {
        "schema_version": 1,
        "kind": "information-cycle-exact-head-validation-receipt",
        "bundle_id": bundle.get("bundle_id", ""),
        "head_commit": head,
        "reviewed_commit": bundle.get("implementation_provenance", {}).get("reviewed_commit", ""),
        "components": components,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "receipt_id": "",
    }
    unsigned = {k: v for k, v in receipt.items() if k not in ("receipt_id", "generated_at")}
    receipt["receipt_id"] = "sha256:" + sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def validate_bundle(path: Path, *, head: str | None = None) -> list[str]:
    bundle = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    errs = _check(bundle, schema, "bundle")
    if errs:
        return errs
    return semantic_errors(bundle, head=head)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    parser.add_argument("--emit-head-receipt", default=None)
    args = parser.parse_args()
    path = Path(args.bundle)
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
        "record chain + output lineage + provenance intact"
    )
    if args.emit_head_receipt:
        receipt = emit_head_receipt(bundle, _REPO, Path(args.emit_head_receipt))
        print(f"exact-head validation receipt: {receipt['receipt_id']} (head {receipt['head_commit'][:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
