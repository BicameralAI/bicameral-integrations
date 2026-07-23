# SPDX-License-Identifier: MIT
"""Incremental GitHub issue ingest for the Bicameral alpha path.

GitHub-specific acquisition terminates at provider-neutral ``Observation`` values.
Every observation passes through the universal adapter normalizer and fail-open
heuristic evaluator before delivery through ``GatewaySink``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

from adapter.core.capabilities import SourceMode
from adapter.core.emissions import AdapterEmission, SourceRef
from adapter.core.observations import Observation
from adapter.core.pipeline import normalize
from runtime.cursor_policy import CursorAction, CursorVerdict, resolve_cursor_action
from runtime.sinks import EmissionSink, GatewayEmissionError

from .auth import InstallationTokenProvider, reject_control_chars
from .transport import GitHubTransport

_MAX_TEXT = 32_000
_ADAPTER_VERSION = "github-issue-ingest/0.1.0"
_SUPPORTED_ACTIONS = {
    "issues": {"opened", "edited", "closed", "reopened"},
    "issue_comment": {"created", "edited", "deleted"},
}


class GitHubIngestError(RuntimeError):
    """Value-free ingest failure suitable for operator logs."""


class SignatureVerificationError(GitHubIngestError):
    """Webhook signature was missing or invalid."""


@dataclass(frozen=True)
class GitHubIssueCursor:
    repository_id: str
    updated_at: str = ""
    last_provider_event_id: str = ""
    schema_version: int = 1


class CursorStore(Protocol):
    def load(self, repository_id: str) -> GitHubIssueCursor: ...
    def save(self, cursor: GitHubIssueCursor) -> None: ...


class JsonCursorStore:
    """Atomic JSON cursor persistence, one file for all repositories."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise GitHubIngestError("cursor store is malformed")
        return raw

    def load(self, repository_id: str) -> GitHubIssueCursor:
        raw = self._read().get(repository_id)
        if not isinstance(raw, dict):
            return GitHubIssueCursor(repository_id=repository_id)
        return GitHubIssueCursor(
            repository_id=repository_id,
            updated_at=str(raw.get("updated_at", "")),
            last_provider_event_id=str(raw.get("last_provider_event_id", "")),
            schema_version=int(raw.get("schema_version", 1)),
        )

    def save(self, cursor: GitHubIssueCursor) -> None:
        state = self._read()
        state[cursor.repository_id] = asdict(cursor)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, sort_keys=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


def verify_webhook_signature(secret: str, body: bytes, signature_header: str) -> None:
    """Verify GitHub's ``sha256=<hex>`` signature in constant time."""
    reject_control_chars("webhook secret", secret)
    if not signature_header.startswith("sha256="):
        raise SignatureVerificationError("missing or malformed GitHub webhook signature")
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise SignatureVerificationError("invalid GitHub webhook signature")


def _bounded(value: Any) -> tuple[str, bool]:
    text = str(value or "")
    if len(text) <= _MAX_TEXT:
        return text, False
    return text[:_MAX_TEXT], True


def _digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _signal(
    code: str,
    basis: str,
    confidence: str,
    effect: str,
    explanation: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "scope": "integration",
        "basis": basis,
        "confidence": confidence,
        "recommended_effect": effect,
        "explanation": explanation,
        "schema_version": 1,
    }


def _integration_signals(actor_type: str, actor_login: str, body: str) -> list[dict[str, Any]]:
    """Derive GitHub-aware signals without suppressing source evidence."""
    signals: list[dict[str, Any]] = []
    login = actor_login.lower()
    lower = body.lower().strip()
    if actor_type == "Bot" or login.endswith("[bot]"):
        signals.append(
            _signal(
                "bot_authored",
                "github_actor_type_or_login_suffix",
                "high",
                "annotate",
                "GitHub identifies the source author as an automation identity.",
            )
        )
    if "dependabot" in login or "renovate" in login:
        signals.append(
            _signal(
                "dependency_automation",
                "github_known_dependency_automation_identity",
                "high",
                "rank_lower",
                "GitHub identifies the author as dependency automation.",
            )
        )
    if lower.startswith("<!--") or "issue template" in lower:
        signals.append(
            _signal(
                "template_dominant",
                "github_template_marker",
                "medium",
                "rank_lower",
                "GitHub issue-template markers dominate the captured body.",
            )
        )
    if lower in {"lgtm", "approved", "done", "fixed", "closed"}:
        signals.append(
            _signal(
                "status_only",
                "github_exact_status_vocabulary",
                "high",
                "rank_lower",
                "The GitHub body contains only a bounded status phrase.",
            )
        )
    return signals


def parse_webhook_observation(
    *,
    event_name: str,
    delivery_id: str,
    payload: dict[str, Any],
    mode: SourceMode = SourceMode.WEBHOOK,
) -> tuple[Observation, GitHubIssueCursor] | None:
    """Parse a supported GitHub event into the provider-neutral adapter input."""
    action = str(payload.get("action", ""))
    if action not in _SUPPORTED_ACTIONS.get(event_name, set()):
        return None
    repo = payload.get("repository") if isinstance(payload.get("repository"), dict) else {}
    issue = payload.get("issue") if isinstance(payload.get("issue"), dict) else {}
    comment = payload.get("comment") if isinstance(payload.get("comment"), dict) else None
    repository_id = str(repo.get("id", ""))
    full_name = str(repo.get("full_name", ""))
    issue_number = str(issue.get("number", ""))
    if not repository_id or not full_name or not issue_number or not delivery_id:
        raise GitHubIngestError("GitHub webhook is missing stable identifiers")

    source = comment or issue
    source_kind = "issue_comment" if comment is not None else "issue"
    source_id = str(source.get("id", ""))
    node_id = str(source.get("node_id", ""))
    updated_at = str(source.get("updated_at") or issue.get("updated_at") or "")
    html_url = str(source.get("html_url") or issue.get("html_url") or "")
    actor = source.get("user") if isinstance(source.get("user"), dict) else {}
    author = str(actor.get("login", ""))
    actor_type = str(actor.get("type", ""))
    raw_body = "" if action == "deleted" else source.get("body", "")
    body, truncated = _bounded(raw_body)
    title, title_truncated = _bounded(issue.get("title", ""))
    version = _digest(source_kind, source_id, node_id, action, updated_at, title, body)
    resource_ref = f"{full_name}#issues/{issue_number}"
    object_ref = f"{resource_ref}:{source_kind}:{source_id}:v:{version}"

    if action == "deleted":
        content = f"GitHub {source_kind} {source_id} was deleted or became unavailable."
        observation_title = f"GitHub issue #{issue_number}: source unavailable"
    else:
        content = body or title or f"GitHub {source_kind} {source_id}"
        observation_title = title or f"GitHub issue #{issue_number} {action}"

    metadata = {
        "repository_id": repository_id,
        "repository_full_name": full_name,
        "issue_number": issue_number,
        "issue_id": str(issue.get("id", "")),
        "comment_id": source_id if comment is not None else "",
        "event_name": event_name,
        "action": action,
        "source_version": version,
        "content_truncated": truncated,
        "title_truncated": title_truncated,
        "tombstone": action == "deleted",
        "actor_login": author,
        "actor_type": actor_type,
        "advisory_signals": _integration_signals(actor_type, author, body),
    }
    observation = Observation(
        source_ref=SourceRef(
            source_id="github",
            ref=object_ref,
            url=html_url,
            kind=source_kind,
        ),
        excerpt=content,
        mode=mode,
        title=observation_title,
        author=author,
        timestamp=updated_at,
        provider_event_id=delivery_id,
        provider_resource_id=f"{source_kind}:{source_id}",
        evidence_id=f"github:{repository_id}:{source_kind}:{source_id}:{version}",
        evidence_metadata=metadata,
        metadata=metadata,
    )
    return observation, GitHubIssueCursor(
        repository_id=repository_id,
        updated_at=updated_at,
        last_provider_event_id=delivery_id,
    )


