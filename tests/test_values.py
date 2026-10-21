from datetime import date

import pytest

from librarian.adapters.readers.element import Element
from librarian.ingest.parsers.parser import ParseError
from librarian.ingest.parsers.sections import Section, from_docling
from librarian.ingest.parsers.values import italian_month


def test_italian_month() -> None:
    assert italian_month("Febbraio 2028") == (date(2028, 2, 1), date(2028, 2, 29))


def test_rejects_unknown_month() -> None:
    with pytest.raises(ParseError):
        italian_month("Brumaio 2030")


def test_sections_from_docling_headings() -> None:
    elements = [
        Element(1, "text", "before", "body", False),
        Element(1, "page_header", "Pagina 1", "furniture", False),
        Element(1, "section_header", "Title", "body", False),
        Element(1, "text", "body", "body", True),
    ]
    assert from_docling(elements) == [Section("", 1, "before"), Section("Title", 1, "body")]
