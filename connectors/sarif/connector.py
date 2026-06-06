# SPDX-License-Identifier: MIT
"""SARIF connector: static-analysis findings into neutral Observations.

A SARIF 2.1.0 report (file import, trust tier T0) maps to one Observation per
result across all runs. Provider field knowledge stays here; normalization is
the universal adapter's job (ADR-0004, ADR-0008 — evidence adapter, not state
authority). File ingest only; no auth/network.
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def _first_location(result: dict) -> tuple[str, str]:
    """Return (uri, start_line) from the first physical location, or ("", "")."""
    for loc in result.get("locations") or []:
        phys = loc.get("physicalLocation") or {}
        uri = (phys.get("artifactLocation") or {}).get("uri") or ""
        line = (phys.get("region") or {}).get("startLine")
        return uri, str(line) if line is not None else ""
    return "", ""


def parse_result(result: dict, tool_name: str) -> Observation:
    """Map one SARIF result into a provider-neutral Observation."""
    rule_id = result.get("ruleId") or ""
    message = (result.get("message") or {}).get("text") or ""
    uri, line = _first_location(result)
    ref = f"{rule_id}@{uri}:{line}" if uri else (rule_id or "sarif-result")
    return Observation(
        source_ref=SourceRef(source_id="sarif", ref=ref, kind="finding"),
        excerpt=message or rule_id or ref,
        mode=SourceMode.PASSIVE,
        title=rule_id or "sarif-finding",
        timestamp="",
        metadata={
            "tool": tool_name,
            "level": result.get("level") or "",
            "uri": uri,
            "start_line": line,
        },
    )


def parse_sarif(report: dict) -> list[Observation]:
    """Flatten a SARIF report into one Observation per result across all runs."""
    out: list[Observation] = []
    for run in report.get("runs") or []:
        tool_name = (((run.get("tool") or {}).get("driver") or {}).get("name")) or ""
        for result in run.get("results") or []:
            out.append(parse_result(result, tool_name))
    return out


class SarifConnector:
    """SARIF connector identity plus the static-import parse surface.

    Trust tier T0: file import only. The live file-watch/CI-collection path is
    deferred (see ``auth.md``); this is the parse surface.
    """

    source_id = "sarif"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.PASSIVE}))

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return parse_sarif(payload)
