# SPDX-License-Identifier: MIT
"""License-header check (stdlib only).

Reports Python source files missing an SPDX license identifier. Advisory this
cycle (ramps to blocking once headers are backfilled repo-wide). Test files and
empty ``__init__`` markers are exempt.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SPDX = "SPDX-License-Identifier:"


def missing_header(path: str, text: str) -> bool:
    """True when a Python source file lacks an SPDX identifier in its first lines.

    Empty files (e.g. package ``__init__.py`` markers) are exempt.
    """
    if not path.endswith(".py"):
        return False
    if not text.strip():
        return False
    head = "\n".join(text.splitlines()[:5])
    return _SPDX not in head


def scan(paths: list[Path]) -> list[str]:
    """Return the subset of ``paths`` whose files are missing an SPDX header."""
    out: list[str] = []
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if missing_header(str(p), text):
            out.append(str(p))
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    roots = [Path(a) for a in args] or [Path("adapter"), Path("connectors"), Path("scripts")]
    files: list[Path] = []
    for root in roots:
        files.extend(root.rglob("*.py") if root.is_dir() else [root])
    missing = scan(files)
    if missing:
        print(f"license-headers: {len(missing)} file(s) missing SPDX header (advisory):")
        for m in missing:
            print(f"  - {m}")
    else:
        print("license-headers: all scanned files carry an SPDX header")
    return 0  # advisory this cycle — never blocks


if __name__ == "__main__":
    sys.exit(main())
