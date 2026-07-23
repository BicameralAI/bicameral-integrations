# SPDX-License-Identifier: MIT
"""Candidate backend registry (lazy: heavy candidates import on first use)."""

from __future__ import annotations

from collections.abc import Callable

from ..seam import RedactionBackend

CANDIDATE_IDS = (
    "bicameral-stdlib-v1",
    "presidio-spacy-lg-v1",
    "presidio-gliner-pii-v1",
    "datafog-regex-v1",
)


def create_backend(candidate_id: str) -> RedactionBackend:
    """Instantiate one candidate by id; raises KeyError for unknown ids."""

    factories: dict[str, Callable[[], RedactionBackend]] = {
        "bicameral-stdlib-v1": _baseline,
        "presidio-spacy-lg-v1": _presidio_spacy,
        "presidio-gliner-pii-v1": _presidio_gliner,
        "datafog-regex-v1": _datafog,
    }
    return factories[candidate_id]()


def _baseline() -> RedactionBackend:
    from .baseline import BicameralStdlibBackend

    return BicameralStdlibBackend()


def _presidio_spacy() -> RedactionBackend:
    from .presidio_spacy import PresidioSpacyBackend

    return PresidioSpacyBackend()


def _presidio_gliner() -> RedactionBackend:
    from .presidio_gliner import PresidioGlinerBackend

    return PresidioGlinerBackend()


def _datafog() -> RedactionBackend:
    from .datafog_backend import DatafogRegexBackend

    return DatafogRegexBackend()
