# SPDX-License-Identifier: MIT
"""Receipt-contract tests (issue #290 defect 3).

Prove the evaluation receipt gate builds the COMPLETE production receipt
shape and validates it through BOTH the external-ingest JSON schema
definition and the literal runtime emission gate
(``runtime.sinks._require_redaction_receipt``) — never a partial dict with a
serialization-only check.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.redaction_evaluation.backends.baseline import (  # noqa: E402
    BicameralStdlibBackend,
)
from runtime.redaction_evaluation.policy import (  # noqa: E402
    RedactionPolicy,
    configuration_digest,
)
from runtime.redaction_evaluation.receipt_contract import (  # noqa: E402
    build_production_receipt,
    validate_production_receipt,
)

POLICY = RedactionPolicy()

_INPUT_PAYLOAD = {"excerpt": "text before sanitization", "title": "t"}
_OUTPUT_PAYLOAD = {"excerpt": "text after [redacted:email]", "title": "t"}


def _build_receipt() -> dict[str, Any]:
    backend = BicameralStdlibBackend()
    config_digest = configuration_digest(
        dict(backend.identity.configuration), backend.label_map, POLICY
    )
    return build_production_receipt(
        backend.identity,
        config_digest,
        _INPUT_PAYLOAD,
        _OUTPUT_PAYLOAD,
        {"pii": 2, "secret": 1, "phi": 0},
        "2026-01-01T00:00:00Z",
    )


def test_receipt_is_the_complete_production_shape() -> None:
    receipt = _build_receipt()
    assert set(receipt) == {
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
    assert receipt["schema_version"] == 1
    assert receipt["engine"] == "bicameral-stdlib-v1"
    assert receipt["ruleset_id"] == "candidate-eval-bicameral-stdlib-v1"
    assert receipt["structural_fields_preserved"] is True
    # Zero-count categories are dropped, exactly like production.
    assert receipt["findings"] == [
        {"category": "pii", "action": "tokenized", "count": 2},
        {"category": "secret", "action": "tokenized", "count": 1},
    ]
    for key in ("ruleset_digest", "input_digest", "output_digest"):
        assert str(receipt[key]).startswith("sha256:")


def test_valid_receipt_passes_schema_and_runtime_gate() -> None:
    receipt = _build_receipt()
    assert validate_production_receipt(receipt) == []


def test_valid_receipt_passes_the_literal_runtime_sink_gate() -> None:
    from adapter.core.emissions import AdapterEmission
    from runtime import sinks

    emission = AdapterEmission(
        source_id="candidate-eval",
        title="",
        body="",
        evidence=(),
        metadata={"redaction_receipt": _build_receipt()},
    )
    # Must not raise GatewayRedactionGated: the receipt satisfies the real
    # production emission gate, not a lookalike.
    sinks._require_redaction_receipt(emission)


def _drop_ruleset_digest(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt.pop("ruleset_digest")
    return receipt


def _break_structural_flag(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt["structural_fields_preserved"] = False
    return receipt


def _break_digest_format(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt["input_digest"] = "sha256:not-a-hex-digest"
    return receipt


@pytest.mark.parametrize(
    "mutate",
    [_drop_ruleset_digest, _break_structural_flag, _break_digest_format],
    ids=["missing-ruleset-digest", "structural-flag-false", "bad-digest-format"],
)
def test_broken_receipts_are_rejected(mutate) -> None:
    receipt = mutate(_build_receipt())
    errors = validate_production_receipt(receipt)
    assert errors, "broken receipt must be rejected"


def test_structural_flag_false_is_caught_by_the_runtime_gate() -> None:
    # The JSON schema allows any boolean; ONLY the runtime-equivalent check
    # rejects structural_fields_preserved=False. This proves the conjunction
    # is load-bearing.
    receipt = _break_structural_flag(_build_receipt())
    errors = validate_production_receipt(receipt)
    assert any(error.startswith("runtime:") for error in errors)
