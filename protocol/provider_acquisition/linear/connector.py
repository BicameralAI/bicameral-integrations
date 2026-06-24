# Copyright 2026 Bicameral AI — MIT License
"""Linear GraphQL discovery connector (ADR-0017 alpha 3/3).

Satisfies the merged ``DiscoveryConnector`` contract (#178) for Linear: workspace →
team → project → issue discovery (`list_resources` dispatches by ``config``) and
issue/comment item fetch. Thin by design — resolve the API key via the injected
``SecretResolver`` (reused; no new type), execute a GraphQL operation through the
injected transport, classify GraphQL errors (``errors.py``), map (``mapping.py``),
screen fail-closed (``screening.py``), and return a typed ``DiscoveryOutcome``.

``create_provider_resource`` is **absent** — provider writes are egress territory.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from adapter.core.capabilities import SourceCapabilities, SourceMode

from ..screening import DiscoveryScreenError, screen_descriptor, screen_item
from ..types import (
    DiscoveryError,
    DiscoveryErrorKind,
    DiscoveryOutcome,
    ProviderItemEnvelope,
    ProviderResourceDescriptor,
)
from . import mapping, queries
from .auth import build_auth_headers
from .errors import error_from_graphql
from .transport import LinearTransport

_PAGE = 50
_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")  # guards an id before it enters a query variable


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _d(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


_NOT_FOUND = DiscoveryError(kind=DiscoveryErrorKind.NOT_FOUND, message="Linear resource not found")
_BAD_ID = DiscoveryError(
    kind=DiscoveryErrorKind.UNSUPPORTED,
    message="malformed resource id",
    action_hint="Ids must match [A-Za-z0-9_-]{1,128}.",
)


class LinearDiscoveryConnector:
    """Linear discovery over an injected GraphQL transport + ``SecretResolver`` (API key).

    ``config`` carries non-secret routing: optional ``team_id`` (→ projects) / ``project_id``
    (→ issues). The API key is resolved per call — never in ``config``.
    """

    source_id = "linear"

    def __init__(
        self,
        *,
        transport: LinearTransport,
        secrets: Any,  # runtime.secrets.SecretResolver (duck-typed: .resolve(id) -> str)
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.capabilities = SourceCapabilities(modes=frozenset({SourceMode.DISCOVERY}))
        self._transport = transport
        self._secrets = secrets
        self._clock = clock or _now_iso

    def _screened(
        self, obj: ProviderResourceDescriptor | ProviderItemEnvelope
    ) -> DiscoveryError | None:
        try:
            screen_item(obj) if isinstance(obj, ProviderItemEnvelope) else screen_descriptor(obj)
        except DiscoveryScreenError as exc:
            return DiscoveryError(
                kind=DiscoveryErrorKind.PROVIDER_ERROR,
                message=f"discovery object failed sensitive-data screen ({exc})",
            )
        return None

    def _execute(
        self, operation: str, query: str, variables: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, DiscoveryError | None]:
        """Execute one GraphQL op → ``(data, None)`` on clean 200, else ``(None, typed-error)``.

        Auth is checked here (missing key → typed error). A non-200 status OR a non-empty
        ``errors`` array is a failure (GraphQL never emits a partial — ``graphql_poll``).
        """
        _, auth_err = build_auth_headers(self._secrets)
        if auth_err is not None:
            return None, auth_err
        resp = self._transport.execute(operation=operation, query=query, variables=variables)
        if resp.status != 200 or resp.errors:
            return None, error_from_graphql(resp.status, resp.errors)
        return (resp.data if isinstance(resp.data, dict) else {}), None

    def _collect(
        self, descriptors: list[ProviderResourceDescriptor]
    ) -> DiscoveryOutcome[list[ProviderResourceDescriptor]]:
        for desc in descriptors:
            if (screen_err := self._screened(desc)) is not None:
                return DiscoveryOutcome(error=screen_err)
        return DiscoveryOutcome(value=descriptors)

    def _emit(
        self, obj: ProviderResourceDescriptor | ProviderItemEnvelope
    ) -> DiscoveryOutcome[Any]:
        screen_err = self._screened(obj)
        return DiscoveryOutcome(error=screen_err) if screen_err else DiscoveryOutcome(value=obj)

    # -- list_resources -----------------------------------------------------

    def list_resources(
        self, *, config: dict[str, Any]
    ) -> DiscoveryOutcome[list[ProviderResourceDescriptor]]:
        if project_id := config.get("project_id"):
            return self._list_issues(str(project_id))
        if team_id := config.get("team_id"):
            return self._list_projects(str(team_id))
        return self._list_teams()

    def _list_teams(self) -> DiscoveryOutcome[list[ProviderResourceDescriptor]]:
        data, err = self._execute("Teams", queries.TEAMS, {"first": _PAGE})
        if err is not None:
            return DiscoveryOutcome(error=err)
        org = _d((data or {}).get("organization"))
        captured = self._clock()
        return self._collect([
            mapping.map_team(
                t, ws_url_key=str(org.get("urlKey", "")), ws_name=str(org.get("name", "")),
                captured_at=captured,
            )
            for t in _d((data or {}).get("teams")).get("nodes", []) if isinstance(t, dict)
        ])

    def _list_projects(self, team_id: str) -> DiscoveryOutcome[list[ProviderResourceDescriptor]]:
        if not _ID_RE.fullmatch(team_id):
            return DiscoveryOutcome(error=_BAD_ID)
        data, err = self._execute("Projects", queries.PROJECTS, {"id": team_id, "first": _PAGE})
        if err is not None:
            return DiscoveryOutcome(error=err)
        team = (data or {}).get("team")
        if not isinstance(team, dict):
            return DiscoveryOutcome(error=_NOT_FOUND)
        url_key = str(_d((data or {}).get("organization")).get("urlKey", ""))
        captured = self._clock()
        return self._collect([
            mapping.map_project(p, team_id=str(team.get("id", "")), ws_url_key=url_key, captured_at=captured)
            for p in _d(team.get("projects")).get("nodes", []) if isinstance(p, dict)
        ])

    def _list_issues(self, project_id: str) -> DiscoveryOutcome[list[ProviderResourceDescriptor]]:
        if not _ID_RE.fullmatch(project_id):
            return DiscoveryOutcome(error=_BAD_ID)
        data, err = self._execute("Issues", queries.ISSUES, {"id": project_id, "first": _PAGE})
        if err is not None:
            return DiscoveryOutcome(error=err)
        project = (data or {}).get("project")
        if not isinstance(project, dict):
            return DiscoveryOutcome(error=_NOT_FOUND)
        team_id = str(_d(project.get("team")).get("id", ""))
        captured = self._clock()
        return self._collect([
            mapping.map_issue_descriptor(i, team_id=team_id, captured_at=captured)
            for i in _d(project.get("issues")).get("nodes", []) if isinstance(i, dict)
        ])

    # -- get_resource / validate_resource_access ----------------------------

    def get_resource(
        self, *, config: dict[str, Any], resource_id: str
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        return self._descriptor_by_id(resource_id)

    def validate_resource_access(
        self, *, config: dict[str, Any], resource_id: str
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        return self._descriptor_by_id(resource_id)

    def _descriptor_by_id(
        self, resource_id: str
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        captured = self._clock()
        if resource_id.startswith("ws_"):
            data, err = self._execute("Org", queries.ORG)
            if err is not None:
                return DiscoveryOutcome(error=err)
            return self._emit(mapping.map_workspace(_d((data or {}).get("organization")), captured_at=captured))
        prefix_map = {
            "team_": ("Team", queries.TEAM),
            "proj_": ("Project", queries.PROJECT),
            "issue_": ("Issue", queries.ISSUE),
        }
        for prefix, (operation, query) in prefix_map.items():
            if resource_id.startswith(prefix):
                node_id = resource_id[len(prefix):]
                if not _ID_RE.fullmatch(node_id):
                    return DiscoveryOutcome(error=_BAD_ID)
                data, err = self._execute(operation, query, {"id": node_id})
                if err is not None:
                    return DiscoveryOutcome(error=err)
                desc = mapping.descriptor_from_node(prefix, _d(data), captured_at=captured)
                return self._emit(desc) if desc is not None else DiscoveryOutcome(error=_NOT_FOUND)
        return DiscoveryOutcome(
            error=DiscoveryError(
                kind=DiscoveryErrorKind.UNSUPPORTED,
                message=f"unsupported resource id {resource_id!r}",
                action_hint="Resource ids must be 'ws_*', 'team_*', 'proj_*', or 'issue_*'.",
            )
        )

    # -- fetch_provider_item ------------------------------------------------

    def fetch_provider_item(
        self, *, config: dict[str, Any], resource_id: str, item_id: str
    ) -> DiscoveryOutcome[ProviderItemEnvelope]:
        fetched = self._clock()
        if item_id.startswith("issue_") or item_id.startswith("comment_"):
            is_issue = item_id.startswith("issue_")
            node_id = item_id[len("issue_" if is_issue else "comment_"):]
            if not _ID_RE.fullmatch(node_id):
                return DiscoveryOutcome(error=_BAD_ID)
            operation, query = ("Issue", queries.ISSUE) if is_issue else ("Comment", queries.COMMENT)
            data, err = self._execute(operation, query, {"id": node_id})
            if err is not None:
                return DiscoveryOutcome(error=err)
            node = (data or {}).get("issue" if is_issue else "comment")
            if not isinstance(node, dict):
                return DiscoveryOutcome(error=_NOT_FOUND)
            item = (
                mapping.map_issue_item(node, resource_id=resource_id, fetched_at=fetched)
                if is_issue
                else mapping.map_comment_item(node, fetched_at=fetched)
            )
            return self._emit(item)
        return DiscoveryOutcome(
            error=DiscoveryError(
                kind=DiscoveryErrorKind.UNSUPPORTED,
                message=f"unsupported item kind for id {item_id!r}",
                action_hint="Item ids must be 'issue_<id>' or 'comment_<id>'.",
            )
        )
