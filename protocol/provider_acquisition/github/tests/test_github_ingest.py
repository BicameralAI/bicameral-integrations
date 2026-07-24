# SPDX-License-Identifier: MIT
"""Component tests for incremental GitHub issue ingest (#256)."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest

from adapter.core.emissions import AdapterEmission
from protocol.provider_acquisition.github.auth import MappingInstallationTokenProvider
from protocol.provider_acquisition.github.ingest import (
    GitHubIssueCursor,
    GitHubIssueIngestRuntime,
    JsonCursorStore,
    SignatureVerificationError,
    normalize_webhook,
    verify_webhook_signature,
)
from protocol.provider_acquisition.github.transport import GitHubResponse, RecordedTransport
from runtime.cursor_policy import CursorVerdict
from runtime.gateway_mapping import emission_to_external_envelope
from runtime.sinks import CollectingSink, GatewayEmissionError


def _payload(*, action: str = "opened", comment: bool = False) -> dict:
    issue = {
        "id": 22,
        "node_id": "I_kwDO",
        "number": 7,
        "title": "Choose the alpha ingest boundary",
        "body": "Use GitHub issues first.",
        "html_url": "https://github.com/BicameralAI/bicameral-integrations/issues/7",
        "updated_at": "2026-07-17T04:00:00Z",
        "user": {"login": "kevin", "type": "User"},
    }
    payload = {
        "action": action,
        "repository": {"id": 11, "full_name": "BicameralAI/bicameral-integrations"},
        "issue": issue,
    }
    if comment:
        payload["comment"] = {
            "id": 33,
            "node_id": "IC_kwDO",
            "body": "Ship the narrow slice.",
            "html_url": issue["html_url"] + "#issuecomment-33",
            "updated_at": "2026-07-17T04:01:00Z",
            "user": {"login": "automation[bot]", "type": "Bot"},
        }
    return payload


def _signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_signature_verification_accepts_valid_and_rejects_invalid() -> None:
    body = b'{"action":"opened"}'
    verify_webhook_signature("secret", body, _signature("secret", body))
    with pytest.raises(SignatureVerificationError):
        verify_webhook_signature("secret", body, "sha256=bad")


def test_issue_normalization_is_evidence_only_and_stable() -> None:
    first = normalize_webhook(event_name="issues", delivery_id="delivery-1", payload=_payload())
    second = normalize_webhook(event_name="issues", delivery_id="delivery-1", payload=_payload())
    assert first is not None and second is not None
    emission, cursor = first
    assert isinstance(emission, AdapterEmission)
    assert emission.emission_type == "evidence"
    assert emission.adapter_version == "github-issue-ingest/0.1.0"
    assert emission.provenance is not None
    assert emission.provenance.provider_event_id == "delivery-1"
    assert emission.provenance.provider_resource_id == "issue:22"
    assert cursor.repository_id == "11"
    assert emission.evidence[0].evidence_id == second[0].evidence[0].evidence_id
    envelope = emission_to_external_envelope(emission)
    assert set(envelope) == {"source_system", "source_uri", "content", "evidence", "candidate_hints"}
    assert "level" not in envelope["candidate_hints"][0]
    assert "content_hash" not in envelope


def test_edit_creates_new_immutable_source_version() -> None:
    original = _payload(action="opened")
    edited = _payload(action="edited")
    edited["issue"]["body"] = "Use signed webhooks plus polling backfill."
    one = normalize_webhook(event_name="issues", delivery_id="d1", payload=original)
    two = normalize_webhook(event_name="issues", delivery_id="d2", payload=edited)
    assert one is not None and two is not None
    assert one[0].evidence[0].evidence_id != two[0].evidence[0].evidence_id


def test_comment_noise_is_advisory_not_dropped() -> None:
    normalized = normalize_webhook(
        event_name="issue_comment", delivery_id="d3", payload=_payload(action="created", comment=True)
    )
    assert normalized is not None
    emission, _ = normalized
    assert emission.body == "Ship the narrow slice."
    assert [advisory.kind for advisory in emission.advisories] == ["bot_authored"]
    assert emission.advisories[0].metadata["scope"] == "integration"
    labels = emission_to_external_envelope(emission)["candidate_hints"][0]["labels"]
    assert any(label.startswith("advisory_v1:bot_authored:integration:") for label in labels)


def test_deleted_comment_becomes_tombstone_without_removed_content() -> None:
    payload = _payload(action="deleted", comment=True)
    payload["comment"]["body"] = "sensitive text that must not be repeated"
    normalized = normalize_webhook(event_name="issue_comment", delivery_id="d4", payload=payload)
    assert normalized is not None
    emission, _ = normalized
    assert emission.metadata["tombstone"] is True
    assert "sensitive text" not in emission.body


def test_webhook_advances_cursor_only_after_sink_success(tmp_path: Path) -> None:
    body = json.dumps(_payload()).encode()
    store = JsonCursorStore(tmp_path / "cursor.json")
    sink = CollectingSink()
    runtime = GitHubIssueIngestRuntime(
        transport=RecordedTransport({}),
        token_provider=MappingInstallationTokenProvider({"inst": "token"}),
        sink=sink,
        cursor_store=store,
    )
    action = runtime.ingest_webhook(
        secret="secret",
        signature_header=_signature("secret", body),
        event_name="issues",
        delivery_id="delivery-1",
        body=body,
    )
    assert action is not None and action.verdict is CursorVerdict.ADVANCE
    assert store.load("11").last_provider_event_id == "delivery-1"
    assert len(sink.emissions) == 1


class _FailingSink:
    def emit(self, emissions: list[AdapterEmission]) -> None:
        raise GatewayEmissionError(503, "gateway_rejected")


def test_retry_does_not_advance_cursor(tmp_path: Path) -> None:
    body = json.dumps(_payload()).encode()
    store = JsonCursorStore(tmp_path / "cursor.json")
    runtime = GitHubIssueIngestRuntime(
        transport=RecordedTransport({}),
        token_provider=MappingInstallationTokenProvider({"inst": "token"}),
        sink=_FailingSink(),
        cursor_store=store,
    )
    action = runtime.ingest_webhook(
        secret="secret",
        signature_header=_signature("secret", body),
        event_name="issues",
        delivery_id="delivery-1",
        body=body,
    )
    assert action is not None and action.verdict is CursorVerdict.RETRY
    assert store.load("11") == GitHubIssueCursor(repository_id="11")


def test_poll_backfill_uses_cursor_and_ignores_pull_requests(tmp_path: Path) -> None:
    path = "/repos/BicameralAI/bicameral-integrations/issues?state=all&sort=updated&direction=asc"
    routes = {
        f"GET {path}": GitHubResponse(
            status=200,
            json=[_payload()["issue"], {**_payload()["issue"], "id": 99, "pull_request": {}}],
        )
    }
    sink = CollectingSink()
    store = JsonCursorStore(tmp_path / "cursor.json")
    runtime = GitHubIssueIngestRuntime(
        transport=RecordedTransport(routes),
        token_provider=MappingInstallationTokenProvider({"inst": "token"}),
        sink=sink,
        cursor_store=store,
    )
    action = runtime.poll_backfill(
        installation_id="inst",
        repository_full_name="BicameralAI/bicameral-integrations",
        repository_id="11",
    )
    assert action.verdict is CursorVerdict.ADVANCE
    assert len(sink.emissions) == 1
    assert sink.emissions[0].provenance is not None
    assert sink.emissions[0].provenance.delivery_mode == "poll"
    assert sink.emissions[0].provenance.verification == "unsigned"
    assert store.load("11").updated_at == "2026-07-17T04:00:00Z"
