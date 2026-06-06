# SPDX-License-Identifier: MIT
"""Emission sinks for the operator-runtime boundary (ADR-0012).

A connector's normalized ``AdapterEmission`` list is handed to an
``EmissionSink``. ``CollectingSink`` (in-memory) serves tests + the **Beta**
readiness stage. ``GatewaySink`` is the **Live** seam: it maps each emission to
the gateway v1 ``IngestRequest`` (``runtime/gateway_mapping.py``) and POSTs it to
a configured ``/api/v1/ingest`` with stdlib ``urllib``. Default-safe — with no
endpoint it raises ``GatewayEmissionGated`` (the operator opts in by configuring
one) — and fail-closed: it re-runs the producer screen at the emission boundary,
accepts only HTTP 201, and raises ``GatewayEmissionError`` on any other status or
transport fault. Read-only evidence boundary (ADR-0008); the auth token is
operator-injected and never appears in an error or log.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Protocol, runtime_checkable

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import validate_emissions

from .gateway_mapping import emission_to_ingest_request

_SUCCESS_STATUS = 201  # the gateway's only success code (v0.2 ingest contract)


class GatewayEmissionGated(RuntimeError):
    """Raised when ``GatewaySink.emit`` is called with no endpoint configured."""


class GatewayEmissionError(RuntimeError):
    """Gateway ingest failed. Carries ``status`` + ``reason`` so the operator can
    distinguish retryable (429) from terminal (4xx governance veto) from
    server-fault (5xx). The message never includes the auth token or request body.
    """

    def __init__(self, status: int, reason: str = "") -> None:
        self.status = status
        self.reason = reason
        super().__init__(
            f"gateway ingest failed (status={status}, reason={reason or 'unknown'})"
        )


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
    """The **Live** seam: POST each emission as a v1 ``IngestRequest`` to the gateway.

    The gateway ingest guards landed (bicameral-bot #109 / PR #131). Configure an
    ``endpoint`` to opt in; with none, ``emit`` raises ``GatewayEmissionGated``
    (default-safe). Auth is operator-injected (``token`` → ``Authorization:
    Bearer``, plus any ``headers``); the token never enters an error or log. Each
    ``emit`` re-runs the producer contract+sensitive screen at the boundary
    (fail-closed regardless of caller), accepts only HTTP 201, and raises
    ``GatewayEmissionError`` on any other status or transport fault.
    """

    def __init__(
        self,
        *,
        endpoint: str = "",
        token: str = "",
        headers: dict[str, str] | None = None,
        schema_version: str = "v1",
        opener: Callable[..., Any] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.endpoint = endpoint
        self.schema_version = schema_version
        self._token = token
        self._headers = dict(headers or {})
        self._opener = opener or urllib.request.urlopen
        self._timeout = timeout
        # Reject a CR/LF-bearing token/header up front: http.client validates headers
        # during the request and raises a ValueError that embeds the full header value
        # (the token) — a token disclosure (#54). The message names only the field.
        for label, value in (("token", self._token), *self._headers.items()):
            if "\r" in str(value) or "\n" in str(value):
                raise ValueError(f"GatewaySink {label!r} contains a CR/LF control character")

    def emit(self, emissions: list[AdapterEmission]) -> None:
        # Re-screen at the emission boundary (producer contract + secret/PII/PAN
        # HARD gate), so a hand-built emission cannot bypass it (audit F-1).
        validate_emissions(emissions)
        if not self.endpoint:
            raise GatewayEmissionGated(
                "gateway emission gated: no endpoint configured (configure "
                "GatewaySink(endpoint=...) to opt in to Live emission)"
            )
        for emission in emissions:
            self._post(emission_to_ingest_request(emission))

    def _post(self, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", **self._headers}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(
            self.endpoint, data=data, headers=headers, method="POST"
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                status = getattr(response, "status", None) or response.getcode()
        except urllib.error.HTTPError as exc:  # 4xx/5xx — body carries the reason
            raise GatewayEmissionError(exc.code, _reason_from_body(exc)) from None
        except urllib.error.URLError as exc:  # transport fault — token-free detail
            raise GatewayEmissionError(0, f"transport_error:{type(exc.reason).__name__}") from None
        except Exception:  # belt-and-suspenders: never let an unexpected error carry the token
            raise GatewayEmissionError(0, "unexpected_error") from None
        if status != _SUCCESS_STATUS:
            raise GatewayEmissionError(status, "unexpected_status_expected_201")


def _reason_from_body(exc: urllib.error.HTTPError) -> str:
    """Parse the gateway ``IngestRejection`` reason (gateway-side, redacted). Never
    touches request headers/body, so the auth token cannot leak into the error.
    """
    try:
        body = json.loads(exc.read().decode("utf-8"))
    except (ValueError, OSError):
        return ""
    if isinstance(body, dict):
        reason = body.get("reason") or body.get("message") or ""
        return str(reason)
    return ""
