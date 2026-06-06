# SPDX-License-Identifier: MIT
"""GitHub PR contributor reputation check.

This is a conservative pre-review gate for unknown PR authors. It does not decide
whether code is acceptable; it flags account patterns that deserve extra human
scrutiny before maintainers spend review authority on the patch.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

_API_ROOT = "https://api.github.com"
_ALLOWLIST_PATH = Path(__file__).resolve().parent / "contributor_check_allowlist.json"

_FEATURE_BUCKETS: dict[str, tuple[str, ...]] = {
    "source_adapters": ("adapter", "connector", "integration", "webhook", "ingest"),
    "governance": ("governance", "policy", "gate", "compliance", "audit"),
    "evidence": ("evidence", "provenance", "observation", "ledger", "trace"),
    "security": ("security", "redaction", "secret", "hmac", "signature"),
    "agent_systems": ("agent", "mcp", "llm", "ai", "copilot"),
    "review_workflow": ("pull request", "review", "ci", "github", "workflow"),
}

_ABUSE_SIGNALS = frozenset(
    {
        "credential_laundering",
        "coordinated_promotion",
        "self_promotion_spray",
        "thin_credibility",
    }
)
_DAMPEN_RULES: dict[str, tuple[str, int | None]] = {
    "recent_repo_burst": ("LOW", 8),
    "cross_repo_spread": ("LOW", None),
    "feature_overlap": ("MEDIUM", 5),
}
_PARTIAL_DAMPEN_SIGNALS = frozenset({"feature_overlap", "cross_repo_spread"})


@dataclass
class Signal:
    """One reputation signal contributing to the final risk."""

    name: str
    severity: str
    detail: str
    value: int | None = None


@dataclass
class ReputationReport:
    """Contributor-check output."""

    username: str
    risk: str = "LOW"
    signals: list[Signal] = field(default_factory=list)

    def add(self, signal: Signal) -> None:
        self.signals.append(signal)

    def compute_risk(self) -> None:
        severities = {s.severity for s in self.signals}
        if "HIGH" in severities:
            self.risk = "HIGH"
        elif "MEDIUM" in severities:
            self.risk = "MEDIUM"
        else:
            self.risk = "LOW"

    def as_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "risk": self.risk,
            "signals": [s.__dict__ for s in self.signals],
        }


def _get_token() -> str:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def _ensure_https(req: Request) -> None:
    """Reject any non-HTTPS request URL before opening it.

    All URLs are built from ``_API_ROOT`` (https), but this is an explicit defense so
    ``urlopen`` can never be coerced into a ``file:``/custom scheme (Bandit B310). The
    raised ``URLError`` is already handled by both call sites (→ ``None``/``False``).
    """
    if not req.full_url.lower().startswith("https://"):
        raise URLError("non-https url rejected")


def _api(path: str, params: dict[str, str] | None = None) -> Any:
    """Call the GitHub REST API and return parsed JSON, or ``None`` on failure."""

    query = ""
    if params:
        query = "?" + "&".join(f"{quote(k)}={quote(v)}" for k, v in params.items())
    req = Request(f"{_API_ROOT}{path}{query}")
    token = _get_token()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        _ensure_https(req)
        with urlopen(req, timeout=15) as resp:  # nosec B310 - https enforced by _ensure_https
            body = resp.read()
    except (HTTPError, URLError, TimeoutError, OSError):
        return None
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError:
        return None


def _parse_dt(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def _age_days(created_at: str) -> int:
    created = _parse_dt(created_at)
    if created is None:
        return 0
    return (datetime.now(timezone.utc) - created).days


def _is_established(user: dict[str, Any]) -> bool:
    """Return True when the personal account has strong organic credibility."""

    age_days = _age_days(str(user.get("created_at", "")))
    followers = int(user.get("followers") or 0)
    public_repos = int(user.get("public_repos") or 0)
    return age_days >= 366 and followers >= 50 and public_repos >= 20


def _is_established_repo_aged(repo: dict[str, Any]) -> bool:
    """Repo credibility that requires both age and sustained traction."""

    stars = int(repo.get("stargazers_count") or 0)
    if stars < 10:
        return False
    return _age_days(str(repo.get("created_at", ""))) >= 365


def _search_issues(query: str, per_page: int = 30) -> list[dict[str, Any]]:
    data = _api("/search/issues", {"q": query, "per_page": str(per_page)})
    items = data.get("items", []) if isinstance(data, dict) else []
    return [item for item in items if isinstance(item, dict)]


def _user_repos(username: str) -> list[dict[str, Any]]:
    data = _api(
        f"/users/{username}/repos",
        {"per_page": "100", "sort": "created", "direction": "desc"},
    )
    return [repo for repo in data if isinstance(repo, dict)] if isinstance(data, list) else []


def _user_contributed_to(owner: str, repo_name: str, username: str) -> bool:
    """Return True if ``username`` appears in the repo contributor list."""

    contributors = _api(f"/repos/{owner}/{repo_name}/contributors", {"per_page": "100"})
    if not isinstance(contributors, list):
        return False
    uname = username.lower()
    return any(
        isinstance(c, dict) and str(c.get("login", "")).lower() == uname
        for c in contributors
    )


def _org_owned_established(username: str) -> tuple[bool, str]:
    """Credit public org membership only when the user contributed to an aged repo."""

    orgs = _api(f"/users/{username}/orgs", {"per_page": "100"})
    if not isinstance(orgs, list):
        return False, ""
    for org in orgs[:10]:
        login = org.get("login") if isinstance(org, dict) else ""
        if not login:
            continue
        repos = _api(f"/orgs/{login}/repos", {"per_page": "100", "sort": "pushed"})
        if not isinstance(repos, list):
            continue
        for repo in repos[:50]:
            name = repo.get("name") if isinstance(repo, dict) else ""
            if (
                name
                and not repo.get("fork")
                and _is_established_repo_aged(repo)
                and _user_contributed_to(str(login), str(name), username)
            ):
                stars = int(repo.get("stargazers_count") or 0)
                return True, f"{login}/{name} ({stars} stars)"
    return False, ""


def _is_public_org_member(org: str, login: str) -> bool:
    """Return True when ``login`` is a public member of ``org``."""

    if not org or not login:
        return False
    req = Request(f"{_API_ROOT}/orgs/{org}/public_members/{login}")
    token = _get_token()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        _ensure_https(req)
        with urlopen(req, timeout=15) as resp:  # nosec B310 - https enforced by _ensure_https
            return getattr(resp, "status", resp.getcode()) == 204
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def _has_prior_target_contribution(username: str, target_repo: str | None) -> bool:
    """Credit >=2 merged PRs merged by distinct public members of the target org."""

    if not target_repo or "/" not in target_repo:
        return False
    target_org = target_repo.split("/", 1)[0]
    prs = _search_issues(f"repo:{target_repo} author:{username} is:pr is:merged", 10)
    maintainers: set[str] = set()
    for pr in prs[:10]:
        number = pr.get("number")
        if not number:
            continue
        detail = _api(f"/repos/{target_repo}/pulls/{number}")
        merged_by = ((detail or {}).get("merged_by") or {}).get("login", "")
        if not merged_by or merged_by.lower() == username.lower():
            continue
        if merged_by.lower() in maintainers:
            continue
        if _is_public_org_member(target_org, merged_by):
            maintainers.add(merged_by.lower())
            if len(maintainers) >= 2:
                return True
    return False


def _established_credibility(
    user: dict[str, Any], org_backed: bool = False, prior_interaction: bool = False
) -> tuple[bool, bool]:
    """Return ``(credible, full_tier)``.

    Personal account establishment is the full tier. Org-backed and prior-target
    interaction are partial tiers that vouch for domain overlap, not sudden volume.
    """

    full = _is_established(user)
    return full or org_backed or prior_interaction, full


def _load_allowlist(path: Path | None = None) -> tuple[set[str], set[str]]:
    """Load maintainer-curated user/org allowlist entries as lowercase sets."""

    p = path or _ALLOWLIST_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set(), set()
    users = {str(u).lower() for u in data.get("users", []) if isinstance(u, str)}
    orgs = {str(o).lower() for o in data.get("orgs", []) if isinstance(o, str)}
    return users, orgs


def _is_allowlisted(
    username: str, user_orgs: list[str], allowlist: tuple[set[str], set[str]]
) -> bool:
    users, orgs = allowlist
    return username.lower() in users or any(org.lower() in orgs for org in user_orgs)


def _repo_text(repo: dict[str, Any]) -> str:
    fields = [
        repo.get("name", ""),
        repo.get("full_name", ""),
        repo.get("description", ""),
        " ".join(repo.get("topics") or []),
        repo.get("language", ""),
    ]
    return " ".join(str(field).lower() for field in fields if field)


def check_feature_overlap(
    username: str, target_repo: str | None = None, repos: list[dict[str, Any]] | None = None
) -> list[Signal]:
    """Find young/thin repos that overlap this project's feature vocabulary."""

    target = (target_repo or "").lower()
    signals: list[Signal] = []
    for repo in repos if repos is not None else _user_repos(username):
        if repo.get("fork"):
            continue
        full_name = str(repo.get("full_name") or "").lower()
        if target and full_name == target:
            continue
        if _is_established_repo_aged(repo):
            continue
        text = _repo_text(repo)
        buckets = [
            bucket
            for bucket, words in _FEATURE_BUCKETS.items()
            if any(word in text for word in words)
        ]
        if len(buckets) >= 4:
            signals.append(
                Signal(
                    name="feature_overlap",
                    severity="HIGH",
                    detail=f"{repo.get('full_name') or repo.get('name')} overlaps {len(buckets)} feature buckets",
                    value=len(buckets),
                )
            )
    return signals


