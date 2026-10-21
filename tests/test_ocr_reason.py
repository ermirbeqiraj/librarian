from librarian.adapters.readers.element import Element
from librarian.ingest.pipeline import ocr_reason


def body(page: int, text: str = "text") -> Element:
    return Element(page, "text", text, "body", False)


def test_no_text_is_a_scan() -> None:
    assert ocr_reason([]) == "scan"


def test_text_only_inside_pictures_is_a_scan() -> None:
    assert ocr_reason([Element(1, "text", "logo", "body", True)]) == "scan"


def test_text_only_in_page_furniture_is_a_scan() -> None:
    assert ocr_reason([Element(1, "page_footer", "page 1", "furniture", False)]) == "scan"


def test_short_document_goes_to_ocr() -> None:
    assert ocr_reason([body(1), body(4)]) == "under 5 pages"


def test_long_document_stays_on_docling() -> None:
    assert ocr_reason([body(1), body(5)]) is None
