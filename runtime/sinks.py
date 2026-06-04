# SPDX-License-Identifier: MIT
"""Emission sinks for the operator-runtime boundary (ADR-0012).

A connector's normalized ``AdapterEmission`` list is handed to an
``EmissionSink``. ``CollectingSink`` (in-memory) serves tests + the **Beta**
readiness stage. ``GatewaySink`` documents the production target
(``POST /api/v1/ingest``, the published v1 wire schema) but does **not** emit —
it raises ``GatewayEmissionGated``, because the gateway ingest guards are still
open (bicameral-bot #109) and the exact ``protocol/schemas/v1/`` field mapping
is pinned at the **Live** stage. Read-only evidence boundary (ADR-0008).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from adapter.core.emissions import AdapterEmission


class GatewayEmissionGated(RuntimeError):
    """Raised when ``GatewaySink.emit`` is called while live emission is gated."""


@runtime_checkable
class EmissionSink(Protocol):
    """Where normalized emissions go. The operator runtime supplies the real one."""

    def emit(self, emissions: list[AdapterEmission]) -> None: ...


class CollectingSink:
    """In-memory sink (tests + Beta): accumulates emissions in order."""

    def __init__(self) -> None:
        self.emissions: list[AdapterEmission] = []

    def emit(self, emissions: list[AdapterEmission]) -> None:
        self.emissions.extend(emissions)


class GatewaySink:
    """Production target (``POST /api/v1/ingest``, v1 schema) — a #109-gated stub.

    Does NOT emit: the gateway ingest guards (size/rate/prompt-injection/
    sensitive-data) are open as bicameral-bot #109, and the ``AdapterEmission`` →
    ``protocol/schemas/v1/`` field mapping is pinned at the Live stage. ``emit``
    raises so the gate is explicit, never a silent skip.
    """

    def __init__(self, *, endpoint: str = "", schema_version: str = "v1") -> None:
        self.endpoint = endpoint
        self.schema_version = schema_version

    def emit(self, emissions: list[AdapterEmission]) -> None:
        raise GatewayEmissionGated(
            "gateway emission gated on bicameral-bot #109 (ingest guards); "
            "AdapterEmission -> protocol/schemas/v1/ mapping is pinned at the Live stage"
        )
