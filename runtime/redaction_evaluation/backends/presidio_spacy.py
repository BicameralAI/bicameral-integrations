# SPDX-License-Identifier: MIT
"""Candidate ``presidio-spacy-lg-v1``: presidio-analyzer over spaCy lg NER.

Pinned engine: presidio-analyzer 2.2.364 driving a spaCy ``en_core_web_lg``
3.8.0 NLP engine with an explicit recognizer registry (never the default
loadout), plus the Bicameral secret/PHI catalog re-expressed as presidio
pattern recognizers. The spaCy NER contributes PERSON and LOCATION only;
DATE_TIME/NRP/ORGANIZATION are ignored at the NLP-engine level and excluded
from the recognizer. The URL recognizer is deliberately absent, so presidio
never touches tldextract's remote public-suffix list; nothing in this
configuration performs network I/O at analyze time.
"""

from __future__ import annotations

from typing import Any

from ..policy import LabelMap, RedactionPolicy
from ..seam import (
    BackendFinding,
    BackendHealth,
    BackendIdentity,
    BackendInvalidConfiguration,
    BackendUnavailable,
)
from ._shared import (
    bicameral_catalog_manifest,
    bicameral_recognizer_names,
    build_bicameral_recognizers,
    require_pinned_version,
    resolve_findings,
)

_PRESIDIO_PIN = "2.2.364"
_SPACY_PIN = "3.8.14"
_MODEL_NAME = "en_core_web_lg"
_MODEL_PIN = "3.8.0"
_SCORE_THRESHOLD = 0.4
_SPACY_ENTITIES = ("PERSON", "LOCATION")
_PHONE_REGIONS = ("US", "GB", "DE", "FR", "IL", "IN", "CA", "BR")

# spaCy model labels kept (mapped to presidio entities) vs ignored entirely.
_SPACY_ENTITY_MAPPING = {
    "PERSON": "PERSON",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "FAC": "LOCATION",
}
_SPACY_LABELS_TO_IGNORE = (
    "CARDINAL",
    "DATE",
    "EVENT",
    "LANGUAGE",
    "LAW",
    "MONEY",
    "NORP",
    "ORDINAL",
    "ORG",
    "PERCENT",
    "PRODUCT",
    "QUANTITY",
    "TIME",
    "WORK_OF_ART",
)

_PREDEFINED_RECOGNIZERS = (
    "SpacyRecognizer",
    "EmailRecognizer",
    "PhoneRecognizer",
    "IpRecognizer",
    "CreditCardRecognizer",
    "IbanRecognizer",
    "UsSsnRecognizer",
    "UsPassportRecognizer",
)

_LABEL_MAP = LabelMap(
    map_id="presidio-spacy-labels-v1",
    mapping={
        "PERSON": ("pii", "person"),
        "LOCATION": ("pii", "address"),
        "EMAIL_ADDRESS": ("pii", "email"),
        "PHONE_NUMBER": ("pii", "phone"),
        "IP_ADDRESS": ("pii", "ip"),
        "CREDIT_CARD": ("credential", "pan"),
        "IBAN_CODE": ("pii", "financial_id"),
        "US_SSN": ("pii", "government_id"),
        "US_PASSPORT": ("pii", "government_id"),
        "BICAMERAL_SECRET": ("secret", "secret"),
        "BICAMERAL_PHI": ("phi", "phi"),
    },
)


