# SPDX-License-Identifier: MIT
"""Google Docs/Drive connector: document payloads into neutral Observations.

Provider-specific knowledge lives here: the Docs/Drive URL grammar and the
structured-document body walk. Normalization into an AdapterEmission is the
universal adapter's job (ADR-0004). The live ``documents.get`` fetch is built this
cycle in ``runtime.doc_fetch`` (driven by ``poll_specs.build_google_drive_spec``) —
this connector stays a **pure parse surface** (it does not itself call the network).
OAuth token refresh, folder polling (Drive ``files.list``), and push-notification
webhooks remain operator-runtime / deferred.
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
# A response documentId must match the Docs id grammar to become the wire ref. Defense-in-depth
# so a hostile 200 cannot make a 16-digit PAN the SourceRef.ref (purple-team PII-3, 2026-06-11).
_DOC_ID_RE = re.compile(r"[A-Za-z0-9_-]{25,128}")


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


def _dicts(value: object) -> list[dict]:
    """The dict members of ``value`` when it is a list, else ``[]``. The Google Docs body is
    an untrusted 200 payload: a non-list container or non-dict member must be skipped, not
    iterated/joined into a crash (purple-team PARSE-3, the #59 skip-don't-crash discipline)."""
    return [m for m in value if isinstance(m, dict)] if isinstance(value, list) else []


def _named_style(para: dict) -> str:
    """``paragraphStyle.namedStyleType`` if present and well-typed, else ``""`` (no crash on a
    non-dict ``paragraphStyle``)."""
    style = para.get("paragraphStyle")
    named = style.get("namedStyleType") if isinstance(style, dict) else None
    return named if isinstance(named, str) else ""


def _extract_text_from_paragraph(para: dict) -> str:
    """Concatenate textRun content across a paragraph's elements (type-guarded)."""
    pieces: list[str] = []
    for elem in _dicts(para.get("elements")):
        run = elem.get("textRun")
        content = run.get("content") if isinstance(run, dict) else None
        pieces.append(content if isinstance(content, str) else "")
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
    """Flatten one table cell's paragraphs into decorated strings (type-guarded)."""
    out: list[str] = []
    for sub_elem in _dicts(cell.get("content")):
        para = sub_elem.get("paragraph")
        if not isinstance(para, dict):
            continue
        decorated = _decorate_paragraph(_extract_text_from_paragraph(para), _named_style(para))
        if decorated:
            out.append(decorated)
    return out


def _walk_table(table: dict) -> list[str]:
    """Flatten table cells into a list of paragraph strings (nesting <=3; type-guarded)."""
    out: list[str] = []
    for row in _dicts(table.get("tableRows")):
        for cell in _dicts(row.get("tableCells")):
            out.extend(_table_cell_texts(cell))
    return out


def extract_document_text(document: dict) -> str:
    """Walk the Google Doc structured body and return joined plain text.

    Paragraphs and tables are flattened; sectionBreak, tableOfContents, and
    other structural elements are skipped intentionally.
    """
    blocks: list[str] = []
    body = document.get("body")
    content = body.get("content") if isinstance(body, dict) else None
    for elem in _dicts(content):
        para = elem.get("paragraph")
        table = elem.get("table")
        if isinstance(para, dict):
            decorated = _decorate_paragraph(_extract_text_from_paragraph(para), _named_style(para))
            if decorated:
                blocks.append(decorated)
        elif isinstance(table, dict):
            blocks.extend(_walk_table(table))
    return "\n".join(blocks).strip()


def parse_document(document: dict) -> Observation:
    """Map a Google Docs ``documents.get`` response into an Observation.

    The excerpt is the flattened document text, falling back to the title when
    the body is empty. ``documentId`` becomes the stable provider ref.
    """
    raw_id = document.get("documentId")
    doc_id = raw_id if isinstance(raw_id, str) and _DOC_ID_RE.fullmatch(raw_id) else ""
    raw_title = document.get("title")
    title = raw_title if isinstance(raw_title, str) and raw_title else (doc_id or "google-doc")
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
