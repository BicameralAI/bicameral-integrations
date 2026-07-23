# SPDX-License-Identifier: MIT
"""Machine-checkable contract for data-bearing ingest lifecycle phase traces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class PhaseTraceContractError(ValueError):
    """A lifecycle trace omitted required data or transformation semantics."""


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PhaseTraceContractError(f"{label}_required")
    return value


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise PhaseTraceContractError(f"{label}_must_be_list")
    output: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise PhaseTraceContractError(f"{label}_items_must_be_nonempty_strings")
        output.append(item)
    return output


def validate_phase_trace(
    trace: Mapping[str, Any],
    *,
    required_phase_ids: Sequence[str] = (),
) -> list[Mapping[str, Any]]:
    """Validate one lifecycle trace and return its phase mappings.

    Each phase must carry actual structured data, a human-readable display summary,
    and an explicit transformation ledger. Required phase IDs allow connector tests
    to enforce the complete expected path for their acquisition mode.
    """
    raw_phases = trace.get("phases")
    if not isinstance(raw_phases, list) or not raw_phases:
        raise PhaseTraceContractError("phases_required")

    phases: list[Mapping[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_phase in enumerate(raw_phases):
        if not isinstance(raw_phase, Mapping):
            raise PhaseTraceContractError(f"phase_{index}_must_be_object")
        phase_id = _required_text(raw_phase.get("id"), f"phase_{index}_id")
        if phase_id in seen_ids:
            raise PhaseTraceContractError(f"duplicate_phase_id:{phase_id}")
        seen_ids.add(phase_id)
        _required_text(raw_phase.get("title"), f"phase_{phase_id}_title")
        _required_text(raw_phase.get("function"), f"phase_{phase_id}_function")

        data = raw_phase.get("data")
        if not isinstance(data, Mapping) or not data:
            raise PhaseTraceContractError(f"phase_{phase_id}_data_required")
        display = _string_list(raw_phase.get("display"), f"phase_{phase_id}_display")
        if not display:
            raise PhaseTraceContractError(f"phase_{phase_id}_display_required")

        transformation = raw_phase.get("transformation")
        if not isinstance(transformation, Mapping):
            raise PhaseTraceContractError(f"phase_{phase_id}_transformation_required")
        _string_list(
            transformation.get("preserved"),
            f"phase_{phase_id}_preserved",
        )
        _string_list(
            transformation.get("added"),
            f"phase_{phase_id}_added",
        )
        _string_list(
            transformation.get("removed"),
            f"phase_{phase_id}_removed",
        )
        _required_text(transformation.get("gate"), f"phase_{phase_id}_gate")
        phases.append(raw_phase)

    missing = [phase_id for phase_id in required_phase_ids if phase_id not in seen_ids]
    if missing:
        raise PhaseTraceContractError("missing_required_phases:" + ",".join(missing))
    return phases
