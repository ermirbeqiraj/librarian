"""Search's SQL on the test database: keyword and vector sides, the filters, the merge."""

from datetime import date
from typing import Any

from conftest import SESSIONS, unit_vector
from sqlalchemy.dialects.postgresql import Range

from librarian.adapters.postgres.search import PostgresSearch
from librarian.application.ingest.document import DocumentStatus, Period
from librarian.application.retrieve.period import Period as QuestionPeriod
from librarian.application.retrieve.ports import Hit


class OneVector:
    """Every query embeds as unit_vector(0)."""

    model = "test"
    budget = 8176

    def count_tokens(self, text: str) -> int:
        return 1

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for _ in texts:
            vectors.append(unit_vector(0))
        return vectors


def search(query: str, **filters: Any) -> list[Hit]:
    return PostgresSearch(SESSIONS, OneVector()).search(query, **filters)


def test_unaccented_keyword_match(add_document) -> None:
    document = add_document(
        sections=[
            (
                "Pagamenti",
                "Il saldo scade perché gli importi non sono stati versati",
                [("Pagamenti\nIl saldo scade perché gli importi non sono stati versati", 0)],
            )
        ]
    )
    hits = search("perche scade il saldo", mode="keyword")
    assert [hit.section_id for hit in hits] == [document.sections[0].id]
    assert hits[0].keyword_rank == 1
    assert hits[0].vector_rank is None


def test_italian_stemming_bolletta_bollette(add_document) -> None:
    document = add_document(
        sections=[
            (
                "Avvertenze",
                "Le bollette tardive accumulano interessi",
                [("Avvertenze\nLe bollette tardive accumulano interessi", 0)],
            )
        ]
    )
    hits = search("bolletta", mode="keyword")
    assert [hit.section_id for hit in hits] == [document.sections[0].id]
    # The typo "bolleta" stems differently and does not match: that is the eval's job.
    assert search("bolleta", mode="keyword") == []


def test_keyword_only_and_vector_only_come_back_merged(add_document) -> None:
    # Cosine distance 0.001 from unit_vector(0): 55 of these push the keyword-only
    # chunk past the vector side's top 50, so it comes back with no vector rank.
    near = [0.999, 0.0447] + [0.0] * 1022
    keyword_only = add_document(
        fields={"issuer": "Parole S.p.A."},
        sections=[
            ("Dettaglio", "alpha beta gamma delta", [("Dettaglio\nalpha beta gamma delta", 1)]),
            ("Riempitivo", "niente qui", [(f"Riempitivo\nniente {i}", near) for i in range(55)]),
        ],
    )
    vector_only = add_document(
        fields={},  # no issuer on older documents
        sections=[("Varie", "zzz yyy xxx www", [("Varie\nzzz yyy xxx www", 0)])],
    )
    hits = search("alpha beta", mode="hybrid", limit=2)
    by_section = {hit.section_id: hit for hit in hits}
    assert set(by_section) == {keyword_only.sections[0].id, vector_only.sections[0].id}
    keyword_hit = by_section[keyword_only.sections[0].id]
    vector_hit = by_section[vector_only.sections[0].id]
    assert keyword_hit.keyword_rank == 1
    assert keyword_hit.vector_rank is None
    assert keyword_hit.issuer == "Parole S.p.A."
    assert vector_hit.vector_rank == 1
    assert vector_hit.keyword_rank is None
    assert vector_hit.issuer is None


def test_one_section_per_hit(add_document) -> None:
    document = add_document(
        sections=[
            (
                "Bolletta",
                "bolletta prima parte. bolletta seconda parte.",
                [
                    ("Bolletta\nbolletta prima parte.", 0),
                    ("Bolletta\nbolletta seconda parte.", 1),
                ],
            )
        ]
    )
    hits = search("bolletta", mode="keyword")
    assert [hit.section_id for hit in hits] == [document.sections[0].id]


def test_hit_carries_the_document_fields(add_document) -> None:
    document = add_document(
        kind="contract",
        validity=Range(date(2026, 5, 1), date(2026, 9, 30), bounds="[)"),
        fields={"issuer": "Controparte S.p.A."},
        status=DocumentStatus.draft,
        sections=[
            (
                "Offerta",
                "offerta controparte giga 150",
                [("Offerta\nofferta controparte giga 150", 0)],
            )
        ],
    )
    hits = search("offerta controparte", mode="keyword")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.document_id == document.id
    assert hit.kind == "contract"
    assert hit.issuer == "Controparte S.p.A."
    # Stored as [1 May, 30 Sep): the last day is 29 September.
    assert hit.validity == Period(date(2026, 5, 1), date(2026, 9, 29))
    assert hit.heading == "Offerta"
    assert "offerta controparte giga 150" in hit.text
    assert hit.verified is False


def test_kind_and_document_ids_filter(add_document) -> None:
    invoice = add_document(
        kind="invoice", sections=[("S", "bolletta gas", [("S\nbolletta gas", 0)])]
    )
    contract = add_document(
        kind="contract", sections=[("S", "bolletta contratto", [("S\nbolletta contratto", 1)])]
    )
    by_kind = search("bolletta", mode="keyword", kind="invoice")
    assert [hit.document_id for hit in by_kind] == [invoice.id]
    by_ids = search("bolletta", mode="keyword", document_ids=[contract.id])
    assert [hit.document_id for hit in by_ids] == [contract.id]


def test_empty_document_ids_find_nothing(add_document) -> None:
    add_document(sections=[("Bolletta", "Bolletta del gas", [("Bolletta\nBolletta del gas", 0)])])
    assert search("bolletta", mode="keyword", document_ids=[]) == []


def test_the_four_ops_and_null_validity(add_document) -> None:
    may = add_document(
        validity=Range(date(2026, 5, 1), date(2026, 6, 1), bounds="[)"),
        sections=[("Bolletta", "bolletta di maggio", [("Bolletta\nbolletta di maggio", 0)])],
    )
    year = add_document(
        validity=Range(date(2026, 1, 1), date(2027, 1, 1), bounds="[)"),
        sections=[("Bolletta", "bolletta dell anno", [("Bolletta\nbolletta dell anno", 1)])],
    )
    timeless = add_document(
        validity=None,
        sections=[("Bolletta", "bolletta senza date", [("Bolletta\nbolletta senza date", 2)])],
    )
    all_three = {may.id, year.id, timeless.id}

    def ids(period: QuestionPeriod) -> set[int | None]:
        return {hit.document_id for hit in search("bolletta", period=period, mode="keyword")}

    assert ids(QuestionPeriod("during", "2026-05")) == all_three
    assert ids(QuestionPeriod("during", "2026-06")) == {year.id, timeless.id}
    assert ids(QuestionPeriod("after", "2026-05")) == {year.id, timeless.id}
    assert ids(QuestionPeriod("before", "2026-05")) == {year.id, timeless.id}
    assert ids(QuestionPeriod("on", "2026-05-14")) == all_three
    assert ids(QuestionPeriod("on", "2025-06-15")) == {timeless.id}
