"""Google Docs/Drive connector: document payloads into neutral Observations.

Provider-specific knowledge lives here: the Docs/Drive URL grammar and the
structured-document body walk. Normalization into an AdapterEmission is the
universal adapter's job (ADR-0004). The live ``documents.get`` HTTP path and
OAuth credential resolution are deferred (no live API this cycle); this
connector provides the provider-neutral parse surface the active path shares.
"""

from __future__ import annotations

import re

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation

_URL_RE = re.compile(
    r"^https?://(?:docs\.google\.com/document/d/|drive\.google\.com/file/d/)"
    r"(?P<id>[A-Za-z0-9_-]{25,128})(?:[/?#].*)?$"
)


def parse_gdrive_url(url: str) -> str:
    """Extract the document id from a Google Docs/Drive URL.

    Cheap pattern match — does not confirm the document resolves.

    Raises:
        ValueError: the URL doesn't match the expected shape.
    """
    m = _URL_RE.match(url.strip())
    if not m:
        raise ValueError(
            f"not a recognized Google Docs/Drive URL: {url!r}. "
            "Expected docs.google.com/document/d/<id> or drive.google.com/file/d/<id>."
        )
    return m.group("id")


def _extract_text_from_paragraph(para: dict) -> str:
    """Concatenate textRun content across a paragraph's elements."""
    pieces: list[str] = []
    for elem in para.get("elements") or []:
        run = elem.get("textRun") or {}
        pieces.append(run.get("content") or "")
    return "".join(pieces).strip()


def _decorate_paragraph(text: str, named_style: str) -> str:
    """Markdown-decorate a paragraph based on its namedStyleType.

    Heading decoration gives downstream review topic anchors.
    """
    if not text:
        return ""
    headings = {
        "HEADING_1": "# ",
        "HEADING_2": "## ",
        "HEADING_3": "### ",
        "HEADING_4": "#### ",
    }
    prefix = headings.get(named_style, "")
    return f"{prefix}{text}"


def _table_cell_texts(cell: dict) -> list[str]:
    """Flatten one table cell's paragraphs into decorated strings."""
    out: list[str] = []
    for sub_elem in cell.get("content") or []:
        if "paragraph" not in sub_elem:
            continue
        para = sub_elem["paragraph"]
        style = (para.get("paragraphStyle") or {}).get("namedStyleType") or ""
        decorated = _decorate_paragraph(_extract_text_from_paragraph(para), style)
        if decorated:
            out.append(decorated)
    return out


def _walk_table(table: dict) -> list[str]:
    """Flatten table cells into a list of paragraph strings (nesting <=3)."""
    out: list[str] = []
    for row in table.get("tableRows") or []:
        for cell in row.get("tableCells") or []:
            out.extend(_table_cell_texts(cell))
    return out


def extract_document_text(document: dict) -> str:
    """Walk the Google Doc structured body and return joined plain text.

    Paragraphs and tables are flattened; sectionBreak, tableOfContents, and
    other structural elements are skipped intentionally.
    """
    blocks: list[str] = []
    body = document.get("body") or {}
    for elem in body.get("content") or []:
        if "paragraph" in elem:
            para = elem["paragraph"]
            style = (para.get("paragraphStyle") or {}).get("namedStyleType") or ""
            decorated = _decorate_paragraph(_extract_text_from_paragraph(para), style)
            if decorated:
                blocks.append(decorated)
        elif "table" in elem:
            blocks.extend(_walk_table(elem["table"]))
    return "\n".join(blocks).strip()


def parse_document(document: dict) -> Observation:
    """Map a Google Docs ``documents.get`` response into an Observation.

    The excerpt is the flattened document text, falling back to the title when
    the body is empty. ``documentId`` becomes the stable provider ref.
    """
    doc_id = document.get("documentId") or ""
    title = document.get("title") or doc_id
    text = extract_document_text(document)
    return Observation(
        source_ref=SourceRef(
            source_id="google_drive",
            ref=doc_id or title,
            kind="document",
        ),
        excerpt=text or title,
        mode=SourceMode.ACTIVE,
        title=title,
    )


class GoogleDriveConnector:
    """Google Drive / Docs connector identity plus the document parse surface.

    Declares the modes Google Drive supports in the source system: active URL
    fetch, passive folder polling, and push-notification webhooks. Only the
    active document parse surface ships this cycle; the live Docs API call,
    OAuth refresh, folder polling, and channel webhooks are deferred.
    """

    source_id = "google_drive"
    capabilities = SourceCapabilities(
        modes=frozenset({SourceMode.ACTIVE, SourceMode.PASSIVE, SourceMode.WEBHOOK})
    )

    def can_handle_ref(self, ref: SourceRef) -> bool:
        if ref.source_id == "google_drive":
            return True
        return bool(_URL_RE.match((ref.url or "").strip()))

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_document(payload)]
