# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""Tests for the fixture-backed discovery emitter stub.

Validates that:
- Stub satisfies the DiscoveryConnector contract for list/get/validate/fetch.
- Stub outputs conform to the provisional bot schema from bot#462.
- Stub outputs reuse the golden fixtures from #177.
- Typed permission/action-needed outcomes are covered.
- create_provider_resource is absent from the discovery surface.
- No live provider credentials are needed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from protocol.provider_acquisition.stub import FixtureDiscoveryStub
from protocol.provider_acquisition.types import (
    DiscoveryErrorKind,
    DiscoveryOutcome,
    PermissionState,
    ProviderItemEnvelope,
    ProviderResourceDescriptor,
)

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"

try:
    from jsonschema import Draft7Validator  # type: ignore[import-untyped]

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


def _load_schema(name: str) -> dict:
    return json.loads((_SCHEMAS_DIR / name).read_text(encoding="utf-8"))


def _descriptor_to_dict(d: ProviderResourceDescriptor) -> dict:
    """Serialize a descriptor to a dict matching the JSON schema shape."""
    result: dict = {
        "provider": d.provider,
        "resource_id": d.resource_id,
        "display_name": d.display_name,
        "resource_type": d.resource_type,
        "captured_at": d.captured_at,
    }
    if d.uri is not None:
        result["uri"] = d.uri
    if d.capabilities:
        result["capabilities"] = list(d.capabilities)
    if d.permission is not None:
        result["permission"] = d.permission.value
    if d.freshness is not None:
        result["freshness"] = {
            k: v
            for k, v in {
                "last_modified": d.freshness.last_modified,
                "etag": d.freshness.etag,
                "item_count": d.freshness.item_count,
            }.items()
            if v is not None
        }
    if d.provider_metadata:
        result["provider_metadata"] = d.provider_metadata
    return result


def _item_to_dict(item: ProviderItemEnvelope) -> dict:
    """Serialize an item envelope to a dict matching the JSON schema shape."""
    result: dict = {
        "provider": item.provider,
        "resource_id": item.resource_id,
        "item_id": item.item_id,
        "item_type": item.item_type,
        "content": item.content,
        "fetched_at": item.fetched_at,
    }
    if item.title is not None:
        result["title"] = item.title
    if item.uri is not None:
        result["uri"] = item.uri
    if item.content_hash is not None:
        result["content_hash"] = item.content_hash
    if item.freshness is not None:
        result["freshness"] = {
            k: v
            for k, v in {
                "last_modified": item.freshness.last_modified,
                "etag": item.freshness.etag,
                "item_count": item.freshness.item_count,
            }.items()
            if v is not None
        }
    if item.provider_metadata:
        result["provider_metadata"] = item.provider_metadata
    return result


# ---------------------------------------------------------------------------
# Fixture: shared stub instance
# ---------------------------------------------------------------------------


@pytest.fixture()
def stub() -> FixtureDiscoveryStub:
    return FixtureDiscoveryStub()


# ---------------------------------------------------------------------------
# Contract shape: list_resources
# ---------------------------------------------------------------------------


