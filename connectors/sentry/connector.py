# SPDX-License-Identifier: MIT
"""Sentry connector: issue webhook events into neutral Observations.

A Sentry issue webhook payload (the `installation`/issue-alert event wrapping
`data.issue`) maps to one provider-neutral Observation (trust tier T1, runtime
error/issue evidence). The live Events-API receipt and `Sentry-Hook-Signature`
verification are deferred (see ``auth.md``); this is the parse surface only.
Read-only evidence, no canonical writes (ADR-0008).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def _text(value: object) -> str:
    """A stripped string for str inputs, else '' (wire payloads carry any type)."""
    return value.strip() if isinstance(value, str) else ""


def parse_issue(event: dict) -> Observation:
    """Map a Sentry issue webhook event into a provider-neutral Observation.

    Unwraps the ``data.issue`` envelope when present; falls back to treating the
    payload as a bare issue object. Defends on absent/wrong-typed fields.
    """
    data = event.get("data")
    issue = data.get("issue") if isinstance(data, dict) else None
    issue = issue if isinstance(issue, dict) else event
    iid = str(issue.get("id") or "sentry-issue")
    title = _text(issue.get("title"))
    culprit = _text(issue.get("culprit"))
    short = str(issue.get("shortId") or "")
    return Observation(
        source_ref=SourceRef(
            source_id="sentry", ref=iid, url=issue.get("permalink") or "", kind="issue"
        ),
        excerpt=title or culprit or short or iid,
        mode=SourceMode.WEBHOOK,
        title=title or short or iid,
        timestamp=str(issue.get("firstSeen") or ""),
        metadata={
            "action": event.get("action") or "",
            "level": issue.get("level") or "",
            "status": issue.get("status") or "",
            "short_id": short,
        },
    )


class SentryConnector:
    """Sentry connector identity plus the issue-event parse surface.

    Trust tier T1. The live Events-API receipt + `Sentry-Hook-Signature`
    verification path is deferred; this is the parse surface.
    """

    source_id = "sentry"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.WEBHOOK}))

    def observations(self, payload: dict) -> list[Observation]:
        return [parse_issue(payload)]
