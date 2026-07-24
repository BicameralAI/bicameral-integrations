# SPDX-License-Identifier: MIT
"""Bot-owned external-ingest protocol compatibility negotiation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit


_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
_CONTRACT_PATH = _SCHEMA_DIR / "external_ingest" / "contract.json"
_CONTRACT_FINGERPRINT_PATH = _SCHEMA_DIR / "external_ingest" / "contract.sha256"
_CONTRACT = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))

EXTERNAL_INGEST_CONTRACT_ID = str(_CONTRACT["contract_id"])
EXTERNAL_INGEST_PROTOCOL_VERSION = int(_CONTRACT["protocol_version"])
EXTERNAL_INGEST_DELIVERY_PATH = str(_CONTRACT["delivery_endpoint"])
EXTERNAL_INGEST_CAPABILITIES_PATH = str(_CONTRACT["capabilities_endpoint"])
EXTERNAL_INGEST_REQUEST_SCHEMA_SHA256 = str(_CONTRACT["request_schema"]["sha256"])
EXTERNAL_INGEST_CONTRACT_FINGERPRINT = hashlib.sha256(
    _CONTRACT_PATH.read_bytes()
).hexdigest()


class ProtocolCompatibilityError(ValueError):
    """Value-free reason for refusing an incompatible Bot endpoint."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def capabilities_url(delivery_url: str) -> str:
    """Build the stable capabilities URL on the configured Bot origin."""
    parsed = urlsplit(delivery_url)
    return urlunsplit(
        (parsed.scheme, parsed.netloc, EXTERNAL_INGEST_CAPABILITIES_PATH, "", "")
    )


def validate_capabilities(report: Mapping[str, Any]) -> None:
    """Require an exact Bot-owned protocol/schema/fingerprint match."""
    expected: tuple[tuple[str, Any, str], ...] = (
        ("contract_id", EXTERNAL_INGEST_CONTRACT_ID, "contract_id_mismatch"),
        (
            "protocol_version",
            EXTERNAL_INGEST_PROTOCOL_VERSION,
            "protocol_version_mismatch",
        ),
        (
            "delivery_endpoint",
            EXTERNAL_INGEST_DELIVERY_PATH,
            "delivery_endpoint_mismatch",
        ),
        (
            "request_schema_sha256",
            EXTERNAL_INGEST_REQUEST_SCHEMA_SHA256,
            "schema_fingerprint_mismatch",
        ),
        (
            "contract_fingerprint",
            EXTERNAL_INGEST_CONTRACT_FINGERPRINT,
            "contract_fingerprint_mismatch",
        ),
        ("redaction_receipt_required", True, "receipt_requirement_mismatch"),
    )
    for field, value, code in expected:
        if report.get(field) != value:
            raise ProtocolCompatibilityError(code)

    supported = report.get("supported_protocol_versions")
    if not isinstance(supported, list) or EXTERNAL_INGEST_PROTOCOL_VERSION not in supported:
        raise ProtocolCompatibilityError("protocol_version_not_supported")


def verify_vendored_contract() -> list[str]:
    """Return offline pin-integrity errors for CI and local release checks."""
    errors: list[str] = []
    recorded = _CONTRACT_FINGERPRINT_PATH.read_text().strip().split()[0]
    if recorded != EXTERNAL_INGEST_CONTRACT_FINGERPRINT:
        errors.append("vendored contract fingerprint does not match contract.json")
    schema = _SCHEMA_DIR / "external_ingest_request_v2.schema.json"
    actual_schema = hashlib.sha256(schema.read_bytes()).hexdigest()
    if actual_schema != EXTERNAL_INGEST_REQUEST_SCHEMA_SHA256:
        errors.append("vendored request schema does not match contract manifest")
    return errors
