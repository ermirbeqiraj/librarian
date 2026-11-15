from dataclasses import asdict
from pathlib import Path

from librarian.application.ingest.chunks import chunk
from librarian.application.ingest.content_hash import content_hash, text_hash
from librarian.application.ingest.document import (
    Chunk,
    Document,
    DocumentSection,
    DocumentStatus,
    Ingestion,
    IngestionStatus,
    Period,
)
from librarian.application.ingest.drafter.drafter import document_text, draft
from librarian.application.ingest.element import Element
from librarian.application.ingest.paid_calls import PaidCalls
from librarian.application.ingest.parsers.detect_parser import (
    UnknownDocument,
    UnknownLayout,
    detect_parser,
)
from librarian.application.ingest.parsers.parser import Parser
from librarian.application.ingest.parsers.sections import Section, from_docling, from_markdown
from librarian.application.ingest.ports import Embedder, Inbox, IngestionRepository, Llm, Reader

OCR_UNDER_PAGES = 5
# Kind, validity and the key fields sit up front; a 65-page booklet timed out the drafter.
DRAFT_PAGES = 10
# OCR, drafter and every retry, the client's own included: past it, quarantine.
PAID_CALLS_PER_DOCUMENT = 5


class Pipeline:
    """Every file in the inbox: read it, work out what it is, store it, file it away."""

    def __init__(
        self,
        reader: Reader,
        ocr: Reader,
        llm: Llm,
        embedder: Embedder,
        ingestions: IngestionRepository,
        inbox: Inbox,
    ) -> None:
        self.reader = reader
        self.ocr = ocr
        self.llm = llm
        self.embedder = embedder
        self.ingestions = ingestions
        self.inbox = inbox

    def ingest_once(self) -> bool:
        """One pass over the inbox. True when a file was still being written and waits."""
        waiting = False
        for path in self.inbox.files():
            if self.inbox.settled(path):
                self.process(path)
            else:
                print(f"{path.name}: still being written, skipped")
                waiting = True
        return waiting

    def process(self, path: Path) -> None:
        ingestion = Ingestion(original_file_name=path.name, file_size=self.inbox.size(path))
        ingestion.id = self.ingestions.start(ingestion)
        try:
            self._ingest(path, ingestion)
        except Exception as error:  # noqa: BLE001
            ingestion.status = IngestionStatus.failed
            ingestion.error = repr(error)
        if ingestion.status == IngestionStatus.duplicate:
            # The row keeps the name and hash; the file goes only once the row is safe.
            self.ingestions.finish(ingestion)
            self.inbox.delete(path)
            print(f"{path.name}: ingestion {ingestion.id} duplicate, deleted")
            return
        kind = None
        if ingestion.document is not None:
            kind = ingestion.document.kind
        ingestion.destination_path = self.inbox.move(path, ingestion.id, kind)
        try:
            self.ingestions.finish(ingestion)
        except Exception:
            self.inbox.move_back(ingestion.destination_path, path)
            raise
        target = ingestion.destination_path
        print(f"{path.name}: ingestion {ingestion.id} {ingestion.status} -> {target}")

    def _ingest(self, path: Path, ingestion: Ingestion) -> None:
        elements = self.reader.read(path)
        try:
            parser = detect_parser(elements)
        except UnknownDocument:
            self._drafted(path, elements, ingestion)
        except UnknownLayout as reason:
            print(f"{path.name}: {reason}, drafted")
            self._drafted(path, elements, ingestion)
        else:
            self._parsed(elements, parser, ingestion)

    def _duplicate(self, ingestion: Ingestion, digest: str) -> bool:
        ingestion.content_hash = digest
        if self.ingestions.is_duplicate(digest):
            ingestion.status = IngestionStatus.duplicate
            return True
        return False

    def _parsed(self, elements: list[Element], parser: Parser, ingestion: Ingestion) -> None:
        if self._duplicate(ingestion, content_hash(elements)):
            return
        parsed = parser.parse(elements)
        ingestion.document = Document(
            kind=parsed.kind,
            validity=parsed.validity,
            fields=parsed.fields,
            parser=parser.parser,
            description=None,
            problems=[],
            status=DocumentStatus.confirmed,
            sections=self._sections(parser.sections(elements)),
        )
        ingestion.status = IngestionStatus.done

    def _drafted(self, path: Path, elements: list[Element], ingestion: Ingestion) -> None:
        paid_calls = PaidCalls(PAID_CALLS_PER_DOCUMENT)
        reason = ocr_reason(elements)
        if reason is None:
            text = document_text([e for e in elements if e.page <= DRAFT_PAGES])
            digest = content_hash(elements)
            sections = from_docling(elements)
        else:
            print(f"{path.name}: read with OCR, {reason}")
            pages: list[str] = []
            for page in self.ocr.read(path, paid_calls):
                pages.append(page.text)
            digest = text_hash("\n\n".join(pages))
            text = "\n\n".join(pages[:DRAFT_PAGES])
            sections = from_markdown(pages)
        if self._duplicate(ingestion, digest):
            return
        checked = draft(text, self.llm, paid_calls=paid_calls)
        drafted = checked.draft
        fields: dict[str, str] = {}
        for field in drafted.fields:
            fields[field.name] = field.value
        problems: list[dict[str, str]] = []
        for problem in checked.problems:
            problems.append(asdict(problem))
        ingestion.document = Document(
            kind=drafted.kind,
            validity=Period(drafted.validity.start, drafted.validity.end),
            fields=fields,
            parser="drafter",
            description=drafted.description,
            problems=problems,
            status=DocumentStatus.draft,
            sections=self._sections(sections),
        )
        ingestion.status = IngestionStatus.done

    def _sections(self, sections: list[Section]) -> list[DocumentSection]:
        """Each section whole, and its chunks embedded for search."""
        stored: list[DocumentSection] = []
        for section in sections:
            pieces = chunk(section, self.embedder.budget, self.embedder.count_tokens)
            vectors = self.embedder.embed(pieces)
            chunks: list[Chunk] = []
            for piece, vector in zip(pieces, vectors, strict=True):
                chunks.append(Chunk(text=piece, model=self.embedder.model, embedding=vector))
            stored.append(
                DocumentSection(heading=section.heading, text=section.text, chunks=chunks)
            )
        return stored


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
