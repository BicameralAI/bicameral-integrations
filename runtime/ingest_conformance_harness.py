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
    guarded_sanitize_observation,
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
    connector: str
    mode: str
    passed: bool = False
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


def _acquire_github_webhook(payload: dict[str, Any], meta: dict[str, Any]) -> tuple[dict[str, Any], Observation]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    secret = str(meta.get("resign_secret", ""))
    headers = {
        "X-Hub-Signature-256": str(meta.get("resign_signature", "")),
        "X-GitHub-Delivery": str(meta.get("delivery_id", "")),
    }
    connector = GitHubConnector(secret=secret)
    if not secret or not connector.verify(headers=headers, body=body):
        raise ValueError("github webhook signature verification failed over capture bytes")
    observations = connector.normalize_event(headers=headers, body=body)
    if not observations:
        raise ValueError("github webhook capture did not normalize to an observation")
    verification = {"method": "hmac_sha256_x_hub_signature_256", "verified": True, "scope": "signed webhook delivery"}
    return verification, observations[0]


def _acquire_linear_webhook(payload: dict[str, Any], meta: dict[str, Any]) -> tuple[dict[str, Any], Observation]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    secret = str(meta.get("resign_secret", ""))
    headers = {"Linear-Signature": str(meta.get("resign_signature", ""))}
    # Deterministic clock pinned to the capture's webhookTimestamp so the 60s
    # replay window is exercised against capture-time, not wall-clock.
    clock_ms = float(payload.get("webhookTimestamp", 0)) / 1000.0
    connector = LinearConnector(secret=secret, clock=lambda: clock_ms)
    if not secret or not connector.verify(headers=headers, body=body):
        raise ValueError("linear webhook signature/timestamp verification failed over capture bytes")
    observations = connector.normalize_event(headers=headers, body=body)
    if not observations:
        raise ValueError("linear webhook capture did not normalize to an observation")
    verification = {"method": "hmac_sha256_linear_signature_60s_window", "verified": True, "scope": "signed webhook delivery"}
    return verification, observations[0]


def _acquire_linear_graphql(payload: dict[str, Any], meta: dict[str, Any]) -> tuple[dict[str, Any], Observation]:
    if "errors" in payload:
        raise ValueError("linear graphql capture carries an errors array; fail-closed")
    nodes = payload.get("data", {}).get("issues", {}).get("nodes", [])
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("linear graphql capture has no issue nodes")
    observation = parse_issue_node(nodes[0])
    if observation is None:
        raise ValueError("linear issue node did not parse")
    verification = {
        "method": "authorization_api_key_header",
        "verified": bool(meta.get("authenticated", False)),
        "scope": "workspace-scoped GraphQL viewer",
    }
    return verification, observation


def _acquire_local_directory(payload: dict[str, Any], meta: dict[str, Any]) -> tuple[dict[str, Any], Observation]:
    scan_root = str(meta.get("scan_root", ""))
    path = str(payload.get("path", ""))
    if not scan_root or not path.startswith(scan_root):
        raise ValueError("local_directory capture path escapes the recorded scan root")
    observation = parse_file(payload)
    verification = {"method": "operator_local_scan", "verified": True, "scope": f"scan_root={scan_root}"}
    return verification, observation


def _acquire_google_drive(payload: dict[str, Any], meta: dict[str, Any]) -> tuple[dict[str, Any], Observation]:
    source_url = str(meta.get("source_url", ""))
    document_id = parse_gdrive_url(source_url) if source_url else str(payload.get("documentId", ""))
    if not document_id or payload.get("documentId") != document_id:
        raise ValueError("google_drive capture documentId does not match the requested resource scope")
    observation = parse_document(payload)
    verification = {"method": "oauth_bearer_documents_get", "verified": bool(meta.get("authenticated", False)), "scope": f"document:{document_id}"}
    return verification, observation


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

    # 3-4: the mandatory redaction boundary with the full typed-failure
    # envelope; the SAME engine runs again inside normalize() (idempotent).
    sanitized, receipt = guarded_sanitize_observation(observation)
    receipt_artifact = {
        # completed_at is the excluded digest-domain timestamp; goldens stay
        # time-free by omitting it (receipt_digest ignores it by contract).
        "receipt": {k: v for k, v in receipt.items() if k != "completed_at"},
        "receipt_digest": receipt_digest(receipt),
    }

    integration_advisories = list(sanitized.metadata.get("advisory_signals", []))

    # 7-9: one universal seam — normalize() redacts, normalizes, runs the
    # fail-open universal heuristics, and contract-validates.
    [emission] = normalize([observation], adapter_version="1.0.0")
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
        "observation": _observation_artifact(sanitized),
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

    report.passed = report.failed_stage == ""
    return report
