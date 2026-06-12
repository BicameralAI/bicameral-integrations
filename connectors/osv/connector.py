# SPDX-License-Identifier: MIT
"""OSV connector: OSV.dev vulnerability records into neutral Observations.

An OSV vulnerability record (the OSV schema shared by GHSA/PyPA/RustSec, served
by the free no-auth OSV.dev API) maps to one provider-neutral Observation
(trust tier T1, read-only). Only ``id`` + ``modified`` are required by the OSV
schema; every other field is optional, so parsing defends on absence and wrong
type throughout (SG-2026-06-04-I). The live OSV query client is deferred (see
``auth.md``); this is the parse surface only. Read-only evidence (ADR-0008).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.redaction import redact


def _text(value: object) -> str:
    """A stripped string for str inputs, else '' (version-skewed fields)."""
    return value.strip() if isinstance(value, str) else ""


def _as_list(value: object) -> list:
    """The value when it is a list, else [] (a non-list field is not iterated)."""
    return value if isinstance(value, list) else []


def _severity(record: dict) -> str:
    """Join ``type:score`` for each dict entry in ``severity``; skip non-dicts."""
    parts = [
        f"{e.get('type', '')}:{e.get('score', '')}"
        for e in _as_list(record.get("severity"))
        if isinstance(e, dict)
    ]
    return ",".join(parts)


def _first_ref_url(record: dict) -> str:
    """URL of the first reference, guarding non-list / empty / non-dict element."""
    refs = _as_list(record.get("references"))
    first = refs[0] if refs and isinstance(refs[0], dict) else {}
    return first.get("url") or ""


def _packages(record: dict) -> str:
    """Comma-joined affected package names; guards non-dict entries + non-str names."""
    names = [
        a["package"]["name"]
        for a in _as_list(record.get("affected"))
        if isinstance(a, dict)
        and isinstance(a.get("package"), dict)
        and isinstance(a["package"].get("name"), str)
        and a["package"]["name"]
    ]
    return ",".join(names)


def parse_vuln(record: dict) -> Observation:
    """Map an OSV vulnerability record into a provider-neutral Observation.

    ``summary`` + ``details`` are free text -> **redact-and-pass** (secret/PHI/PAN + email/phone
    scrubbed; SG-2026-06-13-A). OSV is public technical vuln text (low PII risk), but a description
    can embed a contributor email or a tokened URL, and redaction is non-destructive. The opaque
    ``id`` floor is NOT redacted.
    """
    vid = str(record.get("id") or "osv-vuln")
    summary = redact(_text(record.get("summary")))
    details = redact(_text(record.get("details")))
    return Observation(
        source_ref=SourceRef(
            source_id="osv", ref=vid, url=_first_ref_url(record), kind="vulnerability"
        ),
        excerpt=summary or details or vid,
        mode=SourceMode.ACTIVE,
        title=summary or vid,
        timestamp=str(record.get("modified") or ""),
        metadata={
            "severity": _severity(record),
            "packages": _packages(record),
            "aliases": ",".join(str(a) for a in _as_list(record.get("aliases"))),
        },
    )


class OsvConnector:
    """OSV connector identity plus the vulnerability-record parse surface.

    Trust tier T1 (read API, no credential). The live OSV.dev query client
    (``/v1/query``, ``querybatch``) is deferred; this is the parse surface.
    """

    source_id = "osv"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.ACTIVE}))

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_vuln(payload)]
