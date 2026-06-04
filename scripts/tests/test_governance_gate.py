# SPDX-License-Identifier: MIT
"""Behavioral tests for the governance-integrity gate."""

from __future__ import annotations

import hashlib
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_gate import main, verify_feature_index, verify_ledger_chain  # noqa: E402

_REPO = Path(__file__).resolve().parents[2]


def _entry(num: str, content: str, previous: str, chain: str | None) -> str:
    block = (
        f"### Entry #{num}: X\n\n**Content Hash**:\n```\nSHA256(x)\n= {content}\n```\n\n"
        f"**Previous Hash**: {previous}\n\n"
    )
    if chain is not None:
        block += f"**Chain Hash**:\n```\nSHA256(c+p)\n= {chain}\n```\n\n"
    return block


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _valid_ledger() -> str:
    g = _h("genesis-content")
    c2 = _h("entry2-content")
    chain2 = _h(c2 + g)
    c3 = _h("entry3-content")
    chain3 = _h(c3 + chain2)
    return (
        _entry("1", g, "GENESIS (no predecessor)", None)
        + _entry("2", c2, g, chain2)
        + _entry("3", c3, chain2, chain3)
    )


def test_valid_chain_passes():
    assert verify_ledger_chain(_valid_ledger()) == []


def test_genesis_anchor_handled():
    # Genesis (no chain hash) + first chained entry linking to genesis CONTENT hash → clean.
    assert verify_ledger_chain(_valid_ledger()) == []
    # First chained entry whose previous != genesis content → error.
    g = _h("genesis-content")
    wrong_prev = _h("not-genesis")
    c2 = _h("e2")
    bad = _entry("1", g, "GENESIS (no predecessor)", None) + _entry(
        "2", c2, wrong_prev, _h(c2 + wrong_prev)
    )
    errs = verify_ledger_chain(bad)
    assert any("#2" in e and "link" in e for e in errs)


def test_multiple_genesis_rejected():
    g = _h("genesis-content")
    text = (
        _entry("1", g, "GENESIS (no predecessor)", None)
        + _entry("2", _h("g2"), "GENESIS (no predecessor)", None)  # second genesis — invalid
    )
    errs = verify_ledger_chain(text)
    assert any("multiple genesis" in e for e in errs)


def test_broken_link_detected():
    g = _h("genesis-content")
    c2 = _h("e2")
    chain2 = _h(c2 + g)
    c3 = _h("e3")
    tampered_prev = _h("tampered")
    text = (
        _entry("1", g, "GENESIS (no predecessor)", None)
        + _entry("2", c2, g, chain2)
        + _entry("3", c3, tampered_prev, _h(c3 + tampered_prev))
    )
    errs = verify_ledger_chain(text)
    assert any("#3" in e and "link" in e for e in errs)


def test_recomputation_mismatch_detected():
    g = _h("genesis-content")
    c2 = _h("e2")
    text = _entry("1", g, "GENESIS (no predecessor)", None) + _entry(
        "2", c2, g, "0" * 64  # wrong chain hash
    )
    errs = verify_ledger_chain(text)
    assert any("#2" in e and "mismatch" in e for e in errs)


def test_feature_index_missing_test_path_detected():
    md = (
        "| ID | Feature | Doc | Code | Test | Status |\n"
        "|---|---|---|---|---|---|\n"
        "| FX-X-001 | f | d | c.py | connectors/nope/tests/test_missing.py | Verified |\n"
    )
    errs = verify_feature_index(md, _REPO)
    assert any("FX-X-001" in e for e in errs)


def test_feature_index_waiver_row_skipped():
    md = (
        "| ID | Feature | Doc | Code | Test | Status |\n"
        "|---|---|---|---|---|---|\n"
        "| FX-Y-001 | f | d | c | (D4.d waiver) | Verified |\n"
    )
    assert verify_feature_index(md, _REPO) == []


def test_repo_ledger_verifies():
    # Guards our own committed chain — must stay clean.
    ledger = (_REPO / "docs" / "META_LEDGER.md").read_text(encoding="utf-8")
    assert verify_ledger_chain(ledger) == []


def test_main_accepts_repo_root():
    # --repo-root pointed at the real repo verifies clean (cross-repo contract).
    assert main(["--repo-root", str(_REPO)]) == 0


def test_main_missing_ledger_root_fails_cleanly(tmp_path):
    # A root with no ledger returns non-zero, not a traceback.
    assert main(["--repo-root", str(tmp_path)]) == 1


def test_repo_feature_index_paths_exist():
    fi = (_REPO / "docs" / "FEATURE_INDEX.md").read_text(encoding="utf-8")
    assert verify_feature_index(fi, _REPO) == []
