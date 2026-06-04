# SPDX-License-Identifier: MIT
"""Governance-integrity CI gate (stdlib only).

Verifies the two committed, tamper-evident governance artifacts so a PR cannot
silently corrupt them:

- ``verify_ledger_chain`` — re-derives the ``docs/META_LEDGER.md`` SHA-256 hash
  chain. Genesis Anchor Rule (SG-2026-06-04-D): the first entry carries a
  Content Hash + ``Previous Hash: GENESIS (no predecessor)`` and **no** Chain
  Hash; the first chained entry's ``previous_hash`` equals the genesis
  **content** hash; every entry thereafter has ``previous_hash ==`` the prior
  entry's ``chain_hash`` and ``chain_hash == sha256(content_hash + previous_hash)``.
- ``verify_feature_index`` — every ``docs/FEATURE_INDEX.md`` row that cites a
  test path points at a file that exists (waiver / N-A cells are skipped).

Runs on a clean CI runner with no third-party dependencies and no ``qor`` venv.
Exit code is non-zero when either check reports an error.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

_HEX64 = re.compile(r"[0-9a-f]{64}")
_ENTRY_SPLIT = re.compile(r"^### Entry #(\d+)", re.MULTILINE)
_PREVIOUS = re.compile(r"\*\*Previous Hash\*\*:\s*(.+)")
_PY_PATH = re.compile(r"[\w./-]+\.py")


def _hash_after(body: str, label: str) -> str | None:
    """First 64-hex digest appearing after ``label`` in an entry body."""
    idx = body.find(label)
    if idx == -1:
        return None
    m = _HEX64.search(body, idx)
    return m.group(0) if m else None


def _previous(body: str) -> str | None:
    m = _PREVIOUS.search(body)
    if not m:
        return None
    value = m.group(1).strip()
    hexm = _HEX64.match(value)
    return hexm.group(0) if hexm else value


def _entries(text: str) -> list[tuple[str, str]]:
    parts = _ENTRY_SPLIT.split(text)
    return [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]


def verify_ledger_chain(text: str) -> list[str]:
    """Return a list of chain-integrity errors ([] when the chain verifies)."""
    errors: list[str] = []
    entries = _entries(text)
    if not entries:
        return ["no ledger entries found"]
    prev_link: str | None = None
    genesis_count = 0
    for num, body in entries:
        content = _hash_after(body, "Content Hash")
        previous = _previous(body)
        chain = _hash_after(body, "Chain Hash")
        if previous and "GENESIS" in previous:  # genesis anchor
            genesis_count += 1
            if genesis_count > 1:
                errors.append(f"#{num}: multiple genesis anchors (only entry #1 may be genesis)")
            if content is None:
                errors.append(f"#{num}: genesis missing Content Hash")
            if chain is not None:
                errors.append(f"#{num}: genesis must not carry a Chain Hash")
            prev_link = content
            continue
        if content is None or previous is None or chain is None:
            errors.append(f"#{num}: missing content/previous/chain hash")
            continue
        if prev_link is not None and previous != prev_link:
            errors.append(
                f"#{num}: previous_hash {previous[:12]} does not link to prior {prev_link[:12]}"
            )
        recomputed = hashlib.sha256((content + previous).encode("utf-8")).hexdigest()
        if recomputed != chain:
            errors.append(
                f"#{num}: chain_hash mismatch (recomputed {recomputed[:12]} != stated {chain[:12]})"
            )
        prev_link = chain
    return errors


def verify_feature_index(text: str, repo_root: Path) -> list[str]:
    """Return errors for any FEATURE_INDEX test path that does not exist."""
    errors: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("| FX"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 5:
            continue
        test_cell = cells[4]
        for token in _PY_PATH.findall(test_cell):
            if not (repo_root / token).exists():
                errors.append(f"{cells[0]}: test path not found: {token}")
    return errors


def main(argv: list[str] | None = None) -> int:
    import argparse

    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Verify committed governance artifacts.")
    parser.add_argument("--repo-root", default=str(default_root))
    parser.add_argument("--ledger", default=None)
    parser.add_argument("--feature-index", default=None)
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    ledger_path = Path(args.ledger) if args.ledger else repo_root / "docs" / "META_LEDGER.md"
    fi_path = (
        Path(args.feature_index) if args.feature_index else repo_root / "docs" / "FEATURE_INDEX.md"
    )
    if not ledger_path.exists():
        print(f"governance-gate: FAIL\n  - ledger not found: {ledger_path}")
        return 1
    ledger = ledger_path.read_text(encoding="utf-8")
    feature_index = fi_path.read_text(encoding="utf-8") if fi_path.exists() else ""
    errors = verify_ledger_chain(ledger) + verify_feature_index(feature_index, repo_root)
    if errors:
        print("governance-gate: FAIL")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("governance-gate: OK (ledger chain + FEATURE_INDEX verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
