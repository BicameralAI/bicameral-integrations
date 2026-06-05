"""ServiceNow connector: ITSM incident records into neutral Observations.

The Table API (``GET /api/now/table/incident``, basic/OAuth) returns incident records.
``parse_incident`` emits the safe metadata surface (``number`` / ``short_description`` /
``state`` / ``priority``) with the free-text ``description`` passed through
``adapter.core.redaction.redact``; the ``caller_id`` / ``caller`` identity is **never read**
(PII). Poll-only — no webhooks; the live REST poll + auth stay in the operator runtime
(see ``auth.md``).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.redaction import redact


def _meta(record: dict) -> str:
    """Render the non-PII state/priority tag (``''`` when both absent)."""
    state = (record.get("state") or "").strip()
    priority = (record.get("priority") or "").strip()
    bits = [b for b in (f"state={state}" if state else "", f"priority={priority}" if priority else "") if b]
    return ", ".join(bits)


def parse_incident(record: dict) -> Observation:
    """Map a ServiceNow incident record into a redacted, provider-neutral Observation."""
    number = (record.get("number") or "").strip()
    short = (record.get("short_description") or "").strip()
    description = record.get("description") or ""
    text = " — ".join(p for p in (short, str(description) if description else "") if p)
    body = redact(text)
    meta = _meta(record)
    excerpt = (f"{body} ({meta})" if meta and body else body or meta) or "servicenow-incident"
    return Observation(
        source_ref=SourceRef(
            source_id="servicenow",
            ref=number or "servicenow-incident",
            kind="incident",
        ),
        excerpt=excerpt,
        mode=SourceMode.ACTIVE,
        title=redact(short) or number,
    )


class ServiceNowConnector:
    """ServiceNow connector identity plus the incident parse surface (active poll only)."""

    source_id = "servicenow"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.ACTIVE}))

    def can_handle_ref(self, ref: SourceRef) -> bool:
        return ref.source_id == "servicenow"

    def observations(self, payload: dict) -> list[Observation]:
        return [parse_incident(payload)]
