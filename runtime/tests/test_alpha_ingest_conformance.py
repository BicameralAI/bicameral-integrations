# SPDX-License-Identifier: MIT
"""Alpha ingest manifest conformance runs (GH #258) + negative/recovery gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.ingest_conformance_harness import (
    REASON_CAPTURE_MISSING,
    REASON_GATEWAY_UNPROVEN,
    REASON_GOLDEN_MISMATCH,
    REASON_IMPLEMENTATION_MISSING,
    STAGES,
    canonical_digest,
    collect_artifacts,
    run_entry,
)

_REPO = Path(__file__).resolve().parents[2]
_MANIFEST = json.loads((_REPO / "ingest" / "alpha-ingest-manifest.json").read_text(encoding="utf-8"))
_ENTRIES = {f"{e['connector_id']}/{e['mode']}": e for e in _MANIFEST["entries"]}


def test_manifest_covers_the_alpha_cut_exactly() -> None:
    assert set(_ENTRIES) == {
        "github/webhook",
        "github/active_poll",
        "linear/webhook",
        "linear/graphql_poll",
        "local_directory/passive_import",
        "google_drive/document_fetch",
    }


@pytest.mark.parametrize("route", sorted(_ENTRIES))
def test_every_route_runs_the_universal_harness(route: str) -> None:
    entry = _ENTRIES[route]
    report = run_entry(entry)
    state = entry["conformance_state"]

    if state["implementation"] == "missing":
        assert report.reason_code == REASON_IMPLEMENTATION_MISSING
        assert not report.stages_passed
    elif state["real_capture"] != "recorded":
        # Missing captures skip with a TYPED reason; never a fake pass.
        assert report.reason_code == REASON_CAPTURE_MISSING
        assert not report.component_passed and not report.stages_passed
    else:
        # Component-scoped honesty: checkpoints 1-11 pass, and the result
        # NEVER claims an aggregate pass while the gateway is unproven —
        # ConformanceReport deliberately has no overall `passed` field.
        assert report.component_passed, (report.failed_stage, report.reason_code, report.observed_digest)
        assert not hasattr(report, "passed")
        assert set(STAGES) - {"gateway_sink"} <= set(report.stages_passed)
        assert report.reason_code == REASON_GATEWAY_UNPROVEN
        assert report.gateway_state == "unproven"
        assert report.contract_id == "external-ingest.request.v2"
        assert report.semantic_fingerprint.startswith("sha256:")


def test_recorded_route_artifacts_match_committed_goldens_exactly() -> None:
    entry = _ENTRIES["local_directory/passive_import"]
    artifacts = collect_artifacts(entry)
    for key, rel in entry["expected"].items():
        if key == "gateway_receipt" or not rel:
            continue
        golden = json.loads((_REPO / rel).read_text(encoding="utf-8"))
        assert canonical_digest(artifacts[key]) == canonical_digest(golden), key


def test_golden_mismatch_reports_stage_and_both_digests(tmp_path: Path) -> None:
    entry = json.loads(json.dumps(_ENTRIES["local_directory/passive_import"]))
    tampered = tmp_path / "observation.json"
    golden = json.loads(
        (_REPO / entry["expected"]["observation"]).read_text(encoding="utf-8")
    )
    golden["title"] = "tampered"
    tampered.write_text(json.dumps(golden), encoding="utf-8")
    entry["expected"]["observation"] = str(tampered)

    report = run_entry(entry)
    assert not report.component_passed
    assert report.failed_stage == "observation"
    assert report.reason_code == REASON_GOLDEN_MISMATCH
    assert report.expected_digest.startswith("sha256:")
    assert report.observed_digest.startswith("sha256:")
    assert report.expected_digest != report.observed_digest


def test_gateway_checkpoint_requires_a_real_sink() -> None:
    """A missing sink NEVER reports delivery; component proof stands alone."""
    report = run_entry(_ENTRIES["local_directory/passive_import"], sink=None)
    assert "gateway_sink" not in report.stages_passed
    assert report.gateway_state == "unproven"


def test_acquisition_receipt_is_required() -> None:
    """A capture without the receiver-authored acquisition receipt fails the
    acquisition checkpoint: original provider authentication is unproven."""
    entry = json.loads(json.dumps(_ENTRIES["local_directory/passive_import"]))
    capture = json.loads((_REPO / entry["real_capture"]["path"]).read_text(encoding="utf-8"))
    from runtime.ingest_conformance_harness import ACQUIRERS

    meta = dict(capture["capture_meta"])
    meta.pop("acquisition_receipt")
    with pytest.raises(ValueError, match="acquisition receipt missing"):
        ACQUIRERS[("local_directory", "passive_import")](capture["payload"], meta)


def test_self_declared_authentication_is_rejected() -> None:
    """capture_meta.authenticated=true (or any self-declared boolean) never
    counts: only a receipt with provider verification over ORIGINAL bytes
    satisfies acquisition for provider modes."""
    from runtime.ingest_conformance_harness import ACQUIRERS

    payload = {"documentId": "d" * 30, "title": "x", "body": {"content": []}}
    meta = {"authenticated": True}
    with pytest.raises(ValueError, match="acquisition receipt missing"):
        ACQUIRERS[("google_drive", "document_fetch")](payload, meta)


def test_resigned_sanitized_payload_never_reports_provider_authentication() -> None:
    """A locally re-signed sanitized payload without an acquisition receipt is
    rejected outright; with a receipt, the replay check is labeled test-replay
    evidence, distinct from provider authentication."""
    import hashlib
    import hmac

    from runtime.ingest_conformance_harness import ACQUIRERS

    payload = {
        "action": "closed",
        "number": 7,
        "pull_request": {
            "base": {"repo": {"full_name": "acme/app"}},
            "number": 7,
            "title": "fix",
            "body": "merged the fix",
            "html_url": "https://github.com/acme/app/pull/7",
            "user": {"login": "carol"},
            "merged_at": "2026-07-22T00:00:00Z",
        },
    }
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    secret = "test-replay-secret"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    meta_no_receipt = {
        "replay_secret": secret,
        "replay_signature": signature,
        "delivery_id": "d-1",
    }
    with pytest.raises(ValueError, match="acquisition receipt missing"):
        ACQUIRERS[("github", "webhook")](payload, meta_no_receipt)

    meta = dict(
        meta_no_receipt,
        acquisition_receipt={
            "original_payload_sha256": "sha256:" + "a" * 64,
            "provider_headers": {"X-GitHub-Delivery": "d-1"},
            "provider_verification": {
                "method": "hmac_sha256_x_hub_signature_256",
                "result": "verified",
                "over": "original_bytes",
            },
            "replay_window": {"result": "not_applicable"},
            "receiver": {"identity": "test-receiver", "version": "0"},
            "captured_at": "2026-07-22T00:00:00Z",
            "source_scope": "repo:acme/app webhook",
        },
    )
    verification, observation = ACQUIRERS[("github", "webhook")](payload, meta)
    assert observation.excerpt
    assert "test-replay evidence only" in verification["sanitized_replay_check"]
    assert verification["acquisition"]["result"] == "verified"


def test_sibling_prefix_scan_root_is_rejected() -> None:
    """Canonical containment: a path under `<root>-evil` must not satisfy a
    `<root>` scope (string-prefix checks would wrongly accept it)."""
    from runtime.ingest_conformance_harness import ACQUIRERS

    entry = _ENTRIES["local_directory/passive_import"]
    capture = json.loads((_REPO / entry["real_capture"]["path"]).read_text(encoding="utf-8"))
    meta = json.loads(json.dumps(capture["capture_meta"]))
    meta["acquisition_receipt"]["source_scope"] = "ingest"
    payload = dict(capture["payload"], path="ingest-evil/file.md")
    with pytest.raises(ValueError, match="escapes the recorded scan root"):
        ACQUIRERS[("local_directory", "passive_import")](payload, meta)


class _ExplodingSink:
    def emit(self, emissions: list[object]) -> None:
        raise ConnectionError("gateway unavailable")


def test_gateway_unavailable_fails_visibly_and_cursor_semantics_hold() -> None:
    entry = _ENTRIES["local_directory/passive_import"]
    with pytest.raises(ConnectionError):
        run_entry(entry, sink=_ExplodingSink())
    # Cursor policy: transport failure and non-201 must never advance.
    from runtime.cursor_policy import resolve_cursor_action

    assert str(resolve_cursor_action(status=0, reason="transport_error:conn").verdict) != "CursorVerdict.ADVANCE"
    assert str(resolve_cursor_action(status=503).verdict) != "CursorVerdict.ADVANCE"


def test_sanitized_capture_and_goldens_carry_no_original_sensitive_values() -> None:
    entry = _ENTRIES["local_directory/passive_import"]
    ledger = json.loads(
        (_REPO / entry["real_capture"]["sanitization_ledger"]).read_text(encoding="utf-8")
    )
    assert ledger["structural_fields_proof"]["preserved"] is True
    assert ledger["redaction"]["categories"]  # something real was redacted
    capture_text = (_REPO / entry["real_capture"]["path"]).read_text(encoding="utf-8")
    assert "@" not in capture_text or "[redacted:email]" in capture_text
    from adapter.core.sensitive import detect_sensitive

    assert detect_sensitive(capture_text) == []


def test_duplicate_delivery_yields_one_identity_and_an_advisory() -> None:
    from dataclasses import replace

    from adapter.core.pipeline import normalize
    from runtime.ingest_conformance_harness import ACQUIRERS

    entry = _ENTRIES["local_directory/passive_import"]
    capture = json.loads((_REPO / entry["real_capture"]["path"]).read_text(encoding="utf-8"))
    _, first = ACQUIRERS[("local_directory", "passive_import")](capture["payload"], capture["capture_meta"])
    _, second = ACQUIRERS[("local_directory", "passive_import")](capture["payload"], capture["capture_meta"])
    # Same payload -> same stable identity (one evidence identity downstream;
    # duplicate-delivery pressure is the Bot's dedup concern, not Integrations').
    assert first.source_ref.ref == second.source_ref.ref

    # A redelivery flagged by the runtime becomes a fail-open ADVISORY through
    # the universal heuristics; the evidence itself is never dropped.
    flagged = replace(second, metadata=dict(second.metadata, duplicate_delivery=True))
    [emission] = normalize([flagged], adapter_version="1.0.0")
    assert emission.evidence and emission.evidence[0].excerpt
    assert any(adv.kind == "duplicate_delivery" for adv in emission.advisories)
