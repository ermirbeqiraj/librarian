from datetime import date

from conftest import unit_vector
from sqlalchemy.dialects.postgresql import Range

from librarian.models import DocumentStatus
from librarian.retrieve.search import TRIM_LIMIT, TRIM_MARKER, _term_pattern, search


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
    hits = search("alpha beta", mode="hybrid", limit=2, query_vector=unit_vector(0))
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
    assert (hit.validity.lower, hit.validity.upper, hit.validity.bounds) == (
        date(2026, 5, 1),
        date(2026, 9, 30),
        "[)",
    )
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


def test_seen_section_comes_back_as_its_id_only(add_document) -> None:
    document = add_document(sections=[("S", "bolletta gas", [("S\nbolletta gas", 0)])])
    hits = search("bolletta", mode="keyword", seen={document.sections[0].id})
    assert len(hits) == 1
    assert hits[0].is_ref
    assert hits[0].section_id == document.sections[0].id
    assert hits[0].text is None
    assert hits[0].document_id is None


def test_long_section_is_trimmed_around_the_match_with_a_marker(add_document) -> None:
    filler = "riempitivo " * 300  # 3300 characters
    text = filler + " agoNeedleNet " + filler
    add_document(sections=[("Grande", text, [("Grande\n" + text, 0)])])
    hits = search("agoNeedleNet", mode="keyword")
    assert len(hits) == 1
    hit = hits[0]
    assert TRIM_MARKER in hit.text
    assert len(hit.text) <= TRIM_LIMIT + 2 * len(TRIM_MARKER)
    assert "agoNeedleNet" in hit.text


def test_short_section_is_not_trimmed(add_document) -> None:
    add_document(sections=[("S", "bolletta breve", [("S\nbolletta breve", 0)])])
    hits = search("bolletta", mode="keyword")
    assert hits[0].text == "bolletta breve"
    assert TRIM_MARKER not in hits[0].text


def test_empty_document_ids_find_nothing(add_document) -> None:
    add_document(sections=[("Bolletta", "Bolletta del gas", [("Bolletta\nBolletta del gas", 0)])])
    assert search("bolletta", mode="keyword", document_ids=[]) == []


def test_trim_anchors_on_a_grave_o() -> None:
    assert _term_pattern("pero").search("Il saldo però non scade") is not None
