# SPDX-License-Identifier: MIT
"""Production-shape redaction receipts for candidate evaluation (issue #290).

:func:`build_production_receipt` produces the COMPLETE receipt shape emitted
by ``adapter.core.redaction_receipt.sanitize_observation`` — schema_version,
engine, engine_version, ruleset id/digest, input/output digests via the SAME
canonical digest function, sorted value-free category-count findings,
``structural_fields_preserved``, ``completed_at`` — with the candidate id as
engine and the candidate configuration digest as ruleset digest.

:func:`validate_production_receipt` is two conjunctive checks, both required:

1. JSON-Schema validation against ``definitions.ExternalRedactionReceipt`` in
   ``runtime/schemas/external_ingest_request_v2.schema.json`` (Draft-7
   validator scoped to the file's definitions) when ``jsonschema`` is
   importable, else an equivalent structural fallback;
2. the LITERAL runtime gate: the receipt is placed on a minimal
   ``AdapterEmission`` and passed through
   ``runtime.sinks._require_redaction_receipt`` — the exact function guarding
   Bot-bound emissions — with ``GatewayRedactionGated`` as the failure signal.

All reported errors are typed and value-free (validator keyword + location or
the runtime gate's typed message; never receipt values).
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .seam import BackendIdentity

_SCHEMA_FILENAME = "external_ingest_request_v2.schema.json"
_RECEIPT_DEFINITION = "ExternalRedactionReceipt"

_REQUIRED_TYPES: dict[str, type] = {
    "completed_at": str,
    "engine": str,
    "engine_version": str,
    "input_digest": str,
    "output_digest": str,
    "ruleset_digest": str,
    "ruleset_id": str,
    "schema_version": int,
    "structural_fields_preserved": bool,
}


def _schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "schemas" / _SCHEMA_FILENAME


def build_production_receipt(
    candidate_identity: BackendIdentity,
    config_digest: str,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any],
    findings_counts: dict[str, int],
    completed_at: str,
) -> dict[str, Any]:
    """Build the exact production receipt shape for one sanitized record."""

    from adapter.core.redaction_receipt import _digest

    return {
        "schema_version": 1,
        "engine": candidate_identity.candidate_id,
        "engine_version": candidate_identity.engine_version,
        "ruleset_id": f"candidate-eval-{candidate_identity.candidate_id}",
        "ruleset_digest": config_digest,
        "input_digest": _digest(input_payload),
        "output_digest": _digest(output_payload),
        "findings": [
            {"category": category, "action": "tokenized", "count": count}
            for category, count in sorted(findings_counts.items())
            if count > 0
        ],
        "structural_fields_preserved": True,
        "completed_at": completed_at,
    }


def validate_production_receipt(receipt: dict[str, Any]) -> list[str]:
    """Return every schema + runtime-gate violation (empty list == valid)."""

    errors = _schema_errors(receipt)
    errors.extend(_runtime_gate_errors(receipt))
    return errors


def _schema_errors(receipt: dict[str, Any]) -> list[str]:
    try:
        jsonschema = importlib.import_module("jsonschema")
    except ImportError:
        return _structural_fallback_errors(receipt)
    document = json.loads(_schema_path().read_text(encoding="utf-8"))
    scoped = {
        "$ref": f"#/definitions/{_RECEIPT_DEFINITION}",
        "definitions": document.get("definitions", {}),
    }
    validator = jsonschema.Draft7Validator(scoped)
    errors: list[str] = []
    for error in sorted(
        validator.iter_errors(receipt), key=lambda item: str(item.absolute_path)
    ):
        location = "/".join(str(part) for part in error.absolute_path) or "<receipt>"
        errors.append(f"schema:{location}:{error.validator}")
    return errors


def _structural_fallback_errors(receipt: dict[str, Any]) -> list[str]:
    """Fallback mirroring the schema's required keys and types (no jsonschema)."""

    errors: list[str] = []
    for key, expected in _REQUIRED_TYPES.items():
        if key not in receipt:
            errors.append(f"schema:{key}:required")
            continue
        value = receipt[key]
        if expected is int:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                errors.append(f"schema:{key}:type")
        elif expected is bool:
            if not isinstance(value, bool):
                errors.append(f"schema:{key}:type")
        elif not isinstance(value, expected):
            errors.append(f"schema:{key}:type")
    findings = receipt.get("findings", [])
    if not isinstance(findings, list):
        errors.append("schema:findings:type")
        return errors
    for index, entry in enumerate(findings):
        if (
            not isinstance(entry, dict)
            or set(entry) != {"action", "category", "count"}
            or not isinstance(entry.get("action"), str)
            or not isinstance(entry.get("category"), str)
            or isinstance(entry.get("count"), bool)
            or not isinstance(entry.get("count"), int)
            or entry["count"] < 0
        ):
            errors.append(f"schema:findings/{index}:invalid")
    return errors


def _runtime_gate_errors(receipt: dict[str, Any]) -> list[str]:
    """Run the receipt through the LITERAL runtime emission gate."""

    from adapter.core.emissions import AdapterEmission
    from runtime import sinks

    emission = AdapterEmission(
        source_id="candidate-eval",
        title="",
        body="",
        evidence=(),
        metadata={"redaction_receipt": receipt},
    )
    try:
        sinks._require_redaction_receipt(emission)
    except sinks.GatewayRedactionGated as gated:
        return [f"runtime:{gated}"]
    return []
