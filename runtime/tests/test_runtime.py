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
from connectors.anthropic_admin.connector import AnthropicAdminConnector
from connectors.claude_code.connector import ClaudeCodeConnector
from connectors.confluence.connector import ConfluenceConnector
from connectors.continue_dev.connector import ContinueConnector
from connectors.copilot.connector import CopilotConnector
from connectors.cursor.connector import CursorConnector
from connectors.devin.connector import DevinConnector
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
from connectors.openai_admin.connector import OpenAIAdminConnector
from connectors.osv.connector import OsvConnector
from connectors.pagerduty.connector import PagerDutyConnector
from connectors.sarif.connector import SarifConnector
from connectors.sentry.connector import SentryConnector
from connectors.servicenow.connector import ServiceNowConnector
from connectors.slack.connector import SlackConnector
from connectors.zendesk.connector import ZendeskConnector
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.pipeline import EmissionContractError, normalize
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
            "data": {
                "identifier": "ENG-1",
                "title": "Add health route",
                "description": "do it",
            },
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
    # D1: ingest -> verify -> normalize -> emit -> POST a conforming v2 ExternalIngestEnvelope (#226).
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
    sink = GatewaySink(endpoint="https://gw.example/api/v1/external-ingest", opener=_opener)
    n = deliver_webhook(conn, headers={"Sentry-Hook-Signature": sig}, body=body, sink=sink)
    assert n == 1
    assert captured["body"]["source_system"] == "sentry"
    assert captured["body"]["content"] and captured["body"]["source_uri"]
    assert captured["body"]["evidence"][0]["excerpt"]
    assert captured["body"]["candidate_hints"][0]["title"]


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
        (_FIXTURES / "fathom" / "fixtures" / "webhook_signed.json").read_text(
            encoding="utf-8"
        )
    )
    body = json.dumps(fx["body"]).encode("utf-8")  # same bytes are signed and delivered
    wid, ts, secret = fx["webhook_id"], fx["webhook_timestamp"], fx["secret"]
    key = base64.b64decode(secret[len("whsec_") :])
    sig = base64.b64encode(
        hmac.new(key, f"{wid}.{ts}.".encode() + body, hashlib.sha256).digest()
    )
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


def test_fathom_normalize_event_signed_non_dict_body_returns_empty():
    # purple-team parse_robustness: a validly-SIGNED top-level non-dict JSON body (e.g. [1,2,3])
    # must skip via the shared dict-guard, not raise AttributeError out of normalize_event.
    fx = json.loads(
        (_FIXTURES / "fathom" / "fixtures" / "webhook_signed.json").read_text(
            encoding="utf-8"
        )
    )
    body = b"[1,2,3]"
    wid, ts, secret = fx["webhook_id"], fx["webhook_timestamp"], fx["secret"]
    key = base64.b64decode(secret[len("whsec_") :])
    sig = base64.b64encode(
        hmac.new(key, f"{wid}.{ts}.".encode() + body, hashlib.sha256).digest()
    )
    headers = {
        "webhook-id": wid,
        "webhook-timestamp": str(ts),
        "webhook-signature": "v1," + sig.decode(),
    }
    conn = FathomConnector(secret=secret, clock=lambda: float(ts))
    assert conn.normalize_event(headers=headers, body=body) == []


def _signed_sentry() -> tuple[SentryConnector, bytes, str]:
    secret = "sentry-webhook-secret"
    body = (_FIXTURES / "sentry" / "fixtures" / "issue_event.json").read_bytes()
    return SentryConnector(secret=secret), body, _hex_hmac(secret, body)


def test_deliver_webhook_sentry_beta():
    conn, body, sig = _signed_sentry()
    sink = CollectingSink()
    assert (
        deliver_webhook(
            conn, headers={"Sentry-Hook-Signature": sig}, body=body, sink=sink
        )
        == 1
    )
    assert sink.emissions[0].source_id == "sentry"


def test_deliver_webhook_sentry_bad_sig_emits_nothing():
    conn, body, _sig = _signed_sentry()
    sink = CollectingSink()
    assert (
        deliver_webhook(
            conn, headers={"Sentry-Hook-Signature": "bad"}, body=body, sink=sink
        )
        == 0
    )
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
    assert (
        deliver_webhook(
            conn, headers={"X-PagerDuty-Signature": header}, body=body, sink=sink
        )
        == 1
    )
    assert sink.emissions[0].source_id == "pagerduty"


