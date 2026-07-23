# SPDX-License-Identifier: MIT
"""Candidate ``presidio-gliner-pii-v1``: presidio GLiNERRecognizer over the
pinned ``urchade/gliner_multi_pii-v1`` model.

Pinned engine: presidio-analyzer 2.2.364 with its ``GLiNERRecognizer`` running
gliner 0.2.27 on CPU. The model revision is pinned by passing
``revision=...``/``local_files_only=True`` through the recognizer's
``**model_kwargs`` into ``GLiNER.from_pretrained``, so loading is
cache-only and never touches the network; the loaded weight file's sha256
is recorded in the identity. The spaCy ``en_core_web_sm`` NLP engine is used
for tokenization only: ``SpacyRecognizer`` is excluded from the registry and
every spaCy NER label is ignored, so spaCy never double-reports entities.

GLiNER alone is weak on machine tokens, so the registry also carries the
Bicameral secret/PHI catalog recognizers plus presidio's EmailRecognizer and
CreditCardRecognizer (same construction as ``presidio-spacy-lg-v1``).

Long inputs: the model attends to at most 384 word tokens, so text is chunked
deterministically on whitespace boundaries (250 words per chunk, 30-word
overlap) via a custom presidio text chunker; chunk offsets are mapped back to
the original text and duplicate findings from overlapping chunks collapse
deterministically (higher score first; ties keep the earlier chunk's span via
the stable sort), with the backend's final overlap resolution guaranteeing
one finding per span.
"""

from __future__ import annotations

import hashlib
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
    observed_version,
    require_pinned_version,
    resolve_findings,
)

_PRESIDIO_PIN = "2.2.364"
_GLINER_PIN = "0.2.27"
_SPACY_PIN = "3.8.14"
_NLP_MODEL_NAME = "en_core_web_sm"
_NLP_MODEL_PIN = "3.8.0"
_TORCH_FALLBACK_PIN = "2.13.0+cpu"
_TRANSFORMERS_FALLBACK_PIN = "5.6.2"

_MODEL_ID = "urchade/gliner_multi_pii-v1"
_MODEL_REVISION = "1fcf13e85f4eef5394e1fcd406cf2ca9ea82351d"
_MODEL_WEIGHTS_FILE = "pytorch_model.bin"

_GLINER_THRESHOLD = 0.45
_SCORE_THRESHOLD = 0.4
_FLAT_NER = True
_MULTI_LABEL = False
_CHUNK_WORDS = 250
_CHUNK_OVERLAP_WORDS = 30

_GLINER_LABELS = (
    "person",
    "email address",
    "phone number",
    "physical address",
    "date of birth",
    "social security number",
    "passport number",
    "credit card number",
    "bank account number",
    "medical record number",
    "ip address",
    "account username",
)

# Tokenization-only spaCy engine: every NER label is ignored so no entity
# survives to the (absent) SpacyRecognizer.
_SPACY_LABELS_TO_IGNORE = (
    "CARDINAL",
    "DATE",
    "EVENT",
    "FAC",
    "GPE",
    "LANGUAGE",
    "LAW",
    "LOC",
    "MONEY",
    "NORP",
    "ORDINAL",
    "ORG",
    "PERCENT",
    "PERSON",
    "PRODUCT",
    "QUANTITY",
    "TIME",
    "WORK_OF_ART",
)

_LABEL_MAP = LabelMap(
    map_id="presidio-gliner-labels-v1",
    mapping={
        "person": ("pii", "person"),
        "email address": ("pii", "email"),
        "phone number": ("pii", "phone"),
        "physical address": ("pii", "address"),
        "date of birth": ("pii", "dob"),
        "social security number": ("pii", "government_id"),
        "passport number": ("pii", "government_id"),
        "credit card number": ("credential", "pan"),
        "bank account number": ("pii", "financial_id"),
        "medical record number": ("phi", "mrn"),
        "ip address": ("pii", "ip"),
        "account username": ("pii", "account_id"),
        "EMAIL_ADDRESS": ("pii", "email"),
        "CREDIT_CARD": ("credential", "pan"),
        "BICAMERAL_SECRET": ("secret", "secret"),
        "BICAMERAL_PHI": ("phi", "phi"),
    },
)


