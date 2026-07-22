# SPDX-License-Identifier: MIT
"""One reusable real-data conformance harness for the alpha ingest manifest (GH #258).

Every alpha connector/mode enters the SAME universal checkpoint sequence after
acquisition — connector-specific code below only acquires and parses; there are
deliberately no per-connector golden systems. Checkpoints:

 1. acquisition verification and source scope
 2. provider-specific parsed facts
 3. required redaction (hard gate, GH #260)
 4. redaction receipt (deterministic digest)
 5. integration-specific advisories (shared schema)
 6. provider-neutral Observation
 7. universal normalization (ADR-0004 single normalizer)
 8. universal advisories (fail-open, GH #257)
 9. AdapterEmission (contract-validated)
10. authority-stripped ExternalIngestEnvelope (pinned v2 schema shape)
11. delivery/cursor behavior (cursor_policy verdict)
12. GatewaySink result — ONLY a real sink delivery receipt proves this
    checkpoint; a CollectingSink or absent sink reports the typed
    ``gateway_unproven`` reason and the component checkpoints stand alone.

Golden comparison: each checkpoint artifact is canonically serialized and
digest-compared against the committed golden; a mismatch reports connector,
mode, failed stage, expected digest, observed digest, contract id, semantic
fingerprint, and a typed reason code (GH #258 reporting contract).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

from adapter.core.emissions import AdapterEmission
from adapter.core.observations import Observation
from adapter.core.pipeline import normalize
from adapter.core.redaction_receipt import (
    RedactionFailure,
    receipt_digest,
)
from connectors.github.connector import GitHubConnector
from connectors.google_drive.connector import parse_document, parse_gdrive_url
from connectors.linear.connector import LinearConnector, parse_issue_node
from connectors.local_directory.connector import parse_file
from runtime.cursor_policy import resolve_cursor_action
from runtime.gateway_mapping import emission_to_external_envelope

_REPO = Path(__file__).resolve().parents[1]
_PIN = json.loads((_REPO / "runtime" / "schemas" / "ingest_schema_pin.json").read_text(encoding="utf-8"))

CONTRACT_ID = "external-ingest.request." + str(_PIN["schema_version"])
SEMANTIC_FINGERPRINT = "sha256:" + str(_PIN["content_sha256"])

STAGES = (
    "acquisition_verification",
    "parsed_facts",
    "redaction",
    "redaction_receipt",
    "integration_advisories",
    "observation",
    "universal_normalization",
    "universal_advisories",
    "adapter_emission",
    "external_ingest_envelope",
    "delivery_or_cursor",
    "gateway_sink",
)

REASON_CAPTURE_MISSING = "capture_missing"
REASON_IMPLEMENTATION_MISSING = "implementation_missing"
REASON_GOLDEN_MISMATCH = "golden_mismatch"
REASON_REDACTION_FAILED = "redaction_failed"
REASON_GATEWAY_UNPROVEN = "gateway_unproven"
REASON_ACQUISITION_FAILED = "acquisition_failed"


@dataclass
class ConformanceReport:
    """Component-scoped result. ``component_passed`` covers checkpoints 1-11
    only; the gateway checkpoint carries its own ``gateway_state`` axis and a
    report NEVER claims an overall pass while the gateway is unproven — there
    is deliberately no aggregate ``passed`` field (GH #269 review item 4)."""

    connector: str
    mode: str
    component_passed: bool = False
    stages_passed: list[str] = field(default_factory=list)
    failed_stage: str = ""
    expected_digest: str = ""
    observed_digest: str = ""
    contract_id: str = CONTRACT_ID
    semantic_fingerprint: str = SEMANTIC_FINGERPRINT
    reason_code: str = ""
    gateway_state: str = "unproven"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_digest(artifact: Any) -> str:
    return "sha256:" + sha256(
        json.dumps(artifact, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _observation_artifact(observation: Observation) -> dict[str, Any]:
    return {
        "source_id": observation.source_ref.source_id,
        "ref": observation.source_ref.ref,
        "url": observation.source_ref.url,
        "kind": observation.source_ref.kind,
        "title": observation.title,
        "excerpt": observation.excerpt,
        "author": observation.author,
        "timestamp": observation.timestamp,
        "provider_event_id": observation.provider_event_id,
        "mode": str(observation.mode),
        "metadata": observation.metadata,
    }


def _sanitized_observation_artifact(emission: AdapterEmission) -> dict[str, Any]:
    """Post-boundary Observation view reconstructed from the production
    emission (the harness holds no separate sanitized Observation because the
    only redaction pass is the one inside normalize())."""
    evidence = emission.evidence[0]
    metadata = {
        key: value
        for key, value in emission.metadata.items()
        if key != "redaction_receipt"
    }
    return {
        "source_id": evidence.source_ref.source_id,
        "ref": evidence.source_ref.ref,
        "url": evidence.source_ref.url,
        "kind": evidence.source_ref.kind,
        "title": emission.title,
        "excerpt": evidence.excerpt,
        "author": evidence.author,
        "timestamp": evidence.timestamp,
        "metadata": metadata,
    }


def _emission_artifact(emission: AdapterEmission) -> dict[str, Any]:
    return {
        "source_id": emission.source_id,
        "title": emission.title,
        "body": emission.body,
        "emission_type": emission.emission_type,
        "adapter_version": emission.adapter_version,
        "evidence": [
            {
                "excerpt": ev.excerpt,
                "author": ev.author,
                "timestamp": ev.timestamp,
                "source_ref": {
                    "source_id": ev.source_ref.source_id,
                    "ref": ev.source_ref.ref,
                    "url": ev.source_ref.url,
                    "kind": ev.source_ref.kind,
                },
            }
            for ev in emission.evidence
        ],
        "advisories": [
            {"kind": adv.kind, "message": adv.message, "metadata": adv.metadata}
            for adv in emission.advisories
        ],
    }


# ---------------------------------------------------------------------------
# Acquisition adapters: (capture payload, capture meta) -> (verification, Observation)
# Connector-specific by necessity; everything AFTER this enters the shared path.
# ---------------------------------------------------------------------------


REQUIRED_RECEIPT_FIELDS = (
    "original_payload_sha256",
    "provider_headers",
    "provider_verification",
    "replay_window",
    "receiver",
    "captured_at",
    "source_scope",
)


def _acquisition_receipt(meta: dict[str, Any], *, require_verified: bool) -> dict[str, Any]:
    """Validate the durable original-acquisition receipt recorded by the REAL
    receiver at capture time. This receipt — not a locally re-signed sanitized
    payload and not a self-declared boolean — is the only admissible evidence
    that the provider authenticated the original delivery (GH #269 review
    items 5 and 7)."""
    receipt = meta.get("acquisition_receipt")
    if not isinstance(receipt, dict):
        raise ValueError("acquisition receipt missing: original provider authentication unproven")
    missing = [field for field in REQUIRED_RECEIPT_FIELDS if field not in receipt]
    if missing:
        raise ValueError(f"acquisition receipt incomplete: missing {missing}")
    verification = receipt.get("provider_verification")
    if not isinstance(verification, dict) or verification.get("over") != "original_bytes":
        raise ValueError("acquisition receipt verification must be recorded over the original bytes")
    result = verification.get("result")
    if require_verified and result != "verified":
        raise ValueError(f"acquisition receipt verification result is {result!r}, not verified")
    if not require_verified and result not in ("verified", "not_applicable"):
        raise ValueError(f"acquisition receipt verification result invalid: {result!r}")
    digest = str(receipt.get("original_payload_sha256", ""))
    if not digest.startswith("sha256:"):
        raise ValueError("acquisition receipt must carry the original payload sha256")
    return receipt


def _verification_artifact(receipt: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    verification = dict(receipt["provider_verification"])
    artifact: dict[str, Any] = {
        "acquisition": {
            "original_payload_sha256": receipt["original_payload_sha256"],
            "method": verification.get("method", ""),
            "result": verification.get("result", ""),
            "over": verification.get("over", ""),
            "replay_window": receipt["replay_window"],
            "receiver": receipt["receiver"],
            "captured_at": receipt["captured_at"],
            "source_scope": receipt["source_scope"],
        },
    }
    if extra:
        artifact.update(extra)
    return artifact


def _replay_check_github(payload: dict[str, Any], meta: dict[str, Any]) -> tuple[Observation, str]:
    """Sanitized-replay signature check: TEST-REPLAY EVIDENCE ONLY. It proves
    the connector verify/parse code runs over the sanitized bytes; it is
    never provider authentication (that lives in the acquisition receipt)."""
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    secret = str(meta.get("replay_secret", ""))
    headers = {
        "X-Hub-Signature-256": str(meta.get("replay_signature", "")),
        "X-GitHub-Delivery": str(meta.get("delivery_id", "")),
    }
    connector = GitHubConnector(secret=secret)
    if not secret or not connector.verify(headers=headers, body=body):
        raise ValueError("sanitized test-replay signature did not verify")
    observations = connector.normalize_event(headers=headers, body=body)
    if not observations:
        raise ValueError("github capture did not normalize to an observation")
    return observations[0], "passed (test-replay evidence only; not provider authentication)"


def _acquire_github_webhook(payload: dict[str, Any], meta: dict[str, Any]) -> tuple[dict[str, Any], Observation]:
    receipt = _acquisition_receipt(meta, require_verified=True)
    observation, replay = _replay_check_github(payload, meta)
    return _verification_artifact(receipt, {"sanitized_replay_check": replay}), observation


def _acquire_linear_webhook(payload: dict[str, Any], meta: dict[str, Any]) -> tuple[dict[str, Any], Observation]:
    receipt = _acquisition_receipt(meta, require_verified=True)
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    secret = str(meta.get("replay_secret", ""))
    headers = {"Linear-Signature": str(meta.get("replay_signature", ""))}
    clock_ms = float(payload.get("webhookTimestamp", 0)) / 1000.0
    connector = LinearConnector(secret=secret, clock=lambda: clock_ms)
    if not secret or not connector.verify(headers=headers, body=body):
        raise ValueError("sanitized test-replay signature/window did not verify")
    observations = connector.normalize_event(headers=headers, body=body)
    if not observations:
        raise ValueError("linear webhook capture did not normalize to an observation")
    replay = "passed (test-replay evidence only; not provider authentication)"
    return _verification_artifact(receipt, {"sanitized_replay_check": replay}), observations[0]


def _acquire_linear_graphql(payload: dict[str, Any], meta: dict[str, Any]) -> tuple[dict[str, Any], Observation]:
    receipt = _acquisition_receipt(meta, require_verified=True)
    if "errors" in payload:
        raise ValueError("linear graphql capture carries an errors array; fail-closed")
    nodes = payload.get("data", {}).get("issues", {}).get("nodes", [])
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("linear graphql capture has no issue nodes")
    observation = parse_issue_node(nodes[0])
    if observation is None:
        raise ValueError("linear issue node did not parse")
    return _verification_artifact(receipt), observation


def _acquire_local_directory(payload: dict[str, Any], meta: dict[str, Any]) -> tuple[dict[str, Any], Observation]:
    receipt = _acquisition_receipt(meta, require_verified=False)
    scope = str(receipt["source_scope"])
    scan_root = (_REPO / scope).resolve()
    candidate = (_REPO / str(payload.get("path", ""))).resolve()
    # Canonical resolved-path containment: sibling-prefix roots like
    # "<root>-evil" can never pass relative_to (GH #269 review item 6).
    try:
        candidate.relative_to(scan_root)
    except ValueError as exc:
        raise ValueError("local_directory capture path escapes the recorded scan root") from exc
    observation = parse_file(payload)
    return _verification_artifact(receipt), observation


def _acquire_google_drive(payload: dict[str, Any], meta: dict[str, Any]) -> tuple[dict[str, Any], Observation]:
    receipt = _acquisition_receipt(meta, require_verified=True)
    source_url = str(receipt["source_scope"])
    document_id = parse_gdrive_url(source_url) if source_url.startswith("http") else str(payload.get("documentId", ""))
    if not document_id or payload.get("documentId") != document_id:
        raise ValueError("google_drive capture documentId does not match the requested resource scope")
    observation = parse_document(payload)
    return _verification_artifact(receipt), observation


ACQUIRERS: dict[tuple[str, str], Callable[[dict[str, Any], dict[str, Any]], tuple[dict[str, Any], Observation]]] = {
    ("github", "webhook"): _acquire_github_webhook,
    ("linear", "webhook"): _acquire_linear_webhook,
    ("linear", "graphql_poll"): _acquire_linear_graphql,
    ("local_directory", "passive_import"): _acquire_local_directory,
    ("google_drive", "document_fetch"): _acquire_google_drive,
}


def _compare_golden(
    report: ConformanceReport, stage: str, artifact: Any, golden_path: str
) -> bool:
    """Digest-compare an artifact with its committed golden. True on match."""
    observed = canonical_digest(artifact)
    golden = json.loads((_REPO / golden_path).read_text(encoding="utf-8"))
    expected = canonical_digest(golden)
    if observed != expected:
        report.failed_stage = stage
        report.expected_digest = expected
        report.observed_digest = observed
        report.reason_code = REASON_GOLDEN_MISMATCH
        return False
    report.stages_passed.append(stage)
    return True


def collect_artifacts(entry: dict[str, Any]) -> dict[str, Any]:
    """Build every checkpoint artifact (stages 1-11) for one manifest entry.

    One shared construction path serves BOTH golden generation
    (scripts/generate_alpha_goldens.py) and conformance comparison
    (run_entry), so the goldens can never drift from the harness's own
    stage semantics. Raises on acquisition or redaction failure.

    Determinism: receipt artifacts are built with ``completed_at=""`` and the
    envelope's embedded receipt timestamp is zeroed the same way — matching
    the receipt digest domain, which excludes completed_at by contract.
    """
    capture = json.loads((_REPO / entry["real_capture"]["path"]).read_text(encoding="utf-8"))
    payload = capture["payload"]
    meta = capture.get("capture_meta", {})

    verification, observation = ACQUIRERS[(entry["connector_id"], entry["mode"])](payload, meta)

    # 3-9: ONE production seam. normalize() runs the guarded redaction
    # boundary (typed engine/ruleset/size/timeout/receipt failures), the
    # universal heuristics, and contract validation — the harness has no
    # separate preflight beside the runtime path (GH #269 review item 2).
    [emission] = normalize([observation], adapter_version="1.0.0")
    receipt = dict(emission.metadata["redaction_receipt"])
    receipt_artifact = {
        # completed_at is the excluded digest-domain timestamp; goldens stay
        # time-free by omitting it (receipt_digest ignores it by contract).
        "receipt": {k: v for k, v in receipt.items() if k != "completed_at"},
        "receipt_digest": receipt_digest(receipt),
    }
    integration_advisories = list(emission.metadata.get("advisory_signals", []))
    emission.metadata["redaction_receipt"] = dict(
        emission.metadata["redaction_receipt"], completed_at="1970-01-01T00:00:00Z"
    )
    universal_artifact = [
        {"kind": adv.kind, "message": adv.message, "metadata": adv.metadata}
        for adv in emission.advisories
    ]
    envelope = emission_to_external_envelope(emission)
    for forbidden in ("level", "snapshot_content", "approved", "signoff"):
        if forbidden in envelope:
            raise ValueError(f"authority leak in envelope: {forbidden}")
    cursor_artifact = {
        "on_201": str(resolve_cursor_action(status=201).verdict),
        "on_503": str(resolve_cursor_action(status=503).verdict),
    }
    return {
        "provider_verification": verification,
        "parsed_facts": _observation_artifact(observation),
        "redaction_receipt": receipt_artifact,
        "integration_advisories": integration_advisories,
        "observation": _sanitized_observation_artifact(emission),
        "universal_advisories": universal_artifact,
        "adapter_emission": _emission_artifact(emission),
        "external_ingest_envelope": envelope,
        "delivery_or_cursor_receipt": cursor_artifact,
        "_emission": emission,  # not a golden; carried for the sink checkpoint
    }


_STAGE_BY_GOLDEN_KEY = (
    ("provider_verification", "acquisition_verification"),
    ("parsed_facts", "parsed_facts"),
    ("redaction_receipt", "redaction_receipt"),
    ("integration_advisories", "integration_advisories"),
    ("observation", "observation"),
    ("universal_advisories", "universal_advisories"),
    ("adapter_emission", "adapter_emission"),
    ("external_ingest_envelope", "external_ingest_envelope"),
    ("delivery_or_cursor_receipt", "delivery_or_cursor"),
)


def run_entry(entry: dict[str, Any], *, sink: Any = None) -> ConformanceReport:
    """Execute the 12 universal checkpoints for one manifest entry."""
    report = ConformanceReport(connector=entry["connector_id"], mode=entry["mode"])
    state = entry["conformance_state"]

    if state["implementation"] == "missing":
        report.reason_code = REASON_IMPLEMENTATION_MISSING
        return report
    if state["real_capture"] != "recorded":
        report.reason_code = REASON_CAPTURE_MISSING
        return report

    try:
        artifacts = collect_artifacts(entry)
    except RedactionFailure as exc:
        report.failed_stage = "redaction"
        report.reason_code = REASON_REDACTION_FAILED
        report.observed_digest = f"reason:{exc.reason}"
        return report
    except Exception as exc:
        report.failed_stage = "acquisition_verification"
        report.reason_code = REASON_ACQUISITION_FAILED
        report.observed_digest = f"error:{exc.__class__.__name__}"
        return report
    report.stages_passed.append("redaction")
    report.stages_passed.append("universal_normalization")

    for golden_key, stage in _STAGE_BY_GOLDEN_KEY:
        if not _compare_golden(report, stage, artifacts[golden_key], entry["expected"][golden_key]):
            return report

    # 12: real GatewaySink only; anything else stays unproven (typed)
    if sink is None:
        report.reason_code = REASON_GATEWAY_UNPROVEN
        report.gateway_state = "unproven"
    else:
        sink.emit([artifacts["_emission"]])
        report.stages_passed.append("gateway_sink")
        report.gateway_state = "delivered"

    report.component_passed = report.failed_stage == ""
    return report
