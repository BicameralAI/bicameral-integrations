# SPDX-License-Identifier: MIT
"""Render executable ingest phase traces as reviewable Markdown lifecycle pages."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .ingest_conformance import render_mermaid_trace


def _items(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _bullet_section(label: str, values: list[str]) -> list[str]:
    lines = [f"### {label}", ""]
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- None recorded.")
    lines.append("")
    return lines


def render_markdown_trace(trace: Mapping[str, Any], *, title: str) -> str:
    """Render one phase trace into a standalone, multi-section Markdown page.

    The generated page includes the data-bearing Mermaid overview and one detailed
    section per phase with the exact sanitized payload and transformation ledger.
    """
    raw_phases = trace.get("phases")
    if not isinstance(raw_phases, list) or not raw_phases:
        raise ValueError("trace_has_no_phases")

    lines = [
        f"# {title}",
        "",
        "This page was generated from the executable ingest conformance trace.",
        "The displayed data and transformation ledger therefore describe the tested runtime path.",
        "",
        "## Lifecycle overview",
        "",
        "```mermaid",
        render_mermaid_trace(trace),
        "```",
        "",
    ]

    for index, raw_phase in enumerate(raw_phases, start=1):
        if not isinstance(raw_phase, Mapping):
            raise ValueError("trace_phase_invalid")
        phase_title = str(raw_phase.get("title", f"Phase {index}"))
        function = str(raw_phase.get("function", ""))
        data = raw_phase.get("data", {})
        transformation = raw_phase.get("transformation", {})
        if not isinstance(transformation, Mapping):
            raise ValueError("trace_transformation_invalid")

        lines.extend(
            [
                f"## {index}. {phase_title}",
                "",
                f"**Function or boundary:** `{function}`" if function else "**Function or boundary:** Not recorded.",
                "",
                "### Data at this phase",
                "",
                "```json",
                json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False),
                "```",
                "",
            ]
        )
        lines.extend(_bullet_section("Preserved", _items(transformation.get("preserved"))))
        lines.extend(_bullet_section("Added", _items(transformation.get("added"))))
        lines.extend(_bullet_section("Removed", _items(transformation.get("removed"))))
        gate = str(transformation.get("gate", "")).strip()
        lines.extend(["### Gate", "", gate or "None recorded.", ""])

    lines.extend(
        [
            "## Evidence boundary",
            "",
            "This generated page is component evidence for the phases included in the trace.",
            "It does not independently establish real-provider provenance, terminal Bot persistence, restart/replay, human acceptance, or alpha readiness.",
            "",
        ]
    )
    return "\n".join(lines)
