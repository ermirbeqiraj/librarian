from librarian.ingest.parsers.sections import Section, from_markdown


def test_no_pages_no_sections() -> None:
    assert from_markdown([]) == []
    assert from_markdown(["", "  "]) == []


def test_no_headings_is_one_section() -> None:
    pages = ["Total 9,00\n\n![img-0.jpeg](img-0.jpeg)\n\nPaid", "Thanks"]
    assert from_markdown(pages) == [Section("", 1, "Total 9,00\n\n\nPaid\n\nThanks")]


def test_headings_open_sections_on_their_page() -> None:
    pages = ["before\n\n# Title\n\nbody", "## Details\n\n| a | 1 |"]
    assert from_markdown(pages) == [
        Section("", 1, "before"),
        Section("Title", 1, "body"),
        Section("Details", 2, "| a | 1 |"),
    ]


def test_repeated_heading_stays_in_the_body() -> None:
    pages = ["# Title\n\none", "# Title\n\ntwo"]
    assert from_markdown(pages) == [Section("Title", 1, "one\n\n# Title\n\ntwo")]


def test_heading_without_body_is_kept() -> None:
    assert from_markdown(["# A\n# B\n\ntext"]) == [Section("A", 1, ""), Section("B", 1, "text")]
