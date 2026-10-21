from librarian.adapters.readers.element import Element
from librarian.ingest.content_hash import content_hash


def elements(*texts: str) -> list[Element]:
    return [Element(1, "text", t, "body", False) for t in texts]


def test_same_texts_same_hash() -> None:
    assert content_hash(elements("a", "b")) == content_hash(elements("a", "b"))


def test_order_matters() -> None:
    assert content_hash(elements("a", "b")) != content_hash(elements("b", "a"))


def test_boundaries_matter() -> None:
    assert content_hash(elements("ab", "c")) != content_hash(elements("a", "bc"))


def test_only_text_counts() -> None:
    moved = [Element(2, "title", "a", "furniture", True)]
    assert content_hash(moved) == content_hash(elements("a"))
