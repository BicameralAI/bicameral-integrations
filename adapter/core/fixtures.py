# SPDX-License-Identifier: MIT
"""Fixture helpers placeholder for connector and adapter conformance tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FixtureCase:
    """Named connector or adapter fixture case."""

    fixture_id: str
    source_id: str
    description: str

