#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Render a recorded ingest phase trace into a Markdown lifecycle page."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from runtime.ingest_lifecycle_markdown import render_markdown_trace


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a data-bearing ingest lifecycle Markdown page from trace JSON."
    )
    parser.add_argument("trace", type=Path, help="Path to JSON containing a phase trace.")
    parser.add_argument("--title", required=True, help="Markdown document title.")
    parser.add_argument("--output", type=Path, help="Output path. Defaults to stdout.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        raw = json.loads(args.trace.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"unable to read trace: {exc}") from exc
    if not isinstance(raw, dict):
        raise SystemExit("trace root must be a JSON object")

    try:
        rendered = render_markdown_trace(raw, title=args.title)
    except ValueError as exc:
        raise SystemExit(f"invalid trace: {exc}") from exc

    if args.output is None:
        print(rendered)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
