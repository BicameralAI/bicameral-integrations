# SPDX-License-Identifier: MIT
"""GitHub connector package."""

from .connector import GitHubConnector, parse_pull_request

__all__ = ["GitHubConnector", "parse_pull_request"]
