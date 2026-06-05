"""PII redaction-and-pass: scrub free-text so it can be emitted as evidence.

``redact(text)`` scrubs the FX-SEC-001 catalog classes (secret / PHI / PAN) AND the
generic PII the catalog does not detect (email, phone), returning text that PASSES
``adapter.core.pipeline._screen_sensitive``. It composes WITH — never replaces — the
hard screen, which stays the un-bypassable backstop: if the redactor ever misses a
secret, the gate still rejects the emission (defense in depth).

The catalog pass runs **LAST** (after email/phone), so ``redact_catalog`` evaluates
the final digit layout and ``detect_sensitive(redact(x)) == []`` holds **by
construction** — no later step can surface or fragment a digit run into a detectable
PAN. Redaction is irreversible (placeholders); stdlib ``re`` only.
"""

from __future__ import annotations

import re

from .sensitive import redact_catalog

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[ .\-]?)?(?:\(\d{3}\)|\d{3})[ .\-]?\d{3}[ .\-]?\d{4}(?!\d)"
)


def redact(text: str) -> str:
    """Scrub email + phone + secret/PHI/PAN, returning emit-safe text.

    Order is email -> phone -> ``redact_catalog`` (catalog LAST): the catalog pass
    evaluates the final string, so ``detect_sensitive(redact(x)) == []`` by
    construction. FX-SEC-001 (``_screen_sensitive``) remains the backstop regardless.
    """
    out = _EMAIL_RE.sub("[redacted:email]", text)
    out = _PHONE_RE.sub("[redacted:phone]", out)
    return redact_catalog(out)
