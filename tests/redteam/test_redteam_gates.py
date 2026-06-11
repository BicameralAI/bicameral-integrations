# SPDX-License-Identifier: MIT
"""Red Team CI gates: regression barriers for the purple-team go-live attack classes (2026-06-11).

Each test encodes a confirmed finding's fix as a permanent, behavioral assertion (invoke the unit,
assert its output / fail-closed behavior — never presence-only). A regression in any hardened edge
trips a named gate before any connector reaches Live. Maps to issues #94-#102.

Run as the CI gate: ``pytest tests/redteam -q`` (.github/workflows/red-team.yml).
"""

from __future__ import annotations

import pytest

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from adapter.core.pipeline import EmissionContractError, validate_emissions
from adapter.core.redaction import redact
from adapter.core.sensitive import detect_sensitive

import hashlib
import hmac
import json

from adapter.core.capabilities import SourceMode
from adapter.core.observations import Observation
from adapter.core.webhook_security import DeliveryDedupCache

from connectors.copilot.connector import parse_metrics_day
from connectors.cursor.connector import parse_usage_day
from connectors.devin.connector import parse_session
from connectors.github.connector import GitHubConnector, parse_pull_request
from connectors.google_drive.connector import extract_document_text, parse_document
from connectors.mcp_registry.connector import parse_server
from connectors.slack.connector import parse_message

from runtime import delivery, doc_fetch, graphql_poll, poll_client, sinks
from runtime.local_config import ConfigError, LocalConfig, assert_runnable
from runtime.poll_auth import NoAuth, PollError
from runtime.poll_client import HttpResponse, PollSpec
from runtime.poll_specs import (
    build_copilot_spec,
    build_devin_spec,
    build_granola_spec,
    build_linear_graphql_spec,
    build_servicenow_spec,
)

_LUHN_PAN = "4111111111111111"  # Visa test number: Luhn-valid, not a real card


class _Resolver:
    """Minimal SecretResolver stub."""

    def __init__(self, **secrets: str) -> None:
        self._s = secrets

    def resolve(self, key: str) -> str:
        return self._s.get(key, "")


class _StubTransport:
    """HttpTransport returning a fixed response (no network)."""

    def __init__(self, status: int, body: bytes) -> None:
        self._r = HttpResponse(status, body)

    def request(self, method, url, *, headers, body=None):  # noqa: ANN001
        return self._r


def _emission(*, title="t", body="b", source_id="x", excerpt="e", url="", ref="",
              author="", timestamp="") -> AdapterEmission:
    ev = SourceEvidence(
        source_ref=SourceRef(source_id=source_id, ref=ref, url=url, kind="k"),
        excerpt=excerpt, author=author, timestamp=timestamp,
    )
    return AdapterEmission(
        source_id=source_id, title=title, body=body, evidence=(ev,),
        emission_type="candidate", adapter_version="redteam/1", metadata={},
    )


# --- SSRF-1 (#94): transport must not follow provider 3xx redirects ----------------

def test_pollclient_default_opener_is_no_follow():
    # The default UrllibTransport opener is the no-follow opener (not stdlib urlopen).
    assert poll_client.UrllibTransport()._opener is poll_client._NO_FOLLOW_OPENER


def test_no_follow_handler_returns_none_on_redirect():
    # redirect_request returning None makes urllib surface the 3xx as HTTPError (no follow).
    h = poll_client._NoFollowRedirect()
    assert h.redirect_request(None, None, 302, "Found", {}, "https://evil.example/") is None
    assert sinks._NoFollowRedirect().redirect_request(
        None, None, 301, "Moved", {}, "https://evil.example/") is None


def test_redirect_status_fails_closed_before_secret_resend():
    # A 302 surfaced as a non-200 response fails closed at the 200-only guard -> PollError,
    # so no second credentialed request is ever issued.
    spec = PollSpec(base_url="https://api.example/x", auth=NoAuth(), items=lambda p: p)
    with pytest.raises(PollError):
        poll_client._fetch_page(_StubTransport(302, b'{"to":"evil"}'), spec, spec.base_url)


# --- PARSE-1 (#96): deeply-nested JSON must fail closed, not raise RecursionError ----

@pytest.mark.parametrize("decode", [
    lambda b: poll_client._fetch_page(
        _StubTransport(200, b), PollSpec("u", NoAuth(), items=lambda p: p), "u"),
    lambda b: graphql_poll._decode_page(200, b),
    lambda b: doc_fetch._decode(200, b),
])
def test_deeply_nested_body_fails_closed(decode):
    deep = b"[" * 100_000 + b"]" * 100_000  # exceeds the JSON recursion limit
    with pytest.raises(PollError):
        decode(deep)


