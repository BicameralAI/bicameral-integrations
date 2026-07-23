# SPDX-License-Identifier: MIT
"""Tracked factory-attestation gate (integrations#249 governance-owner decision).

The governance owner authorized tracking factory attestations in-repo under
``.bicameral/factory-attestations/*.json`` (see integrations#249). This gate validates
every tracked attestation, fail-closed, on exactly the dimensions the owner enumerated:

1. **Filename** — ``<factory_commit>.json`` (legacy) or ``<factory_commit>.<run-id>.json``.
2. **Schema** — required top-level fields (read from the pinned mirror
   ``docs/governance/factory-attestation.schema.json``) plus the value constraints the
   canonical Factory validator enforces.
3. **Factory commit** — a 40-char lowercase SHA that reconciles with the pinned
   ``factory_governance.commit`` in ``docs/governance/PIN.json``.
4. **Roadmap reconciliation** — the ``roadmap_reconciliation`` block is present and complete.
5. **State refinement** — the ``state_refinement`` block is present and complete.

Only ``.bicameral/repo-governance.yaml`` and ``.bicameral/factory-attestations/*.json`` are
commit-permitted under ``.bicameral/`` (enforced by ``validate_governance_boundary.py``);
``.bicameral/**`` stays excluded from customer release artifacts (``.gitattributes``
``export-ignore`` + ``scripts/check_release_inventory.py``).

Stdlib only; no live network. Exit 0 on success, exit 1 on any violation or Git failure.
"""

from __future__ import annotations

import json
import re
import subprocess  # nosec B404 — git invocation, not user-controlled
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN_PATH = ROOT / "docs" / "governance" / "PIN.json"
SCHEMA_PATH = ROOT / "docs" / "governance" / "factory-attestation.schema.json"
ATTESTATION_DIR = ".bicameral/factory-attestations"

SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RUN_ID_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]*$")
GITHUB_PR_RE = re.compile(r"^https://github\.com/[^/]+/[^/]+/pull/[0-9]+$")
GITHUB_ISSUE_COMMENT_RE = re.compile(
    r"^https://github\.com/[^/]+/[^/]+/issues/[0-9]+#issuecomment-[0-9]+$"
)
FACTORY_PR_RE = re.compile(
    r"^https://github\.com/BicameralAI/bicameral-factory/pull/[0-9]+$"
)

ALLOWED_DIVERGENCE_RESOLUTIONS = {"none", "promoted", "disabled", "not_applicable"}
ALLOWED_ROADMAP_TYPES = {"validated", "validating", "deferred"}
ALLOWED_PROJECT_STATUSES = {"Todo", "In Progress", "Done"}


