# SPDX-License-Identifier: MIT
"""Recorded ingress journey for GitHub issue evidence (#256).

This is intentionally broader than a mapper unit test. It loads a recorded GitHub
webhook payload, signs the exact bytes, executes the public webhook runtime, captures
the emitted evidence, maps it through the production external-ingest mapper, and
compares the complete stable output to a checked-in recording.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict
from pathlib import Path

from protocol.provider_acquisition.github import (
    GitHubIssueIngestRuntime,
    JsonCursorStore,
    MappingInstallationTokenProvider,
    RecordedTransport,
)
from runtime.cursor_policy import CursorVerdict
from runtime.gateway_mapping import emission_to_external_envelope
from runtime.sinks import CollectingSink

_FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "recorded"
    / "github_ingest"
)
_INPUT = _FIXTURE_DIR / "issues-opened-256.input.json"
_OUTPUT = _FIXTURE_DIR / "issues-opened-256.output.json"
_SECRET = "recorded-webhook-secret"
_DELIVERY_ID = "recorded-delivery-001"


def _signature(body: bytes) -> str:
    digest = hmac.new(_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_recorded_github_issue_ingress_matches_expected_output(tmp_path: Path) -> None:
    payload = json.loads(_INPUT.read_text(encoding="utf-8"))
    # Canonical serialization is part of this recording. The signature is calculated
    # over these exact bytes, just as GitHub signs the delivered request body.
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    sink = CollectingSink()
    cursor_store = JsonCursorStore(tmp_path / "github-issue-cursors.json")
    runtime = GitHubIssueIngestRuntime(
        transport=RecordedTransport({}),
        token_provider=MappingInstallationTokenProvider({"13579": "recorded-token"}),
        sink=sink,
        cursor_store=cursor_store,
    )

    action = runtime.ingest_webhook(
        secret=_SECRET,
        signature_header=_signature(body),
        event_name="issues",
        delivery_id=_DELIVERY_ID,
        body=body,
    )

    assert action is not None
    assert action.verdict is CursorVerdict.ADVANCE
    assert len(sink.emissions) == 1

    emission = sink.emissions[0]
    evidence_metadata = emission.evidence[0].metadata
    actual = {
        "cursor": asdict(cursor_store.load("987654321")),
        "external_ingest_envelope": emission_to_external_envelope(emission),
        "normalized": {
            key: evidence_metadata[key]
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
    }

    expected = json.loads(_OUTPUT.read_text(encoding="utf-8"))
    assert actual == expected

    # Explicit authority boundary regression. The recording must never grow Bot-owned
    # lifecycle fields merely because some future mapper found them convenient.
    envelope = actual["external_ingest_envelope"]
    assert "content_hash" not in envelope
    assert "level" not in envelope["candidate_hints"][0]
