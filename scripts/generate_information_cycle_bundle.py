#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate the ingress information-cycle evidence bundle (GH #269 round 3).

Builds the 20-stage cryptographically linked evidence ledger for one manifest
route using the SAME production code paths as delivery (harness acquisition,
``pipeline.normalize`` with the guarded redaction boundary, gateway mapping,
cursor policy). There is deliberately no second illustrative transformation
implementation: every recomputed artifact is digest-compared against the
committed goldens and the generator aborts on any mismatch.

Stages 1-14 are populated to component evidence. Stages 15-20 are explicit
``unproven`` downstream records naming the required future receipt type, the
responsible authority, and the implementation dependency (gateway negotiation
depends on Integrations PR #262; Bot acceptance and later lifecycle stages
belong to Bot/Factory/recall/host surfaces; credentialed evidence runs are
deferred). No gateway or Bot evidence is invented.

    python scripts/generate_information_cycle_bundle.py \\
        --route local_directory/passive_import \\
        --out ingest/evidence/local_directory-passive_import
"""

from __future__ import annotations

import argparse
import json
# Fixed-argv `git rev-parse` only; no shell, no untrusted input.
import subprocess  # nosec B404
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO / "scripts"))

from runtime.ingest_conformance_harness import (  # noqa: E402
    CONTRACT_ID,
    SEMANTIC_FINGERPRINT,
    canonical_digest,
    collect_artifacts,
)
from validate_information_cycle_bundle import (  # noqa: E402
    aggregate_digest,
    bundle_id,
    file_digest,
)

_MANIFEST = _REPO / "ingest" / "alpha-ingest-manifest.json"


def _artifact(path: str, media_type: str = "application/json", *, read_from: Path | None = None) -> dict[str, Any]:
    source = read_from if read_from is not None else _REPO / path
    return {"path": path, "digest": file_digest(source), "media_type": media_type}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _authority(owner: str, may: list[str], may_not: list[str]) -> dict[str, Any]:
    return {"owner": owner, "may_create": may, "may_not_create": may_not}


def _out(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    return {"artifacts": artifacts, "aggregate_digest": aggregate_digest(artifacts)}


def build_bundle(route: str, out_dir: Path) -> dict[str, Any]:
    connector, mode = route.split("/", 1)
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    entry = next(
        e for e in manifest["entries"] if e["connector_id"] == connector and e["mode"] == mode
    )
    if entry["conformance_state"]["real_capture"] != "recorded":
        raise SystemExit(f"{route}: evidence bundles require a recorded real capture")
    if route != "local_directory/passive_import":
        raise SystemExit("only the local_directory/passive_import example is implemented")

    capture_rel = entry["real_capture"]["path"]
    ledger_rel = entry["real_capture"]["sanitization_ledger"]
    capture = json.loads((_REPO / capture_rel).read_text(encoding="utf-8"))
    ledger = json.loads((_REPO / ledger_rel).read_text(encoding="utf-8"))
    golden = entry["expected"]

    # Recompute every checkpoint through the PRODUCTION path and require exact
    # agreement with the committed goldens before writing any evidence.
    artifacts = collect_artifacts(entry)
    for key, rel in golden.items():
        if key == "gateway_receipt" or not rel:
            continue
        committed = json.loads((_REPO / rel).read_text(encoding="utf-8"))
        if canonical_digest(artifacts[key]) != canonical_digest(committed):
            raise SystemExit(f"production output diverges from committed golden: {key}")

    # Recorded artifact paths are always the canonical evidence location;
    # out_dir only controls where files are WRITTEN (a tmp out_dir regenerates
    # byte-identical artifacts for deterministic comparison).
    rel_out = f"ingest/evidence/{connector}-{mode}"

    # Stage 1: reconstruct the raw acquisition payload from the approved
    # repo-owned source + the structurally preserved capture fields; its digest
    # MUST equal the ledger's original-content digest (cryptographic tie).
    source_path = capture["payload"]["path"]
    raw_payload = {
        "path": source_path,
        "content": (_REPO / source_path).read_text(encoding="utf-8"),
        "modified": capture["payload"]["modified"],
    }
    raw_canon = json.dumps(raw_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    from hashlib import sha256 as _sha256

    raw_digest = "sha256:" + _sha256(raw_canon).hexdigest()
    if raw_digest != ledger["original_content_sha256"]:
        raise SystemExit(
            "reconstructed raw payload does not match the ledger's original "
            "digest; the approved source changed since capture — recapture first"
        )
    _write_json(out_dir / "01-raw-acquisition-payload.json", raw_payload)
    _write_json(
        out_dir / "02-acquisition-receipt.json",
        capture["capture_meta"]["acquisition_receipt"],
    )
    facts = {
        "provider": "local filesystem",
        "extracted_fields": {
            "path": capture["payload"]["path"],
            "content_length": len(str(capture["payload"]["content"])),
            "modified": capture["payload"]["modified"],
        },
        "identity_derivation": "sha256(path)[:16] becomes the opaque source ref token",
    }
    _write_json(out_dir / "04-provider-facts.json", facts)
    receipt = artifacts["redaction_receipt"]["receipt"]
    redaction_changes = {
        "changes": [
            {"path": "observation.excerpt|title|author|metadata", "category": f["category"], "action": f["action"], "count": f["count"]}
            for f in receipt["findings"]
        ],
        "engine": receipt["engine"],
        "ruleset_id": receipt["ruleset_id"],
        "note": "original values are never recorded; placeholders replace them in the sanitized observation",
    }
    _write_json(out_dir / "06-redaction-changes.json", redaction_changes)
    normalization_mapping = {
        "mappings": [
            {"source_path": "observation.source_ref", "target_path": "emission.evidence[0].source_ref", "operation": "copy"},
            {"source_path": "observation.excerpt", "target_path": "emission.body", "operation": "copy"},
            {"source_path": "observation.excerpt", "target_path": "emission.evidence[0].excerpt", "operation": "copy"},
            {"source_path": "observation.title", "target_path": "emission.title", "operation": "copy"},
            {"source_path": "observation.mode", "target_path": "emission.provenance.delivery_mode", "operation": "derive"},
            {"source_path": "observation.metadata", "target_path": "emission.metadata", "operation": "copy"},
            {"source_path": "(redaction receipt)", "target_path": "emission.metadata.redaction_receipt", "operation": "attach"},
        ],
        "note": "descriptive evidence of pipeline._emission_from; not executable authority",
    }
    _write_json(out_dir / "10-normalization-mapping.json", normalization_mapping)

    md = "text/markdown"
    stage_defs: list[dict[str, Any]] = []

    def stage(
        stage_id: str,
        *,
        status: str = "passed",
        evidence_class: str = "component",
        inp: list[dict[str, Any]] | None = None,
        transformation: dict[str, Any] | None = None,
        output: list[dict[str, Any]] | None = None,
        authority: dict[str, Any] | None = None,
        unproven: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        record: dict[str, Any] = {
            "stage_id": stage_id,
            "sequence": len(stage_defs) + 1,
            "status": status,
            "evidence_class": evidence_class,
            "authority": authority
            or _authority("integrations", ["evidence artifacts"], ["candidates", "Decisions", "canonical Product state"]),
        }
        if inp is not None:
            record["input"] = _out(inp)
        if transformation is not None:
            record["transformation"] = transformation
        if output is not None:
            record["output"] = _out(output)
        if unproven is not None:
            record["unproven"] = unproven
        if warnings:
            record["warnings"] = warnings
        stage_defs.append(record)

    def impl(path: str, name: str, **extra: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "name": name,
            "implementation": {"repository": "BicameralAI/bicameral-integrations", "path": path},
        }
        base.update(extra)
        return base

    stage(
        "raw_acquisition",
        inp=[_artifact(source_path, md)],
        transformation=impl(
            "scripts/capture_sanitize.py",
            "operator-run local file read (real passive-import boundary)",
            summary="Reads the approved repo-owned source file from disk into the provider payload shape {path, content, modified}.",
            carried_forward=["path", "content", "modified"],
        ),
        output=[_artifact(f"{rel_out}/01-raw-acquisition-payload.json", read_from=out_dir / "01-raw-acquisition-payload.json")],
    )
    stage(
        "acquisition_verification",
        inp=[_artifact(f"{rel_out}/01-raw-acquisition-payload.json", read_from=out_dir / "01-raw-acquisition-payload.json"), _artifact(f"{rel_out}/02-acquisition-receipt.json", read_from=out_dir / "02-acquisition-receipt.json")],
        transformation=impl(
            "runtime/ingest_conformance_harness.py",
            "acquisition receipt validation + canonical scan-root containment",
            summary="Validates the receiver-authored acquisition receipt (original digest, verification over original bytes, replay window, receiver identity) and resolved-path scope containment.",
        ),
        output=[_artifact(f"{rel_out}/02-acquisition-receipt.json", read_from=out_dir / "02-acquisition-receipt.json"), _artifact(golden["provider_verification"])],
    )
    stage(
        "sanitized_capture",
        inp=[_artifact(f"{rel_out}/01-raw-acquisition-payload.json", read_from=out_dir / "01-raw-acquisition-payload.json")],
        transformation=impl(
            "scripts/capture_sanitize.py",
            "deterministic sanitization of every string leaf + ledger",
            summary="Applies the deterministic redaction engine to the raw payload; original bytes retained only as an irreversible sha256.",
            changes=[{"path": "payload.content", "category": category, "action": "tokenized", "count": count} for category, count in ledger["redaction"]["categories"].items()],
            ruleset_id=ledger["redaction"]["ruleset_id"],
            ruleset_digest=ledger["redaction"]["ruleset_digest"],
        ),
        output=[_artifact(capture_rel), _artifact(ledger_rel)],
    )
    stage(
        "provider_fact_extraction",
        inp=[_artifact(capture_rel)],
        transformation=impl(
            "connectors/local_directory/connector.py",
            "parse_file: provider fact extraction",
            summary="Extracts the provider facts (path, content, modified) and derives the opaque identity token.",
            extracted=["path", "content", "modified"],
            mappings=[
                {"source_path": "payload.path", "target_path": "facts.path", "operation": "copy"},
                {"source_path": "payload.modified", "target_path": "facts.modified", "operation": "copy"},
                {"source_path": "payload.content", "target_path": "facts.content_length", "operation": "measure"},
            ],
        ),
        output=[_artifact(f"{rel_out}/04-provider-facts.json", read_from=out_dir / "04-provider-facts.json")],
    )
    stage(
        "provider_neutral_observation",
        inp=[_artifact(f"{rel_out}/04-provider-facts.json", read_from=out_dir / "04-provider-facts.json"), _artifact(capture_rel)],
        transformation=impl(
            "connectors/local_directory/connector.py",
            "parse_file: provider-neutral Observation",
            summary="Organizes provider facts into the neutral Observation shape; connector-level redact-and-pass applies to free text.",
            mappings=[
                {"source_path": "payload.path", "target_path": "observation.source_ref.ref", "operation": "sha256_token"},
                {"source_path": "payload.content", "target_path": "observation.excerpt", "operation": "sanitized_copy"},
                {"source_path": "payload.path(stem)", "target_path": "observation.title", "operation": "sanitized_copy"},
                {"source_path": "payload.modified", "target_path": "observation.timestamp", "operation": "copy"},
            ],
            added_metadata=["source_ref.kind (redacted source_type_label)"],
        ),
        output=[_artifact(golden["parsed_facts"])],
    )
    stage(
        "guarded_redaction",
        inp=[_artifact(golden["parsed_facts"])],
        transformation=impl(
            "adapter/core/redaction_receipt.py",
            "guarded_sanitize_observation (inside pipeline.normalize)",
            summary="Mandatory hard gate: engine/ruleset identity, size budget, terminable worker-process timeout, structural identity preservation; failures are typed and emit nothing downstream.",
            ruleset_id=receipt["ruleset_id"],
            ruleset_digest=receipt["ruleset_digest"],
            changes=[{"path": "observation.free_text", "category": f["category"], "action": f["action"], "count": f["count"]} for f in receipt["findings"]],
        ),
        output=[_artifact(f"{rel_out}/06-redaction-changes.json", read_from=out_dir / "06-redaction-changes.json")],
    )
    stage(
        "sanitized_observation",
        inp=[_artifact(golden["parsed_facts"]), _artifact(f"{rel_out}/06-redaction-changes.json", read_from=out_dir / "06-redaction-changes.json")],
        transformation=impl(
            "adapter/core/redaction_receipt.py",
            "sanitized Observation materialization",
            summary="The Observation after the hard gate: free text tokenized, structural identity byte-identical.",
            carried_forward=["source_ref", "timestamp", "provider_event_id", "mode"],
            deliberately_omitted=["original free-text values (irreversibly replaced)"],
        ),
        output=[_artifact(golden["observation"])],
    )
    stage(
        "redaction_receipt",
        inp=[_artifact(golden["observation"])],
        transformation=impl(
            "adapter/core/redaction_receipt.py",
            "deterministic value-free receipt",
            summary="Receipt digest domain excludes completed_at; findings carry category+action+count only.",
        ),
        output=[_artifact(golden["redaction_receipt"])],
    )
    stage(
        "integration_advisories",
        inp=[_artifact(golden["observation"])],
        transformation=impl(
            "connectors/local_directory/connector.py",
            "integration-specific advisory signals (shared schema)",
            summary="local_directory emits no integration signals; the empty list is a valid, pinned result.",
        ),
        output=[_artifact(golden["integration_advisories"])],
    )
    stage(
        "universal_normalization",
        inp=[_artifact(golden["observation"])],
        transformation=impl(
            "adapter/core/pipeline.py",
            "normalize: single universal seam",
            summary="Observation -> validated evidence emission; receipt attached to metadata; heuristics run fail-open.",
            mappings=normalization_mapping["mappings"],
        ),
        output=[_artifact(f"{rel_out}/10-normalization-mapping.json", read_from=out_dir / "10-normalization-mapping.json")],
    )
    stage(
        "universal_advisories",
        inp=[_artifact(f"{rel_out}/10-normalization-mapping.json", read_from=out_dir / "10-normalization-mapping.json")],
        transformation=impl(
            "adapter/core/heuristics.py",
            "universal fail-open advisory evaluation",
            summary="Deterministic universal signals annotate/rank/route; evidence is never dropped; malformed advisory data becomes a diagnostic.",
        ),
        output=[_artifact(golden["universal_advisories"])],
    )
    stage(
        "adapter_emission",
        inp=[_artifact(golden["universal_advisories"]), _artifact(f"{rel_out}/10-normalization-mapping.json", read_from=out_dir / "10-normalization-mapping.json")],
        transformation=impl(
            "adapter/core/pipeline.py",
            "validate_emissions: ADR-0005 contract + sensitive hard screen",
            summary="Contract-validated evidence emission; per-leaf sensitive screen is the un-bypassable backstop.",
        ),
        output=[_artifact(golden["adapter_emission"])],
    )
    stage(
        "external_ingest_envelope",
        inp=[_artifact(golden["adapter_emission"])],
        transformation=impl(
            "runtime/gateway_mapping.py",
            "emission_to_external_envelope: authority stripping",
            summary="Maps the emission to the pinned v2 envelope; advisories/provenance flatten into non-authoritative candidate-hint labels.",
            authority_stripped=["confidence (dimensional, dropped)", "unscreened metadata (dropped)", "level/snapshot/accepted fields (never sent)"],
            mappings=[
                {"source_path": "emission.body", "target_path": "envelope.content", "operation": "copy"},
                {"source_path": "emission.source_id", "target_path": "envelope.source_system", "operation": "copy"},
                {"source_path": "emission.evidence[].excerpt", "target_path": "envelope.evidence[].excerpt", "operation": "copy"},
                {"source_path": "emission.advisories", "target_path": "envelope.candidate_hints[0].labels", "operation": "flatten_labels"},
                {"source_path": "emission.metadata.redaction_receipt", "target_path": "envelope.redaction_receipt", "operation": "attach"},
            ],
            downstream_may=["Bot may accept/deduplicate/project; envelope carries no lifecycle authority"],
        ),
        output=[_artifact(golden["external_ingest_envelope"])],
    )
    stage(
        "cursor_or_delivery_decision",
        inp=[_artifact(golden["external_ingest_envelope"])],
        transformation=impl(
            "runtime/cursor_policy.py",
            "resolve_cursor_action: two-phase-commit verdicts",
            summary="201 -> ADVANCE; transport/5xx -> RETRY (no advance); sensitive 422 -> QUARANTINE. Durable checkpoint owner remains the operator runtime.",
        ),
        output=[_artifact(golden["delivery_or_cursor_receipt"])],
    )

    def unproven_stage(stage_id: str, evidence_class: str, receipt_type: str, authority_name: str, dependency: str, reason: str) -> None:
        stage(
            stage_id,
            status="unproven",
            evidence_class=evidence_class,
            authority=_authority(authority_name, [], ["evidence fabrication by Integrations"]),
            unproven={
                "required_receipt_type": receipt_type,
                "responsible_authority": authority_name,
                "implementation_dependency": dependency,
                "reason": reason,
            },
        )

    unproven_stage(
        "gateway_negotiation", "observed_live",
        "capability-negotiation record + closed gateway delivery receipt (/api/v2, contract fingerprint match, HTTP 201)",
        "integrations (protocol) + bot (capabilities endpoint)",
        "accepted Integrations PR #262 external-ingest protocol lifecycle",
        "PR #262 is the authoritative protocol target and has not merged; no parallel implementation is created here.",
    )
    unproven_stage(
        "bot_acceptance", "observed_live",
        "Bot-authored acceptance identity from the real /api/v2 response",
        "BicameralAI/bicameral-bot",
        "real Bot endpoint + PR #262 response surface; credentialed run deferred",
        "Only the real Bot can author an acceptance identity; local derivation is prohibited.",
    )
    unproven_stage(
        "durable_evidence", "terminal_product",
        "Bot durable-evidence record (evidence CAS + canonical EvidenceAccepted)",
        "BicameralAI/bicameral-bot (Bot #856)",
        "terminal Bot journey with a real delivery",
        "Durable evidence is Bot-owned canonical state; Integrations holds no authority here.",
    )
    unproven_stage(
        "candidate_or_decision_lifecycle", "terminal_product",
        "candidate/Decision lifecycle records with promotion + replay proof",
        "BicameralAI/bicameral-bot (Bot #856) + Factory #282 witnessed journey",
        "terminal provider-to-reviewed-Decision run",
        "Candidate and Decision lifecycle is Bot/Factory authority; deferred to the witnessed journey.",
    )
    unproven_stage(
        "recall_transformation", "terminal_product",
        "RecallPacket + transformation-debug trace (Bot #869)",
        "BicameralAI/bicameral-bot (Bot #869)",
        "Bot recall surface over durable evidence",
        "Recall transformation evidence requires accepted durable evidence first.",
    )
    unproven_stage(
        "agent_session_exposure", "terminal_product",
        "agent-session exposure record (host execution surface)",
        "host execution surfaces (mcp/cloud)",
        "recall output exposed to a real agent session",
        "Exposure evidence belongs to the host surfaces after recall exists; credentialed run deferred.",
    )

    bundle: dict[str, Any] = {
        "schema_version": 1,
        "bundle_id": "",
        "run_id": f"{connector}-{mode}-component-cycle",
        "route": {"connector_id": connector, "mode": mode},
        "evidence_class": "component",
        "integrations": {
            "repository": "BicameralAI/bicameral-integrations",
            "commit": subprocess.run(  # nosec B603 B607
                ["git", "-C", str(_REPO), "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True,
            ).stdout.strip(),
        },
        "contract": {"contract_id": CONTRACT_ID, "semantic_fingerprint": SEMANTIC_FINGERPRINT},
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stages": stage_defs,
        "unproven_downstream": [s["stage_id"] for s in stage_defs if s["status"] == "unproven"],
    }

    # Cryptographic linkage: each stage links to the last output-bearing
    # stage's aggregate digest (the anchor carries through output-less stages).
    anchor = ""
    for index, record in enumerate(bundle["stages"]):
        if index > 0:
            record["previous_stage"] = {
                "stage_id": bundle["stages"][index - 1]["stage_id"],
                "output_digest": anchor,
            }
        if "output" in record:
            anchor = record["output"]["aggregate_digest"]

    bundle["bundle_id"] = bundle_id(bundle)
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out_dir = (_REPO / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    bundle = build_bundle(args.route, out_dir)
    _write_json(out_dir / "bundle.json", bundle)
    print(f"bundle written: {out_dir / 'bundle.json'}")
    print(f"bundle_id: {bundle['bundle_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
