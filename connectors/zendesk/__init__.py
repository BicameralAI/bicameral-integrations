# SPDX-License-Identifier: MIT
"""Zendesk connector package."""

from .connector import ZendeskConnector, parse_ticket

__all__ = ["ZendeskConnector", "parse_ticket"]
