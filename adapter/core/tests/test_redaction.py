# SPDX-License-Identifier: MIT
"""Tests for the redaction-and-pass primitive (adapter.core.redaction)."""

from __future__ import annotations

from adapter.core.redaction import redact
from adapter.core.sensitive import detect_sensitive

_VALID_PAN = "4111111111111111"  # Luhn-valid test Visa
_AKIA = "AKIA" + "ABCDEFGHIJKLMNOP"  # AKIA + 16 uppercase alnum (matches the secret pattern)


def test_redact_scrubs_email_and_phone():
    out = redact("ping jane@example.com or (415) 555-0132 today")
    assert "[redacted:email]" in out
    assert "[redacted:phone]" in out
    assert "@" not in out
    assert "555-0132" not in out


def test_redact_scrubs_catalog_values():
    out = redact(f"key {_AKIA} ssn: 123-45-6789 card {_VALID_PAN}")
    assert _AKIA not in out
    assert "123-45-6789" not in out  # PHI VALUE scrubbed, not just the label
    assert _VALID_PAN not in out
    assert "[redacted:secret]" in out
    assert "[redacted:phi]" in out
    assert "[redacted:pan]" in out


def test_redact_output_passes_detect():
    # Keystone invariant, adversarial: redacted output must be clean to detect.
    corpus = "\n".join(
        [
            f"key {_AKIA} ssn: 123-45-6789 card {_VALID_PAN}",
            "email a@b.com phone (415) 555-0132",
            "noluhn 1234567890123 (212) 555-9999",  # (a) non-Luhn abutting a phone group
            f"order_id: ssn: 999-00-1111 {_VALID_PAN}",  # (b) PHI label between id-label and PAN
            f"call 4155550132 then {_VALID_PAN}",  # (c) phone next to a Luhn PAN
            "mrn: 12345678 dob: 1990-01-15",
        ]
    )
    assert detect_sensitive(redact(corpus)) == []


def test_redact_bare_phi_labels_pass_detect():
    # Redaction must be a SUPERSET of detection: bare/empty/punctuation-led PHI
    # labels are detected by detect_sensitive, so redact must scrub them too
    # (else the emission is REJECTED, not passed). Regression for the observer break.
    for x in ["dob:", "ssn= (pending)", "Patient dob: <withheld>", "ssn:\n", "social_security_number:"]:
        assert detect_sensitive(redact(x)) == [], f"bare PHI label leaked: {x!r}"


def test_redact_preserves_non_sensitive_text():
    text = "The team decided to adopt Postgres for the event store."
    assert redact(text) == text


def test_redact_keeps_id_preceded_digits():
    # order_id: <luhn-pan> is NOT a PAN per detect_sensitive; redact keeps it (parity).
    out = redact(f"order_id: {_VALID_PAN}")
    assert _VALID_PAN in out
    assert detect_sensitive(out) == []
