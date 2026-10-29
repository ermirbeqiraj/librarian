import time
from dataclasses import asdict
from pathlib import Path

from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.orm import Session as DbSession

from librarian.adapters import embedder
from librarian.adapters.readers import docling_reader, mistral_ocr
from librarian.adapters.readers.element import Element
from librarian.config import INBOX_DIR, PROCESSED_DIR, QUARANTINE_DIR, ROOT
from librarian.db import Session
from librarian.ingest import repository
from librarian.ingest.chunks import chunk
from librarian.ingest.content_hash import content_hash, text_hash
from librarian.ingest.drafter.drafter import document_text, draft
from librarian.ingest.parsers.detect_parser import UnknownDocument, UnknownLayout, detect_parser
from librarian.ingest.parsers.parser import Parser
from librarian.ingest.parsers.sections import Section, from_docling, from_markdown
from librarian.models import (
    Chunk,
    Document,
    DocumentSection,
    DocumentStatus,
    Ingestion,
    IngestionStatus,
)

SETTLE_SECONDS = 60
OCR_UNDER_PAGES = 5
# Kind, validity and the key fields sit up front; a 65-page booklet timed out the drafter.
DRAFT_PAGES = 10


def ingest_once() -> None:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INBOX_DIR.iterdir()):
        if path.is_file() and not path.name.startswith("."):
            process(path)


def process(path: Path) -> None:
    if not _settled(path):
        print(f"{path.name}: still being written, skipped")
        return
    ingestion = Ingestion(
        original_file_name=path.name,
        file_size=path.stat().st_size,
        status=IngestionStatus.received,
    )
    with Session() as session:
        try:
            _ingest(session, path, ingestion)
        except Exception as error:  # noqa: BLE001
            ingestion.status = IngestionStatus.failed
            ingestion.error = repr(error)
        repository.add(session, ingestion)
        session.flush()
        if ingestion.status == IngestionStatus.duplicate:
            # The row keeps the name and hash; the file goes only once the row is safe.
            session.commit()
            path.unlink()
            print(f"{path.name}: ingestion {ingestion.id} duplicate, deleted")
            return
        target = _destination(path, ingestion)
        ingestion.destination_path = str(target.relative_to(ROOT))
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(f"{target} exists: was the database wiped without the files?")
        path.rename(target)
        try:
            session.commit()
        except Exception:
            target.rename(path)
            raise
        print(f"{path.name}: ingestion {ingestion.id} {ingestion.status} -> {target}")


def _destination(path: Path, ingestion: Ingestion) -> Path:
    """processed/{kind}/{id}.ext when read, quarantine/{id}.ext when failed."""
    name = f"{ingestion.id}{path.suffix.lower()}"
    if ingestion.document is None:
        return QUARANTINE_DIR / name
    return PROCESSED_DIR / ingestion.document.kind / name


def _settled(path: Path) -> bool:
    return time.time() - path.stat().st_mtime >= SETTLE_SECONDS


def _ingest(session: DbSession, path: Path, ingestion: Ingestion) -> None:
    elements = docling_reader.read(path)
    try:
        parser = detect_parser(elements)
    except UnknownDocument:
        _drafted(session, path, elements, ingestion)
    except UnknownLayout as reason:
        ingestion.error = repr(reason)
        _drafted(session, path, elements, ingestion)
    else:
        _parsed(session, path, elements, parser, ingestion)


def ocr_reason(elements: list[Element]) -> str | None:
    """Why a document without a parser should be read with OCR, or None."""
    pages = 0
    has_text = False
    for element in elements:
        pages = max(pages, element.page)
        if element.layer == "body" and not element.in_picture and element.text.strip():
            has_text = True
    if not has_text:
        return "scan"
    if pages < OCR_UNDER_PAGES:
        return f"under {OCR_UNDER_PAGES} pages"
    return None


def _duplicate(session: DbSession, ingestion: Ingestion, digest: str) -> bool:
    ingestion.content_hash = digest
    if repository.find_done_by_hash(session, digest):
        ingestion.status = IngestionStatus.duplicate
        return True
    return False


def _parsed(
    session: DbSession, path: Path, elements: list[Element], parser: Parser, ingestion: Ingestion
) -> None:
    if _duplicate(session, ingestion, content_hash(elements)):
        return
    parsed = parser.parse(elements)
    sections = parser.sections(elements)
    document = Document(
        kind=parsed.kind,
        validity=parsed.validity,
        fields=parsed.fields,
        problems=[],
        status=DocumentStatus.confirmed,
    )
    _add_sections(document, sections)
    ingestion.document = document
    ingestion.status = IngestionStatus.done


def _drafted(session: DbSession, path: Path, elements: list[Element], ingestion: Ingestion) -> None:
    reason = ocr_reason(elements)
    if reason is None:
        text = document_text([e for e in elements if e.page <= DRAFT_PAGES])
        digest = content_hash(elements)
        sections = from_docling(elements)
    else:
        note = f"read with OCR: {reason}"
        if ingestion.error:
            note = f"{ingestion.error}; {note}"
        ingestion.error = note
        pages = mistral_ocr.read_pages(path)
        digest = text_hash("\n\n".join(pages))
        text = "\n\n".join(pages[:DRAFT_PAGES])
        sections = from_markdown(pages)
    if _duplicate(session, ingestion, digest):
        return
    checked = draft(text)
    drafted = checked.draft
    fields: dict[str, str] = {}
    for field in drafted.fields:
        fields[field.name] = field.value
    problems: list[dict[str, str]] = []
    for problem in checked.problems:
        problems.append(asdict(problem))
    document = Document(
        kind=drafted.kind,
        validity=Range(drafted.validity.start, drafted.validity.end, bounds="[]"),
        fields=fields,
        description=drafted.description,
        problems=problems,
        status=DocumentStatus.draft,
    )
    _add_sections(document, sections)
    ingestion.document = document
    ingestion.status = IngestionStatus.done


def _add_sections(document: Document, sections: list[Section]) -> None:
    """Store each section whole, and embed its chunks for search."""
    budget = embedder.LIMIT - embedder.MARGIN
    for position, section in enumerate(sections):
        row = DocumentSection(position=position, heading=section.heading, text=section.text)
        pieces = chunk(section, budget, embedder.count_tokens)
        vectors = embedder.embed(pieces)
        for piece, vector in zip(pieces, vectors, strict=True):
            row.chunks.append(Chunk(text=piece, model=embedder.MODEL, embedding=vector))
        document.sections.append(row)