def _git(args: list[str]) -> tuple[int, list[str]]:
    result = subprocess.run(  # nosec B603 B607
        ["git", *args],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    return result.returncode, lines


def tracked_attestations() -> tuple[list[str], str | None]:
    code, lines = _git(["ls-files", "--", f"{ATTESTATION_DIR}/*.json"])
    if code != 0:
        return [], "git ls-files failed (not a git tree?)"
    return sorted(lines), None


def _pinned_factory_commit() -> tuple[str | None, str | None]:
    if not PIN_PATH.exists():
        return None, f"pin not found: {PIN_PATH}"
    try:
        pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"invalid PIN.json: {exc}"
    commit = pin.get("factory_governance", {}).get("commit")
    if not isinstance(commit, str) or not SHA40_RE.match(commit):
        return None, "PIN.json factory_governance.commit missing or not a 40-char SHA"
    return commit, None


def _required_top_level() -> list[str]:
    """Presence set is driven by the pinned attestation schema mirror when available."""
    if SCHEMA_PATH.exists():
        try:
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
            required = schema.get("required")
            if isinstance(required, list) and all(isinstance(k, str) for k in required):
                return required
        except json.JSONDecodeError:
            pass
    return [
        "version",
        "factory_repo",
        "factory_commit",
        "loaded_context",
        "local_setup_divergence",
        "roadmap_reconciliation",
        "state_refinement",
        "end_of_session_capture",
        "attested_by",
        "timestamp",
    ]


def _valid_datetime(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _check_filename(rel_path: str, factory_commit: object) -> list[str]:
    name = Path(rel_path).name
    if not isinstance(factory_commit, str) or not SHA40_RE.match(factory_commit):
        return []  # commit error is reported separately
    if name == f"{factory_commit}.json":
        return []
    stem = name[:-5] if name.endswith(".json") else name
    prefix = f"{factory_commit}."
    if stem.startswith(prefix) and RUN_ID_RE.match(stem[len(prefix) :]):
        return []
    return [
        f"filename must be {factory_commit}.<run-id>.json (preferred) or "
        f"{factory_commit}.json for factory_commit {factory_commit}"
    ]


def _check_roadmap(roadmap: object) -> list[str]:
    if not isinstance(roadmap, dict):
        return ["roadmap_reconciliation must be an object"]
    errors: list[str] = []
    if roadmap.get("checked") is not True:
        errors.append("roadmap_reconciliation.checked must be true")
    issue_number = roadmap.get("issue_number")
    if (
        not isinstance(issue_number, int)
        or isinstance(issue_number, bool)
        or issue_number <= 0
    ):
        errors.append("roadmap_reconciliation.issue_number must be a positive integer")
    if roadmap.get("issue_type") not in ALLOWED_ROADMAP_TYPES:
        errors.append(
            "roadmap_reconciliation.issue_type must be one of: "
            + ", ".join(sorted(ALLOWED_ROADMAP_TYPES))
        )
    if roadmap.get("project_status") not in ALLOWED_PROJECT_STATUSES:
        errors.append(
            "roadmap_reconciliation.project_status must be one of: "
            + ", ".join(sorted(ALLOWED_PROJECT_STATUSES))
        )
    if roadmap.get("pr_links_checked") is not True:
        errors.append("roadmap_reconciliation.pr_links_checked must be true")
    if roadmap.get("pr_body_links_issue") is not True:
        errors.append("roadmap_reconciliation.pr_body_links_issue must be true")
    pr_links = roadmap.get("pr_links")
    if not isinstance(pr_links, list) or not all(
        isinstance(x, str) and GITHUB_PR_RE.match(x) for x in pr_links
    ):
        errors.append(
            "roadmap_reconciliation.pr_links must be an array of GitHub PR URLs"
        )
    comment_url = roadmap.get("post_work_comment_url")
    if comment_url is not None and (
        not isinstance(comment_url, str)
        or not GITHUB_ISSUE_COMMENT_RE.match(comment_url)
    ):
        errors.append(
            "roadmap_reconciliation.post_work_comment_url must be null or an issue-comment URL"
        )
    if roadmap.get("issue_type") == "deferred":
        override = roadmap.get("deferred_override_reason")
        if not isinstance(override, str) or not override.strip():
            errors.append(
                "roadmap_reconciliation.deferred_override_reason is required when deferred"
            )
    return errors


def _check_state_refinement(state: object) -> list[str]:
    if not isinstance(state, dict):
        return ["state_refinement must be an object"]
    errors: list[str] = []
    if state.get("checked") is not True:
        errors.append("state_refinement.checked must be true")
    if (
        not isinstance(state.get("release_state"), str)
        or not state["release_state"].strip()
    ):
        errors.append("state_refinement.release_state must be a non-empty string")
    for key in ("states_added", "states_deferred"):
        value = state.get(key)
        if not isinstance(value, list) or not all(
            isinstance(x, str) and x for x in value
        ):
            errors.append(
                f"state_refinement.{key} must be an array of non-empty strings"
            )
    invariants = state.get("invariants")
    if (
        not isinstance(invariants, list)
        or not invariants
        or not all(isinstance(x, str) and x.strip() for x in invariants)
    ):
        errors.append(
            "state_refinement.invariants must be a non-empty array of strings"
        )
    review = state.get("minimization_review")
    if not isinstance(review, dict):
        errors.append("state_refinement.minimization_review must be an object")
    else:
        if review.get("reviewed") is not True:
            errors.append("state_refinement.minimization_review.reviewed must be true")
        rejected = review.get("rejected_or_collapsed_states")
        if not isinstance(rejected, list) or not all(
            isinstance(x, str) and x for x in rejected
        ):
            errors.append(
                "state_refinement.minimization_review.rejected_or_collapsed_states "
                "must be an array of non-empty strings"
            )
        rationale = review.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(
                "state_refinement.minimization_review.rationale must be a non-empty string"
            )
    return errors


def _check_divergence(divergence: object) -> list[str]:
    if not isinstance(divergence, dict):
        return ["local_setup_divergence must be an object"]
    errors: list[str] = []
    if divergence.get("checked") is not True:
        errors.append("local_setup_divergence.checked must be true")
    if divergence.get("resolution") not in ALLOWED_DIVERGENCE_RESOLUTIONS:
        errors.append(
            "local_setup_divergence.resolution must be one of: "
            + ", ".join(sorted(ALLOWED_DIVERGENCE_RESOLUTIONS))
        )
    if divergence.get("unresolved_items"):
        errors.append(
            "local_setup_divergence.unresolved_items must be empty or omitted"
        )
    if divergence.get("resolution") == "promoted":
        factory_pr = divergence.get("factory_pr")
        if not isinstance(factory_pr, str) or not FACTORY_PR_RE.match(factory_pr):
            errors.append(
                "promoted local_setup_divergence must include a factory PR URL"
            )
    return errors


def validate_attestation(rel_path: str, data: dict, pinned_commit: str) -> list[str]:
    errors: list[str] = []

    # 2. schema — required top-level presence (driven by the pinned schema mirror).
    missing = sorted(set(_required_top_level()) - set(data))
    if missing:
        errors.append(f"missing required field(s): {', '.join(missing)}")

    if data.get("version") != 1:
        errors.append("version must be 1")
    if data.get("factory_repo") != "BicameralAI/bicameral-factory":
        errors.append("factory_repo must be BicameralAI/bicameral-factory")

    # 3. factory commit — well-formed and reconciled with the pin.
    factory_commit = data.get("factory_commit")
    if not isinstance(factory_commit, str) or not SHA40_RE.match(factory_commit):
        errors.append("factory_commit must be a 40-char lowercase git SHA")
    elif factory_commit != pinned_commit:
        errors.append(
            f"factory_commit {factory_commit} does not reconcile with pinned "
            f"factory_governance.commit {pinned_commit} (docs/governance/PIN.json)"
        )

    # 1. filename.
    errors.extend(_check_filename(rel_path, factory_commit))

    loaded = data.get("loaded_context")
    if (
        not isinstance(loaded, list)
        or len(loaded) < 2
        or not all(isinstance(x, str) and x for x in loaded)
        or "README.md" not in loaded
    ):
        errors.append(
            "loaded_context must be an array (>=2) of non-empty strings including README.md"
        )

    errors.extend(_check_divergence(data.get("local_setup_divergence")))
    # 4 + 5. roadmap reconciliation and state refinement.
    errors.extend(_check_roadmap(data.get("roadmap_reconciliation")))
    errors.extend(_check_state_refinement(data.get("state_refinement")))

    capture = data.get("end_of_session_capture")
    if not isinstance(capture, dict):
        errors.append("end_of_session_capture must be an object")
    else:
        if capture.get("run") is not True:
            errors.append("end_of_session_capture.run must be true")
        factory_pr = capture.get("factory_pr")
        if factory_pr is not None and (
            not isinstance(factory_pr, str) or not FACTORY_PR_RE.match(factory_pr)
        ):
            errors.append(
                "end_of_session_capture.factory_pr must be null or a factory PR URL"
            )

    if not isinstance(data.get("attested_by"), str) or not data["attested_by"].strip():
        errors.append("attested_by must be a non-empty string")
    if not _valid_datetime(data.get("timestamp")):
        errors.append("timestamp must be an ISO-8601 date-time string")

    return errors


def main() -> int:
    pinned_commit, pin_error = _pinned_factory_commit()
    if pin_error:
        print(f"factory-attestation: FAIL\n  - {pin_error}")
        return 1
    assert pinned_commit is not None

    paths, git_error = tracked_attestations()
    if git_error:
        print(f"factory-attestation: FAIL\n  - {git_error}")
        return 1

    if not paths:
        print(
            "factory-attestation: OK (no tracked attestations under "
            f"{ATTESTATION_DIR}/)"
        )
        return 0

    problems: list[str] = []
    for rel_path in paths:
        file_path = ROOT / rel_path
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{rel_path}: invalid JSON: {exc}")
            continue
        if not isinstance(data, dict):
            problems.append(f"{rel_path}: attestation must be a JSON object")
            continue
        problems.extend(
            f"{rel_path}: {err}"
            for err in validate_attestation(rel_path, data, pinned_commit)
        )

    if problems:
        print(f"factory-attestation: FAIL ({len(problems)} violation(s))")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(
        f"factory-attestation: OK ({len(paths)} tracked attestation(s) validated: "
        f"filename + schema + factory-commit reconciliation + roadmap + state refinement)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
