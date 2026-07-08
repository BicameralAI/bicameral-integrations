# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""GitHub App installation discovery connector (#180).

Satisfies the merged ``DiscoveryConnector`` contract (#178) for GitHub, using
**installation auth only**. Thin by design: resolve the installation token, route
the logical GitHub REST call through an injected transport, map the response to a
neutral object (``mapping.py``), screen it fail-closed (``screening.py``), and
return a typed ``DiscoveryOutcome``. Provider mechanics live in ``mapping``;
secrets live behind the injected token provider (cloud#7).

``create_provider_resource`` is **absent** — provider writes are egress /
proposed-action territory (ADR-0008 / ADR-0017 §4), not discovery.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from adapter.core.capabilities import SourceCapabilities, SourceMode

from ..screening import DiscoveryScreenError, screen_descriptor, screen_item
from ..types import (
    DiscoveryError,
    DiscoveryErrorKind,
    DiscoveryOutcome,
    PermissionState,
    ProviderItemEnvelope,
    ProviderResourceDescriptor,
)
from . import mapping
from .auth import GitHubAuthError, InstallationTokenProvider, reject_control_chars
from .errors import error_from_status
from .transport import GitHubTransport

_OK = 200
_REPOS_PATH = "/installation/repositories"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GitHubDiscoveryConnector:
    """GitHub discovery over an injected transport + installation-token provider.

    ``config`` carries the non-secret ``installation_id`` (which installation to
    act as) and an optional ``cursor`` for repository listing. The token itself is
    never in ``config`` — it is resolved from the provider per call.
    """

    source_id = "github"

    def __init__(
        self,
        *,
        transport: GitHubTransport,
        token_provider: InstallationTokenProvider,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.capabilities = SourceCapabilities(modes=frozenset({SourceMode.DISCOVERY}))
        self._transport = transport
        self._tokens = token_provider
        self._clock = clock or _now_iso

    # -- auth ---------------------------------------------------------------

    def _auth_headers(
        self, config: dict[str, Any]
    ) -> tuple[dict[str, str] | None, DiscoveryError | None]:
        installation_id = config.get("installation_id")
        if not installation_id:
            return None, DiscoveryError(
                kind=DiscoveryErrorKind.ACTION_NEEDED,
                message="missing GitHub App installation",
                permission_state=PermissionState.ACTION_NEEDED,
                action_hint="Install the Bicameral GitHub App for this account.",
            )
        token = self._tokens.installation_token(installation_id=str(installation_id))
        if not token:
            return None, DiscoveryError(
                kind=DiscoveryErrorKind.ACTION_NEEDED,
                message="missing installation credentials",
                permission_state=PermissionState.ACTION_NEEDED,
                action_hint="The installation token broker has no token (cloud#7).",
            )
        try:
            reject_control_chars("installation token", token)
        except GitHubAuthError:
            return None, DiscoveryError(
                kind=DiscoveryErrorKind.ACTION_NEEDED,
                message="malformed installation credentials",
                permission_state=PermissionState.ACTION_NEEDED,
                action_hint="Regenerate the GitHub App installation token.",
            )
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }, None

    def _screened(
        self, obj: ProviderResourceDescriptor | ProviderItemEnvelope
    ) -> DiscoveryError | None:
        """Run the fail-closed screen; return a value-free error on a hit."""
        try:
            screen_item(obj) if isinstance(obj, ProviderItemEnvelope) else screen_descriptor(obj)
        except DiscoveryScreenError as exc:
            return DiscoveryError(
                kind=DiscoveryErrorKind.PROVIDER_ERROR,
                message=f"discovery object failed sensitive-data screen ({exc})",
            )
        return None

    # -- list_resources -----------------------------------------------------

    def list_resources(
        self, *, config: dict[str, Any]
    ) -> DiscoveryOutcome[list[ProviderResourceDescriptor]]:
        headers, auth_error = self._auth_headers(config)
        if auth_error is not None:
            return DiscoveryOutcome(error=auth_error)
        cursor = config.get("cursor")
        path = f"{_REPOS_PATH}?cursor={cursor}" if cursor else _REPOS_PATH
        resp = self._transport.request("GET", path, headers=headers or {})
        if resp.status != _OK:
            return DiscoveryOutcome(error=error_from_status(resp))
        captured_at = self._clock()
        body = resp.json if isinstance(resp.json, dict) else {}
        descriptors: list[ProviderResourceDescriptor] = []
        for repo in body.get("repositories", []):
            if not isinstance(repo, dict):
                continue
            desc = mapping.map_repository(repo, captured_at=captured_at)
            screen_error = self._screened(desc)
            if screen_error is not None:
                return DiscoveryOutcome(error=screen_error)
            descriptors.append(desc)
        return DiscoveryOutcome(value=descriptors)

    # -- get_resource / validate_resource_access ----------------------------

    def get_resource(
        self, *, config: dict[str, Any], resource_id: str
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        return self._repo_descriptor(config, resource_id)

    def validate_resource_access(
        self, *, config: dict[str, Any], resource_id: str
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        # Same provider call; a granted descriptor IS the access proof, and the
        # 401/403 mapping yields the action-needed / denied verdict.
        return self._repo_descriptor(config, resource_id)

    def _repo_descriptor(
        self, config: dict[str, Any], resource_id: str
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        headers, auth_error = self._auth_headers(config)
        if auth_error is not None:
            return DiscoveryOutcome(error=auth_error)
        owner_repo = "/".join(resource_id.split("/")[:2])
        resp = self._transport.request(
            "GET", f"/repos/{owner_repo}", headers=headers or {}
        )
        if resp.status != _OK:
            return DiscoveryOutcome(error=error_from_status(resp))
        repo = resp.json if isinstance(resp.json, dict) else {}
        desc = mapping.map_repository(repo, captured_at=self._clock())
        screen_error = self._screened(desc)
        if screen_error is not None:
            return DiscoveryOutcome(error=screen_error)
        return DiscoveryOutcome(value=desc)

    # -- fetch_provider_item ------------------------------------------------

    def fetch_provider_item(
        self, *, config: dict[str, Any], resource_id: str, item_id: str
    ) -> DiscoveryOutcome[ProviderItemEnvelope]:
        headers, auth_error = self._auth_headers(config)
        if auth_error is not None:
            return DiscoveryOutcome(error=auth_error)
        owner_repo = "/".join(resource_id.split("/")[:2])
        endpoint, mapper = self._item_route(owner_repo, item_id, resource_id)
        if endpoint is None:
            return DiscoveryOutcome(
                error=DiscoveryError(
                    kind=DiscoveryErrorKind.UNSUPPORTED,
                    message=f"unsupported item kind for id {item_id!r}",
                    action_hint="Item ids must be 'issue-<n>' or 'pr-<n>'.",
                )
            )
        resp = self._transport.request("GET", endpoint, headers=headers or {})
        if resp.status != _OK:
            return DiscoveryOutcome(error=error_from_status(resp))
        payload = resp.json if isinstance(resp.json, dict) else {}
        item = mapper(payload, resource_id=resource_id, fetched_at=self._clock())
        screen_error = self._screened(item)
        if screen_error is not None:
            return DiscoveryOutcome(error=screen_error)
        return DiscoveryOutcome(value=item)

    @staticmethod
    def _item_route(
        owner_repo: str, item_id: str, resource_id: str
    ) -> tuple[str | None, Any]:
        if item_id.startswith("issue-"):
            number = item_id[len("issue-"):]
            return f"/repos/{owner_repo}/issues/{number}", mapping.map_issue
        if item_id.startswith("pr-"):
            number = item_id[len("pr-"):]
            return f"/repos/{owner_repo}/pulls/{number}", mapping.map_pull_request
        return None, None
