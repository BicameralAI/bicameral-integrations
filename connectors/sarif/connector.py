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
from adapter.core.redaction import redact


def _first_location(result: dict) -> tuple[str, str]:
    """Return (uri, start_line) from the first physical location, or ("", "")."""
    for loc in result.get("locations") or []:
        phys = loc.get("physicalLocation") or {}
        uri = (phys.get("artifactLocation") or {}).get("uri") or ""
        line = (phys.get("region") or {}).get("startLine")
        return uri, str(line) if line is not None else ""
    return "", ""


def parse_result(result: dict, tool_name: str) -> Observation:
    """Map one SARIF result into a provider-neutral Observation.

    A scanner finding's ``message.text`` can quote the very secret it flags (a secret-scanner emits
    "Detected AWS key AKIA... in config.py") -> **redact-and-pass** (`redact()` scrubs secret/PHI/PAN +
    email/phone). This is the security-correct choice: emitted RAW, FX-SEC-001 would HARD-REJECT the
    finding and the security signal would be lost; redact-and-pass scrubs the secret VALUE and PRESERVES
    the finding ("Detected AWS key [redacted:secret] in config.py") -- SG-2026-06-13-E. The connector reads
    the finding ``message`` only, NEVER the raw code ``region.snippet.text`` (data minimization). The
    ``ruleId``/``ref`` floor (a rule identifier + repo path) is NOT redacted.
    """
    rule_id = result.get("ruleId") or ""
    message = redact((result.get("message") or {}).get("text") or "")
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
    """Flatten a SARIF report into one Observation per result across all runs.

    Per-result resilient (purple-team SARIF-PARSE-1, the #59 per-row pattern): a non-list
    ``runs``/``results`` or a non-dict ``run``/``result`` is SKIPPED, so one malformed row
    drops only itself, not every other finding in the report.
    """
    out: list[Observation] = []
    runs = report.get("runs")
    for run in runs if isinstance(runs, list) else []:
        if not isinstance(run, dict):
            continue
        tool_name = (((run.get("tool") or {}).get("driver") or {}).get("name")) or ""
        results = run.get("results")
        for result in results if isinstance(results, list) else []:
            if isinstance(result, dict):
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
