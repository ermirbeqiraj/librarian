from datetime import date
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy.orm import Session as DbSession

from librarian.adapters import embedder
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
    monkeypatch.setattr(pipeline, "draft", lambda text: CheckedDraft([Attempt(drafted, [])]))
    ing = ingestion()
    _drafted(cast(DbSession, None), Path("a.pdf"), elements(), ing)
    assert ing.status == IngestionStatus.done
    assert ing.document is not None
    assert ing.document.parser == "drafter"
    assert ing.document.fields == {"issuer": "X S.p.A."}
