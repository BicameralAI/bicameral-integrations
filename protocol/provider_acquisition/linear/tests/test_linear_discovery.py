# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""Tests for the Linear GraphQL discovery connector (ADR-0017 alpha 3/3).

Validates, against recorded Linear GraphQL responses (no live credentials):
- list (teams/projects/issues) / get / validate / fetch (issue+comment) emit
  schema-conformant descriptors + items;
- GraphQL fail-closed: 200-with-errors is never success; rate-limit is HTTP 400;
- every error-taxonomy row returns the typed DiscoveryErrorKind / permission state;
- the API key comes from the reused SecretResolver in the RAW Authorization header
  (no Bearer), and never appears in an error;
- screening is fail-closed; create_provider_resource is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from protocol.provider_acquisition.linear import (
    LinearDiscoveryConnector,
    RecordedTransport,
)
from protocol.provider_acquisition.linear.auth import build_auth_headers
from protocol.provider_acquisition.linear.transport import LinearResponse, LinearTransport
from protocol.provider_acquisition.screening import DiscoveryScreenError, screen_descriptor
from protocol.provider_acquisition.types import (
    DiscoveryErrorKind,
    DiscoveryOutcome,
    PermissionState,
    ProviderItemEnvelope,
    ProviderResourceDescriptor,
)
from runtime.secrets import MappingSecretResolver, SecretResolver

_RECORDED_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "recorded" / "linear"
_SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"
_FIXED_CLOCK = "2026-06-23T00:00:00+00:00"
_KEY = "test-linear-api-key"
_TEAM = "team-uuid-plat-0001"
_PROJECT = "proj-uuid-q3-0001"
_ISSUE = "issue-uuid-204-0001"
_COMMENT = "comment-uuid-a1b2"

try:
    from jsonschema import Draft7Validator  # type: ignore[import-untyped]

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


def _connector(
    *, key: str = _KEY, transport: LinearTransport | None = None
) -> LinearDiscoveryConnector:
    return LinearDiscoveryConnector(
        transport=transport or RecordedTransport.from_dir(_RECORDED_DIR),
        secrets=MappingSecretResolver({"linear": key} if key else {}),
        clock=lambda: _FIXED_CLOCK,
    )


def _load_schema(name: str) -> dict:
    return json.loads((_SCHEMAS_DIR / name).read_text(encoding="utf-8"))


def _descriptor_to_dict(d: ProviderResourceDescriptor) -> dict:
    out: dict = {
        "provider": d.provider, "resource_id": d.resource_id, "display_name": d.display_name,
        "resource_type": d.resource_type, "captured_at": d.captured_at,
    }
    if d.uri is not None:
        out["uri"] = d.uri
    if d.capabilities:
        out["capabilities"] = list(d.capabilities)
    if d.permission is not None:
        out["permission"] = d.permission.value
    if d.parent is not None:
        out["parent"] = {
            k: v for k, v in {
                "resource_id": d.parent.resource_id, "display_name": d.parent.display_name,
            }.items() if v is not None
        }
    if d.freshness is not None:
        out["freshness"] = {
            k: v for k, v in {
                "last_modified": d.freshness.last_modified, "item_count": d.freshness.item_count,
            }.items() if v is not None
        }
    if d.provider_metadata:
        out["provider_metadata"] = d.provider_metadata
    return out


def _item_to_dict(i: ProviderItemEnvelope) -> dict:
    out: dict = {
        "provider": i.provider, "resource_id": i.resource_id, "item_id": i.item_id,
        "item_type": i.item_type, "content": i.content, "fetched_at": i.fetched_at,
    }
    for k, v in (("title", i.title), ("uri", i.uri), ("content_hash", i.content_hash)):
        if v is not None:
            out[k] = v
    if i.provider_metadata:
        out["provider_metadata"] = i.provider_metadata
    return out


# ---------------------------------------------------------------------------
# list_resources — teams / projects / issues hierarchy
# ---------------------------------------------------------------------------


