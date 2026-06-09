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
    """Resolve a secret by its **credential key**. Operator runtime supplies the real one.

    The argument is the credential **key** — for a single-secret connector that is its ``source_id``
    (e.g. ``"google_drive"``); a multi-credential connector uses **namespaced** keys
    ``<connector>[_<purpose>]`` (e.g. ``"linear"`` for the API key + ``"linear_webhook"`` for the webhook
    signing secret). Keys are globally unique (``load_config`` rejects a cross-connector duplicate).
    ``FileSecretResolver`` resolves env ``BICAMERAL_<KEY>`` then the file (FX-RUNTIME-004/005)."""

    def resolve(self, connector_id: str) -> str: ...


class MappingSecretResolver:
    """Reference resolver over an injected mapping ('' for unknown connector ids)."""

    def __init__(self, secrets: dict[str, str]) -> None:
        self._secrets = dict(secrets)

    def resolve(self, connector_id: str) -> str:
        return self._secrets.get(connector_id, "")
