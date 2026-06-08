"""Devin connector: agentic-session evidence into neutral Observations.

The Devin v3 API (``GET /v3/organizations/{org}/sessions``, Bearer ``cog_`` key) wraps
session objects under ``items`` (verified docs.devin.ai). ``parse_session`` maps a session
(``session_id`` / ``title`` / ``status`` / ``structured_output`` / ``pull_requests``) into an
Observation; free-text (``title`` / ``structured_output``) passes through
``adapter.core.redaction.redact`` because the session trail may carry secrets/PII. The first
``pull_requests[].pr_url`` is kept as the artifact location (consistent with github/gitlab/jira).
Poll-only — no webhooks; the live REST poll (cursor pagination ``after``/``end_cursor``/
``has_next_page``) + token resolution stay in the operator runtime (see ``auth.md``).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.redaction import redact


def _session_body(session: dict) -> str:
    """Join the session's free-text fields (status / title / structured output)."""
    status = (session.get("status") or session.get("status_enum") or "").strip()
    output = session.get("structured_output")
    parts: list[str] = []
    if status:
        parts.append(f"[{status}]")
    title = (session.get("title") or "").strip()
    if title:
        parts.append(title)
    if output:
        parts.append(output if isinstance(output, str) else str(output))
    return " ".join(parts)


def _first_pr_url(session: dict) -> str:
    """First pull-request URL from the verified `pull_requests` array (`[{pr_url, pr_state}]`).

    docs.devin.ai (2026-06-08): the session object carries `pull_requests` (array), not a
    singular `pull_request.url`. Tolerates non-list / non-dict entries (untrusted boundary).
    """
    prs = session.get("pull_requests")
    if not isinstance(prs, list):
        return ""
    for pr in prs:
        if isinstance(pr, dict) and isinstance(pr.get("pr_url"), str) and pr["pr_url"]:
            return pr["pr_url"]
    return ""


def parse_session(session: dict) -> Observation:
    """Map a Devin v3 session object into a redacted, provider-neutral Observation."""
    sid = (session.get("session_id") or "").strip()  # `devin_id` is not a list-object field
    pr = _first_pr_url(session)
    return Observation(
        source_ref=SourceRef(
            source_id="devin",
            ref=sid or "devin-session",
            url=pr,
            kind="session",
        ),
        excerpt=redact(_session_body(session)) or "devin-session",
        mode=SourceMode.ACTIVE,
        title=redact((session.get("title") or "").strip()),
    )


class DevinConnector:
    """Devin connector identity plus the session parse surface (active poll only)."""

    source_id = "devin"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.ACTIVE}))

    def can_handle_ref(self, ref: SourceRef) -> bool:
        return ref.source_id == "devin"

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_session(payload)]
