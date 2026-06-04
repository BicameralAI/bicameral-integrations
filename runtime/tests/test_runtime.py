# SPDX-License-Identifier: MIT
"""Behavior tests for the operator-runtime boundary layer (ADR-0012)."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from connectors.linear.connector import LinearConnector
from connectors.osv.connector import OsvConnector
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
