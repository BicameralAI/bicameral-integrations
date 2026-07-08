# SPDX-License-Identifier: MIT
"""Slack connector package."""

from .connector import SlackConnector, parse_message

__all__ = ["SlackConnector", "parse_message"]
