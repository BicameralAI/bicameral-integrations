# SPDX-License-Identifier: MIT
"""Secret and authority-boundary guard tests for provider acquisition fixtures.

Proves that golden fixtures:
1. Do not contain token/secret/credential material.
2. Do not contain bot authority fields (SourceBinding, SourceSnapshot,
   DecisionCandidate, review commands, local actor authority, event-store
   write intent).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES_DIR = _ROOT / "fixtures"
_ALL_FIXTURES = sorted(_FIXTURES_DIR.rglob("*.json"))

# ---------------------------------------------------------------------------
# Secret/credential detection patterns (mirrors adapter/core/sensitive.py)
# ---------------------------------------------------------------------------

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    # GitHub tokens
    re.compile(r"ghp_[A-Za-z0-9]{36,}"),
    re.compile(r"ghs_[A-Za-z0-9]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9]{20,}"),
    # AWS keys
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"(?i)aws[_\-]?secret[_\-]?access[_\-]?key"),
    # Private keys
    re.compile(r"-----BEGIN\s+(RSA|EC|DSA|OPENSSH|PGP)?\s*PRIVATE KEY-----"),
    # Slack tokens
    re.compile(r"xox[bpas]-[A-Za-z0-9\-]{10,}"),
    # Google API keys
    re.compile(r"AIzaSy[A-Za-z0-9\-_]{33}"),
    # Stripe keys
    re.compile(r"sk_live_[A-Za-z0-9]{20,}"),
    # GitLab tokens
    re.compile(r"glpat-[A-Za-z0-9]{20,}"),
    # npm tokens
    re.compile(r"npm_[A-Za-z0-9]{36,}"),
    # OpenAI keys
    re.compile(r"sk-[A-Za-z0-9]{40,}"),
    # Generic key=value patterns with credential-like keys
    re.compile(
        r"(?i)(api[_\-]?key|api[_\-]?secret|auth[_\-]?token|access[_\-]?token)\s*[:=]\s*['\"]?[A-Za-z0-9\-_]{16,}"
    ),
    # OAuth secrets
    re.compile(r"(?i)client[_\-]?secret\s*[:=]\s*['\"]?[A-Za-z0-9\-_]{16,}"),
    # Bearer tokens in content
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_.]{20,}"),
]

# ---------------------------------------------------------------------------
# Bot authority fields that must NOT appear in provider-fact fixtures
# ---------------------------------------------------------------------------

_FORBIDDEN_AUTHORITY_FIELDS = {
    # Bot lifecycle / governance authority
    "source_binding",
    "SourceBinding",
    "source_snapshot",
    "SourceSnapshot",
    "source_evidence",
    "SourceEvidence",
    "decision_candidate",
    "DecisionCandidate",
    "decision",
    "Decision",
    "review_command",
    "review_commands",
    "signoff",
    "signoff_state",
    "SignoffState",
    "compliance_state",
    "ComplianceState",
    "tracking_state",
    "TrackingState",
    # Local actor authority
    "authority_context",
    "AuthorityContext",
    "actor_id",
    "session_id",
    "workspace_id",
    # Event-store write intent
    "event_store_write",
    "write_intent",
    "append_event",
    "store_event",
    # Tool authority
    "tool_request",
    "ToolRequest",
    "external_ingest_envelope",
    "ExternalIngestEnvelope",
}

# Fields that indicate forbidden content in string values
_FORBIDDEN_CONTENT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)source\s*binding"),
    re.compile(r"(?i)decision\s*candidate"),
    re.compile(r"(?i)event.store\s*write"),
    re.compile(r"(?i)review\s*command"),
    re.compile(r"(?i)signoff\s*approv"),
    re.compile(r"(?i)compliance\s*resolv"),
]


def _all_string_values(obj: object, prefix: str = "") -> list[tuple[str, str]]:
    """Recursively extract all string values with their JSON path."""
    results: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, str):
                results.append((path, v))
            else:
                results.extend(_all_string_values(v, path))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            path = f"{prefix}[{i}]"
            if isinstance(v, str):
                results.append((path, v))
            else:
                results.extend(_all_string_values(v, path))
    return results


def _all_keys(obj: object) -> set[str]:
    """Recursively collect all dictionary keys."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys.update(_all_keys(v))
    elif isinstance(obj, list):
        for v in obj:
            keys.update(_all_keys(v))
    return keys


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoSecretMaterial:
    """Fixtures must not contain tokens, secrets, credentials, or PII."""

    @pytest.mark.parametrize(
        "fixture_path",
        _ALL_FIXTURES,
        ids=[str(p.relative_to(_FIXTURES_DIR)) for p in _ALL_FIXTURES],
    )
    def test_no_secret_patterns(self, fixture_path: Path) -> None:
        raw_text = fixture_path.read_text(encoding="utf-8")
        for pattern in _SECRET_PATTERNS:
            match = pattern.search(raw_text)
            assert match is None, (
                f"{fixture_path.name}: secret pattern matched at "
                f"'{match.group()}' (pattern: {pattern.pattern})"
            )

    @pytest.mark.parametrize(
        "fixture_path",
        _ALL_FIXTURES,
        ids=[str(p.relative_to(_FIXTURES_DIR)) for p in _ALL_FIXTURES],
    )
    def test_no_credential_field_names(self, fixture_path: Path) -> None:
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        keys = _all_keys(data)
        credential_keys = {
            "api_token",
            "api_key",
            "access_token",
            "refresh_token",
            "secret_key",
            "private_key",
            "oauth_client_secret",
            "password",
            "bearer_token",
            "service_account_key",
        }
        found = keys & credential_keys
        assert not found, (
            f"{fixture_path.name}: credential field names present: {found}"
        )


class TestNoBotAuthorityFields:
    """Fixtures must not contain bot authority fields or governance objects."""

    @pytest.mark.parametrize(
        "fixture_path",
        _ALL_FIXTURES,
        ids=[str(p.relative_to(_FIXTURES_DIR)) for p in _ALL_FIXTURES],
    )
    def test_no_forbidden_keys(self, fixture_path: Path) -> None:
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        keys = _all_keys(data)
        found = keys & _FORBIDDEN_AUTHORITY_FIELDS
        assert not found, (
            f"{fixture_path.name}: forbidden authority fields present: {found}"
        )

    @pytest.mark.parametrize(
        "fixture_path",
        _ALL_FIXTURES,
        ids=[str(p.relative_to(_FIXTURES_DIR)) for p in _ALL_FIXTURES],
    )
    def test_no_authority_content_in_values(self, fixture_path: Path) -> None:
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        # Skip _comment and _authority_boundary fields (documentation only)
        filtered = {k: v for k, v in data.items() if not k.startswith("_")}
        values = _all_string_values(filtered)
        violations: list[str] = []
        for path, value in values:
            for pattern in _FORBIDDEN_CONTENT_PATTERNS:
                if pattern.search(value):
                    violations.append(
                        f"{path}: matched '{pattern.pattern}' in '{value[:80]}'"
                    )
        assert not violations, (
            f"{fixture_path.name}: authority content found:\n" + "\n".join(violations)
        )
