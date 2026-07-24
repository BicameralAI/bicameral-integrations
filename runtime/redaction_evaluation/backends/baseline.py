# SPDX-License-Identifier: MIT
"""Baseline candidate: the current ``bicameral-stdlib-redaction`` engine.

Re-expresses the production catalog + generic-PII patterns as span findings
for the seam. The pattern objects are imported from ``adapter.core`` so the
baseline candidate can never drift from the reviewed production detector.
"""

from __future__ import annotations

from adapter.core import redaction as _redaction
from adapter.core import sensitive as _sensitive
from adapter.core.redaction_receipt import ENGINE, ENGINE_VERSION, RULESET_DIGEST

from ..policy import LabelMap, RedactionPolicy
from ..seam import BackendFinding, BackendHealth, BackendIdentity

_LABEL_MAP = LabelMap(
    map_id="bicameral-stdlib-labels-v1",
    mapping={
        "secret": ("secret", "secret"),
        "phi": ("phi", "phi"),
        "pan": ("credential", "pan"),
        "email": ("pii", "email"),
        "phone": ("pii", "phone"),
    },
)

# Priority order for overlapping raw matches mirrors the production
# substitution order: catalog classes are protected before the generic
# PII patterns may fragment them.
_PRIORITY = {"secret": 0, "phi": 1, "pan": 2, "email": 3, "phone": 4}


class BicameralStdlibBackend:
    """Detection-only view of the current production engine."""

    def __init__(self) -> None:
        self._identity = BackendIdentity(
            candidate_id="bicameral-stdlib-v1",
            family="bicameral-stdlib",
            engine_version=ENGINE_VERSION,
            packages={"python-stdlib-re": "builtin"},
            models={},
            configuration={
                "engine": ENGINE,
                "ruleset_digest": RULESET_DIGEST,
                "catalog": "FX-SEC-001/v1",
                "label_map": _LABEL_MAP.map_id,
            },
        )

    @property
    def identity(self) -> BackendIdentity:
        return self._identity

    @property
    def label_map(self) -> LabelMap:
        return _LABEL_MAP

    def initialize(self) -> None:  # stdlib engine has nothing to load
        return None

    def health(self) -> BackendHealth:
        return BackendHealth(ready=True)

    def analyze(
        self,
        text: str,
        *,
        field_path: str,
        policy: RedactionPolicy,
    ) -> list[BackendFinding]:
        del field_path, policy
        raw: list[tuple[int, int, int, str]] = []
        for _label, pattern in _sensitive._SECRET_PATTERNS:
            for match in pattern.finditer(text):
                raw.append((_PRIORITY["secret"], match.start(), match.end(), "secret"))
        for pattern in _sensitive._REDACT_PHI_PATTERNS:
            for match in pattern.finditer(text):
                raw.append((_PRIORITY["phi"], match.start(), match.end(), "phi"))
        for match in _sensitive._PAN_CANDIDATE_RE.finditer(text):
            digits = match.group(0)
            if _sensitive._is_id_preceded(text, match.start()):
                continue
            if not _sensitive._luhn_valid(digits):
                continue
            raw.append((_PRIORITY["pan"], match.start(), match.end(), "pan"))
        for match in _redaction._EMAIL_RE.finditer(text):
            raw.append((_PRIORITY["email"], match.start(), match.end(), "email"))
        for match in _redaction._PHONE_RE.finditer(text):
            raw.append((_PRIORITY["phone"], match.start(), match.end(), "phone"))
        for match in _redaction._PHONE_CONTEXT_RE.finditer(text):
            raw.append((_PRIORITY["phone"], match.start(2), match.end(2), "phone"))

        raw.sort(key=lambda item: (item[0], item[1], -(item[2] - item[1])))
        taken: list[tuple[int, int]] = []
        findings: list[BackendFinding] = []
        for _prio, start, end, label in raw:
            if any(start < t_end and end > t_start for t_start, t_end in taken):
                continue
            taken.append((start, end))
            category, subtype = _LABEL_MAP.mapping[label]
            findings.append(
                BackendFinding(
                    category=category,
                    subtype=subtype,
                    start=start,
                    end=end,
                    backend_label=label,
                    confidence=1.0,
                )
            )
        findings.sort(key=lambda f: (f.start, f.end))
        return findings
