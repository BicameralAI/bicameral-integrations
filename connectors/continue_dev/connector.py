# SPDX-License-Identifier: MIT
"""Continue connector: development-data events into neutral Observations.

Continue (continue.dev) writes "development data" as local JSONL — one event
per developer-AI interaction (``chatInteraction``, ``editOutcome``,
``autocomplete``, ...). Each event maps to one provider-neutral Observation
(trust tier T0, file import). The live file-watch / HTTP-sink collection and the
``level: noCode`` redaction lever stay in the operator runtime (see ``auth.md``);
this is the parse surface only. Read-only evidence, no canonical writes
(ADR-0008). The package is ``continue_dev`` because ``continue`` is a Python
keyword; the ``source_id`` is ``"continue_dev"`` to satisfy the FX-CFG-001
descriptor contract (id == folder == source_id, ADR-0015) — the provider's own
product name is "Continue".
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.redaction import redact


def _event_excerpt(event: dict, name: str) -> str:
    """First non-empty human-text field (**redact-and-passed**), else a terminal literal.

    Continue's per-event schema is versioned and churns (``schema`` 0.1.0/0.2.0)
    and ``level: noCode`` strips text fields entirely; the excerpt must never be
    blank (the emission contract rejects it), so this falls through to a literal.
    The human-text fields (``prompt``/``completion``/``content``/``message``) are
    developer-AI interaction text that can carry code with secrets/emails -> scrubbed
    via ``redact()`` (secret/PHI/PAN + email/phone; SG-2026-06-13-A). The ``continue {name}``
    floor (the event-kind) is NOT redacted. Non-string field values are skipped, not coerced.
    """
    for key in ("prompt", "completion", "content", "message"):
        value = event.get(key)
        text = value.strip() if isinstance(value, str) else ""
        if text:
            return redact(text)
    return f"continue {name}"


def parse_event(event: dict) -> Observation:
    """Map a Continue development-data event into a provider-neutral Observation.

    Field values are coerced to ``str`` where the contract needs a string, so a
    version-skewed event carrying a non-string field is normalized, not crashed
    (the schema is documented to churn — see the connector docstring).
    """
    # verified docs.continue.dev 2026-06-08: the base event field is `eventName`
    # (legacy `name` kept as a tolerant fallback); there is no event-id field.
    name = str(event.get("eventName") or event.get("name") or "continue-event")
    timestamp = str(event.get("timestamp") or event.get("ts") or "")
    ref = str(event.get("eventId") or event.get("id") or f"{name}:{timestamp}")
    return Observation(
        source_ref=SourceRef(source_id="continue_dev", ref=ref, kind=name),
        excerpt=_event_excerpt(event, name),
        mode=SourceMode.PASSIVE,
        title=name,
        author=redact(str(event.get("userId") or "")),  # opaque id passes; an email-shaped userId is scrubbed
        timestamp=timestamp,
        metadata={
            "name": name,
            "schema": str(event.get("schema") or ""),
            # modelTitle is a USER-DEFINED free-form string (a developer names their model config),
            # not uniform-technical like name/schema -> redact-and-pass (purple-team CONTINUE-PII-1).
            "model": redact(str(event.get("modelTitle") or event.get("modelName") or event.get("model") or "")),
        },
    )


class ContinueConnector:
    """Continue connector identity plus the dev-data event parse surface.

    Trust tier T0 (file import). The live JSONL file-watch / HTTP-sink path and
    any Continue Hub API are deferred; this is the parse surface.
    """

    source_id = "continue_dev"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.PASSIVE}))

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_event(payload)]
