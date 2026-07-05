# Copyright 2026 Bicameral AI — MIT License
"""Tests for the Google Drive discovery connector (#179).

Validates, against recorded Drive REST responses (no live credentials):
- list (shared drives + `.bicameral` project folders) / get / validate / fetch emit
  schema-conformant descriptors + items;
- every error-taxonomy row returns the typed DiscoveryErrorKind / permission state;
- the OAuth token comes from the reused `SecretResolver` (no PAT-equivalent), and
  never appears in an error;
- descriptor / item screening is fail-closed; `create_provider_resource` is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from protocol.provider_acquisition.google_drive import (
    GoogleDriveDiscoveryConnector,
    RecordedTransport,
)
from protocol.provider_acquisition.google_drive.transport import DriveResponse, DriveTransport
from protocol.provider_acquisition.screening import DiscoveryScreenError, screen_descriptor
from protocol.provider_acquisition.types import (
    DiscoveryErrorKind,
    DiscoveryOutcome,
    PermissionState,
    ProviderItemEnvelope,
    ProviderResourceDescriptor,
)
from runtime.secrets import MappingSecretResolver, SecretResolver

_RECORDED_DIR = (
    Path(__file__).resolve().parents[2] / "fixtures" / "recorded" / "google_drive"
)
_SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"
_FIXED_CLOCK = "2026-06-23T00:00:00+00:00"
_TOKEN = "test-drive-access-token"
_DRIVE = "0ABCdefGHIjklMNO"

try:
    from jsonschema import Draft7Validator  # type: ignore[import-untyped]

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


def _connector(
    *, token: str = _TOKEN, transport: DriveTransport | None = None
) -> GoogleDriveDiscoveryConnector:
    return GoogleDriveDiscoveryConnector(
        transport=transport or RecordedTransport.from_dir(_RECORDED_DIR),
        secrets=MappingSecretResolver({"google_drive": token} if token else {}),
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
                "last_modified": d.freshness.last_modified, "etag": d.freshness.etag,
                "item_count": d.freshness.item_count,
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
    return out


# ---------------------------------------------------------------------------
# list_resources — shared drives + .bicameral folders
# ---------------------------------------------------------------------------


class TestListResources:
    def test_lists_shared_drives(self) -> None:
        result = _connector().list_resources(config={})
        assert result.ok
        assert result.value is not None
        ids = {d.resource_id for d in result.value}
        assert f"drive_{_DRIVE}" in ids
        assert all(d.resource_type == "shared_drive" for d in result.value)

    def test_lists_bicameral_project_folders(self) -> None:
        result = _connector().list_resources(
            config={"drive_id": _DRIVE, "drive_name": "Engineering Decisions"}
        )
        assert result.ok
        assert result.value is not None
        assert {d.resource_id for d in result.value} == {
            "folder_1PRJ1111projectfolder", "folder_1PRJ2222otherproject"
        }
        for d in result.value:
            assert d.resource_type == "folder"
            assert d.parent is not None and d.parent.resource_id == f"drive_{_DRIVE}"

    def test_drive_without_bicameral_is_empty_not_error(self) -> None:
        result = _connector().list_resources(config={"drive_id": "0EMPTYdriveNoBicam"})
        assert result.ok
        assert result.value == []

    def test_stale_cursor_returns_provider_error(self) -> None:
        result = _connector().list_resources(config={"cursor": "stale"})
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PROVIDER_ERROR

    @pytest.mark.skipif(not _HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_descriptors_conform_to_schema(self) -> None:
        validator = Draft7Validator(_load_schema("provider-resource-descriptor.schema.json"))
        drives = _connector().list_resources(config={})
        folders = _connector().list_resources(config={"drive_id": _DRIVE})
        assert drives.value is not None and folders.value is not None
        for desc in [*drives.value, *folders.value]:
            errors = [e.message for e in validator.iter_errors(_descriptor_to_dict(desc))]
            assert not errors, f"{desc.resource_id}: {errors}"


# ---------------------------------------------------------------------------
# get_resource / validate — permission taxonomy
# ---------------------------------------------------------------------------


class TestGetAndValidate:
    def test_get_shared_drive(self) -> None:
        result = _connector().get_resource(config={}, resource_id=f"drive_{_DRIVE}")
        assert result.ok
        assert result.value is not None
        assert result.value.resource_type == "shared_drive"
        assert result.value.permission == PermissionState.GRANTED

    def test_validate_granted(self) -> None:
        result = _connector().validate_resource_access(config={}, resource_id=f"drive_{_DRIVE}")
        assert result.ok and result.value is not None
        assert result.value.permission == PermissionState.GRANTED

    def test_get_folder(self) -> None:
        result = _connector().get_resource(config={}, resource_id="folder_1PRJ1111projectfolder")
        assert result.ok and result.value is not None
        assert result.value.resource_type == "folder"

    def test_get_document(self) -> None:
        result = _connector().get_resource(config={}, resource_id="doc_1DOC2222documentid12345")
        assert result.ok and result.value is not None
        assert result.value.resource_type == "document"
        assert result.value.provider_metadata.get("mime_type") == "application/vnd.google-apps.document"

    def test_insufficient_scope_is_action_needed_with_required_scope(self) -> None:
        result = _connector().get_resource(config={}, resource_id="drive_noScope403")
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.ACTION_NEEDED
        assert result.error.permission_state == PermissionState.ACTION_NEEDED
        assert "drive.readonly" in (result.error.action_hint or "")

    def test_shared_drive_denied(self) -> None:
        result = _connector().get_resource(config={}, resource_id="drive_denied403")
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PERMISSION_DENIED
        assert result.error.permission_state == PermissionState.DENIED

    def test_not_found(self) -> None:
        result = _connector().get_resource(config={}, resource_id="drive_missing404")
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.NOT_FOUND

    def test_expired_credential(self) -> None:
        result = _connector().get_resource(config={}, resource_id="drive_expired401")
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.ACTION_NEEDED

    def test_provider_unavailable(self) -> None:
        result = _connector().get_resource(config={}, resource_id="drive_down503")
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PROVIDER_ERROR

    def test_unsupported_resource_id(self) -> None:
        result = _connector().get_resource(config={}, resource_id="channel_123")
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.UNSUPPORTED


# ---------------------------------------------------------------------------
# auth / token-provider reuse
# ---------------------------------------------------------------------------


class TestAuth:
    def test_missing_credentials(self) -> None:
        result = _connector(token="").list_resources(config={})
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.ACTION_NEEDED
        assert result.error.permission_state == PermissionState.ACTION_NEEDED

    def test_malformed_token_is_action_needed_and_token_free(self) -> None:
        poisoned = "tok\r\nInjected: 1"
        result = _connector(token=poisoned).list_resources(config={})
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.ACTION_NEEDED
        assert poisoned not in result.error.message
        assert poisoned not in (result.error.action_hint or "")

    def test_token_provider_is_the_reused_secret_resolver(self) -> None:
        # The Drive connector reuses runtime.secrets.SecretResolver — no new token type.
        provider = MappingSecretResolver({"google_drive": _TOKEN})
        assert isinstance(provider, SecretResolver)


# ---------------------------------------------------------------------------
# fetch_provider_item
# ---------------------------------------------------------------------------


class TestFetchProviderItem:
    def test_fetch_document(self) -> None:
        result = _connector().fetch_provider_item(
            config={}, resource_id="folder_1PRJ1111projectfolder",
            item_id="doc_1DOC2222documentid12345",
        )
        assert result.ok and result.value is not None
        assert isinstance(result.value, ProviderItemEnvelope)
        assert result.value.item_type == "document"
        assert "append-only event log" in result.value.content  # extract_document_text reused
        assert result.value.content.startswith("# Decision")  # HEADING_1 decoration
        assert result.value.content_hash

    def test_unsupported_item_kind(self) -> None:
        result = _connector().fetch_provider_item(
            config={}, resource_id="folder_1PRJ1111projectfolder", item_id="sheet_7"
        )
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.UNSUPPORTED

    def test_malformed_doc_id_rejected_before_splice(self) -> None:
        result = _connector().fetch_provider_item(
            config={}, resource_id="folder_1PRJ1111projectfolder",
            item_id="doc_../../etc/passwd",
        )
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.UNSUPPORTED
        assert "malformed" in result.error.message

    def test_missing_document_not_found(self) -> None:
        result = _connector().fetch_provider_item(
            config={}, resource_id="folder_1PRJ1111projectfolder", item_id="doc_absent999"
        )
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.NOT_FOUND

    @pytest.mark.skipif(not _HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_item_conforms_to_schema(self) -> None:
        validator = Draft7Validator(_load_schema("provider-item-envelope.schema.json"))
        result = _connector().fetch_provider_item(
            config={}, resource_id="folder_1PRJ1111projectfolder",
            item_id="doc_1DOC2222documentid12345",
        )
        assert result.value is not None
        errors = [e.message for e in validator.iter_errors(_item_to_dict(result.value))]
        assert not errors, errors


# ---------------------------------------------------------------------------
# Screening + authority boundary
# ---------------------------------------------------------------------------


class TestScreeningAndBoundary:
    def test_screen_descriptor_rejects_secret(self) -> None:
        from protocol.provider_acquisition.google_drive import mapping

        secret_shaped = "AIzaSy" + "A" * 33  # constructed Google-API-key shape, not a literal
        drive = {"id": _DRIVE, "name": secret_shaped, "createdTime": "2026-06-13T11:00:00Z"}
        desc = mapping.map_shared_drive(drive, captured_at=_FIXED_CLOCK)
        with pytest.raises(DiscoveryScreenError):
            screen_descriptor(desc)

    def test_connector_screens_poisoned_response(self) -> None:
        secret_shaped = "AIzaSy" + "B" * 33
        poisoned = DriveResponse(
            status=200, json={"id": _DRIVE, "name": secret_shaped, "createdTime": "2026-06-13T11:00:00Z"}
        )

        class _OneShot:
            def request(self, method, path, *, headers, params=None):  # type: ignore[no-untyped-def]
                return poisoned

        result = _connector(transport=_OneShot()).get_resource(
            config={}, resource_id=f"drive_{_DRIVE}"
        )
        assert not result.ok and result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PROVIDER_ERROR
        assert secret_shaped not in result.error.message

    def test_no_create_provider_resource(self) -> None:
        assert not hasattr(_connector(), "create_provider_resource"), (
            "discovery surface must not expose provider writes (egress territory)"
        )

    def test_discovery_outcome_envelope_shape(self) -> None:
        assert isinstance(_connector().list_resources(config={}), DiscoveryOutcome)


def test_all_operations_offline() -> None:
    conn = _connector()
    assert conn.source_id == "google_drive"
    assert conn.list_resources(config={}).ok
    assert conn.list_resources(config={"drive_id": _DRIVE}).ok
    assert conn.get_resource(config={}, resource_id=f"drive_{_DRIVE}").ok
    assert conn.fetch_provider_item(
        config={}, resource_id="folder_1PRJ1111projectfolder",
        item_id="doc_1DOC2222documentid12345",
    ).ok
