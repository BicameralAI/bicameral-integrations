# Copyright 2026 Bicameral AI — MIT License
"""Tests for the GitHub App installation discovery connector (#180).

Validates, against recorded GitHub REST responses (no live credentials):
- list / get / validate / fetch emit schema-conformant descriptors + items;
- every error-taxonomy row returns the typed DiscoveryErrorKind / permission state;
- installation auth only — no PAT entry point, no create_provider_resource;
- descriptor / item screening is fail-closed;
- the installation token never appears in an error message.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from protocol.provider_acquisition.github import (
    GitHubDiscoveryConnector,
    InstallationTokenProvider,
    MappingInstallationTokenProvider,
    RecordedTransport,
)
from protocol.provider_acquisition.github.auth import (
    reject_control_chars,
    GitHubAuthError,
)
from protocol.provider_acquisition.github.transport import (
    GitHubResponse,
    GitHubTransport,
)
from protocol.provider_acquisition.screening import (
    DiscoveryScreenError,
    screen_descriptor,
)
from protocol.provider_acquisition.types import (
    DiscoveryErrorKind,
    DiscoveryOutcome,
    FreshnessMetadata,
    PermissionState,
    ProviderItemEnvelope,
    ProviderResourceDescriptor,
)

_RECORDED_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "recorded" / "github"
_SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"
_FIXED_CLOCK = "2026-06-23T00:00:00+00:00"
_INSTALL_ID = "inst-1"
# A non-secret-shaped placeholder; resolved like a brokered installation token.
_TOKEN = "test-installation-token"

try:
    from jsonschema import Draft7Validator  # type: ignore[import-untyped]

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


def _connector(
    *, tokens: dict[str, str] | None = None, transport: GitHubTransport | None = None
) -> GitHubDiscoveryConnector:
    return GitHubDiscoveryConnector(
        transport=transport or RecordedTransport.from_dir(_RECORDED_DIR),
        token_provider=MappingInstallationTokenProvider(
            tokens if tokens is not None else {_INSTALL_ID: _TOKEN}
        ),
        clock=lambda: _FIXED_CLOCK,
    )


def _config(**extra: object) -> dict[str, object]:
    return {"installation_id": _INSTALL_ID, **extra}


def _load_schema(name: str) -> dict:
    return json.loads((_SCHEMAS_DIR / name).read_text(encoding="utf-8"))


def _descriptor_to_dict(d: ProviderResourceDescriptor) -> dict:
    out: dict = {
        "provider": d.provider,
        "resource_id": d.resource_id,
        "display_name": d.display_name,
        "resource_type": d.resource_type,
        "captured_at": d.captured_at,
    }
    if d.uri is not None:
        out["uri"] = d.uri
    if d.capabilities:
        out["capabilities"] = list(d.capabilities)
    if d.permission is not None:
        out["permission"] = d.permission.value
    if d.freshness is not None:
        out["freshness"] = {
            k: v
            for k, v in {
                "last_modified": d.freshness.last_modified,
                "etag": d.freshness.etag,
                "item_count": d.freshness.item_count,
            }.items()
            if v is not None
        }
    if d.provider_metadata:
        out["provider_metadata"] = d.provider_metadata
    return out


def _item_to_dict(i: ProviderItemEnvelope) -> dict:
    out: dict = {
        "provider": i.provider,
        "resource_id": i.resource_id,
        "item_id": i.item_id,
        "item_type": i.item_type,
        "content": i.content,
        "fetched_at": i.fetched_at,
    }
    for key, val in (
        ("title", i.title),
        ("uri", i.uri),
        ("content_hash", i.content_hash),
    ):
        if val is not None:
            out[key] = val
    if i.provider_metadata:
        out["provider_metadata"] = i.provider_metadata
    return out


# ---------------------------------------------------------------------------
# list_resources
# ---------------------------------------------------------------------------


class TestListResources:
    def test_lists_installation_repositories(self) -> None:
        result = _connector().list_resources(config=_config())
        assert result.ok
        assert result.value is not None
        ids = {d.resource_id for d in result.value}
        assert "example-org/example-repo" in ids
        assert all(d.provider == "github" for d in result.value)
        assert all(d.resource_type == "repository" for d in result.value)

    def test_repository_capabilities_reflect_permissions(self) -> None:
        result = _connector().list_resources(config=_config())
        assert result.value is not None
        by_id = {d.resource_id: d for d in result.value}
        # push=true -> watch present; push=false -> watch absent.
        assert "watch" in by_id["example-org/example-repo"].capabilities
        assert "watch" not in by_id["example-org/docs-site"].capabilities

    def test_stale_cursor_returns_provider_error(self) -> None:
        result = _connector().list_resources(config=_config(cursor="stale"))
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PROVIDER_ERROR

    @pytest.mark.skipif(not _HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_descriptors_conform_to_schema(self) -> None:
        validator = Draft7Validator(
            _load_schema("provider-resource-descriptor.schema.json")
        )
        result = _connector().list_resources(config=_config())
        assert result.value is not None
        for desc in result.value:
            errors = [
                e.message for e in validator.iter_errors(_descriptor_to_dict(desc))
            ]
            assert not errors, f"{desc.resource_id}: {errors}"


# ---------------------------------------------------------------------------
# get_resource / validate_resource_access — permission taxonomy
# ---------------------------------------------------------------------------


class TestGetAndValidate:
    def test_get_repository(self) -> None:
        result = _connector().get_resource(
            config=_config(), resource_id="example-org/example-repo"
        )
        assert result.ok
        assert result.value is not None
        assert result.value.resource_type == "repository"
        assert result.value.permission == PermissionState.GRANTED
        assert result.value.provider_metadata.get("default_branch") == "main"

    def test_validate_granted(self) -> None:
        result = _connector().validate_resource_access(
            config=_config(), resource_id="example-org/example-repo"
        )
        assert result.ok
        assert result.value is not None
        assert result.value.permission == PermissionState.GRANTED

    def test_denied_permission(self) -> None:
        result = _connector().get_resource(
            config=_config(), resource_id="private-org/internal-tooling"
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PERMISSION_DENIED
        assert result.error.permission_state == PermissionState.DENIED

    def test_not_found(self) -> None:
        result = _connector().get_resource(
            config=_config(), resource_id="missing-org/missing-repo"
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.NOT_FOUND

    def test_rate_limited(self) -> None:
        result = _connector().get_resource(
            config=_config(), resource_id="ratelimited-org/repo"
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PROVIDER_ERROR
        assert "rate limit" in result.error.message.lower()

    def test_expired_credential(self) -> None:
        result = _connector().get_resource(
            config=_config(), resource_id="expired-org/repo"
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.ACTION_NEEDED
        assert result.error.permission_state == PermissionState.ACTION_NEEDED

    def test_provider_unavailable(self) -> None:
        result = _connector().get_resource(
            config=_config(), resource_id="unavailable-org/repo"
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PROVIDER_ERROR


# ---------------------------------------------------------------------------
# auth / installation taxonomy
# ---------------------------------------------------------------------------


class TestInstallationAuth:
    def test_missing_installation_id(self) -> None:
        result = _connector().list_resources(config={})
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.ACTION_NEEDED
        assert "installation" in result.error.message.lower()

    def test_missing_credentials(self) -> None:
        # installation id present but the broker has no token.
        result = _connector(tokens={}).list_resources(config=_config())
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.ACTION_NEEDED
        assert result.error.permission_state == PermissionState.ACTION_NEEDED

    def test_malformed_token_is_action_needed_and_token_free(self) -> None:
        poisoned = "tok\r\nInjected: 1"
        result = _connector(tokens={_INSTALL_ID: poisoned}).list_resources(
            config=_config()
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.ACTION_NEEDED
        # The token value must never appear in the surfaced error.
        assert poisoned not in result.error.message
        assert (result.error.action_hint or "").find(poisoned) == -1

    def test_reject_control_chars_helper(self) -> None:
        reject_control_chars("token", "clean-token")  # no raise
        with pytest.raises(GitHubAuthError):
            reject_control_chars("token", "bad\ntoken")


# ---------------------------------------------------------------------------
# fetch_provider_item
# ---------------------------------------------------------------------------


class TestFetchProviderItem:
    def test_fetch_issue(self) -> None:
        result = _connector().fetch_provider_item(
            config=_config(),
            resource_id="example-org/example-repo/issues",
            item_id="issue-42",
        )
        assert result.ok
        assert result.value is not None
        assert isinstance(result.value, ProviderItemEnvelope)
        assert result.value.item_type == "issue"
        assert result.value.content
        assert result.value.content_hash
        assert result.value.provider_metadata.get("number") == 42

    def test_fetch_pull_request(self) -> None:
        result = _connector().fetch_provider_item(
            config=_config(),
            resource_id="example-org/example-repo/pulls",
            item_id="pr-92",
        )
        assert result.ok
        assert result.value is not None
        assert result.value.item_type == "pull_request"
        assert result.value.provider_metadata.get("merged") is True

    def test_fetch_file_content(self) -> None:
        result = _connector().fetch_provider_item(
            config=_config(),
            resource_id="example-org/example-repo/contents",
            item_id="file-README.md",
        )
        assert result.ok
        assert result.value is not None
        assert isinstance(result.value, ProviderItemEnvelope)
        assert result.value.item_type == "file"
        assert result.value.item_id == "file-README.md"
        assert "Example Repo" in result.value.content
        assert result.value.content_hash
        assert result.value.provider_metadata.get("path") == "README.md"
        assert result.value.provider_metadata.get("sha") == "abc123def456789"
        assert result.value.provider_metadata.get("size") == 142

    def test_fetch_missing_file_not_found(self) -> None:
        result = _connector().fetch_provider_item(
            config=_config(),
            resource_id="example-org/example-repo/contents",
            item_id="file-nonexistent.txt",
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.NOT_FOUND

    def test_unsupported_item_kind(self) -> None:
        result = _connector().fetch_provider_item(
            config=_config(),
            resource_id="example-org/example-repo/issues",
            item_id="comment-7",
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.UNSUPPORTED

    def test_fetch_missing_item_not_found(self) -> None:
        result = _connector().fetch_provider_item(
            config=_config(),
            resource_id="example-org/example-repo/issues",
            item_id="issue-999",
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.NOT_FOUND

    @pytest.mark.skipif(not _HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_items_conform_to_schema(self) -> None:
        validator = Draft7Validator(_load_schema("provider-item-envelope.schema.json"))
        conn = _connector()
        for resource_id, item_id in (
            ("example-org/example-repo/issues", "issue-42"),
            ("example-org/example-repo/pulls", "pr-92"),
            ("example-org/example-repo/contents", "file-README.md"),
        ):
            result = conn.fetch_provider_item(
                config=_config(), resource_id=resource_id, item_id=item_id
            )
            assert result.value is not None
            errors = [
                e.message for e in validator.iter_errors(_item_to_dict(result.value))
            ]
            assert not errors, f"{item_id}: {errors}"


# ---------------------------------------------------------------------------
# Screening (fail-closed)
# ---------------------------------------------------------------------------


class TestScreening:
    def test_screen_descriptor_rejects_secret(self) -> None:
        secret_shaped = "ghp_" + "A" * 36  # constructed, not a literal in source
        descriptor = ProviderResourceDescriptor(
            provider="github",
            resource_id="example-org/example-repo",
            display_name="example-repo",
            resource_type="repository",
            captured_at=_FIXED_CLOCK,
            provider_metadata={"leaked": secret_shaped},
        )
        with pytest.raises(DiscoveryScreenError):
            screen_descriptor(descriptor)

    def test_connector_screens_poisoned_response(self) -> None:
        secret_shaped = "ghp_" + "B" * 36
        poisoned = GitHubResponse(
            status=200,
            json={
                "full_name": "example-org/example-repo",
                "name": "example-repo",
                "html_url": "https://github.com/example-org/example-repo",
                "language": secret_shaped,
                "permissions": {"pull": True},
            },
        )

        class _OneShot:
            def request(
                self, method: str, path: str, *, headers: dict[str, str]
            ) -> GitHubResponse:
                return poisoned

        result = _connector(transport=_OneShot()).get_resource(
            config=_config(), resource_id="example-org/example-repo"
        )
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == DiscoveryErrorKind.PROVIDER_ERROR
        assert secret_shaped not in result.error.message


# ---------------------------------------------------------------------------
# Authority boundary / installation-only
# ---------------------------------------------------------------------------


class TestAuthorityBoundary:
    def test_no_create_provider_resource(self) -> None:
        conn = _connector()
        assert not hasattr(conn, "create_provider_resource"), (
            "discovery surface must not expose provider writes (egress territory)"
        )

    def test_no_pat_entry_point(self) -> None:
        # The token provider exposes installation_token ONLY — no PAT/import path.
        provider = MappingInstallationTokenProvider({})
        assert hasattr(provider, "installation_token")
        for forbidden in ("pat", "personal_access_token", "import_token", "set_token"):
            assert not hasattr(provider, forbidden)

    def test_provider_satisfies_protocol(self) -> None:
        provider = MappingInstallationTokenProvider({_INSTALL_ID: _TOKEN})
        assert isinstance(provider, InstallationTokenProvider)

    def test_discovery_outcome_envelope_shape(self) -> None:
        result = _connector().list_resources(config=_config())
        assert isinstance(result, DiscoveryOutcome)


# ---------------------------------------------------------------------------
# No live credentials needed
# ---------------------------------------------------------------------------


def test_all_operations_offline() -> None:
    conn = _connector()
    assert conn.source_id == "github"
    assert conn.list_resources(config=_config()).ok
    assert conn.get_resource(
        config=_config(), resource_id="example-org/example-repo"
    ).ok
    assert conn.fetch_provider_item(
        config=_config(),
        resource_id="example-org/example-repo/issues",
        item_id="issue-42",
    ).ok
    assert conn.fetch_provider_item(
        config=_config(),
        resource_id="example-org/example-repo/contents",
        item_id="file-README.md",
    ).ok


def test_freshness_helper_roundtrip() -> None:
    # Guard the mapping helper used across descriptors/items.
    fm = FreshnessMetadata(last_modified="2026-06-14T20:00:00Z")
    assert fm.last_modified == "2026-06-14T20:00:00Z"
