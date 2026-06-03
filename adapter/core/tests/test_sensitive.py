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
