# SPDX-License-Identifier: MIT
"""Shared filter vocabulary for connector-facing configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FilterSpec:
    """Source-agnostic filter primitives."""

    keyword_include: tuple[str, ...] = ()
    keyword_exclude: tuple[str, ...] = ()
    author_include: tuple[str, ...] = ()
    author_exclude: tuple[str, ...] = ()
    time_window_after: str = ""
    time_window_before: str = ""
    eval_hook: str = ""
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QuotaSpec:
    """Per-source pull and payload limits."""

    max_items_per_pull: int = 0
    max_payload_bytes: int = 0
