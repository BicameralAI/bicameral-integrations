# SPDX-License-Identifier: MIT
"""Instrumented sink/cursor boundary for the evaluation harness (issue #290).

Production fail-closed semantics — no envelope, no sink call, no cursor
advancement after a redaction failure (``runtime/cursor_policy.py``;
``adapter.core.redaction_receipt.guarded_sanitize_observation``) — are proved
here by OBSERVED calls, not modeled booleans. :class:`RecordingSink`
structurally satisfies the ``runtime.sinks.EmissionSink`` protocol shape
(``emit(self, emissions: list) -> None``); :class:`RecordingCursor` mirrors a
cursor's ``advance``. Both are value-free: they record call counts and record
ids only, never emission content.

:func:`route_outcome` is the single decision point mirroring production
routing: a usable outcome (``sanitized``/``unchanged``) emits exactly once and
advances the cursor; ``failed_closed`` calls NEITHER. The spike routes
observation IDENTITY only, never payloads — the synthetic marker handed to
the sink carries the record id and nothing else.
"""

from __future__ import annotations

from typing import Any

_SUCCESS_OUTCOMES = ("sanitized", "unchanged")


class RecordingSink:
    """Value-free ``EmissionSink`` double: counts calls, stores no content."""

    def __init__(self) -> None:
        self.call_count = 0
        self.emission_counts: list[int] = []
        self.routed_record_ids: list[str] = []

    def emit(self, emissions: list[Any]) -> None:
        self.call_count += 1
        self.emission_counts.append(len(emissions))
        for emission in emissions:
            if isinstance(emission, dict) and "record_id" in emission:
                self.routed_record_ids.append(str(emission["record_id"]))


class RecordingCursor:
    """Value-free cursor double: records which record ids advanced."""

    def __init__(self) -> None:
        self.advance_count = 0
        self.advanced_record_ids: list[str] = []

    def advance(self, record_id: str) -> None:
        self.advance_count += 1
        self.advanced_record_ids.append(str(record_id))


def route_outcome(result_doc: dict[str, Any], sink: Any, cursor: Any) -> None:
    """Route one per-record result through the observed boundary.

    ``sanitized``/``unchanged`` -> exactly one ``sink.emit`` (one synthetic,
    value-free marker carrying the record id only) AND one
    ``cursor.advance(record_id)``. ``failed_closed`` (or any other outcome)
    -> neither is called.
    """

    if result_doc.get("outcome") not in _SUCCESS_OUTCOMES:
        return
    record_id = str(result_doc.get("record_id", ""))
    sink.emit([{"record_id": record_id, "synthetic_marker": True}])
    cursor.advance(record_id)