# --- PII-1 (#95): cross-field PAN suppression closed by per-leaf screening -----------

def test_pan_not_suppressed_across_fields():
    # excerpt ends in an ID label; a Luhn-valid PAN at the START of an adjacent field
    # (url) must NOT be suppressed -> reject. (The old join fabricated suppression.)
    em = _emission(excerpt="see ref=", body="see ref=", url=_LUHN_PAN)
    with pytest.raises(EmissionContractError):
        validate_emissions([em])


def test_within_field_id_label_still_suppresses():
    # Within ONE field, an ID label legitimately suppresses the run (unchanged behavior).
    em = _emission(excerpt=f"order_id: {_LUHN_PAN}", body="ok", url="")
    assert validate_emissions([em])  # no raise


def test_author_timestamp_are_screened():
    # CONFIG-3: untrusted author/timestamp are in the scan set.
    em = _emission(excerpt="ok", author=_LUHN_PAN)
    with pytest.raises(EmissionContractError):
        validate_emissions([em])


# --- PII-4 (#95): wire `source` url/ref is redacted for email/phone ------------------

def test_gateway_source_redacts_email_in_url():
    from runtime.gateway_mapping import emission_to_ingest_request
    em = _emission(excerpt="ok", url="https://git.example/x/pull/1#alice@personal.com")
    req = emission_to_ingest_request(em)
    assert "alice@personal.com" not in req["source"]


# --- SSRF-4 (#99): servicenow instance/fields cannot inject host/path/query ----------

@pytest.mark.parametrize("evil", ["evil.com/x", "host?a=b", "user@host", "h#frag", "a host"])
def test_servicenow_rejects_injected_instance(evil):
    with pytest.raises(PollError):
        build_servicenow_spec(_Resolver(servicenow="pw"), instance=evil, username="u")


def test_servicenow_clean_instance_builds_pinned_url():
    spec = build_servicenow_spec(
        _Resolver(servicenow="pw"), instance="acme.service-now.com", username="u",
        fields="number,short_description")
    assert spec.base_url.startswith("https://acme.service-now.com/api/now/table/incident?")
    assert "&sysparm_fields" not in spec.base_url.split("?", 1)[0]  # no path injection


# --- CONFIG (#101): endpoint host pinning for credentialed requests ------------------

def test_linear_endpoint_host_pinned():
    with pytest.raises(PollError):
        build_linear_graphql_spec(_Resolver(linear="k"), endpoint="https://evil.example/graphql")


def test_devin_base_url_requires_https():
    with pytest.raises(PollError):
        build_devin_spec(_Resolver(devin="k"), base_url="http://api.devin.ai/v3/organizations/o/sessions")


# --- CONFIG (deep-audit SG-2026-06-12-B): EVERY credentialed build_*_spec host-pins -------

def test_devin_endpoint_host_pinned():
    # devin was allow=None (scheme-only); now pinned to api.devin.ai. An off-host https
    # base_url must fail closed before the cog_ Bearer is attached.
    with pytest.raises(PollError):
        build_devin_spec(
            _Resolver(devin="k"),
            base_url="https://attacker.example/v3/organizations/o/sessions")


@pytest.mark.parametrize("evil", [
    "https://attacker.example/orgs/o/copilot/metrics",   # off-provider host
    "http://api.github.com/orgs/o/copilot/metrics",      # http cleartext
    "https://169.254.169.254/orgs/o/copilot/metrics",    # cloud-metadata SSRF
    "https://user:pw@api.github.com/x",                  # userinfo injection
])
def test_copilot_endpoint_host_pinned(evil):
    # build_copilot_spec previously had NO endpoint guard (deep-audit HIGH): the read:org PAT
    # would reach any config host. Now pinned to api.github.com, fail-closed token-free.
    with pytest.raises(PollError):
        build_copilot_spec(_Resolver(copilot="k"), base_url=evil)


@pytest.mark.parametrize("evil", [
    "https://attacker.example/v1/notes",
    "http://public-api.granola.ai/v1/notes",
    "https://169.254.169.254/v1/notes",
])
def test_granola_endpoint_host_pinned(evil):
    # build_granola_spec previously had NO endpoint guard (deep-audit HIGH): the grn_ Bearer
    # fronting PII-dense transcripts would reach any config host. Now pinned, fail-closed.
    with pytest.raises(PollError):
        build_granola_spec(_Resolver(granola="k"), base_url=evil)


