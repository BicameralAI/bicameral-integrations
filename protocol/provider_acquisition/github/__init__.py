# Copyright 2026 Bicameral AI — MIT License
"""GitHub App installation discovery connector (#180).

The first live GitHub provider-acquisition slice — GitHub App **installation auth
only**, behind the merged ``DiscoveryConnector`` surface (#178). This package ships
the mocked/recorded implementation: the live ``urllib`` transport and the App
private-key handling stay hosted-side (BicameralAI/bicameral-cloud#7) and are out
of scope here (a mock never promotes to Live — ADR-0012 / ADR-0017 §6).
"""

from __future__ import annotations

from .auth import (
    GitHubAuthError,
    InstallationTokenProvider,
    MappingInstallationTokenProvider,
)
from .connector import GitHubDiscoveryConnector
from .transport import GitHubResponse, GitHubTransport, RecordedTransport

__all__ = [
    "GitHubAuthError",
    "GitHubDiscoveryConnector",
    "GitHubResponse",
    "GitHubTransport",
    "InstallationTokenProvider",
    "MappingInstallationTokenProvider",
    "RecordedTransport",
]
