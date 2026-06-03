"""GitHub pull-request connector: provider payloads into neutral Observations."""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def parse_pull_request(payload: dict) -> Observation:
    """Map a GitHub pull-request object into a provider-neutral Observation.

    The excerpt is the PR body, falling back to the title when the body is
    empty. Provider-specific field knowledge stays here; normalization into an
    AdapterEmission is the universal adapter's job (ADR-0004).
    """
    repo = payload.get("base", {}).get("repo", {}).get("full_name", "")
    number = payload.get("number", "")
    title = payload.get("title", "")
    body = payload.get("body", "") or ""
    return Observation(
        source_ref=SourceRef(
            source_id="github",
            ref=f"{repo}#{number}",
            url=payload.get("html_url", ""),
            kind="pull_request",
        ),
        excerpt=body or title,
        mode=SourceMode.ACTIVE,
        title=title,
        author=payload.get("user", {}).get("login", ""),
        timestamp=payload.get("merged_at", ""),
    )


class GitHubConnector:
    """GitHub connector identity plus the shared PR-payload parse surface.

    Declares GitHub's supported modes. The live ``fetch_active`` HTTP path and
    webhook signature verification are deferred (no live API this cycle); this
    connector provides the provider-neutral parse surface both modes will share.
    """

    source_id = "github"
    capabilities = SourceCapabilities(
        modes=frozenset({SourceMode.ACTIVE, SourceMode.WEBHOOK})
    )

    def can_handle_ref(self, ref: SourceRef) -> bool:
        return ref.source_id == "github" or "github.com" in ref.url

    def observations(self, payload: dict) -> list[Observation]:
        return [parse_pull_request(payload)]