class PresidioSpacyBackend:
    """Presidio AnalyzerEngine candidate with a pinned spaCy lg NLP engine."""

    def __init__(self) -> None:
        self._analyzer: Any = None
        self._unmapped: dict[str, int] = {}
        self._identity = self._build_identity(_PRESIDIO_PIN, _SPACY_PIN, _MODEL_PIN)

    @staticmethod
    def _build_identity(
        presidio_version: str, spacy_version: str, model_version: str
    ) -> BackendIdentity:
        return BackendIdentity(
            candidate_id="presidio-spacy-lg-v1",
            family="presidio",
            engine_version=presidio_version,
            packages={
                "presidio-analyzer": presidio_version,
                "spacy": spacy_version,
            },
            models={_MODEL_NAME: model_version},
            configuration={
                "engine": "presidio-analyzer",
                "engine_version": presidio_version,
                "nlp_engine": {
                    "name": "spacy",
                    "model": f"{_MODEL_NAME}-{model_version}",
                    "spacy_version": spacy_version,
                    "model_to_presidio_entity_mapping": dict(_SPACY_ENTITY_MAPPING),
                    "labels_to_ignore": list(_SPACY_LABELS_TO_IGNORE),
                },
                "recognizers": [
                    *_PREDEFINED_RECOGNIZERS,
                    *bicameral_recognizer_names(),
                ],
                "spacy_recognizer_entities": list(_SPACY_ENTITIES),
                "phone_regions": list(_PHONE_REGIONS),
                "score_threshold": _SCORE_THRESHOLD,
                "allow_list": [],
                "bicameral_catalog": bicameral_catalog_manifest(),
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
        if self._analyzer is not None:
            return
        presidio_version = require_pinned_version("presidio-analyzer", _PRESIDIO_PIN)
        spacy_version = require_pinned_version("spacy", _SPACY_PIN)
        model_version = require_pinned_version(_MODEL_NAME, _MODEL_PIN)
        try:
            from presidio_analyzer import (  # type: ignore[import-not-found]
                AnalyzerEngine,
                RecognizerRegistry,
            )
            from presidio_analyzer.nlp_engine import (  # type: ignore[import-not-found]
                NlpEngineProvider,
            )
            from presidio_analyzer.predefined_recognizers import (  # type: ignore[import-not-found]
                CreditCardRecognizer,
                EmailRecognizer,
                IbanRecognizer,
                IpRecognizer,
                PhoneRecognizer,
                SpacyRecognizer,
                UsPassportRecognizer,
                UsSsnRecognizer,
            )
        except ImportError as exc:
            raise BackendUnavailable("backend_unavailable") from exc

        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": _MODEL_NAME}],
            "ner_model_configuration": {
                "model_to_presidio_entity_mapping": dict(_SPACY_ENTITY_MAPPING),
                "labels_to_ignore": list(_SPACY_LABELS_TO_IGNORE),
            },
        }
        try:
            nlp_engine = NlpEngineProvider(
                nlp_configuration=nlp_configuration
            ).create_engine()
            recognizers = [
                SpacyRecognizer(supported_entities=list(_SPACY_ENTITIES)),
                EmailRecognizer(),
                PhoneRecognizer(supported_regions=_PHONE_REGIONS),
                IpRecognizer(),
                CreditCardRecognizer(),
                IbanRecognizer(),
                UsSsnRecognizer(),
                UsPassportRecognizer(),
                *build_bicameral_recognizers(),
            ]
            registry = RecognizerRegistry(
                recognizers=recognizers, supported_languages=["en"]
            )
            self._analyzer = AnalyzerEngine(
                registry=registry,
                nlp_engine=nlp_engine,
                supported_languages=["en"],
                default_score_threshold=_SCORE_THRESHOLD,
            )
        except (OSError, RuntimeError, ImportError) as exc:
            raise BackendUnavailable("backend_unavailable") from exc
        except (TypeError, ValueError, KeyError) as exc:
            raise BackendInvalidConfiguration("backend_invalid_configuration") from exc
        self._identity = self._build_identity(
            presidio_version, spacy_version, model_version
        )

    def health(self) -> BackendHealth:
        if self._analyzer is None:
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
        if self._analyzer is None:
            raise BackendUnavailable("backend_unavailable")
        if not text:
            return []
        results = self._analyzer.analyze(text=text, language="en")
        candidates = [
            (str(result.entity_type), int(result.start), int(result.end),
             float(result.score))
            for result in results
        ]
        return resolve_findings(
            candidates,
            label_map=_LABEL_MAP,
            text_length=len(text),
            unmapped_counts=self._unmapped,
        )
