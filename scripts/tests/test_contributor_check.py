# SPDX-License-Identifier: MIT
"""Behavioral tests for the contributor reputation check."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contributor_check import (  # noqa: E402
    ReputationReport,
    Signal,
    _dampen_for_established_accounts,
    _established_credibility,
    _has_prior_target_contribution,
    _is_allowlisted,
    _is_established_repo_aged,
    _load_allowlist,
    check_contributor,
)

TARGET = "BicameralAI/bicameral-integrations"


def _iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _user(*, days: int = 900, followers: int = 12, repos: int = 3) -> dict:
    return {
        "login": "dev",
        "created_at": _iso(days),
        "followers": followers,
        "public_repos": repos,
    }


def _repo(
    name: str,
    *,
    stars: int = 0,
    days: int = 20,
    owner: str = "dev",
    description: str = "source adapter governance evidence security agent review workflow",
) -> dict:
    return {
        "name": name,
        "full_name": f"{owner}/{name}",
        "description": description,
        "topics": [],
        "fork": False,
        "created_at": _iso(days),
        "stargazers_count": stars,
        "language": "Python",
    }


def test_allowlist_loads_users_and_orgs_case_insensitively(tmp_path):
    path = tmp_path / "allowlist.json"
    path.write_text(json.dumps({"users": ["Trusted"], "orgs": ["KnownOrg"]}), encoding="utf-8")

    allowlist = _load_allowlist(path)

    assert _is_allowlisted("trusted", [], allowlist)
    assert _is_allowlisted("someone", ["knownorg"], allowlist)


def test_established_repo_requires_age_and_stars():
    assert _is_established_repo_aged(_repo("mature", stars=10, days=366))
    assert not _is_established_repo_aged(_repo("young", stars=50, days=30))
    assert not _is_established_repo_aged(_repo("old-thin", stars=9, days=700))


def test_prior_target_contribution_requires_distinct_public_maintainers():
    prs = [{"number": 1}, {"number": 2}]

    def fake_api(path, params=None):
        if path.endswith("/pulls/1"):
            return {"merged_by": {"login": "maintA"}}
        if path.endswith("/pulls/2"):
            return {"merged_by": {"login": "maintB"}}
        raise AssertionError(path)

    with (
        patch("contributor_check._search_issues", return_value=prs),
        patch("contributor_check._api", side_effect=fake_api),
        patch("contributor_check._is_public_org_member", return_value=True),
    ):
        assert _has_prior_target_contribution("dev", TARGET)


def test_prior_target_contribution_rejects_self_merge_and_same_maintainer():
    prs = [{"number": 1}, {"number": 2}]

    with (
        patch("contributor_check._search_issues", return_value=prs),
        patch("contributor_check._api", return_value={"merged_by": {"login": "dev"}}),
        patch("contributor_check._is_public_org_member", return_value=True),
    ):
        assert not _has_prior_target_contribution("dev", TARGET)

    with (
        patch("contributor_check._search_issues", return_value=prs),
        patch("contributor_check._api", return_value={"merged_by": {"login": "maintA"}}),
        patch("contributor_check._is_public_org_member", return_value=True),
    ):
        assert not _has_prior_target_contribution("dev", TARGET)


def test_partial_credibility_dampens_domain_overlap_not_volume():
    report = ReputationReport("specialist")
    report.add(Signal("feature_overlap", "HIGH", "one repo", value=4))
    report.add(Signal("recent_repo_burst", "HIGH", "many repos", value=8))

    _dampen_for_established_accounts(
        report, _user(followers=1, repos=1), established=True, full=False
    )

    by_name = {signal.name: signal.severity for signal in report.signals}
    assert by_name["feature_overlap"] == "MEDIUM"
    assert by_name["recent_repo_burst"] == "HIGH"


def test_multi_overlap_stays_high_even_for_credible_account():
    report = ReputationReport("split")
    report.add(Signal("feature_overlap", "HIGH", "repo a", value=4))
    report.add(Signal("feature_overlap", "HIGH", "repo b", value=5))

    _dampen_for_established_accounts(
        report, _user(followers=100, repos=30), established=True, full=True
    )

    assert all(signal.severity == "HIGH" for signal in report.signals)


class FakeGitHub:
    def __init__(
        self,
        *,
        username: str,
        user: dict,
        repos: list[dict],
        orgs=None,
        org_repos=None,
        contributors=None,
    ):
        self.username = username
        self.user = user
        self.repos = repos
        self.orgs = orgs or []
        self.org_repos = org_repos or {}
        self.contributors = contributors or {}

    def api(self, path, params=None):
        if path == f"/users/{self.username}":
            return self.user
        if path == f"/users/{self.username}/repos":
            return self.repos
        if path == f"/users/{self.username}/orgs":
            return self.orgs
        if path == "/search/issues":
            return {"items": []}
        if path.startswith("/orgs/") and path.endswith("/repos"):
            org = path[len("/orgs/") : -len("/repos")]
            return self.org_repos.get(org, [])
        if path.startswith("/repos/") and path.endswith("/contributors"):
            repo = path[len("/repos/") : -len("/contributors")]
            return [{"login": login} for login in self.contributors.get(repo, [])]
        raise AssertionError(path)


def _run(fake: FakeGitHub, allowlist=(frozenset(), frozenset())):
    with (
        patch("contributor_check._api", side_effect=fake.api),
        patch("contributor_check._load_allowlist", return_value=allowlist),
        patch("contributor_check._has_prior_target_contribution", return_value=False),
    ):
        return check_contributor(fake.username, TARGET)


def test_throwaway_with_split_overlap_is_high():
    fake = FakeGitHub(
        username="throwaway",
        user=_user(days=10, followers=0, repos=2),
        repos=[_repo("clone-a"), _repo("clone-b")],
    )

    report = _run(fake)

    assert report.risk == "HIGH"
    assert {signal.name for signal in report.signals} >= {"thin_credibility", "feature_overlap"}


def test_allowlisted_contributor_is_downgraded_to_low():
    fake = FakeGitHub(
        username="trusted",
        user=_user(days=10, followers=0, repos=2),
        repos=[_repo("clone-a"), _repo("clone-b")],
    )

    report = _run(fake, allowlist=({"trusted"}, frozenset()))

    assert report.risk == "LOW"
    assert any(signal.name == "allowlisted" for signal in report.signals)


def test_org_backed_specialist_single_overlap_is_not_high():
    fake = FakeGitHub(
        username="specialist",
        user=_user(days=900, followers=5, repos=3),
        repos=[
            _repo(
                "bicameral-adapter-kit",
                description="source adapter governance evidence security",
            )
        ],
        orgs=[{"login": "myorg"}],
        org_repos={"myorg": [_repo("flagship", stars=25, days=700, owner="myorg")]},
        contributors={"myorg/flagship": ["specialist"]},
    )

    report = _run(fake)

    assert report.risk == "MEDIUM"
    assert any(
        signal.name == "feature_overlap" and signal.severity == "MEDIUM"
        for signal in report.signals
    )


def test_established_credibility_tiers():
    assert _established_credibility(_user(followers=100, repos=30)) == (True, True)
    assert _established_credibility(_user(followers=1, repos=1), org_backed=True) == (
        True,
        False,
    )
    assert _established_credibility(_user(followers=1, repos=1)) == (False, False)
