# SPDX-License-Identifier: MIT
"""Unit tests for the GitLab connector parse surface + plaintext-token verify."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapter.core.webhook_security import (
    DeliveryDedupCache,
    WebhookVerificationError,
    verify_shared_token,
)
from connectors.gitlab.connector import GitLabConnector, parse_issue, parse_merge_request

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
_TOKEN = "gitlab-webhook-token"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _body(name: str) -> bytes:
    return json.dumps(_load(name)).encode("utf-8")


def test_parse_merge_request_maps_fields():
    obs = parse_merge_request(_load("merge_request_event.json"))
    assert obs.source_ref.ref == "acme/widgets!42"  # MR uses !iid
    assert obs.source_ref.kind == "merge_request"
    assert obs.excerpt.startswith("Adds a /health endpoint")  # description, not title
    assert obs.author == "devuser"
    assert obs.source_ref.url.endswith("/merge_requests/42")


def test_parse_issue_maps_fields():
    obs = parse_issue(_load("issue_event.json"))
    assert obs.source_ref.ref == "acme/widgets#7"  # issue uses #iid
    assert obs.source_ref.kind == "issue"
    assert obs.title.startswith("Login rejects")


def test_blank_title_and_body_floor():
    payload = {"object_kind": "issue", "object_attributes": {"title": "  ", "description": ""}}
    obs = parse_issue(payload)
    assert obs.excerpt == "gitlab-issue"  # floored, non-blank
    assert obs.source_ref.ref == "gitlab-issue"  # no project/iid -> floored


def test_body_and_title_redact_and_passed():
    # F1 (medium): MR/issue title + description are redact-and-passed (the github standard).
    payload = {
        "object_kind": "issue",
        "object_attributes": {
            "iid": 9,
            "title": "Outage ping ops@corp.com",
            "description": "leaked AKIAIOSFODNN7EXAMPLE in the logs",
        },
        "project": {"path_with_namespace": "acme/widgets"},
        "user": {"username": "devuser"},
    }
    obs = parse_issue(payload)
    assert "ops@corp.com" not in obs.title
    assert "AKIAIOSFODNN7EXAMPLE" not in obs.excerpt
    assert obs.author == "devuser"  # public username retained (not redacted)


def test_public_username_retained_as_author():
    # F2 (design): the public GitLab username is the artifact author — kept, like github's login.
    payload = {
        "object_kind": "merge_request",
        "object_attributes": {"iid": 1, "title": "x", "description": "clean"},
        "project": {"path_with_namespace": "acme/widgets"},
        "user": {"username": "octo-dev"},
    }
    assert parse_merge_request(payload).author == "octo-dev"


def test_verify_shared_token_via_connector():
    conn = GitLabConnector(secret=_TOKEN)
    body = _body("merge_request_event.json")
    assert conn.verify(headers={"X-Gitlab-Token": _TOKEN}, body=body) is True
    assert conn.verify(headers={"X-Gitlab-Token": "wrong"}, body=body) is False
    assert conn.verify(headers={}, body=body) is False  # missing header -> fail closed


def test_verify_shared_token_helper_rejects_blank_and_mismatch():
    verify_shared_token(header_token=_TOKEN, secret=_TOKEN)  # match -> no raise
    with pytest.raises(WebhookVerificationError):
        verify_shared_token(header_token="", secret=_TOKEN)  # blank header
    with pytest.raises(WebhookVerificationError):
        verify_shared_token(header_token="x", secret=_TOKEN)  # mismatch
    with pytest.raises(WebhookVerificationError):
        verify_shared_token(header_token=_TOKEN, secret="")  # no secret configured


def test_verify_error_never_contains_token_or_secret():
    # advisory [security][LOW]: the raised message must not echo the value.
    try:
        verify_shared_token(header_token="leaky-token-value", secret="the-real-secret")
    except WebhookVerificationError as exc:
        assert "leaky-token-value" not in str(exc)
        assert "the-real-secret" not in str(exc)


def test_normalize_event_dispatches_on_object_kind():
    conn = GitLabConnector(secret=_TOKEN)
    headers = {"X-Gitlab-Token": _TOKEN}
    obs = conn.normalize_event(headers=headers, body=_body("merge_request_event.json"))
    assert len(obs) == 1 and obs[0].source_ref.source_id == "gitlab"
    # unknown object_kind -> no Observation
    unknown = json.dumps({"object_kind": "pipeline", "object_attributes": {}}).encode("utf-8")
    assert conn.normalize_event(headers=headers, body=unknown) == []


def test_normalize_event_bad_token_emits_nothing():
    conn = GitLabConnector(secret=_TOKEN)
    out = conn.normalize_event(
        headers={"X-Gitlab-Token": "wrong"}, body=_body("issue_event.json")
    )
    assert out == []


def test_normalize_event_dedup_drops_replay():
    dedup = DeliveryDedupCache()
    conn = GitLabConnector(secret=_TOKEN, dedup=dedup)
    headers = {"X-Gitlab-Token": _TOKEN, "X-Gitlab-Event-UUID": "uuid-1"}
    body = _body("merge_request_event.json")
    assert len(conn.normalize_event(headers=headers, body=body)) == 1
    assert conn.normalize_event(headers=headers, body=body) == []  # replay dropped


def test_normalize_event_dedup_uuid_less_replay_collapses():
    # purple-team GITLAB-002: a UUID-less replay must still dedup via the body-hash fallback.
    dedup = DeliveryDedupCache()
    conn = GitLabConnector(secret=_TOKEN, dedup=dedup)
    headers = {"X-Gitlab-Token": _TOKEN}  # no X-Gitlab-Event-UUID
    body = _body("issue_event.json")
    assert len(conn.normalize_event(headers=headers, body=body)) == 1
    assert conn.normalize_event(headers=headers, body=body) == []  # id-less replay collapses to one


def test_parse_truthy_non_dict_nested_containers_do_not_crash():
    # purple-team GITLAB-001: a truthy non-dict object_attributes/project/user normalizes, not crashes.
    payload = {"object_kind": "issue", "object_attributes": "oops", "project": "nope", "user": 7}
    obs = parse_issue(payload)  # must not raise
    assert obs.excerpt == "gitlab-issue" and obs.author == ""
    conn = GitLabConnector(secret=_TOKEN)
    body = json.dumps(payload).encode("utf-8")
    out = conn.normalize_event(headers={"X-Gitlab-Token": _TOKEN}, body=body)  # full path
    assert len(out) == 1 and out[0].source_ref.source_id == "gitlab"
