# SPDX-License-Identifier: MIT
"""PII redaction-and-pass: scrub free-text so it can be emitted as evidence.

``redact(text)`` scrubs the FX-SEC-001 catalog classes (secret / PHI / PAN) AND the
generic PII the catalog does not detect (email; phone — NANP 3-3-4, international with a
``+`` or ``00`` dialing prefix, and a keyword-anchored national run such as ``tel:``/``call``/
``mobile``). A bare national number with NO dialing prefix and NO phone keyword is a documented
residual (not auto-scrubbed). It returns text that PASSES
``adapter.core.pipeline._screen_sensitive``. It composes WITH — never replaces — the
hard screen, which stays the un-bypassable backstop: if the redactor ever misses a
secret, the gate still rejects the emission (defense in depth).

The catalog runs both before and after the generic PII passes. The first pass prevents
a phone-like substring from fragmenting a secret or PAN token. The final pass preserves
the invariant that ``detect_sensitive(redact(x)) == []`` even if a later transform
changes digit adjacency. Redaction is irreversible and uses deterministic placeholders.
"""

from __future__ import annotations

import re

from .sensitive import detect_sensitive, redact_catalog

# RFC-bounded quantifiers (local <=64, label <=63, TLD <=63) cap the per-anchor scan to a
# constant, so a long local/domain run with no terminating `.TLD` fails in O(1) per position
# instead of O(n) — O(n) total, no ReDoS (#51). Match set for well-formed emails is unchanged.
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}\b")
# Two bounded branches (no nested unbounded repetition -> O(n), no ReDoS, #51):
#   1. NANP 3-3-4 (optional +CC / parens) — unchanged match set.
#   2. International with an explicit `+` OR `00` DIALING PREFIX, then 6-13 more grouped digits
#      (capped {5,12}+1). The required prefix keeps false positives near zero (SG-2026-06-12-I:
#      a `+`-only branch missed `00`-prefixed forms like `0049 30 1234 5678`).
_PHONE_RE = re.compile(
    r"(?<!\d)(?:"
    r"(?:\+?\d{1,3}[ .\-]?)?(?:\(\d{3}\)|\d{3})[ .\-]?\d{3}[ .\-]?\d{4}"
    r"|"
    r"(?:\+|00)[ .\-]?\d{1,3}[ .\-]?(?:\d[ .\-]?){5,12}\d"
    r")(?!\d)"
)
# Keyword-anchored NATIONAL run (no dialing prefix): a phone keyword immediately before a 7-14
# digit grouped run. Group 1 (the keyword + separator) is preserved; only the number is scrubbed.
# The keyword anchor avoids over-redacting a bare uuid/order-id digit run (SG-2026-06-12-I).
_PHONE_CONTEXT_RE = re.compile(
    r"(?i)((?:tel|phone|call|ring|mobile|cell|fax|whatsapp)\b[ :.\-]{1,4})((?:\d[ .\-]?){6,13}\d)"
)


def redact_with_findings(text: str) -> tuple[str, dict[str, int]]:
    """Scrub text and return category counts without returning matched values."""

    catalog_hits = detect_sensitive(text)
    secret_count = sum(1 for hit in catalog_hits if hit.cls == "secret")
    phi_count = sum(1 for hit in catalog_hits if hit.cls == "phi")
    pan_count = sum(1 for hit in catalog_hits if hit.cls == "pan")

    # Protect catalog-shaped values first so broad PII patterns cannot fragment them.
    out = redact_catalog(text)
    out, email_count = _EMAIL_RE.subn("[redacted:email]", out)
    out, phone_count = _PHONE_RE.subn("[redacted:phone]", out)
    out, contextual_phone_count = _PHONE_CONTEXT_RE.subn(
        r"\1[redacted:phone]", out
    )
    # Defense in depth: ensure later substitutions did not expose a catalog match.
    out = redact_catalog(out)

    findings = {
        "credential": pan_count,
        "pii": email_count + phone_count + contextual_phone_count + phi_count,
        "secret": secret_count,
    }
    return out, {category: count for category, count in findings.items() if count > 0}


def redact(text: str) -> str:
    """Scrub generic PII and catalog classes, returning emit-safe text."""

    return redact_with_findings(text)[0]
