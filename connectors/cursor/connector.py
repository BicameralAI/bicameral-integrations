"""Cursor connector: team daily-usage rows into neutral, PII-free Observations.

The Cursor Admin API (``POST /teams/daily-usage-data``) returns per-user-day rows. EVERY
row carries ``email`` (PII) alongside aggregate usage metrics (verified 2026-06-08: there is
**no ``name``** on this endpoint — ``name`` lives on the members/spend endpoints). FX-SEC-001
(``adapter.core.sensitive``) screens secret / PHI / PAN only — it does **NOT** detect a
generic email and never scans Observation metadata, so there is **no downstream backstop**
(audit #74, HIGH). The PII control is therefore here: ``parse_usage_day`` reads a strict
allowlist of non-PII fields (numeric metrics + ``mostUsedModel``) and **never reads ``email``
/ ``name`` / ``clientVersion``** (``name`` is defended even though absent on this endpoint). **Per-developer attribution uses the OPAQUE integer ``userId``**
(SG-2026-06-05-D supersedes -A for ``userId`` only): a bare vendor id is pseudonymous on its own
(the operator holds the id→identity mapping; the connector never emits the identity). Poll-only —
no webhooks; the live REST poll + API-key (basic-auth) resolution stay in the operator runtime
(see ``auth.md``).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.redaction import redact


def _int(value: object) -> int:
    """Coerce a usage metric to int (0 when absent / non-numeric).

    ``bool`` is excluded — ``isinstance(True, int)`` is True in Python, so an untrusted
    ``true``/``false`` metric must not coerce to 1/0 (provider-boundary robustness).
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _uid(row: dict) -> str:
    """Opaque vendor user id (str) for per-developer attribution; ``''`` when absent.

    ``email``/``name`` are NEVER read — the bare integer id is pseudonymous (the operator
    holds the id→identity mapping). SG-2026-06-05-D supersedes -A for ``userId`` only.
    """
    uid = row.get("userId")
    return str(uid) if isinstance(uid, int) else ""


def _day(row: dict) -> str:
    """Free-text ``day`` as a string (``''`` when absent/non-string).

    A truthy non-string ``day`` (provider drift / hostile row) must not crash ``.strip()`` and
    abort the whole batch — mirrors the ``_int``/``_uid``/``model`` guards (deep-audit PARSE).
    """
    value = row.get("day")
    return value.strip() if isinstance(value, str) else ""


def _usage_summary(row: dict) -> str:
    """PII-free evidence excerpt from a daily-usage row's aggregate metrics ONLY.

    Reads a strict allowlist of numeric metrics + ``mostUsedModel`` + the opaque
    ``userId``; ``email`` / ``name`` / ``clientVersion`` are never touched. The free-text
    ``day``/``mostUsedModel`` are passed through ``redact()`` (#58) — they could carry an
    email/phone, which FX-SEC-001 does not screen; the opaque ``userId`` is unaffected.
    """
    day = _day(row) or "usage"
    uid = _uid(row)
    who = f" user {uid}" if uid else ""
    summary = (
        f"Cursor usage{who} {day}: +{_int(row.get('acceptedLinesAdded'))} accepted lines, "
        f"{_int(row.get('totalAccepts'))}/{_int(row.get('totalApplies'))} accepts, "
        f"{_int(row.get('agentRequests'))} agent + {_int(row.get('chatRequests'))} chat + "
        f"{_int(row.get('composerRequests'))} composer requests"
    )
    model = row.get("mostUsedModel")
    if isinstance(model, str) and model:
        summary += f", model {model}"
    return redact(summary)


def parse_usage_day(row: dict) -> Observation:
    """Map one Cursor daily-usage row into an Observation.

    ``email`` / ``name`` are NEVER read (FX-SEC-001 does not screen generic email).
    Per-developer attribution uses the OPAQUE ``userId`` (pseudonymous; SG-2026-06-05-D).
    """
    day = redact(_day(row))  # #58: day is free-text (could carry PII); _day str-guards (deep-audit)
    base = f"cursor:usage:{day}" if day else "cursor-usage"
    uid = _uid(row)
    return Observation(
        source_ref=SourceRef(
            source_id="cursor",
            ref=f"{base}:user:{uid}" if uid else base,
            kind="usage_metrics",
        ),
        excerpt=_usage_summary(row),
        mode=SourceMode.ACTIVE,
        title=f"Cursor usage {day}".strip(),
    )


class CursorConnector:
    """Cursor connector identity plus the PII-free daily-usage parse surface.

    Active-poll only (no webhooks). The usage row is not URL-addressable, so
    ``can_handle_ref`` matches on ``source_id`` only. The live REST poll + API-key
    resolution are deferred to the operator runtime (``auth.md``).
    """

    source_id = "cursor"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.ACTIVE}))

    def can_handle_ref(self, ref: SourceRef) -> bool:
        return ref.source_id == "cursor"

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_usage_day(payload)]
