# SPDX-License-Identifier: MIT
"""Behavior tests for the operator-runtime boundary layer (ADR-0012)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path

import pytest

from connectors.aider.connector import AiderConnector
from connectors.claude_code.connector import ClaudeCodeConnector
from connectors.confluence.connector import ConfluenceConnector
from connectors.continue_dev.connector import ContinueConnector
from connectors.copilot.connector import CopilotConnector
from connectors.cursor.connector import CursorConnector
from connectors.fathom.connector import FathomConnector
from connectors.github.connector import GitHubConnector
from connectors.gitlab.connector import GitLabConnector
from connectors.google_drive.connector import GoogleDriveConnector
from connectors.granola.connector import GranolaConnector
from connectors.jira.connector import JiraConnector
from connectors.linear.connector import LinearConnector
from connectors.local_directory.connector import LocalDirectoryConnector
from connectors.mcp_registry.connector import McpRegistryConnector
from connectors.notion.connector import NotionConnector
from connectors.osv.connector import OsvConnector
from connectors.pagerduty.connector import PagerDutyConnector
from connectors.sarif.connector import SarifConnector
from connectors.sentry.connector import SentryConnector
from connectors.slack.connector import SlackConnector
from connectors.zendesk.connector import ZendeskConnector
from runtime import (
    CollectingSink,
    GatewayEmissionGated,
    GatewaySink,
    MappingSecretResolver,
    deliver_poll,
    deliver_webhook,
)

_SECRET = "linear-webhook-secret"
_TS_MS = 1_700_000_000_000

_FIXTURES = Path(__file__).resolve().parents[2] / "connectors"


def _hex_hmac(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _signed_linear() -> tuple[LinearConnector, dict, bytes]:
    body = json.dumps(
        {
            "action": "create",
            "type": "Issue",
            "webhookId": "wh-1",
            "webhookTimestamp": _TS_MS,
            "data": {"identifier": "ENG-1", "title": "Add health route", "description": "do it"},
        }
    ).encode("utf-8")
    sig = hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
    conn = LinearConnector(secret=_SECRET, clock=lambda: _TS_MS / 1000)
    return conn, {"Linear-Signature": sig}, body


def test_collecting_sink_accumulates():
    sink = CollectingSink()
    sink.emit([])
    assert sink.emissions == []


def test_gateway_sink_is_109_gated():
    with pytest.raises(GatewayEmissionGated):
        GatewaySink().emit([])


def test_mapping_secret_resolver():
    r = MappingSecretResolver({"linear": _SECRET})
    assert r.resolve("linear") == _SECRET
    assert r.resolve("unknown") == ""


def test_deliver_webhook_signed_reaches_sink():
    conn, headers, body = _signed_linear()
    sink = CollectingSink()
    n = deliver_webhook(conn, headers=headers, body=body, sink=sink)
    assert n == 1
    assert len(sink.emissions) == 1 and sink.emissions[0].source_id == "linear"


def test_deliver_webhook_bad_signature_emits_nothing():
    conn, _headers, body = _signed_linear()
    sink = CollectingSink()
    n = deliver_webhook(conn, headers={"Linear-Signature": "bad"}, body=body, sink=sink)
    assert n == 0 and sink.emissions == []


def test_deliver_webhook_into_gateway_sink_raises_gated():
    # No endpoint configured -> default-safe gate, asserted not skipped.
    conn, headers, body = _signed_linear()
    with pytest.raises(GatewayEmissionGated):
        deliver_webhook(conn, headers=headers, body=body, sink=GatewaySink())


def test_full_path_signed_webhook_to_configured_gateway_sink():
    # D1: ingest -> verify -> normalize -> emit -> POST a conforming v1 IngestRequest.
    captured: dict = {}

    class _R:
        status = 201

    class _Ctx:
        def __enter__(self):
            return _R()

        def __exit__(self, *_a):
            return False

    def _opener(request, timeout=None):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Ctx()

    conn, body, sig = _signed_sentry()
    sink = GatewaySink(endpoint="https://gw.example/api/v1/ingest", opener=_opener)
    n = deliver_webhook(conn, headers={"Sentry-Hook-Signature": sig}, body=body, sink=sink)
    assert n == 1
    assert captured["body"]["source_type"] == "sentry"
    assert captured["body"]["title"] and captured["body"]["description"]
    assert captured["body"]["evidence"][0]["excerpt"]


def test_deliver_poll_over_osv():
    sink = CollectingSink()
    payloads = [{"id": "OSV-1", "summary": "a"}, {"id": "OSV-2", "summary": "b"}]
    n = deliver_poll(OsvConnector(), payloads, sink=sink)
    assert n == 2
    assert all(e.source_id == "osv" for e in sink.emissions)


# --- Beta cohort: signed webhook -> deliver_webhook -> reference sink (ADR-0012) ---


def _signed_fathom() -> tuple[FathomConnector, dict, bytes]:
    """Fathom over Svix/Standard-Webhooks (clock pinned to the fixture timestamp)."""
    fx = json.loads(
        (_FIXTURES / "fathom" / "fixtures" / "webhook_signed.json").read_text(encoding="utf-8")
    )
    body = json.dumps(fx["body"]).encode("utf-8")  # same bytes are signed and delivered
    wid, ts, secret = fx["webhook_id"], fx["webhook_timestamp"], fx["secret"]
    key = base64.b64decode(secret[len("whsec_") :])
    sig = base64.b64encode(hmac.new(key, f"{wid}.{ts}.".encode() + body, hashlib.sha256).digest())
    headers = {
        "webhook-id": wid,
        "webhook-timestamp": str(ts),
        "webhook-signature": "v1," + sig.decode(),
    }
    conn = FathomConnector(secret=secret, clock=lambda: float(ts))
    return conn, headers, body


def test_deliver_webhook_fathom_beta():
    conn, headers, body = _signed_fathom()
    sink = CollectingSink()
    assert deliver_webhook(conn, headers=headers, body=body, sink=sink) == 1
    assert sink.emissions[0].source_id == "fathom"


def test_deliver_webhook_fathom_bad_sig_emits_nothing():
    conn, headers, body = _signed_fathom()
    headers["webhook-signature"] = "v1,deadbeef"
    sink = CollectingSink()
    assert deliver_webhook(conn, headers=headers, body=body, sink=sink) == 0
    assert sink.emissions == []


def _signed_sentry() -> tuple[SentryConnector, bytes, str]:
    secret = "sentry-webhook-secret"
    body = (_FIXTURES / "sentry" / "fixtures" / "issue_event.json").read_bytes()
    return SentryConnector(secret=secret), body, _hex_hmac(secret, body)


def test_deliver_webhook_sentry_beta():
    conn, body, sig = _signed_sentry()
    sink = CollectingSink()
    assert deliver_webhook(conn, headers={"Sentry-Hook-Signature": sig}, body=body, sink=sink) == 1
    assert sink.emissions[0].source_id == "sentry"


def test_deliver_webhook_sentry_bad_sig_emits_nothing():
    conn, body, _sig = _signed_sentry()
    sink = CollectingSink()
    assert deliver_webhook(conn, headers={"Sentry-Hook-Signature": "bad"}, body=body, sink=sink) == 0
    assert sink.emissions == []


def _signed_pagerduty() -> tuple[PagerDutyConnector, bytes, str]:
    secret = "pagerduty-webhook-secret"
    body = (_FIXTURES / "pagerduty" / "fixtures" / "incident_event.json").read_bytes()
    # Correct signature placed SECOND in the rotation set -> proves membership, not equality.
    header = f"v1=deadbeefdeadbeef,v1={_hex_hmac(secret, body)}"
    return PagerDutyConnector(secret=secret), body, header


def test_deliver_webhook_pagerduty_beta_membership():
    conn, body, header = _signed_pagerduty()
    sink = CollectingSink()
    assert deliver_webhook(conn, headers={"X-PagerDuty-Signature": header}, body=body, sink=sink) == 1
    assert sink.emissions[0].source_id == "pagerduty"


def test_deliver_webhook_pagerduty_all_wrong_emits_nothing():
    conn, body, _header = _signed_pagerduty()
    sink = CollectingSink()
    bad = "v1=deadbeef,v1=cafebabe"
    assert deliver_webhook(conn, headers={"X-PagerDuty-Signature": bad}, body=body, sink=sink) == 0
    assert sink.emissions == []


# --- Beta cohort 2: GitHub / Slack / Notion verify-wired through the harness ---


def _fixture_body(connector_name: str, fixture: str) -> bytes:
    path = _FIXTURES / connector_name / "fixtures" / fixture
    return json.dumps(json.loads(path.read_text(encoding="utf-8"))).encode("utf-8")


def _signed_github() -> tuple[GitHubConnector, dict, bytes]:
    body = _fixture_body("github", "webhook_pr.json")
    sig = "sha256=" + _hex_hmac("gh-secret", body)
    headers = {"X-Hub-Signature-256": sig, "X-GitHub-Delivery": "d-1"}
    return GitHubConnector(secret="gh-secret"), headers, body


def test_deliver_webhook_github_beta():
    conn, headers, body = _signed_github()
    sink = CollectingSink()
    assert deliver_webhook(conn, headers=headers, body=body, sink=sink) == 1
    assert sink.emissions[0].source_id == "github"


def test_deliver_webhook_github_bad_sig_emits_nothing():
    conn, _headers, body = _signed_github()
    sink = CollectingSink()
    bad = {"X-Hub-Signature-256": "sha256=bad"}
    assert deliver_webhook(conn, headers=bad, body=body, sink=sink) == 0
    assert sink.emissions == []


def _signed_slack() -> tuple[SlackConnector, dict, bytes]:
    body = _fixture_body("slack", "webhook_message.json")
    ts = "1700000000"
    base = b"v0:" + ts.encode() + b":" + body
    headers = {"X-Slack-Signature": "v0=" + _hex_hmac("slack-secret", base),
               "X-Slack-Request-Timestamp": ts}
    return SlackConnector(secret="slack-secret", clock=lambda: float(ts)), headers, body


def test_deliver_webhook_slack_beta():
    conn, headers, body = _signed_slack()
    sink = CollectingSink()
    assert deliver_webhook(conn, headers=headers, body=body, sink=sink) == 1
    assert sink.emissions[0].source_id == "slack"


def test_deliver_webhook_slack_bad_sig_emits_nothing():
    conn, _headers, body = _signed_slack()
    sink = CollectingSink()
    bad = {"X-Slack-Signature": "v0=bad", "X-Slack-Request-Timestamp": "1700000000"}
    assert deliver_webhook(conn, headers=bad, body=body, sink=sink) == 0
    assert sink.emissions == []


def _signed_notion() -> tuple[NotionConnector, dict, bytes]:
    body = _fixture_body("notion", "webhook_page.json")
    headers = {"X-Notion-Signature": "sha256=" + _hex_hmac("notion-token", body)}
    return NotionConnector(secret="notion-token"), headers, body


def test_deliver_webhook_notion_beta():
    conn, headers, body = _signed_notion()
    sink = CollectingSink()
    assert deliver_webhook(conn, headers=headers, body=body, sink=sink) == 1
    assert sink.emissions[0].source_id == "notion"


def test_deliver_webhook_notion_bad_sig_emits_nothing():
    conn, _headers, body = _signed_notion()
    sink = CollectingSink()
    # bare hex without the required sha256= prefix -> rejected
    assert deliver_webhook(conn, headers={"X-Notion-Signature": _hex_hmac("notion-token", body)},
                           body=body, sink=sink) == 0
    assert sink.emissions == []


def _signed_zendesk() -> tuple[ZendeskConnector, dict, bytes]:
    body = _fixture_body("zendesk", "ticket_event.json")
    ts = "2026-06-03T10:00:00Z"
    digest = hmac.new(b"zendesk-secret", ts.encode() + body, hashlib.sha256).digest()
    sig = base64.b64encode(digest).decode("ascii")
    headers = {"X-Zendesk-Webhook-Signature": sig, "X-Zendesk-Webhook-Signature-Timestamp": ts}
    return ZendeskConnector(secret="zendesk-secret"), headers, body


def test_deliver_webhook_zendesk_beta():
    conn, headers, body = _signed_zendesk()
    sink = CollectingSink()
    assert deliver_webhook(conn, headers=headers, body=body, sink=sink) == 1
    assert sink.emissions[0].source_id == "zendesk"


def test_deliver_webhook_zendesk_bad_sig_emits_nothing():
    conn, _headers, body = _signed_zendesk()
    sink = CollectingSink()
    bad = {"X-Zendesk-Webhook-Signature": "bad", "X-Zendesk-Webhook-Signature-Timestamp": "2026-06-03T10:00:00Z"}
    assert deliver_webhook(conn, headers=bad, body=body, sink=sink) == 0
    assert sink.emissions == []


# --- Beta graduation: every remaining Prototype earned via the runtime harness ---


def _fixture_payload(connector_name: str, fixture: str) -> dict:
    path = _FIXTURES / connector_name / "fixtures" / fixture
    return json.loads(path.read_text(encoding="utf-8"))


def _poll_one(connector, connector_name: str, fixture: str, source_id: str, expected: int):
    sink = CollectingSink()
    payload = _fixture_payload(connector_name, fixture)
    n = deliver_poll(connector, [payload], sink=sink)
    assert n == expected
    assert all(e.source_id == source_id for e in sink.emissions)
    return sink


def test_deliver_poll_granola_beta():
    _poll_one(GranolaConnector(), "granola", "transcript.json", "granola", 1)


def test_deliver_poll_local_directory_beta():
    _poll_one(LocalDirectoryConnector(), "local_directory", "note.json", "local_directory", 1)


def test_deliver_poll_google_drive_beta():
    _poll_one(GoogleDriveConnector(), "google_drive", "doc_decision.json", "google_drive", 1)


def test_deliver_poll_sarif_beta():
    # one Observation per SARIF result (the fixture carries 2) — exact count, not >=1.
    _poll_one(SarifConnector(), "sarif", "scan_report.json", "sarif", 2)


def test_deliver_poll_mcp_registry_beta():
    _poll_one(McpRegistryConnector(), "mcp_registry", "server.json", "mcp_registry", 1)


def test_deliver_poll_continue_beta():
    _poll_one(ContinueConnector(), "continue_dev", "dev_data_event.json", "continue", 1)


def test_deliver_poll_aider_beta():
    _poll_one(AiderConnector(), "aider", "aider_commit.json", "aider", 1)


def test_deliver_poll_claude_code_beta():
    # The JSONL transcript filters: a meta `mode` line drops, an empty assistant
    # line floors to a non-blank literal -> the filtering parse is proven end-to-end.
    path = _FIXTURES / "claude_code" / "fixtures" / "session_lines.jsonl"
    lines = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    sink = CollectingSink()
    n = deliver_poll(ClaudeCodeConnector(), [{"lines": lines}], sink=sink)
    # 5 lines -> the meta `mode` line drops and the empty assistant line floors
    # (it emits rather than vanishing, else the count would be 3) -> 4 emissions.
    assert n == 4
    assert all(e.source_id == "claude-code" for e in sink.emissions)


def _signed_jira() -> tuple[JiraConnector, dict, bytes]:
    body = _fixture_body("jira", "issue_created.json")  # same bytes signed and delivered (F1)
    sig = "sha256=" + _hex_hmac("jira-secret", body)
    return JiraConnector(secret="jira-secret"), {"X-Hub-Signature": sig}, body


def test_deliver_webhook_jira_beta():
    conn, headers, body = _signed_jira()
    sink = CollectingSink()
    assert deliver_webhook(conn, headers=headers, body=body, sink=sink) == 1
    assert sink.emissions[0].source_id == "jira"


def test_deliver_webhook_jira_bad_sig_emits_nothing():
    conn, _headers, body = _signed_jira()
    sink = CollectingSink()
    assert deliver_webhook(conn, headers={"X-Hub-Signature": "sha256=bad"}, body=body, sink=sink) == 0
    assert sink.emissions == []


def _signed_gitlab(fixture: str = "merge_request_event.json") -> tuple[GitLabConnector, dict, bytes]:
    """GitLab over plaintext X-Gitlab-Token (NOT an HMAC — the token is the secret)."""
    token = "gitlab-webhook-token"
    body = _fixture_body("gitlab", fixture)
    headers = {"X-Gitlab-Token": token, "X-Gitlab-Event-UUID": "evt-1"}
    return GitLabConnector(secret=token), headers, body


def test_deliver_webhook_gitlab_beta():
    conn, headers, body = _signed_gitlab()
    sink = CollectingSink()
    assert deliver_webhook(conn, headers=headers, body=body, sink=sink) == 1
    assert sink.emissions[0].source_id == "gitlab"


def test_deliver_webhook_gitlab_bad_token_emits_nothing():
    conn, _headers, body = _signed_gitlab()
    sink = CollectingSink()
    bad = {"X-Gitlab-Token": "wrong-token", "X-Gitlab-Event-UUID": "evt-2"}
    assert deliver_webhook(conn, headers=bad, body=body, sink=sink) == 0
    assert sink.emissions == []


def test_deliver_webhook_gitlab_missing_token_fails_closed():
    conn, _headers, body = _signed_gitlab()
    sink = CollectingSink()
    assert deliver_webhook(conn, headers={}, body=body, sink=sink) == 0
    assert sink.emissions == []


def test_deliver_poll_confluence_beta():
    _poll_one(ConfluenceConnector(), "confluence", "page_content.json", "confluence", 1)


def test_deliver_poll_copilot_beta():
    _poll_one(CopilotConnector(), "copilot", "metrics_day.json", "copilot", 1)


def test_deliver_poll_cursor_beta():
    # Earned Beta + end-to-end PII-drop: the fixture row carries an example.com email;
    # assert it is absent from the emitted (post-normalize) evidence.
    sink = _poll_one(CursorConnector(), "cursor", "daily_usage_row.json", "cursor", 1)
    emission = sink.emissions[0]
    assert "@example.com" not in emission.title
    assert all("@example.com" not in ev.excerpt for ev in emission.evidence)


def test_deliver_webhook_missing_signature_header_fails_closed():
    """No signature header at all -> verify fails closed (not a crash) -> 0 emissions."""
    fathom, _fh, fbody = _signed_fathom()
    sentry, sbody, _sig = _signed_sentry()
    pagerduty, pbody, _hdr = _signed_pagerduty()
    cases = [(fathom, fbody), (sentry, sbody), (pagerduty, pbody)]
    for conn, body in cases:
        sink = CollectingSink()
        assert deliver_webhook(conn, headers={}, body=body, sink=sink) == 0
        assert sink.emissions == []
