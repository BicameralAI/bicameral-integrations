# SPDX-License-Identifier: MIT
"""Behavioral tests for the tracked factory-attestation gate (integrations#249)."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import validate_factory_attestation as vfa  # noqa: E402
from validate_factory_attestation import (  # noqa: E402
    _check_filename,
    _check_roadmap,
    _check_state_refinement,
    _pinned_factory_commit,
    main,
    validate_attestation,
)

_COMMIT = "12d16bd12e06c6bb3296c529d47fa90f0c86755f"


def _real_attestation() -> tuple[str, dict]:
    """The real tracked attestation shipped in this repo, plus its rel path."""
    rel = f".bicameral/factory-attestations/{_COMMIT}.integrations-251.json"
    data = json.loads((vfa.ROOT / rel).read_text(encoding="utf-8"))
    return rel, data


def test_real_tracked_attestation_valid():
    """The gate passes fail-closed against the real tracked attestation set."""
    assert main() == 0


def test_pinned_commit_resolves():
    commit, error = _pinned_factory_commit()
    assert error is None
    assert commit == _COMMIT


def test_real_attestation_has_no_violations():
    rel, data = _real_attestation()
    assert validate_attestation(rel, data, _COMMIT) == []


def test_filename_must_match_factory_commit():
    good = f".bicameral/factory-attestations/{_COMMIT}.run-1.json"
    legacy = f".bicameral/factory-attestations/{_COMMIT}.json"
    bad = ".bicameral/factory-attestations/deadbeef.run-1.json"
    assert _check_filename(good, _COMMIT) == []
    assert _check_filename(legacy, _COMMIT) == []
    assert _check_filename(bad, _COMMIT)


def test_factory_commit_reconciliation_mismatch_flagged():
    rel, data = _real_attestation()
    other = "a" * 40
    errors = validate_attestation(rel, data, other)
    assert any("does not reconcile" in e for e in errors)


def test_schema_missing_required_field_flagged():
    rel, data = _real_attestation()
    broken = copy.deepcopy(data)
    del broken["state_refinement"]
    errors = validate_attestation(rel, broken, _COMMIT)
    assert any(
        "missing required field" in e and "state_refinement" in e for e in errors
    )


def test_roadmap_reconciliation_incomplete_flagged():
    errors = _check_roadmap({"checked": True, "issue_number": 0})
    joined = "\n".join(errors)
    assert "issue_number" in joined
    assert "issue_type" in joined
    assert "project_status" in joined


def test_roadmap_pr_links_must_be_pr_urls():
    roadmap = {
        "checked": True,
        "issue_number": 243,
        "issue_type": "validating",
        "project_status": "In Progress",
        "pr_links_checked": True,
        "pr_body_links_issue": True,
        "pr_links": ["not-a-url"],
        "post_work_comment_url": None,
    }
    assert any("pr_links" in e for e in _check_roadmap(roadmap))
    roadmap["pr_links"] = [
        "https://github.com/BicameralAI/bicameral-integrations/pull/252"
    ]
    assert _check_roadmap(roadmap) == []


def test_state_refinement_requires_invariants_and_review():
    errors = _check_state_refinement(
        {
            "checked": True,
            "release_state": "x",
            "states_added": [],
            "states_deferred": [],
            "invariants": [],
            "minimization_review": {},
        }
    )
    joined = "\n".join(errors)
    assert "invariants" in joined
    assert "minimization_review.reviewed" in joined


def test_bad_version_flagged():
    rel, data = _real_attestation()
    broken = copy.deepcopy(data)
    broken["version"] = 2
    errors = validate_attestation(rel, broken, _COMMIT)
    assert any("version must be 1" in e for e in errors)
