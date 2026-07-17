# SPDX-License-Identifier: MIT
"""Tests for the ingest lifecycle Markdown CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.render_ingest_lifecycle import main


def _trace() -> dict:
    return {
        "phases": [
            {
                "id": "provider_capture",
                "title": "Sanitized provider capture",
                "function": "provider transport",
                "data": {"body": "Decision: preserve evidence."},
                "display": ["body: Decision: preserve evidence."],
                "transformation": {
                    "preserved": ["provider payload"],
                    "added": ["capture digest"],
                    "removed": ["secret headers"],
                    "gate": "signature verification",
                },
            }
        ]
    }


def test_cli_writes_lifecycle_page(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    output_path = tmp_path / "lifecycle.md"
    trace_path.write_text(json.dumps(_trace()), encoding="utf-8")

    result = main(
        [
            str(trace_path),
            "--title",
            "Recorded Lifecycle",
            "--output",
            str(output_path),
        ]
    )

    assert result == 0
    rendered = output_path.read_text(encoding="utf-8")
    assert rendered.startswith("# Recorded Lifecycle")
    assert "```mermaid" in rendered
    assert "Decision: preserve evidence." in rendered
    assert "signature verification" in rendered


def test_cli_prints_to_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(json.dumps(_trace()), encoding="utf-8")

    assert main([str(trace_path), "--title", "Stdout Lifecycle"]) == 0

    output = capsys.readouterr().out
    assert output.startswith("# Stdout Lifecycle")


def test_cli_rejects_non_object_trace(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_text("[]", encoding="utf-8")

    with pytest.raises(SystemExit, match="trace root must be a JSON object"):
        main([str(trace_path), "--title", "Invalid"])


def test_cli_rejects_trace_without_phases(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit, match="invalid trace: trace_has_no_phases"):
        main([str(trace_path), "--title", "Invalid"])
