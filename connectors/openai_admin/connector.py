"""OpenAI Admin connector: organization audit-log events into neutral Observations.

The Admin audit-logs API (``GET /v1/organization/audit_logs``, Bearer admin key) returns
governance/security events: ``{id, effective_at, type, project, actor, <type-detail>}``. The
EVENT (type + project + time) is the evidence; the ``actor`` is structured identity
(``actor.session.user.email``, ``actor.api_key.user.email``, ``actor.session.ip_address``,
user ids) and is **NEVER read** — only the non-PII ``actor.type`` (session/api_key) is
surfaced, allowlisted. FX-SEC-001 screens secret/PHI/PAN but NOT generic email/IP, so the
parse-time drop is the sole control for actor identity; the excerpt also passes through
``redact()`` defensively. Poll-only — no webhooks; the live REST poll + Bearer admin-key
resolution stay in the operator runtime (see ``auth.md``).
"""

from __future__ import annotations

import time

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.redaction import redact

_ACTOR_TYPES = frozenset({"session", "api_key"})


def _event_time(effective_at: object) -> str:
    """Format unix seconds as a UTC ISO string deterministically; ``''`` when absent/bad."""
    if not isinstance(effective_at, int):
        return ""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(effective_at))


def _actor_type(event: dict) -> str:
    """Non-PII actor kind (``session``/``api_key``), allowlisted; ``unknown`` otherwise."""
    actor = event.get("actor")
    kind = actor.get("type") if isinstance(actor, dict) else None
    return kind if kind in _ACTOR_TYPES else "unknown"


def parse_audit_log(event: dict) -> Observation:
    """Map an OpenAI audit-log event into a provider-neutral Observation.

    Identity is dropped: actor email / id / ip_address are NEVER read; only the
    non-PII actor type is surfaced. The excerpt is redacted defensively.
    """
    event_type = (event.get("type") or "").strip()
    project = event.get("project")
    name = (project.get("name") or project.get("id") or "") if isinstance(project, dict) else ""
    summary = f"OpenAI audit {event_type or 'event'}"
    if name:
        summary += f": project {name}"
    summary += f" via {_actor_type(event)}"
    when = _event_time(event.get("effective_at"))
    if when:
        summary += f" at {when}"
    return Observation(
        source_ref=SourceRef(
            source_id="openai_admin",
            ref=str(event.get("id") or "openai-audit-event"),
            kind="audit_event",
        ),
        excerpt=redact(summary) or "openai-audit-event",
        mode=SourceMode.ACTIVE,
        title=redact(f"OpenAI audit {event_type}".strip()),
    )


class OpenAIAdminConnector:
    """OpenAI Admin connector identity plus the audit-log parse surface (active poll only)."""

    source_id = "openai_admin"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.ACTIVE}))

    def can_handle_ref(self, ref: SourceRef) -> bool:
        return ref.source_id == "openai_admin"

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_audit_log(payload)]
