# SPDX-License-Identifier: MIT
"""EM-safe mod manifest loader (ADR-0002 / ADR-0013). Stdlib-only.

Parses the **flat YAML subset** the mod manifests use — scalar ``key: value`` lines plus
``key:`` headers followed by ``  - item`` list lines — with a small hand-rolled reader, so
the runtime stays stdlib-only (no PyYAML). It is **fail-closed**: anything outside the
subset (nesting, tabs, duplicate keys, dangling list items, unknown keys, quoted/flow
syntax) raises ``ModManifestError``. Scalars stay ``str`` (``version: 0.1.0`` is the string
``"0.1.0"``, never a float). CRLF + a UTF-8 BOM are tolerated (Windows-authored files).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

_SCALAR_KEYS = frozenset({"id", "version", "name"})
_LIST_KEYS = frozenset({"outputs", "forbidden_actions"})
_KNOWN_KEYS = _SCALAR_KEYS | _LIST_KEYS


class ModManifestError(ValueError):
    """Raised when a mod ``manifest.yaml`` is malformed or outside the supported subset."""


@dataclass(frozen=True)
class Manifest:
    """A mod's declarative manifest (the v1 schema: ADR-0013 narrows ADR-0002/0007 to these
    five fields; source-types / confidence-dimensions / audit-preservation are deferred)."""

    id: str
    version: str
    name: str
    outputs: frozenset[str]
    forbidden_actions: frozenset[str]


def _fail(msg: str) -> NoReturn:
    raise ModManifestError(msg)


def load_manifest(path: str | Path) -> Manifest:
    """Parse a flat-subset mod manifest; ``ModManifestError`` (fail-closed) on anything else."""
    text = Path(path).read_text(encoding="utf-8-sig")  # utf-8-sig strips a leading BOM
    scalars: dict[str, str] = {}
    lists: dict[str, list[str]] = {}
    current: str | None = None  # the list key currently being populated
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw:
            _fail(f"tab indentation is not allowed: {raw!r}")
        if raw.startswith("  - ") or raw.strip().startswith("- "):
            if current is None:
                _fail(f"list item before any list key: {raw!r}")
            lists[current].append(raw.split("- ", 1)[1].strip())
            continue
        if raw[0].isspace():
            _fail(f"unexpected indented line: {raw!r}")
        key, sep, value = raw.partition(":")
        key = key.strip()
        if not sep:
            _fail(f"not a key line: {raw!r}")
        if key not in _KNOWN_KEYS:
            _fail(f"unknown manifest key: {key!r}")
        if key in scalars or key in lists:
            _fail(f"duplicate key: {key!r}")
        if key in _LIST_KEYS:
            lists[key] = []
            current = key
            if value.strip():
                _fail(f"list key {key!r} must not have an inline value")
        else:
            scalars[key] = value.strip()  # kept as str — no numeric coercion
            current = None
    return _build(scalars, lists)


def _build(scalars: dict[str, str], lists: dict[str, list[str]]) -> Manifest:
    for key in _SCALAR_KEYS:
        if not scalars.get(key):
            _fail(f"missing required scalar key: {key!r}")
    for key in _LIST_KEYS:
        if key not in lists:
            _fail(f"missing required list key: {key!r}")
    if not lists["forbidden_actions"]:
        _fail("forbidden_actions must not be empty")
    return Manifest(
        id=scalars["id"],
        version=scalars["version"],
        name=scalars["name"],
        outputs=frozenset(lists["outputs"]),
        forbidden_actions=frozenset(lists["forbidden_actions"]),
    )
