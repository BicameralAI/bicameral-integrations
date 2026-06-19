"""Provenance attribution for captured evidence (SDK conformance, bicameral-sdk #7).

Mirrors `bicameral-sdk/src/provenance/index.ts` so a connector's output can carry the
capture trail the SDK `Evidence` contract requires: who captured it, how, with what
pipeline version, and a content hash. Pure, stdlib-only, frozen.

Authority note (ADR-0008): the *capturer* of source evidence is the **connector**
(`ActorType.CONNECTOR`), never the human actor in the source system — so attribution
carries the connector/source id and a human identity is never surfaced (consistent with
the PII-drop applied across connectors, SG-2026-06-11-D).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ActorType(StrEnum):
    """Who captured a piece of evidence. Mirrors the SDK `ActorType` union."""

    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"
    CONNECTOR = "connector"


@dataclass(frozen=True)
class Attribution:
    """Capture attribution. For connector-captured evidence ``actor_id`` is the
    connector/source id and ``actor_type`` is ``CONNECTOR`` — never a human identity."""

    actor_id: str
    actor_type: ActorType
    display_name: str = ""


@dataclass(frozen=True)
class Provenance:
    """The capture trail required by the SDK `Evidence` contract.

    ``capture_method`` is the ingest mode (webhook/active/passive); ``pipeline_version``
    is the adapter version; ``source_hash`` is a content hash of the captured excerpt for
    dedup/provenance (``sha256:<hex>``)."""

    captured_at: str
    captured_by: Attribution
    capture_method: str
    pipeline_version: str = ""
    source_hash: str = ""


__all__ = ["ActorType", "Attribution", "Provenance"]