def test_deliver_webhook_pagerduty_all_wrong_emits_nothing():
    conn, body, _header = _signed_pagerduty()
    sink = CollectingSink()
    bad = "v1=deadbeef,v1=cafebabe"
    assert (
        deliver_webhook(
            conn, headers={"X-PagerDuty-Signature": bad}, body=body, sink=sink
        )
        == 0
    )
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
    headers = {
        "X-Slack-Signature": "v0=" + _hex_hmac("slack-secret", base),
        "X-Slack-Request-Timestamp": ts,
    }
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
    body = _fixture_body("notion", "webhook_event.json")
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
    assert (
        deliver_webhook(
            conn,
            headers={"X-Notion-Signature": _hex_hmac("notion-token", body)},
            body=body,
            sink=sink,
        )
        == 0
    )
    assert sink.emissions == []


def _signed_zendesk() -> tuple[ZendeskConnector, dict, bytes]:
    body = _fixture_body("zendesk", "ticket_event.json")
    ts = "2026-06-03T10:00:00Z"
    digest = hmac.new(b"zendesk-secret", ts.encode() + body, hashlib.sha256).digest()
    sig = base64.b64encode(digest).decode("ascii")
    headers = {
        "X-Zendesk-Webhook-Signature": sig,
        "X-Zendesk-Webhook-Signature-Timestamp": ts,
    }
    return ZendeskConnector(secret="zendesk-secret"), headers, body


def test_deliver_webhook_zendesk_beta():
    conn, headers, body = _signed_zendesk()
    sink = CollectingSink()
    assert deliver_webhook(conn, headers=headers, body=body, sink=sink) == 1
    assert sink.emissions[0].source_id == "zendesk"
    # body now emitted via redact-and-pass: the fixture description's secret + email are scrubbed.
    excerpt = sink.emissions[0].evidence[0].excerpt
    assert "AKIAABCDEFGHIJKLMNOP" not in excerpt and "@example.com" not in excerpt


def test_deliver_webhook_zendesk_bad_sig_emits_nothing():
    conn, _headers, body = _signed_zendesk()
    sink = CollectingSink()
    bad = {
        "X-Zendesk-Webhook-Signature": "bad",
        "X-Zendesk-Webhook-Signature-Timestamp": "2026-06-03T10:00:00Z",
    }
    assert deliver_webhook(conn, headers=bad, body=body, sink=sink) == 0
    assert sink.emissions == []


# --- Beta graduation: every remaining Prototype earned via the runtime harness ---


def _fixture_payload(connector_name: str, fixture: str) -> dict:
    path = _FIXTURES / connector_name / "fixtures" / fixture
    return json.loads(path.read_text(encoding="utf-8"))


def _poll_one(
    connector, connector_name: str, fixture: str, source_id: str, expected: int
):
    sink = CollectingSink()
    payload = _fixture_payload(connector_name, fixture)
    n = deliver_poll(connector, [payload], sink=sink)
    assert n == expected
    assert all(e.source_id == source_id for e in sink.emissions)
    return sink


def test_deliver_poll_granola_beta():
    _poll_one(GranolaConnector(), "granola", "transcript.json", "granola", 1)


def test_deliver_poll_local_directory_beta():
    _poll_one(
        LocalDirectoryConnector(), "local_directory", "note.json", "local_directory", 1
    )


def test_deliver_poll_google_drive_beta():
    _poll_one(
        GoogleDriveConnector(), "google_drive", "doc_decision.json", "google_drive", 1
    )


def test_deliver_poll_sarif_beta():
    # one Observation per SARIF result (the fixture carries 2) — exact count, not >=1.
    _poll_one(SarifConnector(), "sarif", "scan_report.json", "sarif", 2)


def test_deliver_poll_mcp_registry_beta():
    _poll_one(McpRegistryConnector(), "mcp_registry", "server.json", "mcp_registry", 1)


def test_deliver_poll_continue_beta():
    _poll_one(
        ContinueConnector(), "continue_dev", "dev_data_event.json", "continue_dev", 1
    )


def test_deliver_poll_aider_beta():
    _poll_one(AiderConnector(), "aider", "aider_commit.json", "aider", 1)


