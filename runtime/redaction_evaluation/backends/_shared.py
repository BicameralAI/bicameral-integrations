# SPDX-License-Identifier: MIT
"""Helpers shared by the heavy candidate backends.

Raw-candidate overlap resolution, version pinning, and the Bicameral
secret/PHI catalog re-expressed for presidio live here so each candidate
states them once. Heavy third-party imports stay inside functions: repo CI
lints and type-checks ``runtime/`` without the spike packages installed.
"""

from __future__ import annotations

from importlib import metadata
from typing import Any

from adapter.core import sensitive as _sensitive

from ..policy import LabelMap, canonical_digest
from ..seam import (
    BackendFinding,
    BackendInvalidConfiguration,
    BackendUnavailable,
)

# One raw candidate as produced by a backend engine, before label mapping and
# overlap resolution: (backend_label, start, end, confidence).
RawCandidate = tuple[str, int, int, float]

BICAMERAL_SECRET_ENTITY = "BICAMERAL_SECRET"
BICAMERAL_PHI_ENTITY = "BICAMERAL_PHI"


def resolve_findings(
    candidates: list[RawCandidate],
    *,
    label_map: LabelMap,
    text_length: int,
    unmapped_counts: dict[str, int],
) -> list[BackendFinding]:
    """Map, bound-check, and overlap-resolve raw candidates deterministically.

    Labels absent from ``label_map`` are dropped and tallied into
    ``unmapped_counts``. Spans that violate ``0 <= start < end <= len(text)``
    are dropped. Overlaps resolve to exactly one finding per span region:
    higher confidence wins, then the longer span, then the lower start, then
    the lexicographically smaller label (a total, deterministic order).
    """

    mapped: list[tuple[float, int, int, str]] = []
    for label, start, end, confidence in candidates:
        if label not in label_map.mapping:
            unmapped_counts[label] = unmapped_counts.get(label, 0) + 1
            continue
        if not (0 <= start < end <= text_length):
            continue
        mapped.append((confidence, start, end, label))

    mapped.sort(key=lambda item: (-item[0], -(item[2] - item[1]), item[1], item[3]))
    taken: list[tuple[int, int]] = []
    findings: list[BackendFinding] = []
    for confidence, start, end, label in mapped:
        if any(start < t_end and end > t_start for t_start, t_end in taken):
            continue
        taken.append((start, end))
        category, subtype = label_map.mapping[label]
        findings.append(
            BackendFinding(
                category=category,
                subtype=subtype,
                start=start,
                end=end,
                backend_label=label,
                confidence=confidence,
            )
        )
    findings.sort(key=lambda finding: (finding.start, finding.end))
    return findings


def require_pinned_version(package: str, pinned: str) -> str:
    """Return the installed version of ``package``; it must equal the pin.

    The candidate identity declares exact versions, so a missing package is
    ``backend_unavailable`` and a version drifting from the pin is
    ``backend_invalid_configuration`` (the pinned identity would be a lie).
    """

    try:
        observed = metadata.version(package)
    except metadata.PackageNotFoundError as exc:
        raise BackendUnavailable("backend_unavailable") from exc
    if observed != pinned:
        raise BackendInvalidConfiguration("backend_invalid_configuration")
    return observed


def observed_version(package: str, fallback: str) -> str:
    """Best-effort installed version with a static fallback pin."""

    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return fallback


def bicameral_catalog_manifest() -> dict[str, object]:
    """JSON-serializable manifest of the Bicameral secret/PHI pattern catalog."""

    return {
        "catalog_version": _sensitive._SENSITIVE_CATALOG_VERSION,
        "secret_patterns": [
            {"id": label, "regex": pattern.pattern}
            for label, pattern in _sensitive._SECRET_PATTERNS
        ],
        "phi_patterns": [
            {"id": f"phi-{index}", "regex": pattern.pattern}
            for index, pattern in enumerate(_sensitive._REDACT_PHI_PATTERNS)
        ],
    }


def bicameral_catalog_digest() -> str:
    """Deterministic digest pinning the exact catalog regex strings."""

    return canonical_digest(bicameral_catalog_manifest())


def bicameral_recognizer_names() -> list[str]:
    """Stable names of the catalog-derived recognizers (no heavy imports)."""

    names = [
        f"bicameral-secret:{label}" for label, _pattern in _sensitive._SECRET_PATTERNS
    ]
    names.extend(
        f"bicameral-phi:phi-{index}"
        for index in range(len(_sensitive._REDACT_PHI_PATTERNS))
    )
    return names


def build_bicameral_recognizers() -> list[Any]:
    """Presidio ``PatternRecognizer``s for the Bicameral secret/PHI catalog.

    One recognizer per catalog entry, each carrying the exact production
    regex string at score 1.0. ``global_regex_flags`` is pinned to
    ``re.UNICODE`` (plain Python-default semantics) instead of presidio's
    IGNORECASE|MULTILINE|DOTALL default, because the secret patterns are
    case-sensitive by design and the PHI patterns carry their own ``(?i)``.
    """

    import re

    from presidio_analyzer import (  # type: ignore[import-not-found]
        Pattern,
        PatternRecognizer,
    )

    recognizers: list[Any] = []
    for label, pattern in _sensitive._SECRET_PATTERNS:
        recognizers.append(
            PatternRecognizer(
                supported_entity=BICAMERAL_SECRET_ENTITY,
                name=f"bicameral-secret:{label}",
                patterns=[Pattern(name=label, regex=pattern.pattern, score=1.0)],
                global_regex_flags=re.UNICODE,
            )
        )
    for index, pattern in enumerate(_sensitive._REDACT_PHI_PATTERNS):
        pattern_id = f"phi-{index}"
        recognizers.append(
            PatternRecognizer(
                supported_entity=BICAMERAL_PHI_ENTITY,
                name=f"bicameral-phi:{pattern_id}",
                patterns=[Pattern(name=pattern_id, regex=pattern.pattern, score=1.0)],
                global_regex_flags=re.UNICODE,
            )
        )
    return recognizers


def chunk_text_by_chars(
    text: str, window_chars: int, overlap_chars: int
) -> list[tuple[int, str]]:
    """Deterministic (offset, window) pairs covering the whole text.

    spaCy-backed NLP engines refuse documents above ``nlp.max_length``
    (1,000,000 chars) and their memory cost grows sharply with document
    size, so long admitted fields are analyzed in character windows split
    at whitespace boundaries when possible. The overlap keeps entities
    that straddle a window boundary detectable; ``resolve_findings``
    dedupes double reports from the overlap region.
    """

    if len(text) <= window_chars:
        return [(0, text)]
    chunks: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + window_chars)
        if end < len(text):
            boundary = text.rfind(" ", start + window_chars // 2, end)
            if boundary > start:
                end = boundary
        chunks.append((start, text[start:end]))
        if end >= len(text):
            break
        start = max(start + 1, end - overlap_chars)
    return chunks
