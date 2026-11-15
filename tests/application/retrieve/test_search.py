"""What a search hands back: a section already seen as its id, a long one trimmed."""

from librarian.application.retrieve.ports import Hit
from librarian.application.retrieve.search import TRIM_LIMIT, TRIM_MARKER, _term_pattern, search


class Found:
    """A search that finds the same hits for any query."""

    def __init__(self, hits: list[Hit]) -> None:
        self.hits = hits

    def search(self, query: str, *args: object) -> list[Hit]:
        return self.hits


def hit(text: str, chunk_text: str = "") -> Hit:
    return Hit(section_id=3, document_id=7, kind="invoice", text=text, chunk_text=chunk_text)


def test_seen_section_comes_back_as_its_id_only() -> None:
    hits = search(Found([hit("bolletta gas")]), "bolletta", seen={3})
    assert len(hits) == 1
    assert hits[0].is_ref
    assert hits[0].section_id == 3
    assert hits[0].text is None
    assert hits[0].document_id is None


def test_long_section_is_trimmed_around_the_match_with_a_marker() -> None:
    filler = "riempitivo " * 300  # 3300 characters
    text = filler + " agoNeedleNet " + filler
    hits = search(Found([hit(text, "Grande\n" + text)]), "agoNeedleNet")
    assert len(hits) == 1
    trimmed = hits[0].text
    assert trimmed is not None
    assert TRIM_MARKER in trimmed
    assert len(trimmed) <= TRIM_LIMIT + 2 * len(TRIM_MARKER)
    assert "agoNeedleNet" in trimmed


def test_short_section_is_not_trimmed() -> None:
    hits = search(Found([hit("bolletta breve")]), "bolletta")
    assert hits[0].text == "bolletta breve"


def test_trim_anchors_on_a_grave_o() -> None:
    assert _term_pattern("pero").search("Il saldo però non scade") is not None