def _make_word_chunker(chunk_words: int, overlap_words: int) -> Any:
    """Whitespace-boundary chunker implementing presidio's chunker seam.

    Chunks are windows of ``chunk_words`` whitespace-delimited words stepping
    ``chunk_words - overlap_words`` words at a time; each chunk spans from the
    first to the last word's exact character offsets, so mapped-back finding
    offsets are exact.
    """

    import re

    from presidio_analyzer.chunkers import (  # type: ignore[import-not-found]
        BaseTextChunker,
        TextChunk,
    )

    class _WordBoundaryChunker(BaseTextChunker):  # type: ignore[misc]
        def chunk(self, text: str) -> list[Any]:
            words = list(re.finditer(r"\S+", text))
            if not words:
                return []
            step = chunk_words - overlap_words
            chunks: list[Any] = []
            index = 0
            while index < len(words):
                window = words[index : index + chunk_words]
                start = window[0].start()
                end = window[-1].end()
                chunks.append(TextChunk(text=text[start:end], start=start, end=end))
                if index + chunk_words >= len(words):
                    break
                index += step
            return chunks

    return _WordBoundaryChunker()


def _make_gliner_recognizer(text_chunker: Any) -> Any:
    """Construct the GLiNER recognizer with the label set pinned exactly.

    Presidio's stock ``GLiNERRecognizer`` appends every other requested
    registry entity (CREDIT_CARD, BICAMERAL_SECRET, ...) to the GLiNER query
    as ad-hoc labels, which both un-pins the label set and induces spurious
    zero-shot matches. The subclass overrides ``analyze`` to always query the
    model with exactly the pinned labels; the identity entity mapping then
    keeps the raw GLiNER label as the reported entity type.
    """

    from presidio_analyzer.predefined_recognizers import (  # type: ignore[import-not-found]
        GLiNERRecognizer,
    )

    class _PinnedLabelGlinerRecognizer(GLiNERRecognizer):  # type: ignore[misc]
        def analyze(
            self, text: str, entities: Any, nlp_artifacts: Any = None
        ) -> Any:
            del entities
            return super().analyze(text, list(_GLINER_LABELS), nlp_artifacts)

    return _PinnedLabelGlinerRecognizer(
        entity_mapping={label: label for label in _GLINER_LABELS},
        model_name=_MODEL_ID,
        flat_ner=_FLAT_NER,
        multi_label=_MULTI_LABEL,
        threshold=_GLINER_THRESHOLD,
        map_location="cpu",
        text_chunker=text_chunker,
        # **model_kwargs, forwarded to GLiNER.from_pretrained:
        revision=_MODEL_REVISION,
        local_files_only=True,
    )


def _weights_sha256() -> str:
    """sha256 of the pinned revision's weight file from the local HF cache."""

    from huggingface_hub import (  # type: ignore[import-not-found]
        try_to_load_from_cache,
    )

    path = try_to_load_from_cache(
        repo_id=_MODEL_ID, filename=_MODEL_WEIGHTS_FILE, revision=_MODEL_REVISION
    )
    if not isinstance(path, str):
        raise BackendUnavailable("backend_unavailable")
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


