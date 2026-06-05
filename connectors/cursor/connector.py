"""Cursor connector: team daily-usage rows into neutral, PII-free Observations.

The Cursor Admin API (``POST /teams/daily-usage-data``) returns per-user-day rows. EVERY
row carries ``email`` and ``name`` (PII) alongside aggregate usage metrics. FX-SEC-001
(``adapter.core.sensitive``) screens secret / PHI / PAN only — it does **NOT** detect a
generic email and never scans Observation metadata, so there is **no downstream backstop**
(audit #74, HIGH). The SOLE PII control is therefore here: ``parse_usage_day`` reads ONLY a
strict allowlist of non-PII aggregate fields (numeric metrics + ``mostUsedModel``) and
**never reads ``email`` / ``name`` / ``userId`` / ``clientVersion``**. Per-developer-attributed
ingest is deferred behind a future PII redaction-and-pass model. Poll-only — no webhooks;
the live REST poll + API-key (basic-auth) resolution stay in the operator runtime
(see ``auth.md``).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def _int(value: object) -> int:
    """Coerce a usage metric to int (0 when absent / non-numeric)."""
    return value if isinstance(value, int) else 0


def _usage_summary(row: dict) -> str:
    """PII-free evidence excerpt from a daily-usage row's aggregate metrics ONLY.

    Reads a strict allowlist of numeric metrics + ``mostUsedModel``;
    ``email`` / ``name`` / ``userId`` / ``clientVersion`` are never touched.
    """
    day = (row.get("day") or "").strip() or "usage"
    summary = (
        f"Cursor usage {day}: +{_int(row.get('acceptedLinesAdded'))} accepted lines, "
        f"{_int(row.get('totalAccepts'))}/{_int(row.get('totalApplies'))} accepts, "
        f"{_int(row.get('agentRequests'))} agent + {_int(row.get('chatRequests'))} chat + "
        f"{_int(row.get('composerRequests'))} composer requests"
    )
    model = row.get("mostUsedModel")
    if isinstance(model, str) and model:
        summary += f", model {model}"
    return summary


def parse_usage_day(row: dict) -> Observation:
    """Map one Cursor daily-usage row into a PII-free aggregate Observation.

    ``email`` / ``name`` / ``userId`` are deliberately NOT read — FX-SEC-001 does not
    screen generic email, so this parse-time exclusion is the sole PII control.
    """
    day = (row.get("day") or "").strip()
    return Observation(
        source_ref=SourceRef(
            source_id="cursor",
            ref=f"cursor:usage:{day}" if day else "cursor-usage",
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
        return [parse_usage_day(payload)]
