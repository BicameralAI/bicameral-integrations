# SPDX-License-Identifier: MIT
"""Behavior tests for the live-poll client (the ingest *fetch* half; ADR-0012).

The poll path is proven end-to-end through a RecordedTransport over captured
provider-response fixtures — request shape + auth/version headers + pagination +
parse + emission — without any live network call (a mock does not promote a
connector to Live; ADR-0012). Reference connector: anthropic_admin (PII-free).
"""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path

import pytest

from adapter.core.sensitive import detect_sensitive
from connectors.anthropic_admin.connector import AnthropicAdminConnector
from runtime.poll_client import (
    ApiKeyHeaderAuth,
    HttpResponse,
    PollError,
    _read_capped,
    build_anthropic_admin_spec,
    poll,
)
from runtime.secrets import MappingSecretResolver
from runtime.sinks import CollectingSink

_FIXTURES = Path(__file__).parent / "fixtures"
_SECRET = "sk-ant-admin-TESTKEY-not-real"


def _fixture_bytes(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


def _resp(name: str) -> HttpResponse:
    return HttpResponse(200, _fixture_bytes(name))


class RecordedTransport:
    """Returns queued responses in order; records every request for assertion."""

    def __init__(self, responses: list[HttpResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def request(self, method, url, *, headers, body=None) -> HttpResponse:
        self.requests.append((method, url, dict(headers), body))
        if not self._responses:
            raise AssertionError("RecordedTransport exhausted")
        return self._responses.pop(0)


def _spec(secret: str = _SECRET):
    resolver = MappingSecretResolver({"anthropic_admin": secret})
    return build_anthropic_admin_spec(resolver)


def test_anthropic_admin_poll_two_pages_emits_two() -> None:
    transport = RecordedTransport([_resp("anthropic_admin_usage_page1.json"),
                                   _resp("anthropic_admin_usage_page2.json")])
    sink = CollectingSink()
    count = poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=sink)
    assert count == 2
    assert len(sink.emissions) == 2
    # Both buckets parsed: page-1 input 1200+300+100=1600 / output 800; page-2 500 / 250.
    joined = " ".join(e.body for e in sink.emissions)
    assert "1600 input / 800 output" in joined
    assert "500 input / 250 output" in joined


def test_page_two_request_carries_returned_token_value() -> None:
    # Audit finding 4: prove token-DRIVEN advancement (page 2 carries page 1's
    # returned `next_page` VALUE), not merely that two responses drain.
    # NOTE: the param NAME ("page") is the UNVERIFIED A2 assumption — this proves
    # our machinery re-sends the provider's token, not that Anthropic accepts it.
    transport = RecordedTransport([_resp("anthropic_admin_usage_page1.json"),
                                   _resp("anthropic_admin_usage_page2.json")])
    poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    assert len(transport.requests) == 2
    page2_url = transport.requests[1][1]
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(page2_url).query))
    assert query.get("page") == "pg2"  # the exact token page 1 returned


def test_request_shape_auth_and_version_headers() -> None:
    transport = RecordedTransport([_resp("anthropic_admin_usage_page1.json"),
                                   _resp("anthropic_admin_usage_page2.json")])
    poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    method, url, headers, _ = transport.requests[0]
    assert method == "GET"
    assert headers["x-api-key"] == _SECRET
    assert headers["anthropic-version"] == "2023-06-01"
    assert "page" not in urllib.parse.urlsplit(url).query  # no token on page 1


def test_pagination_stops_on_has_more_false() -> None:
    transport = RecordedTransport([_resp("anthropic_admin_usage_page2.json")])  # has_more=false
    count = poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    assert count == 1
    assert len(transport.requests) == 1


def test_has_more_true_but_no_token_stops_closed() -> None:
    body = json.dumps({"data": [], "has_more": True}).encode("utf-8")  # token absent
    transport = RecordedTransport([HttpResponse(200, body)])
    count = poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    assert count == 0
    assert len(transport.requests) == 1  # fails closed: no second request, no loop


class _LoopingTransport:
    """Always claims another page (cyclic pager) to exercise the _MAX_PAGES cap."""

    def __init__(self) -> None:
        self.calls = 0

    def request(self, method, url, *, headers, body=None) -> HttpResponse:
        self.calls += 1
        page = {"data": [], "has_more": True, "next_page": f"t{self.calls}"}
        return HttpResponse(200, json.dumps(page).encode("utf-8"))


def test_max_pages_cap() -> None:
    transport = _LoopingTransport()
    with pytest.raises(PollError) as exc:
        poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    assert exc.value.reason == "max_pages_exceeded"
    assert transport.calls <= 101  # bounded, not infinite


def test_poisoned_next_page_token_rejected() -> None:
    # Audit finding 6: the provider response is untrusted; a CR/LF in next_page
    # must not splice into the request URL.
    page = {"data": [], "has_more": True, "next_page": "pg2\r\nX-Injected: evil"}
    transport = RecordedTransport([HttpResponse(200, json.dumps(page).encode("utf-8"))])
    with pytest.raises(PollError) as exc:
        poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    assert "page_token" in exc.value.reason


def test_blank_secret_fails_closed_no_request() -> None:
    transport = RecordedTransport([])
    with pytest.raises(PollError) as exc:
        # build raises before any poll/request is attempted
        spec = build_anthropic_admin_spec(MappingSecretResolver({}))
        poll(AnthropicAdminConnector(), spec, transport=transport, sink=CollectingSink())
    assert exc.value.reason == "secret_unresolved:anthropic_admin"
    assert transport.requests == []  # no request ever attempted


def test_non_200_raises_token_free() -> None:
    transport = RecordedTransport([HttpResponse(401, b'{"error":"unauthorized"}')])
    with pytest.raises(PollError) as exc:
        poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    assert exc.value.status == 401
    assert _SECRET not in str(exc.value)  # token never in the error


def test_unparseable_page_body_fails_closed() -> None:
    bad = RecordedTransport([HttpResponse(200, b"<html>not json</html>")])
    with pytest.raises(PollError) as exc:
        poll(AnthropicAdminConnector(), _spec(), transport=bad, sink=CollectingSink())
    assert exc.value.reason == "unparseable_body"
    # items() yielding a non-list also fails closed
    nonlist = RecordedTransport([HttpResponse(200, json.dumps({"data": {"x": 1}}).encode())])
    with pytest.raises(PollError) as exc2:
        poll(AnthropicAdminConnector(), _spec(), transport=nonlist, sink=CollectingSink())
    assert exc2.value.reason == "items_not_a_list"


class _FakeFp:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, n: int) -> bytes:
        return self._data[:n]


def test_read_capped_bounds_response() -> None:
    out = _read_capped(_FakeFp(b"x" * 64), cap=16)
    assert len(out) == 16  # the cap bounds the read without a network call


def test_crlf_in_secret_rejected() -> None:
    with pytest.raises(PollError) as exc:
        ApiKeyHeaderAuth("x-api-key", "abc\r\ndef")
    assert "control_char" in exc.value.reason
    assert "abc" not in exc.value.reason  # value-free message


def test_recorded_response_is_pii_free() -> None:
    transport = RecordedTransport([_resp("anthropic_admin_usage_page1.json"),
                                   _resp("anthropic_admin_usage_page2.json")])
    sink = CollectingSink()
    poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=sink)
    for emission in sink.emissions:
        assert detect_sensitive(emission.body) == []
        assert detect_sensitive(emission.title) == []