def normalize_webhook(
    *,
    event_name: str,
    delivery_id: str,
    payload: dict[str, Any],
    mode: SourceMode = SourceMode.WEBHOOK,
) -> tuple[AdapterEmission, GitHubIssueCursor] | None:
    """Parse and normalize GitHub input through the universal adapter seam."""
    parsed = parse_webhook_observation(
        event_name=event_name,
        delivery_id=delivery_id,
        payload=payload,
        mode=mode,
    )
    if parsed is None:
        return None
    observation, cursor = parsed
    return normalize([observation], adapter_version=_ADAPTER_VERSION)[0], cursor


class GitHubIssueIngestRuntime:
    """Webhook and polling runtime with two-phase cursor advancement."""

    def __init__(
        self,
        *,
        transport: GitHubTransport,
        token_provider: InstallationTokenProvider,
        sink: EmissionSink,
        cursor_store: CursorStore,
    ) -> None:
        self._transport = transport
        self._tokens = token_provider
        self._sink = sink
        self._cursors = cursor_store

    def ingest_webhook(
        self,
        *,
        secret: str,
        signature_header: str,
        event_name: str,
        delivery_id: str,
        body: bytes,
    ) -> CursorAction | None:
        verify_webhook_signature(secret, body, signature_header)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise GitHubIngestError("GitHub webhook payload must be an object")
        normalized = normalize_webhook(
            event_name=event_name,
            delivery_id=delivery_id,
            payload=payload,
        )
        if normalized is None:
            return None
        emission, proposed_cursor = normalized
        return self._emit_and_commit([emission], proposed_cursor)

    def poll_backfill(
        self,
        *,
        installation_id: str,
        repository_full_name: str,
        repository_id: str,
    ) -> CursorAction:
        token = self._tokens.installation_token(installation_id=installation_id)
        if not token:
            raise GitHubIngestError("missing GitHub App installation token")
        reject_control_chars("installation token", token)
        cursor = self._cursors.load(repository_id)
        path = f"/repos/{repository_full_name}/issues?state=all&sort=updated&direction=asc"
        if cursor.updated_at:
            path += f"&since={cursor.updated_at}"
        response = self._transport.request(
            "GET",
            path,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )
        if response.status != 200:
            return resolve_cursor_action(status=response.status, reason="github_poll_failed")
        rows = response.json if isinstance(response.json, list) else []
        emissions: list[AdapterEmission] = []
        proposed = cursor
        for row in rows:
            if not isinstance(row, dict) or "pull_request" in row:
                continue
            delivery = f"poll:{repository_id}:issue:{row.get('id')}:{row.get('updated_at')}"
            normalized = normalize_webhook(
                event_name="issues",
                delivery_id=delivery,
                payload={
                    "action": "edited",
                    "repository": {
                        "id": repository_id,
                        "full_name": repository_full_name,
                    },
                    "issue": row,
                },
                mode=SourceMode.ACTIVE,
            )
            if normalized is None:
                continue
            emission, proposed = normalized
            emissions.append(emission)
        if not emissions:
            return resolve_cursor_action(status=201)
        return self._emit_and_commit(emissions, proposed)

    def _emit_and_commit(
        self,
        emissions: Iterable[AdapterEmission],
        proposed_cursor: GitHubIssueCursor,
    ) -> CursorAction:
        try:
            self._sink.emit(list(emissions))
        except GatewayEmissionError as exc:
            return resolve_cursor_action(error=exc)
        action = resolve_cursor_action(status=201)
        if action.verdict is CursorVerdict.ADVANCE:
            self._cursors.save(proposed_cursor)
        return action
