# SPDX-License-Identifier: MIT
"""Secret resolution for the operator-runtime boundary (ADR-0012).

Secrets are NEVER stored in this package. The operator runtime supplies a real
keyring-backed resolver; ``MappingSecretResolver`` is a reference implementation
(over an injected mapping) for tests + the Beta stage.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretResolver(Protocol):
    """Resolve a connector's webhook/API secret. Operator runtime supplies the real one."""

    def resolve(self, connector_id: str) -> str: ...


class MappingSecretResolver:
    """Reference resolver over an injected mapping ('' for unknown connector ids)."""

    def __init__(self, secrets: dict[str, str]) -> None:
        self._secrets = dict(secrets)

    def resolve(self, connector_id: str) -> str:
        return self._secrets.get(connector_id, "")
