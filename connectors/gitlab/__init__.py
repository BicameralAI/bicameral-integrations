# SPDX-License-Identifier: MIT
"""GitLab connector package."""

from .connector import GitLabConnector, parse_issue, parse_merge_request

__all__ = ["GitLabConnector", "parse_merge_request", "parse_issue"]
