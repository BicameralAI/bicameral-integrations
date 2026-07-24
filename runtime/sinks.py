# SPDX-License-Identifier: MIT
"""Emission sinks for the operator-runtime boundary (ADR-0012).

A connector's normalized ``AdapterEmission`` list is handed to an
``EmissionSink``. ``CollectingSink`` (in-memory) serves tests + the **Beta**
readiness stage. ``GatewaySink`` is the **Live** seam: it maps each emission to
the bot's v2 ``ExternalIngestEnvelope`` (``runtime/gateway_mapping.py``; #226 —
the authority-stripped external path) and POSTs it to a configured
``/api/v2/external-ingest`` with stdlib ``urllib`` after an exact-match
capability handshake. Default-safe — with no
endpoint it raises ``GatewayEmissionGated`` (the operator opts in by configuring
one) — and fail-closed: it re-runs the producer screen, preserves a complete
upstream receipt or issues a zero-finding receipt after the final hard screen,
accepts only HTTP 201, and raises ``GatewayEmissionError`` on any other status or
transport fault. Read-only evidence boundary (ADR-0008); the auth token is
operator-injected and never appears in an error or log.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import replace
from typing import Any, Callable, Protocol, runtime_checkable

from adapter.core.emissions import AdapterEmission
from adapter.core.gateway_receipt import receipt_for_screened_emission
from adapter.core.pipeline import validate_emissions
from adapter.core.sdk_evidence import emission_to_sdk_evidence

from .gateway_mapping import emission_to_external_envelope
from .ingest_protocol import (
    EXTERNAL_INGEST_DELIVERY_PATH,
    ProtocolCompatibilityError,
    capabilities_url,
    validate_capabilities,
)

_SUCCESS_STATUS = 201
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "engine",
        "engine_version",
        "ruleset_id",
        "ruleset_digest",
        "input_digest",
        "output_digest",
        "findings",
        "structural_fields_preserved",
        "completed_at",
    }
)
_FINDING_KEYS = frozenset({"category", "action", "count"})
_FINDING_CATEGORIES = frozenset({"credential", "pii", "secret"})
_FINDING_ACTIONS = frozenset({"removed", "tokenized"})


class _NoFollowRedirect(urllib.request.HTTPRedirectHandler):
    """Never auto-follow a redirect carrying an operator bearer token."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


_NO_FOLLOW_OPENER = urllib.request.build_opener(_NoFollowRedirect).open


class GatewayEmissionGated(RuntimeError):
    """Raised when live delivery is disabled by configuration."""


class GatewayRedactionGated(RuntimeError):
    """Raised when a Bot-bound emission carries a malformed redaction receipt."""


class GatewayEmissionError(RuntimeError):
    """Typed token-free failure returned by the external ingest transport."""

    def __init__(self, status: int, reason: str = "") -> None:
        self.status = status
        self.reason = reason
        super().__init__(
            f"gateway ingest failed (status={status}, reason={reason or 'unknown'})"
        )


class GatewayProtocolMismatch(GatewayEmissionError):
    """Fail-closed, value-free contract skew before evidence delivery."""

    def __init__(self, code: str) -> None:
        super().__init__(0, f"protocol_mismatch:{code}")


def _require_redaction_receipt(emission: AdapterEmission) -> None:
    receipt = emission.metadata.get("redaction_receipt")
    if not isinstance(receipt, dict):
        raise GatewayRedactionGated("gateway emission gated: redaction_receipt_required")
    if set(receipt) != _RECEIPT_KEYS:
        raise GatewayRedactionGated("gateway emission gated: redaction_receipt_incomplete")
    if receipt.get("schema_version") != 1:
        raise GatewayRedactionGated("gateway emission gated: redaction_receipt_version")
    if receipt.get("structural_fields_preserved") is not True:
        raise GatewayRedactionGated(
            "gateway emission gated: structural_fields_not_preserved"
        )
    for key in ("engine", "engine_version", "ruleset_id"):
        value = receipt.get(key)
        if not isinstance(value, str) or not value.strip():
            raise GatewayRedactionGated(f"gateway emission gated: invalid_{key}")
    for key in ("ruleset_digest", "input_digest", "output_digest"):
        value = receipt.get(key)
        if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
            raise GatewayRedactionGated(f"gateway emission gated: invalid_{key}")
    findings = receipt.get("findings")
    if not isinstance(findings, list):
        raise GatewayRedactionGated(
            "gateway emission gated: redaction_findings_invalid"
        )
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != _FINDING_KEYS:
            raise GatewayRedactionGated(
                "gateway emission gated: redaction_finding_shape"
            )
        if finding.get("category") not in _FINDING_CATEGORIES:
            raise GatewayRedactionGated(
                "gateway emission gated: redaction_finding_category"
            )
        if finding.get("action") not in _FINDING_ACTIONS:
            raise GatewayRedactionGated(
                "gateway emission gated: redaction_finding_action"
            )
        count = finding.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise GatewayRedactionGated(
                "gateway emission gated: redaction_finding_count"
            )
    completed_at = receipt.get("completed_at")
    if not isinstance(completed_at, str) or not _RFC3339_RE.fullmatch(completed_at):
        raise GatewayRedactionGated("gateway emission gated: invalid_completed_at")


