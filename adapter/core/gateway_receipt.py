# SPDX-License-Identifier: MIT
"""Issue a deterministic receipt when GatewaySink screens an already-clean emission."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone

from .emissions import AdapterEmission
from .redaction_receipt import RULESET_DIGEST, RULESET_ID

ENGINE = "bicameral-sensitive-screen"
ENGINE_VERSION = "1.0.0"


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def receipt_for_screened_emission(
    emission: AdapterEmission,
    *,
    completed_at: str | None = None,
) -> dict[str, object]:
    """Return value-free proof that the final Bot-bound hard screen passed.

    Callers must run ``validate_emissions`` first. Because the emission is already
    clean, the input and output digests are identical and findings are empty.
    """

    digest = _canonical_digest(asdict(emission))
    return {
        "schema_version": 1,
        "engine": ENGINE,
        "engine_version": ENGINE_VERSION,
        "ruleset_id": RULESET_ID,
        "ruleset_digest": RULESET_DIGEST,
        "input_digest": digest,
        "output_digest": digest,
        "findings": [],
        "structural_fields_preserved": True,
        "completed_at": completed_at
        or datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }
