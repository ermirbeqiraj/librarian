import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from conftest import SESSIONS
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from librarian.adapters.inbox import FolderInbox
from librarian.adapters.mistral import Mistral
from librarian.adapters.ocr import MistralOcr
from librarian.adapters.postgres import models
from librarian.adapters.postgres.ingestions import PostgresIngestions
from librarian.application.ingest import pipeline
from librarian.application.ingest.document import Ingestion, IngestionStatus
from librarian.application.ingest.drafter import drafter
from librarian.application.ingest.drafter.drafter import Attempt, CheckedDraft
from librarian.application.ingest.drafter.schema import DocumentField, Draft, Validity
from librarian.application.ingest.element import Element
from librarian.application.ingest.kinds import DocumentKind
from librarian.application.ingest.paid_calls import PaidCalls
from librarian.application.ingest.parsers.parser import Claim, Parsed
from librarian.application.ingest.parsers.sections import Section
from librarian.application.ingest.pipeline import Pipeline


class StubLayout:
    issuer = "Stub S.p.A."
    parser = "stub"

    def is_this_yours(self, elements: list[Element]) -> Claim:
        return Claim.full

    def parse(self, elements: list[Element]) -> Parsed:
        return Parsed(DocumentKind.invoice, None, {"issuer": self.issuer, "number": "1"})

    def sections(self, elements: list[Element]) -> list[Section]:
        return [Section("s", 1, "text")]


class Pages:
    """A reader that gives back the same elements for every file."""

    def __init__(self, elements: list[Element]) -> None:
        self.elements = elements

    def read(self, path: Path, paid_calls: PaidCalls | None = None) -> list[Element]:
        return self.elements


class NoDuplicates:
    def start(self, ingestion: Ingestion) -> int:
        return 1

    def is_duplicate(self, content_hash: str) -> bool:
        return False

    def finish(self, ingestion: Ingestion) -> None:
        pass


class ZeroEmbedder:
    model = "test"
    budget = 8176

    def count_tokens(self, text: str) -> int:
        return 1

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for _ in texts:
            vectors.append([0.0] * 1024)
        return vectors


def elements() -> list[Element]:
    return [Element(10, "text", "a bill", "body", False)]


def ingestion() -> Ingestion:
    return Ingestion(original_file_name="a.pdf", file_size=1)


def fakes(ocr: list[Element] | None = None) -> Pipeline:
    return Pipeline(
        reader=Pages(elements()),
        ocr=Pages(ocr or []),
        llm=Mistral("unused"),
        embedder=ZeroEmbedder(),
        ingestions=NoDuplicates(),
        inbox=FolderInbox(Path("unused")),
    )


def drafted(fields: list[DocumentField]) -> CheckedDraft:
    draft = Draft(
        kind=DocumentKind.other,
        validity=Validity(start=date(2030, 1, 1), end=None, as_written="01/01/2030"),
        fields=fields,
        description="",
    )
    return CheckedDraft([Attempt(draft, [])])


def test_parsed_document_stores_the_parser() -> None:
    ing = ingestion()
    fakes()._parsed(elements(), StubLayout(), ing)
    assert ing.status == IngestionStatus.done
    assert ing.document is not None
    assert ing.document.parser == "stub"
    assert ing.document.fields["issuer"] == "Stub S.p.A."


def test_drafted_document_stores_drafter(monkeypatch: pytest.MonkeyPatch) -> None:
    field = DocumentField(name="issuer", value="X S.p.A.", as_written="01/01/2030")
    monkeypatch.setattr(pipeline, "draft", lambda text, llm, paid_calls: drafted([field]))
    ing = ingestion()
    fakes()._drafted(Path("a.pdf"), elements(), ing)
    assert ing.status == IngestionStatus.done
    assert ing.document is not None
    assert ing.document.parser == "drafter"
    assert ing.document.fields == {"issuer": "X S.p.A."}


def test_a_short_document_read_with_ocr_logs_why(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(pipeline, "draft", lambda text, llm, paid_calls: drafted([]))
    ing = ingestion()
    short = [Element(1, "text", "a", "body", False)]
    fakes([Element(1, "page", "# A\n\nb", "body", False)])._drafted(Path("a.pdf"), short, ing)
    assert ing.status == IngestionStatus.done
    assert ing.error is None
    assert ing.document is not None
    assert ing.document.sections[0].heading == "A"
    assert "a.pdf: read with OCR, under 5 pages" in capsys.readouterr().out


def never_fits() -> dict[str, Any]:
    """A Mistral chat answer whose Draft has no kind, validity or description."""
    call = {"id": "abcdefghi", "function": {"name": "Draft", "arguments": json.dumps({})}}
    message = {"role": "assistant", "content": "", "tool_calls": [call]}
    return {
        "id": "1",
        "model": "m",
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def test_a_draft_that_never_fits_stops_at_the_cap(
    db: DbSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sent: list[str] = []

    def mistral(transport: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        sent.append(request.url.path)
        if request.url.path == "/v1/ocr":
            return httpx.Response(200, json={"pages": [{"markdown": "# A\n\nb"}]})
        if len(sent) == 2:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, json=never_fits())

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", mistral)
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    monkeypatch.setenv("MISTRAL_API_KEY", "test")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    path = inbox / "a.pdf"
    path.write_bytes(b"%PDF-")
    os.utime(path, (0, 0))
    ingest = Pipeline(
        reader=Pages([Element(1, "text", "a", "body", False)]),
        ocr=MistralOcr(),
        llm=Mistral(drafter.MODEL),
        embedder=ZeroEmbedder(),
        ingestions=PostgresIngestions(SESSIONS),
        inbox=FolderInbox(tmp_path),
    )

    ingest.ingest_once()

    assert sent == [
        "/v1/ocr",
        "/v1/chat/completions",
        "/v1/chat/completions",
        "/v1/chat/completions",
        "/v1/chat/completions",
    ]
    row = db.scalars(select(models.Ingestion)).one()
    assert row.status == IngestionStatus.failed
    assert row.error is not None and "5 paid calls spent" in row.error
    assert row.destination_path == f"quarantine/{row.id}.pdf"
    assert (tmp_path / "quarantine" / f"{row.id}.pdf").exists()
