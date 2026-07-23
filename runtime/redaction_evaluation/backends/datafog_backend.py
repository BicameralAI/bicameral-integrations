# SPDX-License-Identifier: MIT
"""Candidate ``datafog-regex-v1``: datafog 4.8.0's regex detection engine.

Measured standalone: the regex engine only (``RegexAnnotator`` from
``datafog.processing.text_processing.regex_annotator``), no spaCy extras and
no Bicameral catalog augmentation. ``RegexAnnotator.annotate_with_spans``
returns character offsets directly (``Span.start``/``Span.end`` into the
given text), so no value-relocation search is needed; had the API returned
values only, spans would have been located by deterministic leftmost
non-overlapping search of each returned value.

The annotator is constructed with its default (English/base) label set:
EMAIL, PHONE, SSN, CREDIT_CARD, IP_ADDRESS, DOB, ZIP. The shipped pattern
set is pinned by recording a sha256 digest of the exact regex source strings
in the identity. ZIP has no neutral-taxonomy mapping and is dropped and
counted as unmapped. Datafog telemetry is opt-in and additionally forced off
via ``DATAFOG_NO_TELEMETRY``; the regex path performs no network I/O.
"""

from __future__ import annotations

import os
from typing import Any

from ..policy import LabelMap, RedactionPolicy, canonical_digest
from ..seam import (
    BackendFinding,
    BackendHealth,
    BackendIdentity,
    BackendInvalidConfiguration,
    BackendUnavailable,
)
from ._shared import require_pinned_version, resolve_findings

_DATAFOG_PIN = "4.8.0"
_EXPECTED_LABELS = (
    "CREDIT_CARD",
    "DOB",
    "EMAIL",
    "IP_ADDRESS",
    "PHONE",
    "SSN",
    "ZIP",
)

_LABEL_MAP = LabelMap(
    map_id="datafog-labels-v1",
    mapping={
        "EMAIL": ("pii", "email"),
        "PHONE": ("pii", "phone"),
        "SSN": ("pii", "government_id"),
        "CREDIT_CARD": ("credential", "pan"),
        "IP_ADDRESS": ("pii", "ip"),
        "DOB": ("pii", "dob"),
    },
)


class DatafogRegexBackend:
    """Datafog regex-engine candidate, measured without augmentation."""

    def __init__(self) -> None:
        self._annotator: Any = None
        self._unmapped: dict[str, int] = {}
        self._identity = self._build_identity(_DATAFOG_PIN, patterns_digest="")

    @staticmethod
    def _build_identity(
        datafog_version: str, *, patterns_digest: str
    ) -> BackendIdentity:
        return BackendIdentity(
            candidate_id="datafog-regex-v1",
            family="datafog",
            engine_version=datafog_version,
            packages={"datafog": datafog_version},
            models={},
            configuration={
                "engine": "datafog-regex",
                "engine_version": datafog_version,
                "annotator": "RegexAnnotator",
                "engine_options": {"locales": [], "enabled_labels": "default"},
                "active_labels": list(_EXPECTED_LABELS),
                "patterns_digest": patterns_digest,
                "augmentation": "none",
                "label_map": _LABEL_MAP.map_id,
            },
        )

    @property
    def identity(self) -> BackendIdentity:
        return self._identity

    @property
    def label_map(self) -> LabelMap:
        return _LABEL_MAP

    def unmapped_labels(self) -> dict[str, int]:
        """Counts of engine labels dropped because the label map omits them."""

        return dict(self._unmapped)

    def initialize(self) -> None:
        if self._annotator is not None:
            return
        datafog_version = require_pinned_version("datafog", _DATAFOG_PIN)
        os.environ.setdefault("DATAFOG_NO_TELEMETRY", "1")
        try:
            from datafog.processing.text_processing.regex_annotator import (  # type: ignore[import-not-found]
                RegexAnnotator,
            )
        except ImportError as exc:
            raise BackendUnavailable("backend_unavailable") from exc
        try:
            annotator = RegexAnnotator()
        except (OSError, RuntimeError) as exc:
            raise BackendUnavailable("backend_unavailable") from exc
        except (TypeError, ValueError) as exc:
            raise BackendInvalidConfiguration("backend_invalid_configuration") from exc
        active_labels = sorted(annotator.patterns)
        if active_labels != sorted(_EXPECTED_LABELS):
            raise BackendInvalidConfiguration("backend_invalid_configuration")
        patterns_digest = canonical_digest(
            {label: annotator.patterns[label].pattern for label in active_labels}
        )
        self._annotator = annotator
        self._identity = self._build_identity(
            datafog_version, patterns_digest=patterns_digest
        )

    def health(self) -> BackendHealth:
        if self._annotator is None:
            return BackendHealth(ready=False, detail="not_initialized")
        return BackendHealth(ready=True)

    def analyze(
        self,
        text: str,
        *,
        field_path: str,
        policy: RedactionPolicy,
    ) -> list[BackendFinding]:
        del field_path, policy
        if self._annotator is None:
            raise BackendUnavailable("backend_unavailable")
        if not text:
            return []
        _by_label, result = self._annotator.annotate_with_spans(text)
        candidates = [
            (str(span.label), int(span.start), int(span.end), 1.0)
            for span in result.spans
        ]
        return resolve_findings(
            candidates,
            label_map=_LABEL_MAP,
            text_length=len(text),
            unmapped_counts=self._unmapped,
        )
