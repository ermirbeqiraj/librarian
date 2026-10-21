from librarian.ingest.chunks import chunk
from librarian.ingest.parsers.sections import Section


def words(text: str) -> int:
    return len(text.split())


def test_short_section_is_one_chunk() -> None:
    section = Section("T", 1, "a b c\n\nd e")
    assert chunk(section, 10, words) == ["T\na b c d e"]


def test_paragraphs_are_packed_until_the_budget() -> None:
    section = Section("T", 1, "a b c\n\nd e f\n\ng h")
    assert chunk(section, 7, words) == ["T\na b c d e f", "T\ng h"]


def test_big_paragraph_is_split_into_sentences() -> None:
    section = Section("T", 1, "a b. c d. e f.")
    assert chunk(section, 5, words) == ["T\na b. c d.", "T\ne f."]


def test_big_sentence_is_split_at_commas() -> None:
    section = Section("T", 1, "a b c, d e f.")
    assert chunk(section, 4, words) == ["T\na b c,", "T\nd e f."]


def test_big_phrase_is_split_into_words() -> None:
    section = Section("T", 1, "a b c d e")
    assert chunk(section, 3, words) == ["T\na b", "T\nc d", "T\ne"]


def test_dot_without_space_is_not_a_sentence_end() -> None:
    section = Section("T", 1, "Data 22.10.2024 ok. Fine here.")
    assert chunk(section, 4, words) == ["T\nData 22.10.2024 ok.", "T\nFine here."]
