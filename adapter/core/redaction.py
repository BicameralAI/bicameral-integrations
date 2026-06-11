"""PII redaction-and-pass: scrub free-text so it can be emitted as evidence.

``redact(text)`` scrubs the FX-SEC-001 catalog classes (secret / PHI / PAN) AND the
generic PII the catalog does not detect (email; phone — NANP 3-3-4, international with a
``+`` or ``00`` dialing prefix, and a keyword-anchored national run such as ``tel:``/``call``/
``mobile``). A bare national number with NO dialing prefix and NO phone keyword is a documented
residual (not auto-scrubbed). It returns text that PASSES
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


def redact(text: str) -> str:
    """Scrub email + phone + secret/PHI/PAN, returning emit-safe text.

    Order is email -> phone (+/00 international, then keyword-anchored national) -> ``redact_catalog``
    (catalog LAST): the catalog pass evaluates the final string, so ``detect_sensitive(redact(x)) == []``
    by construction. FX-SEC-001 (``_screen_sensitive``) remains the backstop regardless.
    """
    out = _EMAIL_RE.sub("[redacted:email]", text)
    out = _PHONE_RE.sub("[redacted:phone]", out)
    out = _PHONE_CONTEXT_RE.sub(r"\1[redacted:phone]", out)  # keep the keyword, scrub the number
    return redact_catalog(out)
