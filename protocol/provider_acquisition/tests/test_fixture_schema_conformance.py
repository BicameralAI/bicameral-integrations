"""Schema conformance tests for provider acquisition golden fixtures.

Validates that all golden descriptor and item-envelope fixtures conform to the
provisional alpha schemas from BicameralAI/bicameral-bot#462.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SCHEMAS_DIR = _ROOT / "schemas"
_FIXTURES_DIR = _ROOT / "fixtures"
_DESCRIPTOR_DIR = _FIXTURES_DIR / "descriptors"
_ITEMS_DIR = _FIXTURES_DIR / "items"

_DESCRIPTOR_SCHEMA_PATH = _SCHEMAS_DIR / "provider-resource-descriptor.schema.json"
_ITEM_SCHEMA_PATH = _SCHEMAS_DIR / "provider-item-envelope.schema.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _descriptor_fixtures() -> list[Path]:
    return sorted(_DESCRIPTOR_DIR.glob("*.json"))


def _item_fixtures() -> list[Path]:
    return sorted(_ITEMS_DIR.glob("*.json"))


# ---------------------------------------------------------------------------
# Schema validation using jsonschema (stdlib-only fallback if unavailable)
# ---------------------------------------------------------------------------

try:
    from jsonschema import Draft7Validator  # type: ignore[import-untyped]

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


def _validate_against_schema(instance: dict, schema: dict) -> list[str]:
    """Validate instance against JSON Schema draft-07. Returns error messages."""
    if _HAS_JSONSCHEMA:
        validator = Draft7Validator(schema)
        return [e.message for e in validator.iter_errors(instance)]
    # Fallback: check required fields only (stdlib-only minimal validation).
    errors: list[str] = []
    for field in schema.get("required", []):
        if field not in instance:
            errors.append(f"required field missing: {field}")
    return errors


# ---------------------------------------------------------------------------
# Descriptor conformance
# ---------------------------------------------------------------------------


class TestDescriptorSchemaConformance:
    """All descriptor fixtures must conform to ProviderResourceDescriptor schema."""

    @pytest.fixture(autouse=True)
    def _load_schema(self) -> None:
        self.schema = _load_json(_DESCRIPTOR_SCHEMA_PATH)

    @pytest.mark.parametrize(
        "fixture_path",
        _descriptor_fixtures(),
        ids=[p.stem for p in _descriptor_fixtures()],
    )
    def test_descriptor_conforms_to_schema(self, fixture_path: Path) -> None:
        fixture = _load_json(fixture_path)
        # Strip underscore-prefixed metadata keys (comments, boundary notes)
        data = {k: v for k, v in fixture.items() if not k.startswith("_")}
        errors = _validate_against_schema(data, self.schema)
        assert not errors, f"{fixture_path.name}: {errors}"

    @pytest.mark.parametrize(
        "fixture_path",
        _descriptor_fixtures(),
        ids=[p.stem for p in _descriptor_fixtures()],
    )
    def test_descriptor_has_required_fields(self, fixture_path: Path) -> None:
        fixture = _load_json(fixture_path)
        required = {
            "provider",
            "resource_id",
            "display_name",
            "resource_type",
            "captured_at",
        }
        missing = required - set(fixture.keys())
        assert not missing, f"{fixture_path.name} missing required fields: {missing}"

    @pytest.mark.parametrize(
        "fixture_path",
        _descriptor_fixtures(),
        ids=[p.stem for p in _descriptor_fixtures()],
    )
    def test_descriptor_capabilities_valid(self, fixture_path: Path) -> None:
        fixture = _load_json(fixture_path)
        valid_caps = {"list", "read", "search", "watch", "incremental_fetch"}
        caps = fixture.get("capabilities", [])
        for cap in caps:
            assert cap in valid_caps, f"{fixture_path.name}: invalid capability '{cap}'"

    @pytest.mark.parametrize(
        "fixture_path",
        _descriptor_fixtures(),
        ids=[p.stem for p in _descriptor_fixtures()],
    )
    def test_descriptor_permission_valid(self, fixture_path: Path) -> None:
        fixture = _load_json(fixture_path)
        valid_perms = {"granted", "unknown", "action_needed", "denied", None}
        perm = fixture.get("permission")
        assert perm in valid_perms, f"{fixture_path.name}: invalid permission '{perm}'"


# ---------------------------------------------------------------------------
# Item envelope conformance
# ---------------------------------------------------------------------------


class TestItemEnvelopeSchemaConformance:
    """All item fixtures must conform to ProviderItemEnvelope schema."""

    @pytest.fixture(autouse=True)
    def _load_schema(self) -> None:
        self.schema = _load_json(_ITEM_SCHEMA_PATH)

    @pytest.mark.parametrize(
        "fixture_path",
        _item_fixtures(),
        ids=[p.stem for p in _item_fixtures()],
    )
    def test_item_conforms_to_schema(self, fixture_path: Path) -> None:
        fixture = _load_json(fixture_path)
        data = {k: v for k, v in fixture.items() if not k.startswith("_")}
        errors = _validate_against_schema(data, self.schema)
        assert not errors, f"{fixture_path.name}: {errors}"

    @pytest.mark.parametrize(
        "fixture_path",
        _item_fixtures(),
        ids=[p.stem for p in _item_fixtures()],
    )
    def test_item_has_required_fields(self, fixture_path: Path) -> None:
        fixture = _load_json(fixture_path)
        required = {
            "provider",
            "resource_id",
            "item_id",
            "item_type",
            "content",
            "fetched_at",
        }
        missing = required - set(fixture.keys())
        assert not missing, f"{fixture_path.name} missing required fields: {missing}"


# ---------------------------------------------------------------------------
# Coverage assertions — ensure expected fixture breadth
# ---------------------------------------------------------------------------


class TestFixtureCoverage:
    """Ensure golden fixtures cover the expected provider alpha paths."""

    def test_descriptor_providers_covered(self) -> None:
        providers = set()
        for f in _descriptor_fixtures():
            data = _load_json(f)
            providers.add(data.get("provider"))
        assert "linear" in providers, "Missing Linear descriptor fixtures"
        assert "google_drive" in providers, "Missing Google Drive descriptor fixtures"
        assert "github" in providers, "Missing GitHub descriptor fixtures"

    def test_item_providers_covered(self) -> None:
        providers = set()
        for f in _item_fixtures():
            data = _load_json(f)
            providers.add(data.get("provider"))
        assert "linear" in providers, "Missing Linear item fixtures"
        # At least one of github or google_drive
        assert providers & {"github", "google_drive"}, (
            "Missing GitHub or Google Drive item fixtures"
        )

    def test_permission_states_covered(self) -> None:
        states: set[str | None] = set()
        for f in _descriptor_fixtures():
            data = _load_json(f)
            states.add(data.get("permission"))
        assert "granted" in states, "No granted-permission fixture"
        assert "action_needed" in states, "No action_needed-permission fixture"
        assert "denied" in states, "No denied-permission fixture"