def _check_account_shape(user: dict[str, Any]) -> list[Signal]:
    age = _age_days(str(user.get("created_at", "")))
    followers = int(user.get("followers") or 0)
    public_repos = int(user.get("public_repos") or 0)
    if age < 30 and followers < 3:
        return [
            Signal(
                name="thin_credibility",
                severity="HIGH",
                detail=f"new low-signal account ({age} days old, {followers} followers)",
                value=age,
            )
        ]
    if age < 180 and followers < 10 and public_repos < 5:
        return [
            Signal(
                name="thin_credibility",
                severity="MEDIUM",
                detail=f"young low-signal account ({age} days old, {followers} followers)",
                value=age,
            )
        ]
    return []


def _check_recent_repo_burst(repos: list[dict[str, Any]]) -> list[Signal]:
    recent = [
        repo
        for repo in repos
        if not repo.get("fork") and _age_days(str(repo.get("created_at", ""))) <= 90
    ]
    count = len(recent)
    if count >= 8:
        return [
            Signal(
                name="recent_repo_burst",
                severity="HIGH",
                detail=f"{count} public repos created in the last 90 days",
                value=count,
            )
        ]
    if count >= 4:
        return [
            Signal(
                name="recent_repo_burst",
                severity="MEDIUM",
                detail=f"{count} public repos created in the last 90 days",
                value=count,
            )
        ]
    return []