class PresidioGlinerBackend:
    """Presidio AnalyzerEngine candidate around a pinned GLiNER PII model."""

    def __init__(self) -> None:
        self._analyzer: Any = None
        self._unmapped: dict[str, int] = {}
        self._identity = self._build_identity(
            presidio_version=_PRESIDIO_PIN,
            gliner_version=_GLINER_PIN,
            spacy_version=_SPACY_PIN,
            nlp_model_version=_NLP_MODEL_PIN,
            torch_version=_TORCH_FALLBACK_PIN,
            transformers_version=_TRANSFORMERS_FALLBACK_PIN,
            weights_digest="",
        )

    @staticmethod
    def _build_identity(
        *,
        presidio_version: str,
        gliner_version: str,
        spacy_version: str,
        nlp_model_version: str,
        torch_version: str,
        transformers_version: str,
        weights_digest: str,
    ) -> BackendIdentity:
        models = {
            _MODEL_ID: _MODEL_REVISION,
            _NLP_MODEL_NAME: nlp_model_version,
        }
        if weights_digest:
            models[f"{_MODEL_ID}#{_MODEL_WEIGHTS_FILE}"] = weights_digest
        return BackendIdentity(
            candidate_id="presidio-gliner-pii-v1",
            family="presidio-gliner",
            engine_version=presidio_version,
            packages={
                "presidio-analyzer": presidio_version,
                "gliner": gliner_version,
                "spacy": spacy_version,
                "torch": torch_version,
                "transformers": transformers_version,
            },
            models=models,
            configuration={
                "engine": "presidio-analyzer+gliner",
                "engine_version": presidio_version,
                "gliner_version": gliner_version,
                "model": _MODEL_ID,
                "model_revision": _MODEL_REVISION,
                "model_options": {
                    "map_location": "cpu",
                    "local_files_only": True,
                    "flat_ner": _FLAT_NER,
                    "multi_label": _MULTI_LABEL,
                    "threshold": _GLINER_THRESHOLD,
                },
                "gliner_labels": list(_GLINER_LABELS),
                "gliner_label_pinning": "query-labels-fixed-no-ad-hoc-entities",
                "chunking": {
                    "strategy": "whitespace-word-window",
                    "chunk_words": _CHUNK_WORDS,
                    "overlap_words": _CHUNK_OVERLAP_WORDS,
                },
                "nlp_engine": {
                    "name": "spacy",
                    "model": f"{_NLP_MODEL_NAME}-{nlp_model_version}",
                    "role": "tokenization-only",
                    "labels_to_ignore": list(_SPACY_LABELS_TO_IGNORE),
                },
                "recognizers": [
                    "GLiNERRecognizer",
                    "EmailRecognizer",
                    "CreditCardRecognizer",
                    *bicameral_recognizer_names(),
                ],
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
        gliner_version = require_pinned_version("gliner", _GLINER_PIN)
        spacy_version = require_pinned_version("spacy", _SPACY_PIN)
        nlp_model_version = require_pinned_version(_NLP_MODEL_NAME, _NLP_MODEL_PIN)
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
            )
        except ImportError as exc:
            raise BackendUnavailable("backend_unavailable") from exc

        weights_digest = _weights_sha256()
        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": _NLP_MODEL_NAME}],
            "ner_model_configuration": {
                "model_to_presidio_entity_mapping": {"PERSON": "PERSON"},
                "labels_to_ignore": list(_SPACY_LABELS_TO_IGNORE),
            },
        }
        try:
            nlp_engine = NlpEngineProvider(
                nlp_configuration=nlp_configuration
            ).create_engine()
            gliner_recognizer = _make_gliner_recognizer(
                _make_word_chunker(_CHUNK_WORDS, _CHUNK_OVERLAP_WORDS)
            )
            recognizers = [
                gliner_recognizer,
                EmailRecognizer(),
                CreditCardRecognizer(),
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
            presidio_version=presidio_version,
            gliner_version=gliner_version,
            spacy_version=spacy_version,
            nlp_model_version=nlp_model_version,
            torch_version=observed_version("torch", _TORCH_FALLBACK_PIN),
            transformers_version=observed_version(
                "transformers", _TRANSFORMERS_FALLBACK_PIN
            ),
            weights_digest=weights_digest,
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
