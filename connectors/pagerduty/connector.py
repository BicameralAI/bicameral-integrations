# SPDX-License-Identifier: MIT
"""PagerDuty connector: v3 incident webhook events into neutral Observations.

A PagerDuty v3 webhook envelope (`{event: {event_type, occurred_at, data}}`)
for an incident maps to one provider-neutral Observation (trust tier T1,
incident/on-call evidence). The live webhook receipt and `X-PagerDuty-Signature`
verification (which carries multiple comma-separated rotating signatures — the
deferred ``verify()`` must do membership, not equality) are deferred (see
``auth.md``); this is the parse surface only. Read-only evidence (ADR-0008).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def _text(value: object) -> str:
    """A stripped string for str inputs, else '' (webhook bodies carry any type)."""
    return value.strip() if isinstance(value, str) else ""


def parse_event(envelope: dict) -> Observation:
    """Map a PagerDuty v3 incident webhook envelope into an Observation.

    Unwraps the nested ``event.data`` envelope; both levels are isinstance-
    guarded so a malformed/partial payload normalizes rather than crashes.
    """
    event = envelope.get("event")
    ev = event if isinstance(event, dict) else envelope
    nested = ev.get("data")
    data = nested if isinstance(nested, dict) else {}
    iid = str(data.get("id") or "pagerduty-incident")
    title = _text(data.get("title")) or _text(data.get("summary"))
    return Observation(
        source_ref=SourceRef(
            source_id="pagerduty", ref=iid, url=data.get("html_url") or "", kind="incident"
        ),
        excerpt=title or iid,
        mode=SourceMode.WEBHOOK,
        title=title or iid,
        timestamp=str(data.get("created_at") or ev.get("occurred_at") or ""),
        metadata={
            "event_type": ev.get("event_type") or "",
            "status": data.get("status") or "",
            "urgency": data.get("urgency") or "",
        },
    )


class PagerDutyConnector:
    """PagerDuty connector identity plus the incident-event parse surface.

    Trust tier T1. The live webhook receipt + multi-signature
    `X-PagerDuty-Signature` verification path is deferred; this is the parse
    surface.
    """

    source_id = "pagerduty"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.WEBHOOK}))

    def observations(self, payload: dict) -> list[Observation]:
        return [parse_event(payload)]
