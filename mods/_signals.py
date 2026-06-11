# SPDX-License-Identifier: MIT
"""Shared, deterministic helpers for the advisory mods (mod purple-team remediation, MP2).

- ``matched_terms`` / ``any_match`` — keyword matching that WORD-BOUNDARY-matches a pure-alphanumeric
  term (so ``auth`` no longer fires on "author", ``adr`` on "quadratic", ``retire`` on "retired")
  and SUBSTRING-matches a phrase/path/punctuated term (``.github/workflows``, ``auto-merge``,
  ``migrate to v``) where substring is the intended behavior (SG-2026-06-12-E).
- ``safe_id`` — return a source_id only when it is the contract-clean shape ``[A-Za-z0-9._-]{1,128}``,
  else ``"unknown"``; so a mod that echoes an id into an advisory message cannot leak a generic
  name/email the FX-SEC-001 screen does not catch (mod purple-team pii_secret_output).

Stdlib-only, pure functions; ``adapter`` must NOT import ``mods`` so these live here.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

# Evidence kinds that mark an emission as a code/change event (the PR-review mod family gates on it).
_CHANGE_KINDS = frozenset({"pull_request", "issue", "merge_request"})


def is_change_evidence(emission: object) -> bool:
    """True iff the emission carries change evidence (a pull_request / issue / merge_request).

    Totality-safe: tolerates a None/odd ``evidence``, a None/non-``SourceRef`` ``source_ref``, and a
    non-str / UNHASHABLE ``kind`` (a list/dict kind would otherwise crash a ``in frozenset`` test —
    mod purple-team crash_dos) — any malformed shape simply does not count as change evidence."""
    for ev in (getattr(emission, "evidence", None) or ()):
        kind = getattr(getattr(ev, "source_ref", None), "kind", None)
        if isinstance(kind, str) and kind in _CHANGE_KINDS:
            return True
    return False


def matched_terms(text: str, terms: Iterable[str]) -> list[str]:
    """Terms occurring in ``text`` (case-insensitive). A pure-alphanumeric term must match a WHOLE
    token (``term.isalnum()`` → word-boundary); any other term (space/dot/slash/hyphen present)
    matches as a substring, since those are deliberate phrase/path patterns."""
    low = text.lower()
    tokens = set(_TOKEN_RE.findall(low))
    out: list[str] = []
    for term in terms:
        hit = (term in tokens) if term.isalnum() else (term in low)
        if hit:
            out.append(term)
    return out


def any_match(text: str, terms: Iterable[str]) -> bool:
    """True iff any term matches ``text`` under :func:`matched_terms` semantics."""
    low = text.lower()
    tokens = set(_TOKEN_RE.findall(low))
    return any((term in tokens) if term.isalnum() else (term in low) for term in terms)


def safe_id(source_id: object) -> str:
    """``source_id`` if it is the contract-clean shape ``[A-Za-z0-9._-]{1,128}``, else ``'unknown'``.
    Keeps a mod leak-safe when it echoes an id into an advisory message/metadata, independent of
    whether the upstream input validator already ran."""
    return source_id if isinstance(source_id, str) and _ID_RE.match(source_id) else "unknown"
