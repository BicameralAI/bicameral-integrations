# SPDX-License-Identifier: MIT
"""Recorded cross-seam ingress journeys for GitHub issue evidence (#256)."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from protocol.provider_acquisition.github import (
    GitHubIssueIngestRuntime,
    JsonCursorStore,
    MappingInstallationTokenProvider,
    RecordedTransport,
    parse_webhook_observation,
)
from runtime.cursor_policy import CursorVerdict
from runtime.ingest_conformance import emission_checkpoint, trace_ingest
from runtime.sinks import CollectingSink

_FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "recorded"
    / "github_ingest"
)
_SECRET = "recorded-webhook-secret"
_ADAPTER_VERSION = "github-issue-ingest/0.1.0"


def _signature(body: bytes) -> str:
    digest = hmac.new(_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _recorded_result(
    *,
    tmp_path: Path,
    fixture_stem: str,
    event_name: str,
    delivery_id: str,
) -> dict:
    input_path = _FIXTURE_DIR / f"{fixture_stem}.input.json"
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    sink = CollectingSink()
    cursor_store = JsonCursorStore(tmp_path / f"{fixture_stem}-cursors.json")
    runtime = GitHubIssueIngestRuntime(
        transport=RecordedTransport({}),
        token_provider=MappingInstallationTokenProvider({"13579": "recorded-token"}),
        sink=sink,
        cursor_store=cursor_store,
    )

    action = runtime.ingest_webhook(
        secret=_SECRET,
        signature_header=_signature(body),
        event_name=event_name,
        delivery_id=delivery_id,
        body=body,
    )

    assert action is not None
    assert action.verdict is CursorVerdict.ADVANCE
    assert len(sink.emissions) == 1

    parsed = parse_webhook_observation(
        event_name=event_name,
        delivery_id=delivery_id,
        payload=payload,
    )
    assert parsed is not None
    observation, _ = parsed
    trace = trace_ingest([observation], adapter_version=_ADAPTER_VERSION)[0]
    emission = sink.emissions[0]

    # The public runtime and reusable conformance path must produce the same
    # normalized emission. Otherwise the recording is merely testing a side door.
    assert emission_checkpoint(emission) == trace["emission"]

    metadata = trace["observation"]["metadata"]
    return {
        "cursor": asdict(cursor_store.load("987654321")),
        "observation": {
            "source_ref": trace["observation"]["source_ref"],
            "excerpt": trace["observation"]["excerpt"],
            "mode": trace["observation"]["mode"],
            "provider_event_id": trace["observation"]["provider_event_id"],
            "provider_resource_id": trace["observation"]["provider_resource_id"],
            "evidence_id": trace["observation"]["evidence_id"],
            "normalized": {
                key: metadata[key]
                for key in (
                    "action",
                    "content_truncated",
                    "event_name",
                    "issue_id",
                    "issue_number",
                    "repository_full_name",
                    "repository_id",
                    "source_version",
                    "title_truncated",
                    "tombstone",
                )
            },
            "integration_advisories": metadata["advisory_signals"],
        },
        "emission": {
            "adapter_version": trace["emission"]["adapter_version"],
            "emission_type": trace["emission"]["emission_type"],
            "evidence_id": trace["emission"]["evidence"][0]["evidence_id"],
            "advisories": trace["emission"]["advisories"],
            "provenance": trace["emission"]["provenance"],
        },
        "external_ingest_envelope": trace["external_ingest_envelope"],
    }


@pytest.mark.parametrize(
    ("fixture_stem", "event_name", "delivery_id"),
    [
        ("issues-opened-256", "issues", "recorded-delivery-001"),
        (
            "issue-comment-bot-decision",
            "issue_comment",
            "recorded-delivery-bot-001",
        ),
    ],
)
def test_recorded_github_ingress_matches_expected_output(
    tmp_path: Path,
    fixture_stem: str,
    event_name: str,
    delivery_id: str,
) -> None:
    actual = _recorded_result(
        tmp_path=tmp_path,
        fixture_stem=fixture_stem,
        event_name=event_name,
        delivery_id=delivery_id,
    )
    expected = json.loads(
        (_FIXTURE_DIR / f"{fixture_stem}.output.json").read_text(encoding="utf-8")
    )
    assert actual == expected

    envelope = actual["external_ingest_envelope"]
    assert "content_hash" not in envelope
    assert "level" not in envelope["candidate_hints"][0]


def test_bot_authored_real_decision_remains_ingested(tmp_path: Path) -> None:
    actual = _recorded_result(
        tmp_path=tmp_path,
        fixture_stem="issue-comment-bot-decision",
        event_name="issue_comment",
        delivery_id="recorded-delivery-bot-001",
    )

    decision_text = (
        "Decision: keep ingress heuristics fail-open; preserve evidence and rank downstream."
    )
    assert actual["observation"]["excerpt"] == decision_text
    assert actual["external_ingest_envelope"]["content"] == decision_text
    assert actual["emission"]["advisories"][0]["code"] == "bot_authored"
    labels = actual["external_ingest_envelope"]["candidate_hints"][0]["labels"]
    assert any(
        label.startswith("advisory_v1:bot_authored:integration:")
        for label in labels
    )
