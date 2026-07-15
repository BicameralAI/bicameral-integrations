# SPDX-License-Identifier: MIT
"""Behavioral tests for the inter-repo contract provenance + drift gate (#251)."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate_governance_pin import (  # noqa: E402
    _check_contract,
    _check_factory_governance,
    _is_sha,
    main,
)

_SHA40 = "0" * 40
_SHA64 = "a" * 64


def test_real_pin_verifies():
    assert main() == 0


def test_is_sha():
    assert _is_sha(_SHA40)
    assert not _is_sha("0" * 39)
    assert not _is_sha("Z" * 40)
    assert not _is_sha(None)


def test_factory_governance_requires_commit_and_doctrine():
    errors = _check_factory_governance(
        {"producer": "a", "consumer": "b", "commit": "short", "doctrine": []}
    )
    joined = "\n".join(errors)
    assert "40-char" in joined
    assert "non-empty list" in joined


def test_contract_missing_ownership_flagged():
    errors = _check_contract(0, {"contract_id": "x", "upstream_commit": _SHA40})
    joined = "\n".join(errors)
    assert "producer" in joined
    assert "consumer" in joined


def test_contract_local_mirror_drift(tmp_path, monkeypatch):
    import validate_governance_pin as vgp

    monkeypatch.setattr(vgp, "ROOT", tmp_path)
    mirror = tmp_path / "runtime" / "schemas" / "x.json"
    mirror.parent.mkdir(parents=True)
    mirror.write_text("real-bytes", encoding="utf-8")
    contract = {
        "contract_id": "c",
        "producer": "p",
        "consumer": "q",
        "upstream_repo": "r",
        "upstream_path": "u",
        "upstream_commit": _SHA40,
        "local_path": "runtime/schemas/x.json",
        "content_sha256": _SHA64,  # wrong on purpose
    }
    errors = vgp._check_contract(0, contract)
    assert any("drift" in e for e in errors)

    # Correct hash → no drift error.
    contract["content_sha256"] = hashlib.sha256(b"real-bytes").hexdigest()
    assert vgp._check_contract(0, contract) == []