def _ensure_redaction_receipt(emission: AdapterEmission) -> AdapterEmission:
    receipt = emission.metadata.get("redaction_receipt")
    if receipt is not None:
        _require_redaction_receipt(emission)
        return emission

    metadata = dict(emission.metadata)
    metadata["redaction_receipt"] = receipt_for_screened_emission(emission)
    prepared = replace(emission, metadata=metadata)
    _require_redaction_receipt(prepared)
    return prepared


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


class SdkEvidenceSink:
    """Shape each emission into SDK Evidence dictionaries and accumulate them."""

    def __init__(self, *, capture_method: str = "active") -> None:
        self._capture_method = capture_method
        self.evidence: list[dict] = []

    def emit(self, emissions: list[AdapterEmission]) -> None:
        for emission in emissions:
            self.evidence.extend(
                emission_to_sdk_evidence(emission, capture_method=self._capture_method)
            )


class GatewaySink:
    """POST each screened, receipt-bearing emission to external ingest."""

    def __init__(
        self,
        *,
        endpoint: str = "",
        token: str = "",
        headers: dict[str, str] | None = None,
        opener: Callable[..., Any] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.endpoint = endpoint
        self._token = token
        self._headers = dict(headers or {})
        self._opener = opener or _NO_FOLLOW_OPENER
        self._timeout = timeout
        self._compatibility_verified = False
        for label, value in (("token", self._token), *self._headers.items()):
            if "\r" in str(value) or "\n" in str(value):
                raise ValueError(
                    f"GatewaySink {label!r} contains a CR/LF control character"
                )

    def emit(self, emissions: list[AdapterEmission]) -> None:
        screened = validate_emissions(emissions)
        prepared = [_ensure_redaction_receipt(emission) for emission in screened]
        if not self.endpoint:
            raise GatewayEmissionGated(
                "gateway emission gated: no endpoint configured (configure "
                "GatewaySink(endpoint=...) to opt in to Live emission)"
            )
        if urllib.parse.urlsplit(self.endpoint).path != EXTERNAL_INGEST_DELIVERY_PATH:
            raise GatewayProtocolMismatch("delivery_endpoint_not_v2")
        self._verify_compatibility()
        for emission in prepared:
            self._post(emission_to_external_envelope(emission))

    def _verify_compatibility(self) -> None:
        if self._compatibility_verified:
            return
        request = urllib.request.Request(
            capabilities_url(self.endpoint),
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                status = getattr(response, "status", None) or response.getcode()
                if status != 200:
                    raise GatewayProtocolMismatch(f"capabilities_http_{status}")
                raw = response.read()
        except GatewayProtocolMismatch:
            raise
        except urllib.error.HTTPError as exc:
            raise GatewayProtocolMismatch(f"capabilities_http_{exc.code}") from None
        except urllib.error.URLError as exc:
            raise GatewayEmissionError(
                0,
                f"transport_error:{type(exc.reason).__name__}",
            ) from None
        except Exception:
            raise GatewayProtocolMismatch("capabilities_invalid_response") from None
        try:
            report = json.loads(raw)
            if not isinstance(report, dict):
                raise ProtocolCompatibilityError("capabilities_not_object")
            validate_capabilities(report)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise GatewayProtocolMismatch("capabilities_invalid_json") from None
        except ProtocolCompatibilityError as exc:
            raise GatewayProtocolMismatch(exc.code) from None
        self._compatibility_verified = True

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
        except urllib.error.HTTPError as exc:
            raise GatewayEmissionError(exc.code, "gateway_rejected") from None
        except urllib.error.URLError as exc:
            raise GatewayEmissionError(
                0,
                f"transport_error:{type(exc.reason).__name__}",
            ) from None
        except Exception:
            raise GatewayEmissionError(0, "unexpected_error") from None
        if status != _SUCCESS_STATUS:
            raise GatewayEmissionError(status, "unexpected_status_expected_201")