def test_deliver_poll_claude_code_beta():
    # The JSONL transcript filters: a meta `mode` line drops, an empty assistant
    # line floors to a non-blank literal -> the filtering parse is proven end-to-end.
    path = _FIXTURES / "claude_code" / "fixtures" / "session_lines.jsonl"
    lines = [
        json.loads(ln)
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    sink = CollectingSink()
    n = deliver_poll(ClaudeCodeConnector(), [{"lines": lines}], sink=sink)
    # 5 lines -> the meta `mode` line drops and the empty assistant line floors
    # (it emits rather than vanishing, else the count would be 3) -> 4 emissions.
    assert n == 4
    assert all(e.source_id == "claude_code" for e in sink.emissions)


def _signed_jira() -> tuple[JiraConnector, dict, bytes]:
    body = _fixture_body(
        "jira", "issue_created.json"
    )  # same bytes signed and delivered (F1)
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
    assert (
        deliver_webhook(
            conn, headers={"X-Hub-Signature": "sha256=bad"}, body=body, sink=sink
        )
        == 0
    )
    assert sink.emissions == []


def _signed_gitlab(
    fixture: str = "merge_request_event.json",
) -> tuple[GitLabConnector, dict, bytes]:
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


def test_deliver_poll_devin_beta():
    sink = _poll_one(DevinConnector(), "devin", "session.json", "devin", 1)
    assert "@example.com" not in sink.emissions[0].evidence[0].excerpt  # body redacted


def test_deliver_poll_servicenow_beta():
    # Required pre-Bot redaction preserves the incident while removing quoted secrets.
    record = _fixture_payload("servicenow", "incident.json")
    raw = Observation(
        source_ref=SourceRef(source_id="servicenow", ref="x"),
        excerpt=record["description"],
    )
    sanitized = normalize([raw], adapter_version="runtime/0.1.0")[0]
    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized.body
    assert "[redacted:secret]" in sanitized.body
    assert sanitized.metadata["redaction_receipt"]["findings"] == [
        {"category": "secret", "action": "tokenized", "count": 1}
    ]
    sink = _poll_one(
        ServiceNowConnector(), "servicenow", "incident.json", "servicenow", 1
    )
    excerpt = sink.emissions[0].evidence[0].excerpt
    assert "AKIAABCDEFGHIJKLMNOP" not in excerpt and "@example.com" not in excerpt


def test_deliver_poll_openai_admin_beta():
    # Actor identity dropped end-to-end: the fixture event carries an email + IP.
    sink = _poll_one(
        OpenAIAdminConnector(), "openai_admin", "audit_event.json", "openai_admin", 1
    )
    excerpt = sink.emissions[0].evidence[0].excerpt
    assert "@example.com" not in excerpt and "203.0.113.7" not in excerpt


def test_deliver_poll_anthropic_admin_beta():
    _poll_one(
        AnthropicAdminConnector(),
        "anthropic_admin",
        "usage_bucket.json",
        "anthropic_admin",
        1,
    )


# --- provenance fields (#196) ---


def test_webhook_provenance_github():
    conn, headers, body = _signed_github()
    sink = CollectingSink()
    deliver_webhook(conn, headers=headers, body=body, sink=sink)
    em = sink.emissions[0]
    assert em.provenance is not None
    assert (
        em.provenance.delivery_mode == "poll"
    )  # GitHub parse sets mode=ACTIVE (REST shape)
    assert em.provenance.verification == "unsigned"
    assert em.provenance.provider_event_id  # X-GitHub-Delivery populated


def test_webhook_provenance_sentry():
    conn, body, sig = _signed_sentry()
    sink = CollectingSink()
    deliver_webhook(conn, headers={"Sentry-Hook-Signature": sig}, body=body, sink=sink)
    em = sink.emissions[0]
    assert em.provenance is not None
    assert em.provenance.delivery_mode == "webhook"
    assert em.provenance.verification == "signed"
    assert em.provenance.provider_event_id


def test_webhook_provenance_pagerduty():
    conn, body, header = _signed_pagerduty()
    sink = CollectingSink()
    deliver_webhook(
        conn, headers={"X-PagerDuty-Signature": header}, body=body, sink=sink
    )
    em = sink.emissions[0]
    assert em.provenance is not None
    assert em.provenance.delivery_mode == "webhook"
    assert em.provenance.verification == "signed"
    assert em.provenance.provider_event_id


def test_webhook_provenance_slack():
    conn, headers, body = _signed_slack()
    sink = CollectingSink()
    deliver_webhook(conn, headers=headers, body=body, sink=sink)
    em = sink.emissions[0]
    assert em.provenance is not None
    assert em.provenance.delivery_mode == "webhook"
    assert em.provenance.verification == "signed"


def test_webhook_provenance_notion():
    conn, headers, body = _signed_notion()
    sink = CollectingSink()
    deliver_webhook(conn, headers=headers, body=body, sink=sink)
    em = sink.emissions[0]
    assert em.provenance is not None
    assert em.provenance.delivery_mode == "webhook"
    assert em.provenance.verification == "signed"
    assert em.provenance.provider_event_id


def test_webhook_provenance_zendesk():
    conn, headers, body = _signed_zendesk()
    sink = CollectingSink()
    deliver_webhook(conn, headers=headers, body=body, sink=sink)
    em = sink.emissions[0]
    assert em.provenance is not None
    assert em.provenance.delivery_mode == "webhook"
    assert em.provenance.verification == "signed"
    assert em.provenance.provider_event_id


def test_webhook_provenance_jira():
    conn, headers, body = _signed_jira()
    sink = CollectingSink()
    deliver_webhook(conn, headers=headers, body=body, sink=sink)
    em = sink.emissions[0]
    assert em.provenance is not None
    assert em.provenance.delivery_mode == "webhook"
    assert em.provenance.verification == "signed"
    assert em.provenance.provider_event_id


def test_webhook_provenance_gitlab():
    conn, headers, body = _signed_gitlab()
    sink = CollectingSink()
    deliver_webhook(conn, headers=headers, body=body, sink=sink)
    em = sink.emissions[0]
    assert em.provenance is not None
    assert em.provenance.delivery_mode == "webhook"
    assert em.provenance.verification == "signed"
    assert em.provenance.provider_event_id


def test_poll_provenance_osv():
    sink = CollectingSink()
    deliver_poll(OsvConnector(), [{"id": "OSV-1", "summary": "a"}], sink=sink)
    em = sink.emissions[0]
    assert em.provenance is not None
    assert em.provenance.delivery_mode == "poll"
    assert em.provenance.verification == "unsigned"


def test_poll_provenance_copilot():
    sink = _poll_one(CopilotConnector(), "copilot", "metrics_day.json", "copilot", 1)
    em = sink.emissions[0]
    assert em.provenance is not None
    assert em.provenance.delivery_mode == "poll"
    assert em.provenance.verification == "unsigned"


def test_provenance_no_secrets():
    conn, headers, body = _signed_github()
    sink = CollectingSink()
    deliver_webhook(conn, headers=headers, body=body, sink=sink)
    em = sink.emissions[0]
    prov = em.provenance
    assert prov is not None
    for val in [prov.provider_event_id, prov.provider_resource_id]:
        assert "AKIA" not in val
        assert "ghp_" not in val
        assert "xox" not in val


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


# --- red-team Cycle B regression: hostile payloads fail closed ---


def test_huge_int_body_fails_closed():
    # #55: a >4300-digit int makes json.loads raise ValueError -> caught -> 0, no crash.
    conn, _h, _b = _signed_github()
    body = b'{"pull_request":{"number":' + b"9" * 5000 + b"}}"
    sig = "sha256=" + _hex_hmac("gh-secret", body)
    assert (
        deliver_webhook(
            conn, headers={"X-Hub-Signature-256": sig}, body=body, sink=CollectingSink()
        )
        == 0
    )


def test_oversized_body_rejected():
    # #55: a body over 1 MiB is rejected before parse/verify.
    conn, headers, _b = _signed_github()
    assert (
        deliver_webhook(
            conn, headers=headers, body=b"x" * (1_048_576 + 1), sink=CollectingSink()
        )
        == 0
    )


def test_all_observations_reject_non_dict():
    # #59: representative connectors fail closed on a non-dict payload (all 26 verified in-cycle).
    for conn in (
        OsvConnector(),
        CopilotConnector(),
        GranolaConnector(),
        ServiceNowConnector(),
    ):
        for arg in (None, "x", 5, []):
            assert conn.observations(arg) == []


def test_fathom_verify_nonstr_header_fails_closed():
    # #57: a non-str webhook-id (past a valid secret) must fail closed, not crash.
    conn, headers, body = _signed_fathom()
    headers = dict(headers)
    headers["webhook-id"] = 12345  # int, not str
    assert conn.verify(headers=headers, body=body) is False


def _signed_zendesk_body(body: bytes) -> dict:
    ts = "2026-06-03T10:00:00Z"
    sig = base64.b64encode(
        hmac.new(b"zendesk-secret", ts.encode() + body, hashlib.sha256).digest()
    ).decode("ascii")
    return {
        "X-Zendesk-Webhook-Signature": sig,
        "X-Zendesk-Webhook-Signature-Timestamp": ts,
    }


def test_idless_replay_deduped_by_body():
    # #60: an id-less but identically-signed delivery is deduped by body hash (no unbounded replay),
    # while a DISTINCT id-less body still emits (the hash discriminates, not a constant).
    from adapter.core.webhook_security import DeliveryDedupCache

    conn = ZendeskConnector(secret="zendesk-secret", dedup=DeliveryDedupCache())
    body = json.dumps(
        {"type": "x", "subject": "plain", "detail": {"subject": "Hello there"}}
    ).encode("utf-8")
    h = _signed_zendesk_body(body)
    assert (
        deliver_webhook(conn, headers=h, body=body, sink=CollectingSink()) == 1
    )  # first
    assert (
        deliver_webhook(conn, headers=h, body=body, sink=CollectingSink()) == 0
    )  # id-less replay deduped
    body2 = json.dumps(
        {"type": "x", "subject": "plain", "detail": {"subject": "A different ticket"}}
    ).encode("utf-8")
    assert (
        deliver_webhook(
            conn, headers=_signed_zendesk_body(body2), body=body2, sink=CollectingSink()
        )
        == 1
    )
