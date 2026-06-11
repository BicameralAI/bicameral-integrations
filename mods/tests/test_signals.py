# SPDX-License-Identifier: MIT
"""Tests for the shared advisory-mod signal helpers (mod purple-team MP2)."""

from __future__ import annotations

from mods._signals import any_match, matched_terms, safe_id


def test_alnum_term_is_word_boundary_not_substring():
    # the SG-2026-06-12-E class: a pure-alphanumeric term must NOT fire on a superstring.
    assert matched_terms("update the author field", ["auth"]) == []
    assert matched_terms("optimize quadratic sort", ["adr"]) == []
    assert matched_terms("the feature was retired", ["retire"]) == []
    assert matched_terms("rename policyholder model", ["policy"]) == []
    assert matched_terms("add cryptocurrency widget", ["crypto"]) == []


def test_alnum_term_matches_whole_token():
    assert matched_terms("update auth flow", ["auth"]) == ["auth"]
    assert matched_terms("implements ADR-0013", ["adr"]) == ["adr"]
    assert matched_terms("retire the endpoint", ["retire"]) == ["retire"]


def test_phrase_and_path_terms_match_substring():
    assert any_match("edit .github/workflows/ci.yml", [".github/workflows"])
    assert any_match("enable auto-merge on green", ["auto-merge"])
    assert any_match("migrate to v3 of the api", ["migrate to v"])


def test_any_match_matches_matched_terms():
    assert any_match("update auth flow", ["auth", "token"]) is True
    assert any_match("nothing relevant here", ["auth", "token"]) is False


def test_safe_id_passes_clean_rejects_dirty():
    assert safe_id("github") == "github"
    assert safe_id("anthropic_admin") == "anthropic_admin"
    assert safe_id("patient Jane Doe +1-555-123-4567") == "unknown"  # spaces/+ rejected
    assert safe_id(123) == "unknown"
    assert safe_id("a" * 200) == "unknown"  # over 128
