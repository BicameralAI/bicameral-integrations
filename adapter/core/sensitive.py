"""Sensitive-data detector — secret / PHI / PAN catalog for adapter emissions.

Faithful port of bicameral-mcp's `handlers/sensitive_patterns.py` (catalog v1):
the integrations adapter screens emissions before forwarding them so credentials
or PII never reach the gateway. Adopting the mcp catalog rather than re-deriving a
weaker one keeps the data-leakage standard consistent across repos.

Three classes, distinct detection semantics:
- ``secret``: pure regex (cloud-provider key prefixes, JWT shape, PEM blocks).
- ``phi``: regex with required label-adjacency (e.g. ``MRN:`` + digits).
- ``pan``: candidate digit runs validated by Luhn checksum AND filtered when an
  ID-class label (``order_id:`` etc.) precedes them.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import NamedTuple

_SENSITIVE_CATALOG_VERSION = "v1"

_EXCERPT_MAX = 64
_PAN_CONTEXT_LOOKBACK = 30


class SensitiveHit(NamedTuple):
    """One match of a sensitive-data pattern against scanned content.

    ``cls`` is one of ``secret`` / ``phi`` / ``pan``. ``pattern_id`` indexes the
    per-class pattern tuple (0 for PAN). ``match_excerpt`` is the first
    ``_EXCERPT_MAX`` chars of the match; secret-class excerpts are additionally
    body-redacted so the value never travels in an error or log.
    """

    cls: str
    pattern_id: int
    match_excerpt: str


_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-pat", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b")),
    (
        "azure-storage-key",
        re.compile(
            r"DefaultEndpointsProtocol=https;AccountName=[a-z0-9]+;"
            r"AccountKey=[A-Za-z0-9+/]{40,};"
        ),
    ),
    ("private-key-pem", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")),
)

_PHI_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "mrn-with-label",
        re.compile(
            r"(?i)\b(?:mrn|medical\s+record(?:\s+number)?|patient\s+id)"
            r"\s*[:=]\s*\d{5,12}\b"
        ),
    ),
    (
        "phi-field-label",
        re.compile(
            r"(?i)\b(?:patient_(?:id|name|email)|date_of_birth|dob|ssn|"
            r"social_security(?:_number)?)\s*[:=]"
        ),
    ),
)

_PAN_CANDIDATE_RE = re.compile(r"\b\d{13,19}\b")
_PAN_CONTEXT_LABEL_RE = re.compile(
    r"(?i)\b(?:order_id|order|ref|ref_id|transaction_id|txn_id|"
    r"id|user_id|account_id|invoice_id|receipt)\s*[:=]\s*$"
)


def _luhn_valid(digits: str) -> bool:
    """Standard mod-10 Luhn checksum; True iff the digit string validates."""
    total = 0
    parity = len(digits) % 2
    for i, char in enumerate(digits):
        n = int(char)
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _is_id_preceded(content: str, start: int) -> bool:
    """True when the candidate at ``start`` is preceded within
    ``_PAN_CONTEXT_LOOKBACK`` chars by an ID-class label (so ``order_id: ...``
    digit runs are not mistaken for cardholder data)."""
    lookback_start = max(0, start - _PAN_CONTEXT_LOOKBACK)
    preceding = content[lookback_start:start]
    return _PAN_CONTEXT_LABEL_RE.search(preceding) is not None


def _redact_excerpt(cls: str, raw: str) -> str:
    """Truncate to ``_EXCERPT_MAX``; for ``secret`` also asterisk the body so an
    error/log carries only first-4 + last-4 chars, never the full credential."""
    truncated = raw[:_EXCERPT_MAX]
    if cls == "secret" and len(truncated) > 8:
        return truncated[:4] + "*" * (len(truncated) - 8) + truncated[-4:]
    return truncated


def detect_sensitive(content: str) -> list[SensitiveHit]:
    """Run every pattern across all three classes; return all hits ([] = clean).

    PAN candidates pass Luhn + label-context validation before becoming hits.
    """
    hits: list[SensitiveHit] = []
    for idx, (_label, pattern) in enumerate(_SECRET_PATTERNS):
        for match in pattern.finditer(content):
            hits.append(SensitiveHit("secret", idx, _redact_excerpt("secret", match.group(0))))
    for idx, (_label, pattern) in enumerate(_PHI_PATTERNS):
        for match in pattern.finditer(content):
            hits.append(SensitiveHit("phi", idx, _redact_excerpt("phi", match.group(0))))
    for match in _PAN_CANDIDATE_RE.finditer(content):
        digits = match.group(0)
        if _is_id_preceded(content, match.start()) or not _luhn_valid(digits):
            continue
        hits.append(SensitiveHit("pan", 0, _redact_excerpt("pan", digits)))
    return hits


_sensitive_detect: Callable[[str], list[SensitiveHit]] = detect_sensitive
"""v2 extension surface: swap this pointer for a classifier-backed detector."""


# --- redaction (redact-and-pass) -----------------------------------------------
# `redact_catalog` substitutes the catalog classes with placeholders so the result
# PASSES `detect_sensitive` (and therefore `pipeline._screen_sensitive`). It reuses
# the detection catalog but — unlike detection, which for PHI keys on the LABEL only
# — redaction consumes the VALUE. `detect_sensitive` and the detection patterns above
# are unchanged; this is purely additive.

# Value-consuming PHI redaction: the MRN detection pattern already includes its
# `\d{5,12}` value; the field-label pattern swallows the adjacent value. The value
# quantifier is `*` (NOT `+`) so redaction is a strict SUPERSET of detection — a
# bare/empty/punctuation-led label (`dob:`, `ssn= (pending)`) that `detect_sensitive`
# would still flag is also scrubbed, keeping `detect_sensitive(redact(x)) == []`.
_REDACT_PHI_PATTERNS: tuple[re.Pattern[str], ...] = (
    _PHI_PATTERNS[0][1],
    re.compile(
        r"(?i)\b(?:patient_(?:id|name|email)|date_of_birth|dob|ssn|"
        r"social_security(?:_number)?)\s*[:=]\s*[\w@.\-]*"
    ),
)


def _redact_pan(text: str) -> str:
    """Replace Luhn-valid, non-ID-preceded 13-19 digit runs with ``[redacted:pan]``.

    Reuses ``_luhn_valid`` + ``_is_id_preceded`` so it redacts exactly what
    ``detect_sensitive`` would flag (an ``order_id:`` run stays; a real PAN goes).
    """

    def _repl(match: re.Match[str]) -> str:
        digits = match.group(0)
        if _is_id_preceded(text, match.start()) or not _luhn_valid(digits):
            return digits
        return "[redacted:pan]"

    return _PAN_CANDIDATE_RE.sub(_repl, text)


def redact_catalog(text: str) -> str:
    """Scrub secret / PHI / PAN spans to placeholders (value-consuming for PHI).

    The result contains none of the catalog classes, so ``detect_sensitive`` of it
    is empty. This is the last transform ``redaction.redact`` applies, which is what
    makes the redact-and-pass invariant hold by construction.
    """
    out = text
    for _label, pattern in _SECRET_PATTERNS:
        out = pattern.sub("[redacted:secret]", out)
    for pattern in _REDACT_PHI_PATTERNS:
        out = pattern.sub("[redacted:phi]", out)
    return _redact_pan(out)