@pytest.mark.parametrize("evil", ["169.254.169.254", "metadata.google.internal", "127.0.0.1", "10.0.0.5"])
def test_servicenow_rejects_internal_metadata_instance(evil):
    # _require_bare_host admitted private/metadata IP literals + metadata names (deep-audit low):
    # a credentialed Basic request to an SSRF/metadata target. Now denylisted, fail-closed.
    with pytest.raises(PollError):
        build_servicenow_spec(_Resolver(servicenow="pw"), instance=evil, username="u")


def test_pinned_builders_accept_their_verified_host():
    # The pins must NOT break the documented host (regression guard against an over-tight pin).
    assert build_copilot_spec(_Resolver(copilot="k")).base_url.startswith("https://api.github.com/")
    assert build_granola_spec(_Resolver(granola="k")).base_url.startswith("https://public-api.granola.ai/")
    assert build_devin_spec(
        _Resolver(devin="k"), base_url="https://api.devin.ai/v3/organizations/o/sessions"
    ).base_url.startswith("https://api.devin.ai/")


# --- CONFIG (#101): undeclared runtime keys are rejected (no silent widening) --------

def test_runtime_config_allowlist_rejects_undeclared_key():
    cfg = LocalConfig(
        connectors={"linear": {"enabled": True, "secrets": {"linear": "k"},
                               "runtime": {"endpoint": "https://evil.example/graphql"}}},
        mods={}, gateway={}, secret_map={"linear": "k"},
    )
    with pytest.raises(ConfigError):
        assert_runnable(cfg, "linear", mode="active")


# --- PARSE-2 (#97): devin parse_session tolerates non-string scalar fields -----------

def test_devin_parse_session_non_string_scalars():
    obs = parse_session({"session_id": 12345, "status": ["x"], "title": 1})
    assert obs.source_ref.source_id == "devin"
    assert obs.excerpt  # floored, no crash


# --- PARSE (deep-audit Cycle 2): non-string scalar fields must not crash the batch ----

@pytest.mark.parametrize("parse, payload", [
    (parse_usage_day, {"day": 12345, "userId": 7}),                       # cursor .strip() crash
    (parse_usage_day, {"day": ["x"], "mostUsedModel": 9}),
    (parse_metrics_day, {"date": 12345}),                                 # copilot .strip() crash
    (parse_metrics_day, {"date": {"k": "v"}}),
    (parse_pull_request, {"title": 123, "body": 456,                      # github redact() crash
                          "base": {"repo": {"full_name": "a/b"}}, "number": 1}),
    (parse_message, {"event": {"text": 999, "channel": ["c"], "ts": 1.5, "user": 7}}),  # slack .strip()
])
def test_connector_parse_tolerates_non_string_scalars(parse, payload):
    # A truthy non-string scalar in a malformed/hostile provider row must floor to a valid
    # Observation, never raise AttributeError/TypeError (which would abort the whole batch).
    obs = parse(payload)
    assert obs.excerpt  # non-empty floor, no crash
    assert isinstance(obs.source_ref.ref, str)


class _CrashOnBadRow:
    """Connector whose parse raises on a flagged row (simulates a residual field-type defect)."""

    source_id = "stub"

    def observations(self, payload):  # noqa: ANN001
        if payload.get("bad"):
            raise TypeError("simulated non-string parse crash")
        return [Observation(source_ref=SourceRef(source_id="stub", ref="r", kind="k"),
                            excerpt="ok", mode=SourceMode.ACTIVE, title="t")]


def test_deliver_poll_skips_malformed_row_not_whole_batch():
    # deliver_poll wraps each connector.observations() call: one crashing row is logged-and-
    # skipped; the good rows in the same batch still emit (deep-audit Cycle 2 backstop).
    sink = sinks.CollectingSink()
    n = delivery.deliver_poll(_CrashOnBadRow(), [{"bad": True}, {}, {"bad": True}], sink=sink)
    assert n == 1  # the one good row emitted; two bad rows skipped, batch not aborted


# --- PARSE-3 (#98) + PII-3 (#95): gdrive body walk + documentId guard ----------------

@pytest.mark.parametrize("doc", [
    {"body": {"content": [1, 2, 3]}},
    {"body": "not-a-dict"},
    {"body": {"content": [{"paragraph": {"elements": [{"textRun": {"content": 5}}]}}]}},
    {"body": {"content": [{"table": {"tableRows": "nope"}}]}},
])
def test_gdrive_body_walk_type_confusion_no_crash(doc):
    assert isinstance(extract_document_text(doc), str)


def test_gdrive_pan_documentid_not_used_as_ref():
    obs = parse_document({"documentId": _LUHN_PAN, "title": "Doc"})
    assert obs.source_ref.ref != _LUHN_PAN  # malformed id dropped; ref falls back to title


