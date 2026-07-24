# SPDX-License-Identifier: MIT
"""Behavior tests for the live GraphQL poll path (FX-LINEAR-003; ADR-0012).

Proven end-to-end through a recording transport over crafted GraphQL responses —
cursor-from-body advance, fail-closed on untrusted transport edges, and mandatory
pre-Bot sanitization — without any live network.
"""

from __future__ import annotations

import json

import pytest

from runtime.graphql_poll import GraphQLPollSpec, poll_graphql
from runtime.poll_auth import PollError
from runtime.poll_client import HttpResponse
from runtime.poll_specs import build_linear_graphql_spec
from runtime.secrets import MappingSecretResolver
from runtime.sinks import CollectingSink

_AKIA = "AKIAIOSFODNN7EXAMPLE"


class _RecordingTransport:
    """Returns queued responses in order and records request bodies."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.bodies: list[bytes | None] = []
        self._i = 0

    def request(self, method, url, *, headers, body=None):
        self.bodies.append(body)
        resp = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return resp


def _resp(status: int, payload: object) -> HttpResponse:
    return HttpResponse(status, json.dumps(payload).encode("utf-8"))


def _page(nodes: list, *, has_next: bool, end_cursor: str | None) -> object:
    return _resp(
        200,
        {
            "data": {
                "issues": {
                    "nodes": nodes,
                    "pageInfo": {
                        "hasNextPage": has_next,
                        "endCursor": end_cursor,
                    },
                }
            }
        },
    )


def _issue(identifier: str, desc: str = "a clean description") -> dict:
    return {
        "identifier": identifier,
        "title": "Fix bug",
        "description": desc,
        "url": f"https://linear.app/x/{identifier}",
        "updatedAt": "2026-06-01",
        "state": {"name": "In Progress"},
    }


def _spec() -> GraphQLPollSpec:
    return build_linear_graphql_spec(
        MappingSecretResolver({"linear": "lin_key_123"})
    )


def test_linear_graphql_two_page_walk():
    transport = _RecordingTransport(
        [
            _page([_issue("ENG-1")], has_next=True, end_cursor="c1"),
            _page([_issue("ENG-2")], has_next=False, end_cursor=None),
        ]
    )
    sink = CollectingSink()
    count = poll_graphql(_spec(), transport, sink)
    assert count == 2
    assert json.loads(transport.bodies[0])["variables"]["after"] is None
    assert json.loads(transport.bodies[1])["variables"]["after"] == "c1"


def test_graphql_200_with_errors_fails_closed():
    transport = _RecordingTransport([_resp(200, {"errors": [{"message": "boom"}]})])
    sink = CollectingSink()
    with pytest.raises(PollError):
        poll_graphql(_spec(), transport, sink)
    assert not sink.emissions


def test_graphql_400_ratelimited_fails_closed():
    transport = _RecordingTransport(
        [_resp(400, {"errors": [{"code": "RATELIMITED"}]})]
    )
    with pytest.raises(PollError) as exc:
        poll_graphql(_spec(), transport, CollectingSink())
    assert exc.value.reason == "rate_limited"


def test_graphql_malformed_400_fails_closed():
    for body in (b"not json at all", json.dumps({"errors": "nope"}).encode()):
        transport = _RecordingTransport([HttpResponse(400, body)])
        with pytest.raises(PollError) as exc:
            poll_graphql(_spec(), transport, CollectingSink())
        assert exc.value.reason == "http_error"


def test_graphql_nonlist_nodes_fails_closed():
    transport = _RecordingTransport(
        [_resp(200, {"data": {"issues": {"nodes": {}, "pageInfo": {}}}})]
    )
    with pytest.raises(PollError) as exc:
        poll_graphql(_spec(), transport, CollectingSink())
    assert exc.value.reason == "nodes_not_a_list"


def test_graphql_oversized_body_fails_closed(monkeypatch):
    import runtime.graphql_poll as gp

    monkeypatch.setattr(gp, "_MAX_RESPONSE", 10)
    transport = _RecordingTransport(
        [_page([_issue("ENG-1")], has_next=False, end_cursor=None)]
    )
    with pytest.raises(PollError) as exc:
        poll_graphql(_spec(), transport, CollectingSink())
    assert exc.value.reason == "oversized_body"


def test_blank_secret_makes_no_request():
    with pytest.raises(PollError) as exc:
        build_linear_graphql_spec(MappingSecretResolver({"linear": ""}))
    assert exc.value.reason == "secret_unresolved:linear"


def test_graphql_secret_in_description_is_sanitized_and_receipted():
    transport = _RecordingTransport(
        [
            _page(
                [_issue("ENG-9", desc=f"deploy key {_AKIA}")],
                has_next=False,
                end_cursor=None,
            )
        ]
    )
    sink = CollectingSink()
    assert poll_graphql(_spec(), transport, sink) == 1
    assert len(sink.emissions) == 1
    emission = sink.emissions[0]
    assert _AKIA not in emission.body
    assert "[redacted:secret]" in emission.body
    assert emission.metadata["redaction_receipt"]["findings"] == [
        {"category": "secret", "action": "tokenized", "count": 1}
    ]


def test_graphql_runaway_cursor_stops():
    transport = _RecordingTransport(
        [_page([_issue("ENG-1")], has_next=True, end_cursor="")]
    )
    count = poll_graphql(_spec(), transport, CollectingSink())
    assert count == 1
    assert len(transport.bodies) == 1


def test_graphql_circular_cursor_fails_closed():
    transport = _RecordingTransport(
        [_page([_issue("ENG-1")], has_next=True, end_cursor="c1")]
    )
    with pytest.raises(PollError) as exc:
        poll_graphql(_spec(), transport, CollectingSink())
    assert exc.value.reason == "circular_cursor"
    assert len(transport.bodies) == 2


def test_graphql_missing_data_fails_closed():
    transport = _RecordingTransport([_resp(200, {"notdata": {"issues": {}}})])
    with pytest.raises(PollError) as exc:
        poll_graphql(_spec(), transport, CollectingSink())
    assert exc.value.reason == "missing_data"


def test_graphql_aggregate_bytes_cap(monkeypatch):
    import runtime.graphql_poll as gp

    monkeypatch.setattr(gp, "_MAX_TOTAL_BYTES", 500)
    pages = [
        _page(
            [_issue("ENG-1", desc="p" * 300)],
            has_next=True,
            end_cursor="c1",
        ),
        _page(
            [_issue("ENG-2", desc="p" * 300)],
            has_next=False,
            end_cursor=None,
        ),
    ]
    transport = _RecordingTransport(pages)
    sink = CollectingSink()
    with pytest.raises(PollError) as exc:
        poll_graphql(_spec(), transport, sink)
    assert "aggregate_bytes_exceeded" in str(exc.value)
    assert sink.emissions == []
