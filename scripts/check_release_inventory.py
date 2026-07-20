# SPDX-License-Identifier: MIT
"""Release-artifact inventory gate (#251) — deterministic, fail-closed.

Bicameral Integrations ships as a source library (`git archive` / release
tarball is the published integration format). This gate proves that the exact
set of files a release archive would contain carries **no Factory-internal or
contributor-only development material** — the customer-distribution boundary
from bicameral-factory#243.

It is deterministic and exact-head: it enumerates the release file set from the
tracked tree at `HEAD`, honoring `.gitattributes` `export-ignore` (the same
filter `git archive` applies), and fails closed if any shipped path or shipped
text file matches a forbidden pattern.

A release artifact must NOT include:

- `.bicameral/` development evidence (repo-governance facts stay a development
  declaration; attestations, factory context, receipts never ship);
- Factory context, copied skills, run manifests, receipts, or hooks;
- internal roadmap, SOC 2 evidence, risk, review-queue, or Shadow Genome data;
- private Factory links or internal sibling-tool references (Qor-logic,
  FailSafe, `.qor/`, `bic-logic`);
- unapproved contributor-local files.

`--manifest` prints the sorted release inventory plus an aggregate SHA-256 so a
run can be retained as exact-head evidence. Stdlib only; no live network.

Exit 0 when the release set is clean, exit 1 on any violation or git error.
"""

from __future__ import annotations

import fnmatch
import hashlib
import re
import subprocess  # nosec B404 — git invocation, not user-controlled
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Paths that must never appear in a customer release artifact. Matched against
# the release file set (paths already filtered by export-ignore); listed here
# too so the gate fails closed even if an export-ignore entry is dropped.
FORBIDDEN_PATH_PATTERNS = (
    ".bicameral/*",  # all repo-local development evidence
    ".qor/*",  # Qor-logic sibling scratch
    ".agent/*",
    ".agents/*",
    ".claude/*",
    ".cursor/*",
    ".windsurf/*",
    ".failsafe/*",
    ".github/*",  # CI/dev workflows and hooks
    "AGENTS.md",  # contributor-only development process
    "docs/governance/*",  # contributor development-governance contract
    "docs/META_LEDGER.md",  # internal hash-chained development ledger
    "docs/SHADOW_GENOME.md",  # internal failure-mode narrative
    "docs/GOVERNANCE_INDEX.md",
    "docs/SYSTEM_STATE.md",
    "docs/BACKLOG.md",
    "docs/WHATS_NEXT.md",
    "docs/compliance/*",  # SOC 2 / framework evidence mappings
    "docs/ecosystem/*",
    "docs/research-brief-*.md",
    "docs/rfq-*.md",
    "docs/scope-*.md",
    "docs/connector-verification-*.md",
    "*/factory-attestation*.json",
    "factory-plan.json",
    "RUN_SUMMARY.md",
    "ISSUE.md",
    "BICAMERAL_CONTEXT.md",
    "FACTORY_RULES.md",
    "skills-lock.json",
    "plan-*.md",
)

# Forbidden references inside shipped text files: private Factory operational
# links and internal sibling-tool names. Product connectors that *ingest* a
# tool (e.g. a "Cursor" or "Claude Code" connector) are legitimate product
# surfaces and are intentionally NOT matched here — only maintainer-internal
# tooling names and the private Factory control-plane link are forbidden.
FORBIDDEN_REFERENCE_PATTERNS = (
    (
        re.compile(r"github\.com/BicameralAI/bicameral-factory"),
        "private Factory repository link",
    ),
    (re.compile(r"\bbic-logic\b"), "stale bic-logic terminology"),
    (re.compile(r"\bQor-logic\b", re.IGNORECASE), "internal sibling tool (Qor-logic)"),
    (re.compile(r"\bFailSafe\b"), "internal sibling tool (FailSafe)"),
    (
        re.compile(r"\bMythologIQ\b", re.IGNORECASE),
        "internal sibling tool (MythologIQ)",
    ),
    (re.compile(r"(?<![\w.])\.qor/"), "internal sibling-tool path (.qor/)"),
    (re.compile(r"\bShadow Genome\b"), "internal Shadow Genome reference"),
)