# --- DOS-1 (#101): aggregate item cap across paginated pages -------------------------

class _StubConn:
    source_id = "x"

    def observations(self, payload):  # noqa: ANN001 (not reached; cap raises first)
        return []


def test_pollclient_aggregate_item_cap(monkeypatch):
    monkeypatch.setattr(poll_client, "_MAX_TOTAL_ITEMS", 3)
    spec = PollSpec(base_url="https://api.example/x", auth=NoAuth(), items=lambda p: p)
    transport = _StubTransport(200, b"[{},{},{},{}]")  # 4 items > cap of 3
    with pytest.raises(PollError):
        poll_client.poll(_StubConn(), spec, transport=transport, sink=sinks.CollectingSink())


def test_graphql_aggregate_item_cap(monkeypatch):
    monkeypatch.setattr(graphql_poll, "_MAX_TOTAL_ITEMS", 3)
    spec = graphql_poll.GraphQLPollSpec(
        endpoint="https://api.linear.app/graphql", auth=NoAuth(), query="q",
        nodes_path="data.x.nodes", page_info_path="data.x.pageInfo", parse=lambda n: n,
    )
    body = b'{"data":{"x":{"nodes":[{},{},{},{}],"pageInfo":{"hasNextPage":false}}}}'
    with pytest.raises(PollError):
        graphql_poll.poll_graphql(spec, _StubTransport(200, body), sinks.CollectingSink())


# --- WEBHOOK dedup (deep-audit Cycle 4): empty delivery id cannot bypass dedup --------

def test_github_empty_delivery_id_replay_deduped():
    # An empty/absent X-GitHub-Delivery header previously skipped dedup (bare `if delivery_id`),
    # so a byte-identical id-less replay re-emitted. Body-hash fallback collapses it.
    secret = "gh-secret"
    envelope = {"number": 1, "pull_request": {"title": "t", "body": "b",
                "base": {"repo": {"full_name": "a/b"}}, "html_url": "https://x/1"}}
    body = json.dumps(envelope).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": sig}  # NO X-GitHub-Delivery
    conn = GitHubConnector(secret=secret, dedup=DeliveryDedupCache())
    assert len(conn.normalize_event(headers=headers, body=body)) == 1
    assert conn.normalize_event(headers=headers, body=body) == []  # replay collapsed


# --- PII (deep-audit Cycle 4): mcp_registry redact-and-passes attacker public free text

def test_mcp_registry_redacts_public_free_text():
    obs = parse_server({"name": "io.x/srv", "description": "ping me at alice@personal.com",
                        "websiteUrl": "https://x.example"})
    assert "alice@personal.com" not in obs.excerpt  # generic email scrubbed before the wire


def test_mcp_registry_non_string_fields_no_crash():
    obs = parse_server({"name": ["a"], "title": 1, "description": 9999, "version": []})
    assert obs.excerpt and isinstance(obs.source_ref.ref, str)  # floored, no TypeError


# --- CHOKEPOINT (mod purple-team MP1): validate_emissions is uniformly fail-closed ----

def _ev(**kw):
    base = dict(source_ref=SourceRef(source_id="x", ref="r", url="", kind="k"), excerpt="e")
    base.update(kw)
    return SourceEvidence(**base)


def _em(**kw):
    base = dict(source_id="x", title="t", body="b", evidence=(_ev(),), adapter_version="rt/1")
    base.update(kw)
    return AdapterEmission(**base)


@pytest.mark.parametrize("em", [
    _em(source_id=123),                    # re.match would TypeError
    _em(emission_type=["hint"]),           # unhashable membership would TypeError
    _em(title=5),                          # detect_sensitive would TypeError
    _em(body=None),
    _em(adapter_version=9),                # .strip() would AttributeError
    _em(evidence=5),                       # iteration would TypeError
    _em(evidence=(_ev(source_ref=None),)),  # .url would AttributeError
    _em(evidence=(_ev(author=["x"]),)),    # detect_sensitive would TypeError
    _em(evidence=(_ev(excerpt=42),)),
])
def test_validate_emissions_fail_closed_on_malformed(em):
    # A type-malformed emission must raise the CONTRACT error, never a raw TypeError/AttributeError,
    # so every consumer (mods, gateway bridge) sees a uniform fail-closed boundary (SG-2026-06-12-F).
    with pytest.raises(EmissionContractError):
        validate_emissions([em])


# --- redaction invariant (the backstop's core contract) ------------------------------

@pytest.mark.parametrize("sample", [
    "AKIA" + "A" * 16, _LUHN_PAN, "ssn: 123-45-6789",
])
def test_redact_pass_invariant(sample):
    assert detect_sensitive(redact(sample)) == []
