# SPDX-License-Identifier: MIT
"""Tests for the redaction-and-pass primitive (adapter.core.redaction)."""

from __future__ import annotations

import time as _t

from adapter.core.redaction import redact
from adapter.core.sensitive import detect_sensitive
from connectors.confluence.connector import _strip_storage_html

_VALID_PAN = "4111111111111111"  # Luhn-valid test Visa
_AKIA = "AKIA" + "ABCDEFGHIJKLMNOP"  # AKIA + 16 uppercase alnum (matches the secret pattern)


def test_redact_scrubs_email_and_phone():
    out = redact("ping jane@example.com or (415) 555-0132 today")
    assert "[redacted:email]" in out
    assert "[redacted:phone]" in out
    assert "@" not in out
    assert "555-0132" not in out


def test_redact_scrubs_international_phone():
    # deep-audit low: NANP-only _PHONE_RE leaked international numbers. The E.164 branch
    # scrubs +CC formats (UK/FR/DE/CN/AU/IN) and the keystone invariant still holds.
    samples = [
        ("UK", "+44 20 7946 0958"),
        ("FR", "+33 6 12 34 56 78"),
        ("DE", "+49 30 12345678"),
        ("CN", "+86 138 0013 8000"),
        ("AU", "+61 2 1234 5678"),
        ("IN", "+91 98765 43210"),
    ]
    for label, number in samples:
        out = redact(f"call {label} on {number} please")
        assert "[redacted:phone]" in out, f"{label} not scrubbed: {out!r}"
        assert number not in out, f"{label} number leaked: {out!r}"
        assert detect_sensitive(out) == []  # invariant holds for the broadened branch


def test_redact_scrubs_00_prefix_and_keyword_anchored_phone():
    # purple-team SG-2026-06-12-I: non-`+` international (00-prefix) + keyword-anchored national.
    for raw, leaked in [
        ("ring me on 0049 30 1234 5678", "0049 30 1234 5678"),   # 00 international prefix
        ("00 44 7911 123456 is the line", "00 44 7911 123456"),
        ("phone: 020 7946 0958", "020 7946 0958"),               # keyword-anchored UK national
        ("call 06 12 34 56 78 today", "06 12 34 56 78"),         # keyword-anchored FR national
        ("mobile 020 7946 0958", "020 7946 0958"),
    ]:
        out = redact(raw)
        assert "[redacted:phone]" in out and leaked not in out, f"leaked: {out!r}"
        assert detect_sensitive(out) == []


def test_redact_keyword_anchor_does_not_over_redact_non_phone():
    # the keyword anchor must not scrub a bare id digit run, nor a keyword with no number after it.
    assert "1234567" in redact("order id 1234567 shipped")  # 7-digit id, no phone keyword -> kept
    assert redact("the phone book has shelves") == "the phone book has shelves"  # keyword, no number

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


# --- #50/#51: ReDoS regression (linear, not O(n^2)) ---


def test_strip_storage_html_linear_on_pathological():
    start = _t.perf_counter()
    _strip_storage_html("<" * 200_000)  # would hang at O(n^2)
    assert _t.perf_counter() - start < 1.0
    assert _strip_storage_html("<p>hello</p>") == "hello"  # still strips


def test_redact_email_linear_on_pathological():
    start = _t.perf_counter()
    redact("a@" + "a-" * 200_000)  # would hang at O(n^2)
    assert _t.perf_counter() - start < 1.0


def test_redact_email_match_set_preserved():
    for e in ["jane@example.com", "jane.doe@example.com", "user@example.com", "a@b.com",
              "x+tag@sub.example.co.uk", "noreply@aider.chat", "security@bicameral.ai", "ops@a.io"]:
        assert "[redacted:email]" in redact(f"contact {e} now"), e
