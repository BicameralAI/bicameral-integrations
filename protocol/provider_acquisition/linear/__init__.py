# Copyright 2026 Bicameral AI — MIT License
"""Linear discovery connector (ADR-0017 alpha provider 3/3).

The Linear slice of the merged ``DiscoveryConnector`` surface (#178): workspace →
team → project → issue discovery and issue/comment item fetch, over Linear's GraphQL
API. Mocked/recorded — the live GraphQL POST stays operator-side and is out of scope
(a mock never promotes to Live — ADR-0012). Reuses the runtime ``SecretResolver`` as
the API-key provider (no new type) and ``screening.py``.
"""

from __future__ import annotations

from .connector import LinearDiscoveryConnector
from .transport import LinearResponse, LinearTransport, RecordedTransport

__all__ = [
    "LinearDiscoveryConnector",
    "LinearResponse",
    "LinearTransport",
    "RecordedTransport",
]
