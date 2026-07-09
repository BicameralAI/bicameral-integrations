# SPDX-License-Identifier: MIT
"""Atomic writer for the operator-local config — the write half of FX-RUNTIME-004 (#227 LD7).

``load_config`` (runtime/local_config.py) stays read-only; THIS module owns every mutation of
``config/bicameral.local.json``. Writes are atomic (temp file in the same directory, closed, then
``os.replace`` — Windows-safe) and the temp file is NAMED to match the ``config/bicameral.local*.json``
gitignore glob, so a hard kill between write and replace never leaves a secret-bearing, git-visible
file (audit #231 A1). When the config is absent it is seeded from ``config/bicameral.example.json``
with every ``secrets`` VALUE emptied to ``""`` — the example's placeholder values would satisfy the
truthiness credential gate and be sent as live credentials (audit #230 F3; ``""`` fails closed).
No secret value is ever logged or echoed here. Stdlib-only.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Callable

from .local_config import ConfigError, _descriptor

_REPO = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = _REPO / "config" / "bicameral.example.json"


def _check_runtime_allowlist(doc: dict) -> None:
    """Write-side mirror of the load-side runtime-key allowlist (purple-team CONFIG 2026-06-11):
    a runtime sub-key not declared in the connector's descriptor ``runtime_config`` is never
    written, so a credentialed builder kwarg cannot be smuggled in through the writer either."""
    for cid, block in (doc.get("connectors") or {}).items():
        if cid.startswith("_") or not isinstance(block, dict):
            continue
        desc = _descriptor(cid)
        if desc is None:
            continue  # unknown connector block: load-side validation owns that complaint
        declared = {rc["key"] for rc in desc.get("runtime_config", [])}
        unknown = set(block.get("runtime") or {}) - declared
        if unknown:
            raise ConfigError(f"{cid}: runtime key(s) not declared in descriptor runtime_config: "
                              f"{sorted(unknown)}")


def seeded_document() -> dict:
    """The example config with every connector secret VALUE emptied (fail-closed seed; #230 F3)."""
    doc = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    for cid, block in (doc.get("connectors") or {}).items():
        if cid.startswith("_") or not isinstance(block, dict):
            continue
        secrets = block.get("secrets")
        if isinstance(secrets, dict):
            block["secrets"] = {key: "" for key in secrets}
    return doc


def load_or_seed(path: str | Path) -> dict:
    """The current config document, or the emptied-example seed when the file does not exist."""
    p = Path(path)
    if not p.exists():
        return seeded_document()
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigError("config root must be an object")
    return raw


def write_local_config(path: str | Path, mutate_fn: Callable[[dict], None]) -> None:
    """Read-modify-write the local config atomically. ``mutate_fn`` edits the document in place;
    if it raises, the original file is untouched and no temp file is left behind."""
    p = Path(path)
    doc = load_or_seed(p)
    mutate_fn(doc)  # raises BEFORE any file is created -> original untouched
    _check_runtime_allowlist(doc)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=p.parent,
        prefix="bicameral.local.",  # matches the config/bicameral.local*.json gitignore glob (A1)
        suffix=".json",
        delete=False,
    )
    try:
        with fd:
            json.dump(doc, fd, indent=2)
            fd.write("\n")
        os.replace(fd.name, p)  # atomic on POSIX + Windows; temp file must be CLOSED first (F5)
    except BaseException:
        try:
            os.unlink(fd.name)  # failure path: never leave a secret-bearing temp file (F5/A1)
        except OSError:
            pass
        raise


__all__ = ["EXAMPLE_CONFIG", "load_or_seed", "seeded_document", "write_local_config"]
