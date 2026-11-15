import json
import os
from datetime import date
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from librarian.adapters import embedder
from librarian.adapters.readers import docling_reader
from librarian.adapters.readers.element import Element
from librarian.ingest import pipeline, repository
from librarian.ingest.drafter.drafter import Attempt, CheckedDraft
from librarian.ingest.drafter.schema import DocumentField, Draft, Validity
from librarian.ingest.parsers.parser import Claim, Parsed
from librarian.ingest.parsers.sections import Section
from librarian.ingest.pipeline import _drafted, _parsed  # pyright: ignore[reportPrivateUsage]
from librarian.models import Ingestion, IngestionStatus
from librarian.models.document_kind import DocumentKind


class StubLayout:
    issuer = "Stub S.p.A."
    parser = "stub"

    def is_this_yours(self, elements: list[Element]) -> Claim:
        return Claim.full

    def parse(self, elements: list[Element]) -> Parsed:
        return Parsed(DocumentKind.invoice, None, {"issuer": self.issuer, "number": "1"})

    def sections(self, elements: list[Element]) -> list[Section]:
        return [Section("s", 1, "text")]


def elements() -> list[Element]:
    return [Element(10, "text", "a bill", "body", False)]


def ingestion() -> Ingestion:
    return Ingestion(original_file_name="a.pdf", file_size=1, status=IngestionStatus.received)


@pytest.fixture(autouse=True)
def no_db_no_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repository, "find_done_by_hash", lambda session, digest: None)
    monkeypatch.setattr(embedder, "count_tokens", lambda text, *args, **kwargs: 1)
    monkeypatch.setattr(
        embedder, "embed", lambda texts, *args, **kwargs: [[0.0] * 1024 for _ in texts]
    )


def test_parsed_document_stores_the_parser() -> None:
    ing = ingestion()
    _parsed(cast(DbSession, None), Path("a.pdf"), elements(), StubLayout(), ing)
    assert ing.status == IngestionStatus.done
    assert ing.document is not None
    assert ing.document.parser == "stub"
    assert ing.document.fields["issuer"] == "Stub S.p.A."


def test_drafted_document_stores_drafter(monkeypatch: pytest.MonkeyPatch) -> None:
    drafted = Draft(
        kind=DocumentKind.other,
        validity=Validity(start=date(2030, 1, 1), end=None, as_written="01/01/2030"),
        fields=[DocumentField(name="issuer", value="X S.p.A.", as_written="01/01/2030")],
        description="",
    )
    monkeypatch.setattr(
        pipeline, "draft", lambda text, paid_calls: CheckedDraft([Attempt(drafted, [])])
    )
    ing = ingestion()
    _drafted(cast(DbSession, None), Path("a.pdf"), elements(), ing)
    assert ing.status == IngestionStatus.done
    assert ing.document is not None
    assert ing.document.parser == "drafter"
    assert ing.document.fields == {"issuer": "X S.p.A."}


def test_a_short_document_read_with_ocr_logs_why(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    drafted = Draft(
        kind=DocumentKind.other,
        validity=Validity(start=date(2030, 1, 1), end=None, as_written="01/01/2030"),
        fields=[],
        description="",
    )
    monkeypatch.setattr(pipeline.mistral_ocr, "read_pages", lambda path, paid_calls: ["# A\n\nb"])
    monkeypatch.setattr(
        pipeline, "draft", lambda text, paid_calls: CheckedDraft([Attempt(drafted, [])])
    )
    ing = ingestion()
    _drafted(cast(DbSession, None), Path("a.pdf"), [Element(1, "text", "a", "body", False)], ing)
    assert ing.status == IngestionStatus.done
    assert ing.error is None
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
    monkeypatch.setattr(
        docling_reader, "read", lambda path: [Element(1, "text", "a", "body", False)]
    )
    for name in ["INBOX_DIR", "QUARANTINE_DIR", "PROCESSED_DIR"]:
        monkeypatch.setattr(pipeline, name, tmp_path / name.removesuffix("_DIR").lower())
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    path = inbox / "a.pdf"
    path.write_bytes(b"%PDF-")
    os.utime(path, (0, 0))

    pipeline.ingest_once()

    assert sent == [
        "/v1/ocr",
        "/v1/chat/completions",
        "/v1/chat/completions",
        "/v1/chat/completions",
        "/v1/chat/completions",
    ]
    row = db.scalars(select(Ingestion)).one()
    assert row.status == IngestionStatus.failed
    assert row.error is not None and "5 paid calls spent" in row.error
    assert row.destination_path == f"quarantine/{row.id}.pdf"
    assert (tmp_path / "quarantine" / f"{row.id}.pdf").exists()
