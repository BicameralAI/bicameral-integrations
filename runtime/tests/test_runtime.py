# SPDX-License-Identifier: MIT
"""Behavior tests for the operator-runtime boundary layer (ADR-0012)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path

import pytest

from connectors.fathom.connector import FathomConnector
from connectors.github.connector import GitHubConnector
from connectors.linear.connector import LinearConnector
from connectors.notion.connector import NotionConnector
from connectors.osv.connector import OsvConnector
from connectors.pagerduty.connector import PagerDutyConnector
from connectors.sentry.connector import SentryConnector
from connectors.slack.connector import SlackConnector
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
    # A valid delivery reaches the sink; the #109 gate is asserted, not skipped.
    conn, headers, body = _signed_linear()
    with pytest.raises(GatewayEmissionGated):
        deliver_webhook(conn, headers=headers, body=body, sink=GatewaySink())


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