class TestListResources:
    def test_lists_teams(self) -> None:
        result = _connector().list_resources(config={})
        assert result.ok and result.value is not None
        ids = {d.resource_id for d in result.value}
        assert f"team_{_TEAM}" in ids
        for d in result.value:
            assert d.resource_type == "team"
            assert d.parent is not None and d.parent.resource_id == "ws_acme"

    def test_lists_projects_under_team(self) -> None:
        result = _connector().list_resources(config={"team_id": _TEAM})
        assert result.ok and result.value is not None
        assert f"proj_{_PROJECT}" in {d.resource_id for d in result.value}
        for d in result.value:
            assert d.resource_type == "project"
            assert d.parent is not None and d.parent.resource_id == f"team_{_TEAM}"

    def test_lists_issues_under_project(self) -> None:
        result = _connector().list_resources(config={"project_id": _PROJECT})
        assert result.ok and result.value is not None
        assert f"issue_{_ISSUE}" in {d.resource_id for d in result.value}
        for d in result.value:
            assert d.resource_type == "issue"
            assert d.parent is not None and d.parent.resource_id == f"team_{_TEAM}"

    @pytest.mark.skipif(not _HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_descriptors_conform_to_schema(self) -> None:
        validator = Draft7Validator(_load_schema("provider-resource-descriptor.schema.json"))
        conn = _connector()
        descs = []
        descs += conn.list_resources(config={}).value or []
        descs += conn.list_resources(config={"team_id": _TEAM}).value or []
        descs += conn.list_resources(config={"project_id": _PROJECT}).value or []
        for desc in descs:
            errors = [e.message for e in validator.iter_errors(_descriptor_to_dict(desc))]
            assert not errors, f"{desc.resource_id}: {errors}"


# ---------------------------------------------------------------------------
# get / validate + GraphQL error taxonomy
# ---------------------------------------------------------------------------


class TestGetAndTaxonomy:
    def test_get_workspace(self) -> None:
        result = _connector().get_resource(config={}, resource_id="ws_acme")
        assert result.ok and result.value is not None
        assert result.value.resource_type == "workspace"

    def test_get_team(self) -> None:
        result = _connector().get_resource(config={}, resource_id=f"team_{_TEAM}")
        assert result.ok and result.value is not None
        assert result.value.resource_type == "team"
        assert result.value.permission == PermissionState.GRANTED

    def test_validate_granted(self) -> None:
        result = _connector().validate_resource_access(config={}, resource_id=f"team_{_TEAM}")
        assert result.ok and result.value is not None
        assert result.value.permission == PermissionState.GRANTED

    def test_get_project_and_issue(self) -> None:
        proj = _connector().get_resource(config={}, resource_id=f"proj_{_PROJECT}")
        issue = _connector().get_resource(config={}, resource_id=f"issue_{_ISSUE}")
        assert proj.ok and proj.value is not None and proj.value.resource_type == "project"
        assert issue.ok and issue.value is not None and issue.value.resource_type == "issue"

    def test_auth_error_is_action_needed(self) -> None:
        result = _connector().get_resource(config={}, resource_id="team_team-uuid-authfail")
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.ACTION_NEEDED
        assert result.error.permission_state == PermissionState.ACTION_NEEDED

    def test_forbidden_is_permission_denied(self) -> None:
        result = _connector().get_resource(config={}, resource_id="team_team-uuid-forbidden")
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PERMISSION_DENIED
        assert result.error.permission_state == PermissionState.DENIED

    def test_ratelimited_is_provider_error(self) -> None:
        result = _connector().get_resource(config={}, resource_id="team_team-uuid-ratelimited")
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PROVIDER_ERROR
        assert "rate limit" in result.error.message.lower()

    def test_null_node_is_not_found(self) -> None:
        result = _connector().get_resource(config={}, resource_id="team_team-uuid-null")
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.NOT_FOUND

    def test_unrouted_node_is_not_found(self) -> None:
        # The recorded transport returns a synthetic ENTITY_NOT_FOUND for an unrouted op.
        result = _connector().get_resource(config={}, resource_id="team_team-uuid-ghost")
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.NOT_FOUND

    def test_unsupported_resource_id(self) -> None:
        result = _connector().get_resource(config={}, resource_id="channel_123")
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.UNSUPPORTED

    def test_malformed_id_rejected(self) -> None:
        result = _connector().get_resource(config={}, resource_id="team_../../etc")
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.UNSUPPORTED


# ---------------------------------------------------------------------------
# auth / token-provider reuse
# ---------------------------------------------------------------------------


class TestAuth:
    def test_missing_key(self) -> None:
        result = _connector(key="").list_resources(config={})
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.ACTION_NEEDED

    def test_malformed_key_token_free(self) -> None:
        poisoned = "key\r\nInjected: 1"
        result = _connector(key=poisoned).list_resources(config={})
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.ACTION_NEEDED
        assert poisoned not in result.error.message
        assert poisoned not in (result.error.action_hint or "")

    def test_raw_authorization_no_bearer(self) -> None:
        headers, err = build_auth_headers(MappingSecretResolver({"linear": "mykey"}))
        assert err is None and headers is not None
        assert headers["Authorization"] == "mykey"
        assert not headers["Authorization"].startswith("Bearer")

    def test_token_provider_is_the_reused_secret_resolver(self) -> None:
        assert isinstance(MappingSecretResolver({"linear": _KEY}), SecretResolver)


# ---------------------------------------------------------------------------
# fetch_provider_item
# ---------------------------------------------------------------------------


class TestFetchProviderItem:
    def test_fetch_issue_item(self) -> None:
        result = _connector().fetch_provider_item(
            config={}, resource_id=f"team_{_TEAM}", item_id=f"issue_{_ISSUE}"
        )
        assert result.ok and result.value is not None
        assert isinstance(result.value, ProviderItemEnvelope)
        assert result.value.item_type == "issue"
        assert "advisory locks" in result.value.content  # parse_issue_node excerpt reused
        assert result.value.provider_metadata.get("identifier") == "PLAT-204"

    def test_fetch_comment_item(self) -> None:
        result = _connector().fetch_provider_item(
            config={}, resource_id=f"issue_{_ISSUE}", item_id=f"comment_{_COMMENT}"
        )
        assert result.ok and result.value is not None
        assert result.value.item_type == "comment"
        assert "advisory locks" in result.value.content
        assert result.value.provider_metadata.get("parent_issue_identifier") == "PLAT-204"

    def test_unsupported_item_kind(self) -> None:
        result = _connector().fetch_provider_item(
            config={}, resource_id=f"team_{_TEAM}", item_id="reaction_7"
        )
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.UNSUPPORTED

    def test_malformed_item_id_rejected(self) -> None:
        result = _connector().fetch_provider_item(
            config={}, resource_id=f"team_{_TEAM}", item_id="issue_../../x"
        )
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.UNSUPPORTED

    @pytest.mark.skipif(not _HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_items_conform_to_schema(self) -> None:
        validator = Draft7Validator(_load_schema("provider-item-envelope.schema.json"))
        conn = _connector()
        for resource_id, item_id in (
            (f"team_{_TEAM}", f"issue_{_ISSUE}"),
            (f"issue_{_ISSUE}", f"comment_{_COMMENT}"),
        ):
            result = conn.fetch_provider_item(config={}, resource_id=resource_id, item_id=item_id)
            assert result.value is not None
            errors = [e.message for e in validator.iter_errors(_item_to_dict(result.value))]
            assert not errors, f"{item_id}: {errors}"


# ---------------------------------------------------------------------------
# Screening + authority boundary
# ---------------------------------------------------------------------------


class TestScreeningAndBoundary:
    def test_screen_descriptor_rejects_secret(self) -> None:
        from protocol.provider_acquisition.linear import mapping

        secret_shaped = "AIzaSy" + "C" * 33
        team = {"id": _TEAM, "key": "PLAT", "name": secret_shaped}
        desc = mapping.map_team(team, ws_url_key="acme", ws_name="Acme Corp", captured_at=_FIXED_CLOCK)
        with pytest.raises(DiscoveryScreenError):
            screen_descriptor(desc)

    def test_connector_screens_poisoned_response(self) -> None:
        secret_shaped = "AIzaSy" + "D" * 33
        poisoned = LinearResponse(
            status=200,
            data={"team": {"id": _TEAM, "key": "PLAT", "name": secret_shaped,
                           "organization": {"urlKey": "acme", "name": "Acme Corp"}}},
        )

        class _OneShot:
            def execute(self, *, operation, query, variables=None):  # type: ignore[no-untyped-def]
                return poisoned

        result = _connector(transport=_OneShot()).get_resource(
            config={}, resource_id=f"team_{_TEAM}"
        )
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PROVIDER_ERROR
        assert secret_shaped not in result.error.message

    def test_no_create_provider_resource(self) -> None:
        assert not hasattr(_connector(), "create_provider_resource")

    def test_discovery_outcome_envelope_shape(self) -> None:
        assert isinstance(_connector().list_resources(config={}), DiscoveryOutcome)


def test_all_operations_offline() -> None:
    conn = _connector()
    assert conn.source_id == "linear"
    assert conn.list_resources(config={}).ok
    assert conn.list_resources(config={"team_id": _TEAM}).ok
    assert conn.get_resource(config={}, resource_id=f"team_{_TEAM}").ok
    assert conn.fetch_provider_item(
        config={}, resource_id=f"team_{_TEAM}", item_id=f"issue_{_ISSUE}"
    ).ok
