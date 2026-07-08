# SPDX-License-Identifier: MIT
"""Behavior tests for the projection profile descriptor contract (ADR-0019).

Tests both the structural/semantic validator AND the golden conformance fixtures
(canonical decision + profile -> rendered payload + receipt-mapping; offline only).
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import validate_projection_profile as vpp  # noqa: E402

_REPO = Path(__file__).resolve().parents[2]
_CONNECTORS = _REPO / "connectors"
_SCHEMA = json.loads(
    (_CONNECTORS / "_schema" / "projection-profile.schema.json").read_text(
        encoding="utf-8"
    )
)


def _linear_profiles() -> list[dict[str, object]]:
    return json.loads(
        (_CONNECTORS / "linear" / "projection.json").read_text(encoding="utf-8")
    )


def _first_profile() -> dict[str, object]:
    return copy.deepcopy(_linear_profiles()[0])


# --- exemplar validation ---


def test_exemplar_profiles_valid():
    assert vpp.validate_all() == {}


def test_linear_declares_three_profiles():
    profiles = _linear_profiles()
    assert len(profiles) == 3
    ids = {p["profile_id"] for p in profiles}
    assert ids == {
        "linear.issue.summary.v1",
        "linear.issue.work_item.v1",
        "linear.comment.status.v1",
    }


def test_all_profiles_require_canonical_ref():
    for p in _linear_profiles():
        assert p["required_canonical_ref"] is True


def test_all_profiles_require_receipt():
    for p in _linear_profiles():
        assert p["required_receipt"] is True


# --- structural checks ---


def test_rejects_unknown_key_fail_closed():
    p = _first_profile()
    p["surprise"] = 1
    assert any("unknown key" in e for e in vpp._check(p, _SCHEMA, "x"))


def test_rejects_nested_unknown_key():
    p = _first_profile()
    rc = p.get("rendering_constraints")
    assert isinstance(rc, dict)
    rc["surprise"] = 1
    errs = vpp._check(p, _SCHEMA, "x")
    assert any("unknown key" in e for e in errs)


def test_rejects_wrong_scalar_type():
    p = _first_profile()
    p["required_canonical_ref"] = "yes"
    assert any("expected boolean" in e for e in vpp._check(p, _SCHEMA, "x"))


def test_rejects_out_of_enum_mutation():
    p = _first_profile()
    p["mutation_capability"] = "delete"
    assert any("not in" in e for e in vpp._check(p, _SCHEMA, "x"))


def test_rejects_missing_required_key():
    p = _first_profile()
    del p["profile_id"]
    assert any("missing required key" in e for e in vpp._check(p, _SCHEMA, "x"))


# --- semantic / drift-guard checks ---


def test_rejects_profile_id_not_matching_target():
    p = _first_profile()
    p["profile_id"] = "github.issue.summary.v1"
    errs = vpp._semantic(p, "linear")
    assert any("target prefix" in e for e in errs)


def test_rejects_profile_id_not_matching_surface():
    p = _first_profile()
    p["profile_id"] = "linear.comment.summary.v1"
    errs = vpp._semantic(p, "linear")
    assert any("surface" in e for e in errs)


def test_rejects_target_not_matching_folder():
    p = _first_profile()
    p["target_system"] = "github"
    errs = vpp._semantic(p, "linear")
    assert any("connector folder" in e for e in errs)


def test_rejects_canonical_ref_false():
    p = _first_profile()
    p["required_canonical_ref"] = False
    errs = vpp._semantic(p, "linear")
    assert any("required_canonical_ref must be true" in e for e in errs)


def test_rejects_receipt_false():
    p = _first_profile()
    p["required_receipt"] = False
    errs = vpp._semantic(p, "linear")
    assert any("required_receipt must be true" in e for e in errs)


def test_rejects_malformed_profile_id():
    p = _first_profile()
    p["profile_id"] = "linear-issue-summary"
    errs = vpp._semantic(p, "linear")
    assert any("must match" in e for e in errs)


# --- authority-free discipline ---


def test_rejects_authority_field_in_allowed():
    p = _first_profile()
    assert isinstance(p["allowed_fields"], list)
    p["allowed_fields"].append("permission_grant")
    errs = vpp._semantic(p, "linear")
    assert any("authority/permission/secret" in e for e in errs)


def test_rejects_secret_field_in_allowed():
    p = _first_profile()
    assert isinstance(p["allowed_fields"], list)
    p["allowed_fields"].append("api_secret")
    errs = vpp._semantic(p, "linear")
    assert any("authority/permission/secret" in e for e in errs)


def test_rejects_approval_field_in_forbidden():
    p = _first_profile()
    assert isinstance(p["forbidden_fields"], list)
    p["forbidden_fields"].append("approval_status")
    errs = vpp._semantic(p, "linear")
    assert any("authority/permission/secret" in e for e in errs)


def test_rejects_credential_field_in_allowed():
    p = _first_profile()
    assert isinstance(p["allowed_fields"], list)
    p["allowed_fields"].append("credential_value")
    errs = vpp._semantic(p, "linear")
    assert any("authority/permission/secret" in e for e in errs)


def test_rejects_token_field_in_allowed():
    p = _first_profile()
    assert isinstance(p["allowed_fields"], list)
    p["allowed_fields"].append("access_token")
    errs = vpp._semantic(p, "linear")
    assert any("authority/permission/secret" in e for e in errs)


def test_rejects_overlapping_allowed_and_forbidden():
    p = _first_profile()
    assert isinstance(p["allowed_fields"], list)
    assert isinstance(p["forbidden_fields"], list)
    p["allowed_fields"].append("state")
    errs = vpp._semantic(p, "linear")
    assert any("overlap" in e for e in errs)


# --- golden conformance fixtures ---


def _load_golden(name: str) -> dict[str, object]:
    path = _CONNECTORS / "linear" / "fixtures" / "projection" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_golden_summary_v1_shape():
    g = _load_golden("golden_summary_v1.json")
    assert g["profile_id"] == "linear.issue.summary.v1"
    assert g["canonical_ref_present"] is True
    assert g["receipt_required"] is True
    payload = g["expected_rendered_payload"]
    assert isinstance(payload, dict)
    assert "description" in payload
    assert "dec_001" in payload["description"]
    mut = g["expected_mutation"]
    assert isinstance(mut, dict)
    assert mut["operation"] == "issueUpdate"
    assert "description" in mut["fields_populated"]
    for f in mut["fields_not_touched"]:
        assert f not in mut["fields_populated"]
    receipt = g["expected_receipt_mapping"]
    assert isinstance(receipt, dict)
    assert receipt["status"] == "updated"


def test_golden_work_item_v1_shape():
    g = _load_golden("golden_work_item_v1.json")
    assert g["profile_id"] == "linear.issue.work_item.v1"
    assert g["canonical_ref_present"] is True
    assert g["receipt_required"] is True
    payload = g["expected_rendered_payload"]
    assert isinstance(payload, dict)
    assert "title" in payload
    assert "description" in payload
    assert "teamId" in payload
    assert "dec_002" in payload["description"]
    mut = g["expected_mutation"]
    assert isinstance(mut, dict)
    assert mut["operation"] == "issueCreate"
    assert set(mut["fields_populated"]) == {"title", "description", "teamId"}


def test_golden_status_v1_shape():
    g = _load_golden("golden_status_v1.json")
    assert g["profile_id"] == "linear.comment.status.v1"
    assert g["canonical_ref_present"] is True
    assert g["receipt_required"] is True
    payload = g["expected_rendered_payload"]
    assert isinstance(payload, dict)
    assert "body" in payload
    assert "issueId" in payload
    assert "dec_001" in payload["body"]
    mut = g["expected_mutation"]
    assert isinstance(mut, dict)
    assert mut["operation"] == "commentCreate"
    assert set(mut["fields_populated"]) == {"body", "issueId"}


def test_golden_fixtures_match_profiles():
    """Each golden fixture's fields_populated are a subset of the profile's allowed_fields,
    and fields_not_touched are a subset of the profile's forbidden_fields."""
    profiles = {p["profile_id"]: p for p in _linear_profiles()}
    fixtures_dir = _CONNECTORS / "linear" / "fixtures" / "projection"
    for fpath in sorted(fixtures_dir.glob("golden_*.json")):
        g = json.loads(fpath.read_text(encoding="utf-8"))
        pid = g["profile_id"]
        assert pid in profiles, f"fixture {fpath.name} references unknown profile {pid}"
        profile = profiles[pid]
        mut = g["expected_mutation"]
        for field in mut["fields_populated"]:
            assert field in profile["allowed_fields"], (
                f"fixture {fpath.name}: populated field {field!r} not in profile allowed_fields"
            )
        for field in mut["fields_not_touched"]:
            assert field in profile["forbidden_fields"], (
                f"fixture {fpath.name}: not-touched field {field!r} not in profile forbidden_fields"
            )


def test_golden_fixtures_canonical_ref_consistent():
    """Every golden fixture must have canonical_ref_present == the profile's required_canonical_ref."""
    profiles = {p["profile_id"]: p for p in _linear_profiles()}
    fixtures_dir = _CONNECTORS / "linear" / "fixtures" / "projection"
    for fpath in sorted(fixtures_dir.glob("golden_*.json")):
        g = json.loads(fpath.read_text(encoding="utf-8"))
        pid = g["profile_id"]
        profile = profiles[pid]
        assert g["canonical_ref_present"] == profile["required_canonical_ref"]
        assert g["receipt_required"] == profile["required_receipt"]


# --- top-level file array constraint ---


def test_rejects_non_array_top_level():
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"profile_id": "x"}, f)
        f.flush()
        errs = vpp.validate_projection(Path(f.name), _SCHEMA)
    assert any("top-level must be an array" in e for e in errs)


def test_rejects_empty_array():
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump([], f)
        f.flush()
        errs = vpp.validate_projection(Path(f.name), _SCHEMA)
    assert any("at least one profile" in e for e in errs)
