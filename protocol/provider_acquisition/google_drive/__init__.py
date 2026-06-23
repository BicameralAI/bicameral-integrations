# Copyright 2026 Bicameral AI — MIT License
"""Google Drive discovery connector (#179).

The Drive slice of the merged ``DiscoveryConnector`` surface (#178): shared-drive +
`.bicameral` project-folder discovery and document-leaf fetch, behind an injected
transport + an injected ``SecretResolver`` (the OAuth access-token provider — reused
from the runtime, no new type). Mocked/recorded: the live ``urllib`` transport and
OAuth refresh stay operator-side (`runtime.google_oauth.RefreshTokenSecretResolver`)
and are out of scope here (a mock never promotes to Live — ADR-0012 / factory#93).
"""

from __future__ import annotations

from .connector import GoogleDriveDiscoveryConnector
from .transport import DriveResponse, DriveTransport, RecordedTransport

__all__ = [
    "DriveResponse",
    "DriveTransport",
    "GoogleDriveDiscoveryConnector",
    "RecordedTransport",
]
