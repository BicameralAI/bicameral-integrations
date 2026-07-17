# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""GitHub App acquisition and incremental issue-ingest surfaces."""

from __future__ import annotations

from .auth import (
    GitHubAuthError,
    InstallationTokenProvider,
    MappingInstallationTokenProvider,
)
from .connector import GitHubDiscoveryConnector
from .ingest import (
    GitHubIngestError,
    GitHubIssueCursor,
    GitHubIssueIngestRuntime,
    JsonCursorStore,
    SignatureVerificationError,
    normalize_webhook,
    verify_webhook_signature,
)
from .transport import GitHubResponse, GitHubTransport, RecordedTransport

__all__ = [
    "GitHubAuthError",
    "GitHubDiscoveryConnector",
    "GitHubIngestError",
    "GitHubIssueCursor",
    "GitHubIssueIngestRuntime",
    "GitHubResponse",
    "GitHubTransport",
    "InstallationTokenProvider",
    "JsonCursorStore",
    "MappingInstallationTokenProvider",
    "RecordedTransport",
    "SignatureVerificationError",
    "normalize_webhook",
    "verify_webhook_signature",
]
