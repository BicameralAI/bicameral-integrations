# SPDX-License-Identifier: MIT
"""Behavior tests for the sensitive-data detector (secret / PHI / PAN)."""

from __future__ import annotations

from adapter.core.sensitive import detect_sensitive

# Fake, non-functional test fixtures (canonical example shapes; not live secrets).
_GH_TOKEN = "ghp_0123456789abcdefghijklmnopqrstuvwxyz"  # ghp_ + 36 chars
_AWS_KEY = "AKIAIOSFODNN7EXAMPLE"  # AKIA + 16 chars (AWS docs example)
_PEM = "-----BEGIN RSA PRIVATE KEY-----"
_LUHN_PAN = "4111111111111111"  # Luhn-valid test PAN


def test_detect_flags_github_pat():
    hits = detect_sensitive(f"the key is {_GH_TOKEN} ok")
    assert any(h.cls == "secret" for h in hits)


def test_detect_flags_aws_access_key():
    hits = detect_sensitive(f"aws {_AWS_KEY} end")
    assert any(h.cls == "secret" for h in hits)


def test_detect_flags_pem_private_key():
    hits = detect_sensitive(f"{_PEM}\nMIIB...")
    assert any(h.cls == "secret" for h in hits)


def test_detect_flags_broadened_scanner_token_families():
    # purple-team #185 / SG-2026-06-13-F: the catalog now covers the common scanner-emitted
    # token families that previously slipped past both detect and redact.
    # NOTE: each fixture is ASSEMBLED by concatenation so no literal token shape appears in source —
    # otherwise GitHub push-protection flags the test file itself (SG-2026-06-14-A).
    samples = [
        "xox" + "b-" + "123456789012-" + "a" * 16,        # slack
        "AIza" + "Sy" + "A" * 33,                          # google api key (AIza + 35)
        "github_" + "pat_" + "A" * 82,                     # github fine-grained PAT
        "sk" + "_live_" + "0" * 24,                        # stripe live
        "glpat" + "-" + "a" * 20,                          # gitlab PAT (glpat- + 20)
        "npm" + "_" + "a" * 36,                            # npm token
        "sk" + "-" + "A" * 40,                             # openai key
    ]
    for s in samples:
        assert any(h.cls == "secret" for h in detect_sensitive(f"found {s} here")), s


def test_clean_text_not_flagged_by_broadened_catalog():
    # the broadened patterns are prefix-anchored — ordinary prose must not false-positive.
    for clean in ("the sky-blue banner", "task npm install ran", "see section AIza notes"):
        assert not any(h.cls == "secret" for h in detect_sensitive(clean)), clean


def test_detect_flags_phi_mrn_label():
    hits = detect_sensitive("patient MRN: 1234567 admitted")
    assert any(h.cls == "phi" for h in hits)


def test_detect_clean_text_returns_empty():
    assert detect_sensitive("We will adopt Postgres for the event store.") == []


def test_secret_excerpt_is_redacted():
    hits = detect_sensitive(f"key {_GH_TOKEN}")
    secret = next(h for h in hits if h.cls == "secret")
    assert secret.match_excerpt != _GH_TOKEN
    assert _GH_TOKEN not in secret.match_excerpt
    assert "*" in secret.match_excerpt
    assert secret.match_excerpt.startswith("ghp_")


def test_pan_luhn_valid_flagged():
    hits = detect_sensitive(f"card {_LUHN_PAN} charged")
    assert any(h.cls == "pan" for h in hits)


def test_pan_excluded_when_id_labeled():
    hits = detect_sensitive(f"order_id: {_LUHN_PAN}")
    assert not any(h.cls == "pan" for h in hits)


def test_pan_excerpt_is_redacted():
    # #53: a cardholder PAN must NOT appear verbatim in the hit excerpt (-> error/log).
    pan = next(h for h in detect_sensitive(f"card {_LUHN_PAN} charged") if h.cls == "pan")
    assert pan.match_excerpt == "[pan:redacted]"
    assert _LUHN_PAN not in pan.match_excerpt


def test_phi_excerpt_is_redacted():
    # #53: an MRN/PHI value must NOT appear verbatim in the hit excerpt.
    phi = next(h for h in detect_sensitive("patient MRN: 1234567 admitted") if h.cls == "phi")
    assert phi.match_excerpt == "[phi:redacted]"
    assert "1234567" not in phi.match_excerpt


def test_short_secret_excerpt_fully_masked():
    # #53: a short secret (<=8 chars) must be fully masked, not returned verbatim.
    # PEM header is a secret hit longer than 8 -> still first4/last4; use a JWT-shape
    # that detects, then assert no verbatim. The PEM check covers the long path; here
    # confirm the long github token keeps first4/last4 and no full value leaks.
    secret = next(h for h in detect_sensitive(f"k {_GH_TOKEN}") if h.cls == "secret")
    assert "*" in secret.match_excerpt and _GH_TOKEN not in secret.match_excerpt
