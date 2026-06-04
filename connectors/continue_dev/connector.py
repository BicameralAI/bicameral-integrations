# SPDX-License-Identifier: MIT
"""Continue connector: development-data events into neutral Observations.

Continue (continue.dev) writes "development data" as local JSONL — one event
per developer-AI interaction (``chatInteraction``, ``editOutcome``,
``autocomplete``, ...). Each event maps to one provider-neutral Observation
(trust tier T0, file import). The live file-watch / HTTP-sink collection and the
``level: noCode`` redaction lever stay in the operator runtime (see ``auth.md``);
this is the parse surface only. Read-only evidence, no canonical writes
(ADR-0008). The package is ``continue_dev`` because ``continue`` is a Python
keyword; the provider id is the string ``"continue"``.
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def _event_excerpt(event: dict, name: str) -> str:
    """First non-empty human-text field, else a terminal non-empty literal.

    Continue's per-event schema is versioned and churns (``schema`` 0.1.0/0.2.0)
    and ``level: noCode`` strips text fields entirely; the excerpt must never be
    blank (the emission contract rejects it), so this falls through to a literal.
    Non-string field values (a version-skewed event) are skipped, not coerced.
    """
    for key in ("prompt", "completion", "content", "message"):
        value = event.get(key)
        text = value.strip() if isinstance(value, str) else ""
        if text:
            return text
    return f"continue {name}"


def parse_event(event: dict) -> Observation:
    """Map a Continue development-data event into a provider-neutral Observation.

    Field values are coerced to ``str`` where the contract needs a string, so a
    version-skewed event carrying a non-string field is normalized, not crashed
    (the schema is documented to churn — see the connector docstring).
    """
    name = str(event.get("name") or "continue-event")
    timestamp = str(event.get("timestamp") or event.get("ts") or "")
    ref = str(event.get("eventId") or event.get("id") or f"{name}:{timestamp}")
    return Observation(
        source_ref=SourceRef(source_id="continue", ref=ref, kind=name),
        excerpt=_event_excerpt(event, name),
        mode=SourceMode.PASSIVE,
        title=name,
        author=str(event.get("userId") or ""),
        timestamp=timestamp,
        metadata={
            "name": name,
            "schema": str(event.get("schema") or ""),
            "model": str(event.get("modelTitle") or event.get("model") or ""),
        },
    )


class ContinueConnector:
    """Continue connector identity plus the dev-data event parse surface.

    Trust tier T0 (file import). The live JSONL file-watch / HTTP-sink path and
    any Continue Hub API are deferred; this is the parse surface.
    """

    source_id = "continue"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.PASSIVE}))

    def observations(self, payload: dict) -> list[Observation]:
        return [parse_event(payload)]