# Text extensions scanned for forbidden references (binary/data files skipped).
_TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".rst",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".cfg",
    ".ini",
}


def _git(args: list[str]) -> list[str]:
    result = subprocess.run(  # nosec B603 B607
        ["git", *args],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed with code {result.returncode}")
    return [line for line in result.stdout.splitlines() if line]


def _export_ignored(paths: list[str]) -> set[str]:
    """Return the subset of `paths` marked `export-ignore` in .gitattributes.

    Uses `git check-attr --stdin` so the result matches what `git archive`
    would omit from a release tarball.
    """
    if not paths:
        return set()
    proc = subprocess.run(  # nosec B603 B607
        ["git", "check-attr", "--stdin", "-z", "export-ignore"],
        cwd=ROOT,
        input="\0".join(paths) + "\0",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    ignored: set[str] = set()
    # -z output is NUL-separated triples: <path>\0<attr>\0<value>\0
    fields = proc.stdout.split("\0")
    for i in range(0, len(fields) - 2, 3):
        path, _attr, value = fields[i], fields[i + 1], fields[i + 2]
        if value == "set":
            ignored.add(path)
    return ignored


def release_files() -> list[str]:
    """The sorted file set a release archive would contain (export-ignore applied)."""
    tracked = _git(["ls-files"])
    ignored = _export_ignored(tracked)
    return sorted(p for p in tracked if p not in ignored)


def _matches_forbidden_path(path: str) -> str | None:
    for pattern in FORBIDDEN_PATH_PATTERNS:
        if fnmatch.fnmatch(path, pattern):
            return pattern
    return None


def _scan_references(path: str) -> list[str]:
    file_path = ROOT / path
    if file_path.suffix.lower() not in _TEXT_SUFFIXES or not file_path.is_file():
        return []
    try:
        text = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    hits: list[str] = []
    for regex, label in FORBIDDEN_REFERENCE_PATTERNS:
        if regex.search(text):
            hits.append(f"{path}: forbidden reference — {label}")
    return hits


def scan(files: list[str]) -> list[str]:
    problems: list[str] = []
    for path in files:
        pattern = _matches_forbidden_path(path)
        if pattern is not None:
            problems.append(
                f"{path}: forbidden path in release artifact (matches `{pattern}`)"
            )
            continue
        problems.extend(_scan_references(path))
    return problems


def manifest(files: list[str]) -> str:
    digest = hashlib.sha256("\n".join(files).encode("utf-8")).hexdigest()
    lines = [f"release inventory: {len(files)} files", f"sha256: {digest}", ""]
    lines.extend(files)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        files = release_files()
    except RuntimeError as exc:
        print(f"release-inventory: FAIL\n  - {exc}")
        return 1

    problems = scan(files)

    if "--manifest" in argv:
        # Exact-head evidence, but still fail closed: emit the inventory + digest and
        # then surface any violation with a nonzero exit.
        print(manifest(files))
        if problems:
            print(f"\nrelease-inventory: FAIL ({len(problems)} violation(s))")
            for problem in problems:
                print(f"  - {problem}")
            return 1
        return 0

    if problems:
        print(
            f"release-inventory: FAIL ({len(problems)} violation(s) in {len(files)} release files)"
        )
        for problem in problems:
            print(f"  - {problem}")
        print(
            "\nCustomer release artifacts must not ship Factory-internal or contributor-only "
            "development material. See AGENTS.md and .bicameral/repo-governance.yaml "
            "(customer_distribution)."
        )
        return 1

    print(
        f"release-inventory: OK ({len(files)} release files, no forbidden paths or references)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