def _check_cross_repo_spread(username: str) -> list[Signal]:
    since = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
    issues = _search_issues(f"author:{username} created:>={since}", 50)
    repos = {
        str(item.get("repository_url", "")).removeprefix(f"{_API_ROOT}/repos/")
        for item in issues
        if item.get("repository_url")
    }
    count = len(repos)
    if count >= 8:
        return [
            Signal(
                name="cross_repo_spread",
                severity="HIGH",
                detail=f"recent issues/PRs across {count} repositories",
                value=count,
            )
        ]
    if count >= 5:
        return [
            Signal(
                name="cross_repo_spread",
                severity="MEDIUM",
                detail=f"recent issues/PRs across {count} repositories",
                value=count,
            )
        ]
    return []


def _dampen_for_established_accounts(
    report: ReputationReport,
    user: dict[str, Any],
    *,
    established: bool | None = None,
    full: bool = True,
) -> None:
    """Downgrade eligible signals for credible accounts without hiding abuse."""

    if established is None:
        established = _is_established(user)
    if not established:
        return
    names = {signal.name for signal in report.signals}
    if names & _ABUSE_SIGNALS:
        return
    overlap_high = sum(
        1 for s in report.signals if s.name == "feature_overlap" and s.severity == "HIGH"
    )
    for signal in report.signals:
        rule = _DAMPEN_RULES.get(signal.name)
        if rule is None:
            continue
        if not full and signal.name not in _PARTIAL_DAMPEN_SIGNALS:
            continue
        if signal.name == "feature_overlap" and overlap_high >= 2:
            continue
        new_severity, max_value = rule
        if max_value is not None and signal.value is not None and signal.value > max_value:
            continue
        signal.severity = new_severity
        signal.detail += " (dampened for contributor credibility)"


def check_contributor(username: str, target_repo: str | None = None) -> ReputationReport:
    """Run the contributor reputation check."""

    report = ReputationReport(username=username)
    user = _api(f"/users/{username}")
    if not isinstance(user, dict):
        report.add(
            Signal(
                name="github_lookup_failed",
                severity="HIGH",
                detail="could not load contributor profile from GitHub",
            )
        )
        report.compute_risk()
        return report

    repos = _user_repos(username)
    for signal in _check_account_shape(user):
        report.add(signal)
    for signal in _check_recent_repo_burst(repos):
        report.add(signal)
    for signal in _check_cross_repo_spread(username):
        report.add(signal)
    for signal in check_feature_overlap(username, target_repo, repos):
        report.add(signal)

    try:
        org_backed, _evidence = _org_owned_established(username)
        prior_interaction = _has_prior_target_contribution(username, target_repo)
    except Exception:
        org_backed, prior_interaction = False, False
    established, full_tier = _established_credibility(user, org_backed, prior_interaction)
    _dampen_for_established_accounts(report, user, established=established, full=full_tier)
    report.compute_risk()

    orgs_resp = _api(f"/users/{username}/orgs", {"per_page": "100"})
    user_orgs = (
        [str(org.get("login", "")) for org in orgs_resp if isinstance(org, dict)]
        if isinstance(orgs_resp, list)
        else []
    )
    if _is_allowlisted(username, user_orgs, _load_allowlist()):
        report.risk = "LOW"
        report.add(
            Signal(
                name="allowlisted",
                severity="LOW",
                detail="maintainer allowlist: auto-flag downgraded; code review still required",
            )
        )
    return report


def _print_text(report: ReputationReport) -> None:
    print(f"contributor-check: {report.username} risk={report.risk}")
    for signal in report.signals:
        value = "" if signal.value is None else f" value={signal.value}"
        print(f"- {signal.severity} {signal.name}:{value} {signal.detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("--target-repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--fail-on", choices=["HIGH", "MEDIUM", "LOW"], default="HIGH")
    args = parser.parse_args(argv)

    report = check_contributor(args.username, args.target_repo)
    if args.json_output:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        _print_text(report)

    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    return 1 if order[report.risk] >= order[args.fail_on] else 0


if __name__ == "__main__":
    sys.exit(main())