class TestListResources:
    def test_returns_discovery_outcome(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.list_resources(config={})
        assert isinstance(result, DiscoveryOutcome)
        assert result.ok

    def test_returns_descriptors(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.list_resources(config={})
        assert result.value is not None
        assert len(result.value) > 0
        for desc in result.value:
            assert isinstance(desc, ProviderResourceDescriptor)

    def test_filter_by_provider(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.list_resources(config={"provider": "github"})
        assert result.ok
        assert result.value is not None
        for desc in result.value:
            assert desc.provider == "github"

    def test_filter_unknown_provider_returns_empty(
        self, stub: FixtureDiscoveryStub
    ) -> None:
        result = stub.list_resources(config={"provider": "nonexistent"})
        assert result.ok
        assert result.value == []

    @pytest.mark.skipif(not _HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_descriptors_conform_to_schema(self, stub: FixtureDiscoveryStub) -> None:
        schema = _load_schema("provider-resource-descriptor.schema.json")
        validator = Draft7Validator(schema)
        result = stub.list_resources(config={})
        assert result.value is not None
        for desc in result.value:
            data = _descriptor_to_dict(desc)
            errors = [e.message for e in validator.iter_errors(data)]
            assert not errors, f"{desc.resource_id}: {errors}"


# ---------------------------------------------------------------------------
# Contract shape: get_resource
# ---------------------------------------------------------------------------


class TestGetResource:
    def test_get_existing_resource(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.get_resource(config={}, resource_id="example-org/example-repo")
        assert result.ok
        assert result.value is not None
        assert result.value.provider == "github"
        assert result.value.resource_type == "repository"

    def test_get_missing_resource(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.get_resource(config={}, resource_id="does-not-exist")
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.NOT_FOUND

    def test_get_denied_resource(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.get_resource(
            config={}, resource_id="private-org/internal-tooling"
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PERMISSION_DENIED
        assert result.error.permission_state == PermissionState.DENIED

    def test_get_action_needed_resource(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.get_resource(config={}, resource_id="drive_0BPyyyyyyyyyyyyyy")
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.ACTION_NEEDED
        assert result.error.permission_state == PermissionState.ACTION_NEEDED
        assert result.error.action_hint is not None


# ---------------------------------------------------------------------------
# Contract shape: validate_resource_access
# ---------------------------------------------------------------------------


class TestValidateResourceAccess:
    def test_validate_granted(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.validate_resource_access(
            config={}, resource_id="example-org/example-repo"
        )
        assert result.ok
        assert result.value is not None
        assert result.value.permission == PermissionState.GRANTED

    def test_validate_denied(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.validate_resource_access(
            config={}, resource_id="private-org/internal-tooling"
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PERMISSION_DENIED

    def test_validate_action_needed(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.validate_resource_access(
            config={}, resource_id="drive_0BPyyyyyyyyyyyyyy"
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.ACTION_NEEDED

    def test_validate_not_found(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.validate_resource_access(config={}, resource_id="nope")
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.NOT_FOUND


# ---------------------------------------------------------------------------
# Contract shape: fetch_provider_item
# ---------------------------------------------------------------------------


class TestFetchProviderItem:
    def test_fetch_existing_item(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.fetch_provider_item(
            config={},
            resource_id="example-org/example-repo/issues",
            item_id="issue-42",
        )
        assert result.ok
        assert result.value is not None
        assert isinstance(result.value, ProviderItemEnvelope)
        assert result.value.provider == "github"
        assert result.value.content  # non-empty screened content

    def test_fetch_missing_item(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.fetch_provider_item(
            config={},
            resource_id="example-org/example-repo/issues",
            item_id="nonexistent",
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.NOT_FOUND

    @pytest.mark.skipif(not _HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_items_conform_to_schema(self, stub: FixtureDiscoveryStub) -> None:
        schema = _load_schema("provider-item-envelope.schema.json")
        validator = Draft7Validator(schema)
        all_result = stub.list_resources(config={})
        assert all_result.value is not None
        for desc in all_result.value:
            for item in stub._items:
                if item.resource_id.startswith(desc.resource_id.split("/")[0]):
                    data = _item_to_dict(item)
                    errors = [e.message for e in validator.iter_errors(data)]
                    assert not errors, f"{item.item_id}: {errors}"


# ---------------------------------------------------------------------------
# create_provider_resource is absent
# ---------------------------------------------------------------------------


class TestEgressExclusion:
    def test_no_create_provider_resource_method(
        self, stub: FixtureDiscoveryStub
    ) -> None:
        assert not hasattr(stub, "create_provider_resource"), (
            "create_provider_resource must not exist on the discovery surface; "
            "provider writes belong to egress / proposed-action territory"
        )


# ---------------------------------------------------------------------------
# Permission / action-needed outcome coverage
# ---------------------------------------------------------------------------


class TestPermissionOutcomeCoverage:
    def test_all_permission_states_reachable(self, stub: FixtureDiscoveryStub) -> None:
        """The stub must exercise granted, denied, and action_needed paths."""
        result = stub.list_resources(config={})
        assert result.value is not None
        states = {d.permission for d in result.value if d.permission is not None}
        assert PermissionState.GRANTED in states
        assert PermissionState.DENIED in states
        assert PermissionState.ACTION_NEEDED in states

    def test_denied_returns_error_with_hint(self, stub: FixtureDiscoveryStub) -> None:
        result = stub.get_resource(
            config={}, resource_id="private-org/internal-tooling"
        )
        assert result.error is not None
        assert result.error.permission_state == PermissionState.DENIED

    def test_action_needed_returns_error_with_hint(
        self, stub: FixtureDiscoveryStub
    ) -> None:
        result = stub.get_resource(config={}, resource_id="drive_0BPyyyyyyyyyyyyyy")
        assert result.error is not None
        assert result.error.action_hint is not None


# ---------------------------------------------------------------------------
# No live credentials required
# ---------------------------------------------------------------------------


class TestNoLiveCredentials:
    def test_stub_init_needs_no_credentials(self) -> None:
        stub = FixtureDiscoveryStub()
        assert stub.source_id == "fixture-discovery-stub"

    def test_all_operations_work_offline(self) -> None:
        stub = FixtureDiscoveryStub()
        assert stub.list_resources(config={}).ok
        assert stub.get_resource(config={}, resource_id="example-org/example-repo").ok
        assert stub.validate_resource_access(
            config={}, resource_id="example-org/example-repo"
        ).ok
        assert stub.fetch_provider_item(
            config={},
            resource_id="example-org/example-repo/issues",
            item_id="issue-42",
        ).ok
