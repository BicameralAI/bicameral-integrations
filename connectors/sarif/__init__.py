"""SARIF 2.1.0 connector package."""

from .connector import SarifConnector, parse_result, parse_sarif

__all__ = ["SarifConnector", "parse_result", "parse_sarif"]
