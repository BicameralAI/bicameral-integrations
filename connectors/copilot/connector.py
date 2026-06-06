"""GitHub Copilot connector: aggregate usage-metrics days into neutral Observations.

The Copilot metrics API (``GET /orgs/{org}/copilot/metrics``, also enterprise/team
scopes) returns a daily array of **aggregate, PII-free** objects: ``date``,
``total_active_users``, ``total_engaged_users``, and the breakdowns
``copilot_ide_code_completions`` / ``copilot_ide_chat`` / ``copilot_dotcom_chat`` /
``copilot_dotcom_pull_requests``. There is no per-developer identity in this surface.
``parse_metrics_day`` summarizes one day's aggregates into a review-evidence excerpt.
Poll-only — no webhooks for this data; the live REST poll + token
(``manage_billing:copilot`` / ``read:org``) resolution stay in the operator runtime
(see ``auth.md``). The newer per-user NDJSON "usage metrics" report API is deferred.
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def _count(value: object) -> str:
    """Render an integer count, or ``'?'`` when absent / non-int (no nested ternary)."""
    if isinstance(value, int):
        return str(value)
    return "?"


def _engaged(obj: object) -> str:
    """``total_engaged_users`` of a breakdown object as text, ``''`` when absent."""
    if not isinstance(obj, dict):
        return ""
    value = obj.get("total_engaged_users")
    if not isinstance(value, int):
        return ""
    return str(value)


def _summary(day: dict) -> str:
    """Concise PII-free evidence excerpt from one day's aggregate counts."""
    date = (day.get("date") or "").strip() or "metrics"
    segments = [
        f"Copilot {date}: {_count(day.get('total_active_users'))} active / "
        f"{_count(day.get('total_engaged_users'))} engaged users"
    ]
    breakdowns = (
        ("code-completions", day.get("copilot_ide_code_completions")),
        ("IDE chat", day.get("copilot_ide_chat")),
        ("dotcom chat", day.get("copilot_dotcom_chat")),
        ("PR summaries", day.get("copilot_dotcom_pull_requests")),
    )
    for label, obj in breakdowns:
        engaged = _engaged(obj)
        if engaged:
            segments.append(f"{label} {engaged} engaged")
    return "; ".join(segments)


def parse_metrics_day(day: dict) -> Observation:
    """Map one Copilot aggregate-metrics day into a provider-neutral Observation."""
    date = (day.get("date") or "").strip()
    return Observation(
        source_ref=SourceRef(
            source_id="copilot",
            ref=f"copilot:metrics:{date}" if date else "copilot-metrics",
            kind="usage_metrics",
        ),
        excerpt=_summary(day),
        mode=SourceMode.ACTIVE,
        title=f"Copilot usage metrics {date}".strip(),
    )


class CopilotConnector:
    """GitHub Copilot connector identity plus the aggregate-metrics parse surface.

    Active-poll only (no webhooks for this data). The metrics object is not
    URL-addressable, so ``can_handle_ref`` matches on ``source_id`` only. The live
    REST poll + token resolution are deferred to the operator runtime (``auth.md``).
    """

    source_id = "copilot"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.ACTIVE}))

    def can_handle_ref(self, ref: SourceRef) -> bool:
        return ref.source_id == "copilot"

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_metrics_day(payload)]
