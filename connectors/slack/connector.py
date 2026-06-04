# SPDX-License-Identifier: MIT
"""Slack connector: message events into neutral Observations.

A Slack message — a bare message object or an Events-API ``event_callback``
envelope — maps to one provider-neutral Observation (read/ingest evidence
surface, trust tier T2). Notify/write (T3+) is deferred (ADR-0008,
evidence-before-action). Live Events-API receipt + webhook signature
verification are deferred (see ``auth.md``).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def parse_message(payload: dict) -> Observation:
    """Map a Slack message (or event_callback envelope) into an Observation.

    Slack messages routinely have empty ``text`` (system messages, join/leave);
    the excerpt falls back to a stripped-non-empty locating string so the
    emission contract's non-empty-excerpt rule always holds. Edit subtypes
    (``message_changed`` et al.) carry their real content in a nested
    ``message`` object, which is unwrapped so the edited text is not lost.
    """
    event = payload.get("event")
    msg = event if isinstance(event, dict) else payload
    nested = msg.get("message")
    inner = nested if isinstance(nested, dict) else {}
    channel = msg.get("channel") or inner.get("channel") or ""
    ts = msg.get("ts") or inner.get("ts") or ""
    excerpt = (msg.get("text") or inner.get("text") or "").strip() or f"(no text) {channel}:{ts}"
    return Observation(
        source_ref=SourceRef(source_id="slack", ref=f"{channel}:{ts}", kind="message"),
        excerpt=excerpt,
        mode=SourceMode.WEBHOOK,
        author=msg.get("user") or inner.get("user") or "",
        timestamp=ts,
        metadata={"channel": channel, "type": msg.get("type") or ""},
    )


class SlackConnector:
    """Slack connector identity plus the message parse surface.

    Trust tier T2 (read/ingest). The live Events-API receipt + signature
    verification path and any notify/write (T3+) are deferred.
    """

    source_id = "slack"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.WEBHOOK}))

    def observations(self, payload: dict) -> list[Observation]:
        return [parse_message(payload)]
